import json
import logging
import os
import random
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.inspiration_message import InspirationMessage

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "inspiration"
VALID_ROLES = {"parent", "teacher", "student"}


def seed_messages(db: Session) -> int:
    """Import messages from JSON seed files into the database.

    Only imports if the table is empty. Returns the number of messages imported.
    """
    existing = db.query(InspirationMessage).count()
    if existing > 0:
        logger.info(f"Inspiration table already has {existing} messages — skipping seed")
        return 0

    total = 0
    for role in VALID_ROLES:
        filepath = SEED_DIR / f"{role}.json"
        if not filepath.exists():
            logger.warning(f"Seed file not found: {filepath}")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            messages = json.load(f)

        for msg in messages:
            db.add(InspirationMessage(
                role=role,
                text=msg["text"],
                author=msg.get("author"),
                is_active=True,
            ))
            total += 1

    db.commit()
    logger.info(f"Seeded {total} inspiration messages")
    return total


def get_random_message(db: Session, role: str) -> dict | None:
    """Return a random active inspiration message for the given role."""
    role = role.lower()
    if role not in VALID_ROLES:
        return None

    messages = (
        db.query(InspirationMessage)
        .filter(
            InspirationMessage.role == role,
            InspirationMessage.is_active == True,
        )
        .all()
    )

    if not messages:
        return None

    msg = random.choice(messages)
    return {
        "id": msg.id,
        "text": msg.text,
        "author": msg.author,
        "role": msg.role,
    }
