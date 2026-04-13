"""
ILE Cost Optimizer — question bank pre-generation + hint caching (#3209).

Batch pre-generates questions and pre-computes hint trees to reduce
on-demand AI calls. Target: 50-65% AI cost reduction via bank-first serving.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ile_question_bank import ILEQuestionBank
from app.models.ile_session import ILESession
from app.services.ile_question_service import (
    generate_questions,
    generate_hint,
)

logger = get_logger(__name__)

BANK_TTL_DAYS = 7
MIN_BANK_SIZE = 20  # Minimum questions before triggering prefill


async def prefill_question_bank(
    db: Session,
    subject: str,
    topic: str,
    grade_level: int,
    difficulty: str = "medium",
    count: int = 20,
) -> int:
    """Batch generate questions for a topic and store in bank.

    - Generate `count` questions via AI
    - For each question, pre-compute 3 escalating hints (hint_tree_json)
    - Store in ile_question_bank with 7-day expiry
    - Skip if bank already has >= count unexpired questions for this combo

    Returns the number of questions added.
    """
    now = datetime.now(timezone.utc)

    # Check existing bank size
    existing = (
        db.query(sa_func.count(ILEQuestionBank.id))
        .filter(
            ILEQuestionBank.subject == subject,
            ILEQuestionBank.topic == topic,
            ILEQuestionBank.grade_level == grade_level,
            ILEQuestionBank.difficulty == difficulty,
            ILEQuestionBank.flagged == False,  # noqa: E712
            (ILEQuestionBank.expires_at > now) | (ILEQuestionBank.expires_at.is_(None)),
        )
        .scalar()
    )

    if existing >= count:
        logger.info(
            "Bank already has %d/%d questions for %s/%s grade %d %s — skipping",
            existing, count, subject, topic, grade_level, difficulty,
        )
        return 0

    needed = count - existing
    logger.info(
        "Prefilling %d questions for %s/%s grade %d %s (have %d)",
        needed, subject, topic, grade_level, difficulty, existing,
    )

    try:
        questions = await generate_questions(
            subject=subject,
            topic=topic,
            grade_level=grade_level,
            difficulty=difficulty,
            count=needed,
        )
    except Exception as e:
        logger.error("Failed to generate questions for prefill: %s", e)
        return 0

    expires_at = now + timedelta(days=BANK_TTL_DAYS)
    added = 0

    for q in questions:
        # Pre-compute hint tree
        hint_tree = await _generate_hint_tree(q, grade_level)

        bank_item = ILEQuestionBank(
            subject=subject,
            topic=topic,
            grade_level=grade_level,
            difficulty=q.get("difficulty", difficulty),
            blooms_tier=q.get("blooms_tier", "recall"),
            question_format="mcq",
            question_json=json.dumps(q),
            explanation_text=q.get("explanation"),
            hint_tree_json=json.dumps(hint_tree) if hint_tree else None,
            expires_at=expires_at,
        )
        db.add(bank_item)
        added += 1

    db.commit()
    logger.info("Prefilled %d questions for %s/%s grade %d", added, subject, topic, grade_level)
    return added


async def prefill_hint_tree(db: Session, question_bank_id: int) -> bool:
    """Pre-compute 3 escalating hints for a banked question.

    Returns True if hints were generated, False otherwise.
    """
    item = db.query(ILEQuestionBank).filter(ILEQuestionBank.id == question_bank_id).first()
    if not item:
        logger.warning("Question bank item %d not found", question_bank_id)
        return False

    if item.hint_tree_json:
        logger.info("Question %d already has hint tree", question_bank_id)
        return False

    try:
        q = json.loads(item.question_json)
    except (json.JSONDecodeError, TypeError):
        logger.error("Corrupt question_json for bank item %d", question_bank_id)
        return False

    hint_tree = await _generate_hint_tree(q, item.grade_level)
    if hint_tree:
        item.hint_tree_json = json.dumps(hint_tree)
        db.commit()
        logger.info("Generated hint tree for question %d", question_bank_id)
        return True

    return False


def cleanup_expired_bank(db: Session) -> int:
    """Delete expired and flagged questions from the bank.

    Returns the count of removed items.
    """
    now = datetime.now(timezone.utc)

    expired_count = (
        db.query(ILEQuestionBank)
        .filter(
            ILEQuestionBank.expires_at.isnot(None),
            ILEQuestionBank.expires_at < now,
        )
        .delete(synchronize_session=False)
    )

    flagged_count = (
        db.query(ILEQuestionBank)
        .filter(ILEQuestionBank.flagged == True)  # noqa: E712
        .delete(synchronize_session=False)
    )

    db.commit()
    total = expired_count + flagged_count
    logger.info("Cleaned up %d bank items (%d expired, %d flagged)", total, expired_count, flagged_count)
    return total


async def prefill_active_topics(db: Session) -> dict:
    """Pre-fill bank for all active topic combinations.

    Finds unique (subject, topic, grade_level) from recent sessions
    and prefills bank for each combo that is running low.

    Returns dict with total_topics and total_added counts.
    """
    # Find unique combos from sessions in the last 30 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    combos = (
        db.query(
            ILESession.subject,
            ILESession.topic,
            ILESession.grade_level,
        )
        .filter(ILESession.created_at >= cutoff)
        .distinct()
        .all()
    )

    total_added = 0
    topics_filled = 0

    for subject, topic, grade_level in combos:
        if not grade_level:
            continue
        try:
            added = await prefill_question_bank(
                db, subject, topic, grade_level, count=MIN_BANK_SIZE,
            )
            if added > 0:
                topics_filled += 1
            total_added += added
        except Exception as e:
            logger.error(
                "Failed to prefill %s/%s grade %d: %s",
                subject, topic, grade_level, e,
            )
            continue

    logger.info(
        "Prefill active topics: %d topics checked, %d filled, %d questions added",
        len(combos), topics_filled, total_added,
    )
    return {"total_topics": len(combos), "topics_filled": topics_filled, "total_added": total_added}


def get_bank_stats(db: Session) -> dict:
    """Return bank statistics."""
    now = datetime.now(timezone.utc)

    total = db.query(sa_func.count(ILEQuestionBank.id)).scalar()
    active = (
        db.query(sa_func.count(ILEQuestionBank.id))
        .filter(
            ILEQuestionBank.flagged == False,  # noqa: E712
            (ILEQuestionBank.expires_at > now) | (ILEQuestionBank.expires_at.is_(None)),
        )
        .scalar()
    )
    expired = (
        db.query(sa_func.count(ILEQuestionBank.id))
        .filter(
            ILEQuestionBank.expires_at.isnot(None),
            ILEQuestionBank.expires_at < now,
        )
        .scalar()
    )
    flagged = (
        db.query(sa_func.count(ILEQuestionBank.id))
        .filter(ILEQuestionBank.flagged == True)  # noqa: E712
        .scalar()
    )
    with_hints = (
        db.query(sa_func.count(ILEQuestionBank.id))
        .filter(ILEQuestionBank.hint_tree_json.isnot(None))
        .scalar()
    )
    total_served = db.query(sa_func.coalesce(sa_func.sum(ILEQuestionBank.times_served), 0)).scalar()
    total_correct = db.query(sa_func.coalesce(sa_func.sum(ILEQuestionBank.times_correct), 0)).scalar()

    # Top topics by question count
    top_topics = (
        db.query(
            ILEQuestionBank.subject,
            ILEQuestionBank.topic,
            ILEQuestionBank.grade_level,
            sa_func.count(ILEQuestionBank.id).label("count"),
        )
        .filter(
            ILEQuestionBank.flagged == False,  # noqa: E712
            (ILEQuestionBank.expires_at > now) | (ILEQuestionBank.expires_at.is_(None)),
        )
        .group_by(ILEQuestionBank.subject, ILEQuestionBank.topic, ILEQuestionBank.grade_level)
        .order_by(sa_func.count(ILEQuestionBank.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total": total,
        "active": active,
        "expired": expired,
        "flagged": flagged,
        "with_hints": with_hints,
        "total_served": total_served,
        "total_correct": total_correct,
        "top_topics": [
            {"subject": s, "topic": t, "grade_level": g, "count": c}
            for s, t, g, c in top_topics
        ],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _generate_hint_tree(question: dict, grade_level: int | None) -> list[str]:
    """Generate 3 escalating hints for a question."""
    correct = question.get("correct_answer", "")
    q_text = question.get("question", "")
    if not q_text or not correct:
        return []

    # Use a generic wrong answer for hint generation
    options = question.get("options", {})
    wrong_answer = "A" if correct != "A" else "B"

    hints = []
    for attempt in range(1, 4):
        try:
            hint = await generate_hint(
                question=q_text,
                wrong_answer=wrong_answer,
                correct_answer=correct,
                attempt_number=attempt,
                previous_hints=hints if hints else None,
                grade_level=grade_level,
            )
            hints.append(hint)
        except Exception as e:
            logger.warning("Failed to generate hint %d: %s", attempt, e)
            break

    return hints


def save_questions_to_bank(
    db: Session,
    questions: list[dict],
    subject: str,
    topic: str,
    grade_level: int,
    difficulty: str = "medium",
) -> int:
    """Save on-demand generated questions to the bank for future reuse.

    Returns the number of questions saved.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=BANK_TTL_DAYS)
    saved = 0

    for q in questions:
        bank_item = ILEQuestionBank(
            subject=subject,
            topic=topic,
            grade_level=grade_level,
            difficulty=q.get("difficulty", difficulty),
            blooms_tier=q.get("blooms_tier", "recall"),
            question_format="mcq",
            question_json=json.dumps(q),
            explanation_text=q.get("explanation"),
            expires_at=expires_at,
        )
        db.add(bank_item)
        saved += 1

    if saved:
        db.commit()
        logger.info("Saved %d on-demand questions to bank for %s/%s", saved, subject, topic)

    return saved
