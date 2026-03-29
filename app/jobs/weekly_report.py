"""
Background job: send Weekly Family Report Card emails to all parents.

Runs every Sunday at 8 PM UTC via APScheduler (#2228).
Default: opted-in for all parents (respects email_notifications flag).
"""
import logging

from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.services.weekly_report_service import send_weekly_report_email

logger = logging.getLogger(__name__)


async def send_weekly_reports():
    """Send the weekly family report card email to all active parents."""
    logger.info("Running weekly family report card job...")

    db = SessionLocal()
    sent = 0
    failed = 0
    skipped = 0
    try:
        parents = (
            db.query(User)
            .filter(
                User.is_active == True,  # noqa: E712
                User.email.isnot(None),
            )
            .all()
        )

        # Filter to users who have the parent role
        parent_users = [p for p in parents if p.has_role(UserRole.PARENT)]

        logger.info("Weekly report: found %d parent users", len(parent_users))

        for parent in parent_users:
            # Respect email_notifications preference (default: opted-in)
            if not getattr(parent, "email_notifications", True):
                skipped += 1
                continue

            try:
                success = await send_weekly_report_email(db, parent.id)
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    "Weekly report failed for user %d | error=%s",
                    parent.id,
                    e,
                    exc_info=True,
                )
                failed += 1

        logger.info(
            "Weekly report job complete | sent=%d | failed=%d | skipped=%d",
            sent,
            failed,
            skipped,
        )
    except Exception:
        db.rollback()
        logger.exception("Weekly report job failed")
    finally:
        db.close()
