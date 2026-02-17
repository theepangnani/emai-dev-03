"""Seed the FAQ table with initial how-to entries from data/faq/seed.json.

Only runs if the faq_questions table is empty (idempotent).
Uses a dedicated "system" admin user so seeds work even before any real user registers.
"""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.faq import FAQQuestion, FAQAnswer, FAQQuestionStatus, FAQAnswerStatus

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "faq" / "seed.json"


def seed_faq(db: Session) -> int:
    """Import FAQ entries from seed.json. Returns number of entries created."""
    existing = db.query(FAQQuestion).count()
    if existing > 0:
        logger.info(f"FAQ table already has {existing} questions — skipping seed")
        return 0

    if not SEED_FILE.exists():
        logger.warning(f"FAQ seed file not found: {SEED_FILE}")
        return 0

    # Find or create a system user for seeding
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    system_user = db.query(User).filter(User.email == "system@classbridge.ca").first()
    if not system_user:
        system_user = User(
            email="system@classbridge.ca",
            full_name="ClassBridge Team",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash("__system_seed_only__"),
            is_active=True,
        )
        db.add(system_user)
        db.commit()
        db.refresh(system_user)

    with open(SEED_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)

    count = 0
    for entry in entries:
        question = FAQQuestion(
            title=entry["title"],
            description=entry.get("description"),
            category=entry.get("category", "other"),
            status=FAQQuestionStatus.ANSWERED.value,
            error_code=entry.get("error_code"),
            is_pinned=entry.get("is_pinned", False),
            created_by_user_id=system_user.id,
        )
        db.add(question)
        db.flush()  # get question.id

        answer = FAQAnswer(
            question_id=question.id,
            content=entry["answer"],
            created_by_user_id=system_user.id,
            status=FAQAnswerStatus.APPROVED.value,
            is_official=True,
            reviewed_by_user_id=system_user.id,
        )
        db.add(answer)
        count += 1

    db.commit()
    logger.info(f"Seeded {count} FAQ entries")
    return count
