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


def sync_new_messages(db: Session) -> int:
    """Insert any seed-file messages that don't already exist in the DB.

    Matches by exact text to avoid duplicates.  Never updates or deletes
    existing rows so admin-curated messages are preserved.
    Returns the count of newly inserted messages.
    """
    existing_texts: set[str] = {
        row[0] for row in db.query(InspirationMessage.text).all()
    }

    added = 0
    for role in VALID_ROLES:
        filepath = SEED_DIR / f"{role}.json"
        if not filepath.exists():
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            messages = json.load(f)

        for msg in messages:
            if msg["text"] not in existing_texts:
                db.add(InspirationMessage(
                    role=role,
                    text=msg["text"],
                    author=msg.get("author"),
                    is_active=True,
                ))
                existing_texts.add(msg["text"])
                added += 1

    if added:
        db.commit()
        logger.info(f"Synced {added} new inspiration messages from seed files")
    else:
        logger.info("No new inspiration messages to sync")

    return added


def get_random_message(db: Session, role: str) -> dict | None:
    """Return a random active inspiration message for the given role.

    Admin users get a random message from any role.
    """
    role = role.lower()

    query = db.query(InspirationMessage).filter(InspirationMessage.is_active == True)
    if role in VALID_ROLES:
        query = query.filter(InspirationMessage.role == role)
    # else: admin or unknown role gets messages from all roles

    messages = query.all()

    if not messages:
        return None

    msg = random.choice(messages)
    return {
        "id": msg.id,
        "text": msg.text,
        "author": msg.author,
        "role": msg.role,
    }
