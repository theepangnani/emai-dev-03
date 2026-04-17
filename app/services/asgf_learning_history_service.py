"""ASGF Learning History Intelligence — spaced repetition & adaptive context (#3403)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.learning_history import LearningHistory

logger = get_logger(__name__)

# Ebbinghaus spaced-repetition intervals (days since last session)
EBBINGHAUS_INTERVALS = [1, 3, 7, 14, 30]

# Score threshold: topics scoring below this are candidates for review
WEAK_SCORE_THRESHOLD = 70


async def get_spaced_repetition_topics(
    student_id: int, db: Session
) -> list[dict]:
    """Return topics due for spaced-repetition review.

    Queries learning_history for sessions where overall_score_pct < 70%,
    then checks whether the elapsed time since the last session on that
    topic matches the next Ebbinghaus interval (1, 3, 7, 14, or 30 days).
    """
    now = datetime.now(timezone.utc)

    rows = (
        db.query(LearningHistory)
        .filter(
            and_(
                LearningHistory.student_id == student_id,
                LearningHistory.overall_score_pct.isnot(None),
                LearningHistory.overall_score_pct < WEAK_SCORE_THRESHOLD,
            ),
        )
        .order_by(LearningHistory.created_at.desc())
        .all()
    )

    # Group by subject+topic to find the latest session per topic
    topic_latest: dict[str, LearningHistory] = {}
    for row in rows:
        key = _topic_key(row)
        if key and key not in topic_latest:
            topic_latest[key] = row

    results: list[dict] = []
    for key, row in topic_latest.items():
        created = row.created_at
        if created is None:
            continue

        # Make timezone-aware if naive
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        days_since = (now - created).days
        due_interval = _due_review_interval(days_since)

        if due_interval is not None:
            results.append({
                "session_id": row.session_id,
                "subject": row.subject or "",
                "topic": _extract_topic(row),
                "score_pct": row.overall_score_pct,
                "weak_concepts": row.weak_concepts or [],
                "days_since_last": days_since,
                "review_interval": due_interval,
                "last_session_date": created.isoformat(),
            })

    logger.info(
        "Spaced repetition: student_id=%d, candidates=%d, due=%d",
        student_id,
        len(topic_latest),
        len(results),
    )
    return results


async def get_adaptive_context(
    student_id: int, topic: str, db: Session
) -> dict:
    """Return adaptive context for a repeat session on a topic.

    Looks at prior sessions on the same topic to identify:
    - mastered_concepts: concepts the student got right (skip in new session)
    - weak_concepts: concepts the student struggled with (emphasize)
    - session_count: how many times this topic has been studied
    - best_score: highest score achieved
    """
    topic_lower = topic.lower().strip()

    rows = (
        db.query(LearningHistory)
        .filter(LearningHistory.student_id == student_id)
        .order_by(LearningHistory.created_at.desc())
        .all()
    )

    # Filter to matching topic
    matching: list[LearningHistory] = []
    for row in rows:
        row_topic = _extract_topic(row).lower().strip()
        row_subject = (row.subject or "").lower().strip()
        if topic_lower in row_topic or topic_lower in row_subject:
            matching.append(row)

    if not matching:
        return {
            "is_repeat": False,
            "mastered_concepts": [],
            "weak_concepts": [],
            "session_count": 0,
            "best_score": None,
        }

    # Aggregate mastered vs weak concepts from quiz results
    mastered: set[str] = set()
    weak: set[str] = set()
    best_score: int | None = None

    for row in matching:
        score = row.overall_score_pct
        if score is not None:
            if best_score is None or score > best_score:
                best_score = score

        # Collect weak concepts from the dedicated column
        if row.weak_concepts:
            for concept in row.weak_concepts:
                if isinstance(concept, str):
                    weak.add(concept)

        # Analyse quiz_results to find mastered questions
        if row.quiz_results and isinstance(row.quiz_results, list):
            for qr in row.quiz_results:
                if not isinstance(qr, dict):
                    continue
                q_text = qr.get("question_text", "")
                if qr.get("correct"):
                    mastered.add(q_text)
                else:
                    weak.add(q_text)

    # Remove items from mastered that also appear in weak (conservative)
    mastered -= weak

    return {
        "is_repeat": True,
        "mastered_concepts": sorted(mastered),
        "weak_concepts": sorted(weak),
        "session_count": len(matching),
        "best_score": best_score,
    }


async def update_learning_history_on_complete(
    session_id: str, quiz_results: list[dict], db: Session
) -> None:
    """Update the learning_history record with quiz data after session completion.

    Computes overall_score_pct, avg_attempts_per_q, and weak_concepts from
    the provided quiz results and persists them to the row.
    """
    row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not row:
        logger.warning(
            "update_learning_history_on_complete: session %s not found",
            session_id,
        )
        return

    if not quiz_results:
        return

    total = len(quiz_results)
    correct = sum(1 for qr in quiz_results if qr.get("correct"))
    attempts = [qr.get("attempts", 1) for qr in quiz_results]

    row.quiz_results = quiz_results
    row.overall_score_pct = int((correct / total) * 100) if total else None
    row.avg_attempts_per_q = round(sum(attempts) / len(attempts), 2) if attempts else None

    # Identify weak concepts (incorrect answers)
    weak = [
        qr.get("question_text", "")
        for qr in quiz_results
        if not qr.get("correct") and qr.get("question_text")
    ]
    if weak:
        row.weak_concepts = weak

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to update learning_history for session %s", session_id
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _topic_key(row: LearningHistory) -> str:
    """Build a de-duplication key from subject + first topic tag."""
    subject = (row.subject or "").strip().lower()
    topic = _extract_topic(row).strip().lower()
    if subject or topic:
        return f"{subject}::{topic}"
    return ""


def _extract_topic(row: LearningHistory) -> str:
    """Extract the primary topic string from a learning_history row."""
    if row.topic_tags and isinstance(row.topic_tags, list) and row.topic_tags:
        first = row.topic_tags[0]
        if isinstance(first, str):
            return first
    return row.subject or ""


def _due_review_interval(days_since: int) -> int | None:
    """Return the Ebbinghaus interval the student is due for, or None.

    Finds the largest interval <= days_since. If days_since hasn't reached
    the first interval (1 day), returns None (not yet due).
    """
    matched: int | None = None
    for interval in EBBINGHAUS_INTERVALS:
        if days_since >= interval:
            matched = interval
        else:
            break
    return matched
