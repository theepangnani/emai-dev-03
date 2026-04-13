"""
ILE Topic Mastery Service — CB-ILE-001/M2 (#3206).

Tracks per-student per-topic mastery after each session completion.
Detects weak areas based on average attempts per question.
"""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_topic_mastery import ILETopicMastery
from app.models.ile_session import ILESession

logger = get_logger(__name__)

WEAK_AREA_THRESHOLD = 2.0  # avg_attempts > this => weak area


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

    db.commit()
    db.refresh(mastery)

    logger.info(
        "Mastery updated | student=%d subject=%s topic=%s sessions=%d avg_attempts=%.2f weak=%s",
        session.student_id, session.subject, session.topic,
        mastery.total_sessions, mastery.avg_attempts_per_question, mastery.is_weak_area,
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
