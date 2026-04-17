"""
Background job: send Daily Morning Digest emails to all opted-in parents.

Runs every day at 7 AM UTC via APScheduler (#2023).
"""
import logging

from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.services.daily_digest_service import send_daily_digest_email

logger = logging.getLogger(__name__)


async def send_daily_digests():
    """Send the daily digest email to all parents with daily_digest_enabled."""
    logger.info("Running daily digest job...")

    db = SessionLocal()
    sent = 0
    skipped = 0
    failed = 0
    try:
        parents = (
            db.query(User)
            .filter(
                User.role == UserRole.PARENT,
                User.is_active == True,
                User.daily_digest_enabled == True,
            )
            .all()
        )

        logger.info("Daily digest: found %d opted-in parents", len(parents))

        for parent in parents:
            try:
                success = await send_daily_digest_email(db, parent.id)
                if success:
                    sent += 1
                else:
                    skipped += 1  # no content to report
            except Exception as e:
                db.rollback()
                logger.error(
                    "Daily digest failed for user %d | error=%s",
                    parent.id,
                    e,
                    exc_info=True,
                )
                failed += 1

        logger.info(
            "Daily digest job complete | sent=%d | skipped=%d | failed=%d",
            sent,
            skipped,
            failed,
        )
    except Exception:
        db.rollback()
        logger.exception("Daily digest job failed")
    finally:
        db.close()
