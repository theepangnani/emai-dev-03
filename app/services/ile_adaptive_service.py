"""
ILE Adaptive Difficulty Engine — CB-ILE-001/M1 (#3204).

Within-session difficulty adjustment based on consecutive performance patterns.
"""
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_session import ILESession
from app.models.ile_question_attempt import ILEQuestionAttempt

logger = get_logger(__name__)

DIFFICULTY_LEVELS = ["easy", "medium", "challenging"]

# Thresholds
CONSECUTIVE_FIRST_ATTEMPT_CORRECT_TO_INCREASE = 2
CONSECUTIVE_MULTI_ATTEMPT_TO_DECREASE = 2


def adjust_within_session(
    db: Session, session: ILESession, latest_attempt: ILEQuestionAttempt
) -> str | None:
    """Adjust difficulty within a session based on performance.

    Rules:
    - 2 consecutive first-attempt correct → increase difficulty
    - 2 consecutive multi-attempt (>1 attempt) answers → decrease difficulty
    - Difficulty levels: easy → medium → challenging

    Returns new difficulty level if changed, None if unchanged.
    """
    current_difficulty = session.difficulty
    current_idx = current_difficulty_index(current_difficulty)
    if current_idx is None:
        return None

    # Get completed question indices (up to and including the latest)
    # We need the last N completed questions' attempt patterns
    completed_questions = (
        db.query(
            ILEQuestionAttempt.question_index,
            ILEQuestionAttempt.is_correct,
            ILEQuestionAttempt.attempt_number,
        )
        .filter(
            ILEQuestionAttempt.session_id == session.id,
            ILEQuestionAttempt.is_correct == True,  # noqa: E712
        )
        .order_by(ILEQuestionAttempt.question_index.desc())
        .limit(CONSECUTIVE_FIRST_ATTEMPT_CORRECT_TO_INCREASE)
        .all()
    )

    # Check for increase: last N questions all first-attempt correct
    if len(completed_questions) >= CONSECUTIVE_FIRST_ATTEMPT_CORRECT_TO_INCREASE:
        all_first_attempt = all(
            row.attempt_number == 1 for row in completed_questions
        )
        if all_first_attempt and current_idx < len(DIFFICULTY_LEVELS) - 1:
            new_difficulty = DIFFICULTY_LEVELS[current_idx + 1]
            _apply_change(db, session, current_difficulty, new_difficulty)
            return new_difficulty

    # Check for decrease: last N completed questions all multi-attempt
    # Re-query to get multi-attempt pattern
    if len(completed_questions) >= CONSECUTIVE_MULTI_ATTEMPT_TO_DECREASE:
        # Get the final (correct) attempt for each of the last N completed questions
        recent_correct = (
            db.query(
                ILEQuestionAttempt.question_index,
                ILEQuestionAttempt.attempt_number,
            )
            .filter(
                ILEQuestionAttempt.session_id == session.id,
                ILEQuestionAttempt.is_correct == True,  # noqa: E712
            )
            .order_by(ILEQuestionAttempt.question_index.desc())
            .limit(CONSECUTIVE_MULTI_ATTEMPT_TO_DECREASE)
            .all()
        )
        if len(recent_correct) >= CONSECUTIVE_MULTI_ATTEMPT_TO_DECREASE:
            all_multi_attempt = all(
                row.attempt_number > 1 for row in recent_correct
            )
            if all_multi_attempt and current_idx > 0:
                new_difficulty = DIFFICULTY_LEVELS[current_idx - 1]
                _apply_change(db, session, current_difficulty, new_difficulty)
                return new_difficulty

    return None


def current_difficulty_index(difficulty: str) -> int | None:
    """Get the index of a difficulty level, or None if invalid."""
    try:
        return DIFFICULTY_LEVELS.index(difficulty)
    except ValueError:
        return None


def _apply_change(
    db: Session,
    session: ILESession,
    old_difficulty: str,
    new_difficulty: str,
) -> None:
    """Update session difficulty and log the transition."""
    session.difficulty = new_difficulty
    # No db.commit() here — caller (submit_answer) commits the transaction
    logger.info(
        "ILE adaptive: session %d difficulty %s → %s | student=%d question_index=%d",
        session.id,
        old_difficulty,
        new_difficulty,
        session.student_id,
        session.current_question_index,
    )
