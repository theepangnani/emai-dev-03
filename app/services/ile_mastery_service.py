"""
ILE Mastery Service — SM-2 spaced repetition + glow intensity (#3210).

Manages topic mastery updates after sessions and computes Memory Glow values.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_topic_mastery import ILETopicMastery

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# SM-2 Algorithm
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
# Glow Intensity
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
    student_id: int,
    subject: str,
    topic: str,
    total_correct: int,
    total_questions: int,
    total_first_attempt_correct: int,
    score_pct: float,
    difficulty: str,
    grade_level: int | None = None,
) -> ILETopicMastery:
    """Create or update mastery record after a completed session.

    Updates cumulative stats, SM-2 fields, and weak-area flag.
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

    now = datetime.now(timezone.utc)

    if mastery is None:
        mastery = ILETopicMastery(
            student_id=student_id,
            subject=subject,
            topic=topic,
            grade_level=grade_level,
        )
        db.add(mastery)

    # Update cumulative stats
    mastery.total_sessions = (mastery.total_sessions or 0) + 1
    mastery.total_questions_seen = (mastery.total_questions_seen or 0) + total_questions
    mastery.total_first_attempt_correct = (
        (mastery.total_first_attempt_correct or 0) + total_first_attempt_correct
    )

    # Average attempts per question (running average)
    if total_questions > 0:
        avg_this_session = total_questions / total_first_attempt_correct if total_first_attempt_correct > 0 else total_questions
        prev_avg = mastery.avg_attempts_per_question or 0.0
        prev_total = mastery.total_sessions - 1
        if prev_total > 0:
            mastery.avg_attempts_per_question = round(
                (prev_avg * prev_total + avg_this_session) / mastery.total_sessions, 2
            )
        else:
            mastery.avg_attempts_per_question = round(avg_this_session, 2)

    mastery.last_score_pct = score_pct
    mastery.last_session_at = now
    mastery.current_difficulty = difficulty

    # Update weak-area flag: weak if score < 60% or avg attempts > 2.5
    mastery.is_weak_area = score_pct < 60 or (mastery.avg_attempts_per_question or 0) > 2.5

    # SM-2 spaced repetition update
    quality_score = compute_quality_score(
        total_correct, total_questions, total_first_attempt_correct
    )
    update_spaced_repetition(mastery, quality_score)

    db.commit()
    db.refresh(mastery)

    logger.info(
        "Mastery updated | student=%d subject=%s topic=%s quality=%d ef=%.2f interval=%d",
        student_id, subject, topic, quality_score,
        mastery.easiness_factor, mastery.review_interval_days,
    )

    return mastery
