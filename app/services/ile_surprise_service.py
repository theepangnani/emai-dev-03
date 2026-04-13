"""
ILE Surprise Me — weighted topic selection (CB-ILE-001/M2 #3207).

Picks a topic for the student, weighted by weak areas and review schedule.
"""
import random
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_topic_mastery import ILETopicMastery
from app.services.ile_service import get_available_topics

logger = get_logger(__name__)

# Weight multipliers
WEAK_AREA_WEIGHT = 3
DUE_FOR_REVIEW_WEIGHT = 2
NORMAL_WEIGHT = 1


def get_surprise_topic(db: Session, student_id: int) -> dict:
    """Pick a topic for Surprise Me, weighted by weak areas.

    Weighting:
    - Weak areas (is_weak_area=True): 3x weight
    - Topics due for review (next_review_at < now): 2x weight
    - Normal topics: 1x weight

    Returns: {topic: dict, reason: str}
    e.g. {"topic": {...}, "reason": "Weak area -- avg 2.3 attempts"}
    """
    topics = get_available_topics(db, student_id)
    if not topics:
        raise ValueError("No topics available. Enroll in a course or enter a custom topic.")

    # Load mastery data for this student
    mastery_rows = (
        db.query(ILETopicMastery)
        .filter(ILETopicMastery.student_id == student_id)
        .all()
    )
    mastery_map: dict[tuple[str, str], ILETopicMastery] = {
        (m.subject, m.topic): m for m in mastery_rows
    }

    now = datetime.now(timezone.utc)
    weighted_topics: list[dict] = []
    weights: list[int] = []

    for t in topics:
        key = (t["subject"], t["topic"])
        mastery = mastery_map.get(key)

        weight = NORMAL_WEIGHT
        reason = "Random selection"

        if mastery:
            t["mastery_pct"] = (
                round(mastery.last_score_pct, 1) if mastery.last_score_pct is not None else None
            )
            t["is_weak_area"] = mastery.is_weak_area
            t["next_review_at"] = (
                mastery.next_review_at.isoformat() if mastery.next_review_at else None
            )

            if mastery.is_weak_area:
                weight = WEAK_AREA_WEIGHT
                avg = round(mastery.avg_attempts_per_question, 1)
                reason = f"Weak area -- avg {avg} attempts"
            elif mastery.next_review_at and mastery.next_review_at <= now:
                weight = DUE_FOR_REVIEW_WEIGHT
                reason = "Due for review"
        else:
            t.setdefault("mastery_pct", None)
            t.setdefault("is_weak_area", False)
            t.setdefault("next_review_at", None)

        weighted_topics.append({**t, "_reason": reason})
        weights.append(weight)

    # Weighted random selection
    selected = random.choices(weighted_topics, weights=weights, k=1)[0]
    reason = selected.pop("_reason")

    logger.info(
        "Surprise Me picked topic=%s subject=%s for student=%d (reason=%s)",
        selected["topic"], selected["subject"], student_id, reason,
    )

    return {"topic": selected, "reason": reason}
