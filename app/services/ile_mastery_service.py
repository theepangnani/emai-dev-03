"""
ILE Topic Mastery Service — CB-ILE-001/M2 (#3206, #3210).

Tracks per-student per-topic mastery after each session completion.
Detects weak areas based on average attempts per question.
Includes SM-2 spaced repetition and Memory Glow computation.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_topic_mastery import ILETopicMastery
from app.models.ile_session import ILESession

logger = get_logger(__name__)

WEAK_AREA_THRESHOLD = 2.0  # avg_attempts > this => weak area


# ---------------------------------------------------------------------------
# SM-2 Algorithm (#3210)
# ---------------------------------------------------------------------------

def compute_quality_score(
    total_correct: int,
    total_questions: int,
    total_first_attempt_correct: int,
) -> int:
    """Convert session results to SM-2 quality score (0-5).

    Based on first-attempt accuracy percentage:
    - 5: perfect (100%)
    - 4: correct after hesitation (80-99%)
    - 3: correct with difficulty (60-79%)
    - 2: incorrect but close (40-59%)
    - 1: mostly wrong (20-39%)
    - 0: complete blank (<20%)
    """
    if total_questions <= 0:
        return 0
    pct = total_first_attempt_correct / total_questions * 100
    if pct >= 100:
        return 5
    if pct >= 80:
        return 4
    if pct >= 60:
        return 3
    if pct >= 40:
        return 2
    if pct >= 20:
        return 1
    return 0


def update_spaced_repetition(mastery: ILETopicMastery, quality_score: int) -> None:
    """Update SM-2 spaced repetition fields after a session.

    SM-2 algorithm (Piotr Wozniak, 1987):
    - EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    - EF  = max(1.3, EF')
    - If q >= 3: interval grows by EF
    - If q < 3:  interval resets to 1
    - next_review_at = now + interval days
    """
    q = quality_score
    ef = mastery.easiness_factor

    # Update easiness factor
    ef_prime = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ef = max(1.3, ef_prime)
    mastery.easiness_factor = round(ef, 4)

    if q >= 3:
        # Successful recall — grow interval
        # SM-2: first successful = 1 day, second successful = 6, then *= EF
        prev_interval = mastery.review_interval_days or 1
        if prev_interval < 6:
            # First or second successful review — advance to 6
            new_interval = 6
        else:
            new_interval = round(prev_interval * ef)
        mastery.review_interval_days = new_interval
    else:
        # Failed recall — reset
        mastery.review_interval_days = 1

    now = datetime.now(timezone.utc)
    mastery.next_review_at = now + timedelta(days=mastery.review_interval_days)


# ---------------------------------------------------------------------------
# Glow Intensity (#3210)
# ---------------------------------------------------------------------------

def compute_glow_intensity(next_review_at: datetime | None) -> float:
    """Compute Memory Glow intensity from review schedule.

    Returns 0.0 (faded/overdue) to 1.0 (bright/recently reviewed).

    - If next_review_at is None (never reviewed): 0.0
    - If overdue by 7+ days: 0.0
    - If overdue by 0-7 days: 0.0 to 0.3 (less overdue = higher)
    - If due today: 0.5
    - If due in the future: 0.5 to 1.0 (further out = brighter)
    """
    if next_review_at is None:
        return 0.0

    now = datetime.now(timezone.utc)
    # Make both offset-aware for comparison
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=timezone.utc)

    diff_days = (next_review_at - now).total_seconds() / 86400

    if diff_days < -7:
        # Very overdue
        return 0.0
    if diff_days < 0:
        # Overdue: 0.0 (7 days overdue) to 0.3 (just overdue)
        return round(0.3 * (1 + diff_days / 7), 2)
    if diff_days < 1:
        # Due today
        return 0.5
    # Future: 0.5 to 1.0 — capped at 30 days out
    capped = min(diff_days, 30)
    return round(0.5 + 0.5 * (capped / 30), 2)


# ---------------------------------------------------------------------------
# Mastery Update (called after session completion)
# ---------------------------------------------------------------------------

def update_mastery_after_session(
    db: Session,
    session: ILESession,
    question_results: list[dict],
) -> ILETopicMastery:
    """Update ile_topic_mastery after session completion.

    - Get or create mastery record for student+subject+topic
    - Increment total_sessions
    - Add total_questions_seen from this session
    - Count first_attempt_correct from question_results
    - Recalculate avg_attempts_per_question (weighted rolling average)
    - Flag is_weak_area when avg_attempts > 2.0
    - Update mcq_correct_streak
    - Update last_session_at, last_score_pct
    - Update current_difficulty from session
    - Compute SM-2 quality score and update spaced repetition fields (#3210)
    """
    mastery = _get_or_create_mastery(
        db,
        student_id=session.student_id,
        subject=session.subject,
        topic=session.topic,
        grade_level=session.grade_level,
    )

    # Session stats from question_results
    session_questions = len(question_results)
    session_first_correct = sum(
        1 for qr in question_results
        if qr["is_correct"] and qr["attempts"] == 1
    )
    session_total_attempts = sum(qr["attempts"] for qr in question_results)

    # Update cumulative counters
    prev_total_questions = mastery.total_questions_seen
    mastery.total_sessions += 1
    mastery.total_questions_seen += session_questions
    mastery.total_first_attempt_correct += session_first_correct

    # Weighted rolling average for avg_attempts_per_question
    if mastery.total_questions_seen > 0:
        # Weight: old_avg * old_count + session_avg * session_count / total_count
        old_weighted = mastery.avg_attempts_per_question * prev_total_questions
        new_weighted = session_total_attempts  # sum of attempts for this session
        mastery.avg_attempts_per_question = round(
            (old_weighted + new_weighted) / mastery.total_questions_seen, 2
        )

    # Weak area detection
    mastery.is_weak_area = mastery.avg_attempts_per_question > WEAK_AREA_THRESHOLD

    # MCQ correct streak: count consecutive correct from end of session
    streak = 0
    for qr in reversed(question_results):
        if qr["is_correct"] and qr["attempts"] == 1:
            streak += 1
        else:
            break
    # If the entire session was a streak, add to existing streak; otherwise reset
    if streak == session_questions and session_questions > 0:
        mastery.mcq_correct_streak += streak
    else:
        mastery.mcq_correct_streak = streak

    # Update metadata
    mastery.current_difficulty = session.difficulty or "medium"
    mastery.last_session_at = datetime.now(timezone.utc)

    # Score percentage for this session
    correct_count = sum(1 for qr in question_results if qr["is_correct"])
    mastery.last_score_pct = round(
        (correct_count / session_questions * 100) if session_questions else 0, 1
    )

    # SM-2 spaced repetition update (#3210)
    quality_score = compute_quality_score(
        correct_count, session_questions, session_first_correct
    )
    update_spaced_repetition(mastery, quality_score)

    db.commit()
    db.refresh(mastery)

    logger.info(
        "Mastery updated | student=%d subject=%s topic=%s sessions=%d avg_attempts=%.2f weak=%s quality=%d ef=%.2f interval=%d",
        session.student_id, session.subject, session.topic,
        mastery.total_sessions, mastery.avg_attempts_per_question, mastery.is_weak_area,
        quality_score, mastery.easiness_factor, mastery.review_interval_days,
    )
    return mastery


def get_student_mastery(db: Session, student_id: int) -> list[ILETopicMastery]:
    """Get all mastery entries for a student."""
    return (
        db.query(ILETopicMastery)
        .filter(ILETopicMastery.student_id == student_id)
        .order_by(ILETopicMastery.subject, ILETopicMastery.topic)
        .all()
    )


def check_aha_moment(mastery_before: dict, mastery_after: ILETopicMastery) -> bool:
    """Detect breakthrough: topic was weak (avg > 2.0), now improved (avg < 1.5).

    Args:
        mastery_before: dict with avg_attempts_per_question and is_weak_area
            captured before update_mastery_after_session.
        mastery_after: The mastery record after updating.

    Returns:
        True if the student had a breakthrough moment.
    """
    was_weak = (
        mastery_before.get("is_weak_area", False)
        or mastery_before.get("avg_attempts_per_question", 0) > WEAK_AREA_THRESHOLD
    )
    now_improved = mastery_after.avg_attempts_per_question < 1.5

    if was_weak and now_improved:
        logger.info(
            "Aha moment detected | student=%d subject=%s topic=%s "
            "avg_before=%.2f avg_after=%.2f",
            mastery_after.student_id,
            mastery_after.subject,
            mastery_after.topic,
            mastery_before.get("avg_attempts_per_question", 0),
            mastery_after.avg_attempts_per_question,
        )
        return True
    return False


def get_mastery_snapshot(db: Session, student_id: int, subject: str, topic: str) -> dict:
    """Capture a snapshot of current mastery state before an update.

    Returns dict with avg_attempts_per_question and is_weak_area,
    or defaults if no mastery record exists yet.
    """
    mastery = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.subject == subject,
            ILETopicMastery.topic == topic,
        )
        .first()
    )
    if mastery:
        return {
            "avg_attempts_per_question": mastery.avg_attempts_per_question,
            "is_weak_area": mastery.is_weak_area,
        }
    return {
        "avg_attempts_per_question": 0.0,
        "is_weak_area": False,
    }


def get_decaying_topics(db: Session, student_id: int) -> list[dict]:
    """Get topics past next_review_at, grouped by urgency.

    Returns list of dicts with topic info and decay_level:
    - "amber": 2-6 days overdue
    - "urgent": 7+ days overdue
    """
    now = datetime.now(timezone.utc)
    amber_threshold = now - timedelta(days=2)

    overdue = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.next_review_at != None,  # noqa: E711
            ILETopicMastery.next_review_at < amber_threshold,
        )
        .order_by(ILETopicMastery.next_review_at.asc())
        .all()
    )

    results = []
    urgent_threshold = now - timedelta(days=7)
    for m in overdue:
        review_at = m.next_review_at
        if review_at.tzinfo is None:
            review_at = review_at.replace(tzinfo=timezone.utc)
        decay_level = "urgent" if review_at < urgent_threshold else "amber"
        results.append({
            "subject": m.subject,
            "topic": m.topic,
            "next_review_at": m.next_review_at,
            "decay_level": decay_level,
            "days_overdue": (now - review_at).days,
        })
    return results


def send_decay_notifications(db: Session) -> int:
    """Check all students for decaying topics and send notifications.

    Returns the number of notifications sent.
    """
    from app.models.user import User
    from app.models.notification import NotificationType
    from app.services.notification_service import send_multi_channel_notification

    now = datetime.now(timezone.utc)
    amber_threshold = now - timedelta(days=2)

    # Get all overdue mastery records
    overdue_records = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.next_review_at != None,  # noqa: E711
            ILETopicMastery.next_review_at < amber_threshold,
        )
        .all()
    )

    sent = 0
    for m in overdue_records:
        review_at = m.next_review_at
        if review_at.tzinfo is None:
            review_at = review_at.replace(tzinfo=timezone.utc)

        days_overdue = (now - review_at).days
        if days_overdue >= 7:
            title = f"Your {m.subject} skills are fading!"
            content = f"It's been {days_overdue} days since you reviewed {m.topic}. 5 min to refresh!"
        else:
            title = f"Time to review {m.topic}"
            content = f"Your {m.topic} ({m.subject}) knowledge needs a quick refresh. 5 min is all it takes!"

        student_user = db.query(User).filter(User.id == m.student_id).first()
        if not student_user:
            continue

        try:
            notif = send_multi_channel_notification(
                db=db,
                recipient=student_user,
                sender=None,
                title=title,
                content=content,
                notification_type=NotificationType.ILE_KNOWLEDGE_DECAY,
                link="/flash-tutor",
                channels=["app_notification"],
                source_type="ile_decay",
                source_id=m.id,
            )
            if notif:
                sent += 1
        except Exception:
            logger.warning(
                "Failed to send decay notification for student=%d topic=%s",
                m.student_id, m.topic,
            )

    if sent:
        db.commit()
    logger.info("Knowledge decay check complete: %d notifications sent", sent)
    return sent


def get_weak_areas(db: Session, student_id: int) -> list[ILETopicMastery]:
    """Get topics flagged as weak areas."""
    return (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.is_weak_area == True,  # noqa: E712
        )
        .order_by(ILETopicMastery.avg_attempts_per_question.desc())
        .all()
    )


def _get_or_create_mastery(
    db: Session,
    student_id: int,
    subject: str,
    topic: str,
    grade_level: int | None,
) -> ILETopicMastery:
    """Get existing mastery record or create a new one.

    Handles race conditions: if two concurrent requests both try to create,
    the loser catches IntegrityError, rolls back, and re-fetches.
    """
    mastery = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.subject == subject,
            ILETopicMastery.topic == topic,
        )
        .first()
    )
    if mastery is None:
        try:
            mastery = ILETopicMastery(
                student_id=student_id,
                subject=subject,
                topic=topic,
                grade_level=grade_level,
            )
            db.add(mastery)
            db.flush()
        except IntegrityError:
            db.rollback()
            mastery = (
                db.query(ILETopicMastery)
                .filter(
                    ILETopicMastery.student_id == student_id,
                    ILETopicMastery.subject == subject,
                    ILETopicMastery.topic == topic,
                )
                .first()
            )
    return mastery
