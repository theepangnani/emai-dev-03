"""
Background job: send Weekly Progress Pulse digest emails to all opted-in parents.

Runs every Sunday at 7 PM UTC via APScheduler (#2022).
"""
import logging

from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.services.weekly_digest_service import send_weekly_digest_email

logger = logging.getLogger(__name__)


async def send_weekly_digests():
    """Send the weekly digest email to all parents with daily_digest_enabled."""
    logger.info("Running weekly digest job...")

    db = SessionLocal()
    sent = 0
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

        logger.info("Weekly digest: found %d opted-in parents", len(parents))

        for parent in parents:
            try:
                success = await send_weekly_digest_email(db, parent.id)
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                db.rollback()
                logger.error(
                    "Weekly digest failed for user %d | error=%s",
                    parent.id,
                    e,
                    exc_info=True,
                )
                failed += 1

        logger.info(
            "Weekly digest job complete | sent=%d | failed=%d",
            sent,
            failed,
        )
    except Exception:
        db.rollback()
        logger.exception("Weekly digest job failed")
    finally:
        db.close()
