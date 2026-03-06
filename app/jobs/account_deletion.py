"""Background job: process account deletions past the 30-day grace period."""

import logging

from app.db.database import SessionLocal
from app.services.account_deletion_service import process_expired_deletions

logger = logging.getLogger(__name__)


async def process_expired_account_deletions():
    """Scheduled job that anonymizes accounts past the grace period."""
    db = SessionLocal()
    try:
        count = process_expired_deletions(db)
        if count:
            logger.info("Account deletion job: anonymized %d user(s)", count)
    except Exception:
        logger.exception("Account deletion job failed")
    finally:
        db.close()
