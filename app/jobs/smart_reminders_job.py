"""APScheduler job wrapper for SmartReminderService.

Runs every 3 hours (configurable) via CronTrigger in main.py.
Keeps the existing check_assignment_reminders daily job intact for backward compat.
"""
import logging

from app.db.database import SessionLocal
from app.services.smart_reminders import SmartReminderService

logger = logging.getLogger(__name__)


async def run_smart_reminders_job() -> None:
    """Entry point called by APScheduler.

    Opens its own DB session, delegates to SmartReminderService, then closes.
    """
    logger.info("APScheduler: smart reminder job triggered")
    db = SessionLocal()
    try:
        service = SmartReminderService()
        result = service.run_smart_reminders(db)
        logger.info(
            f"APScheduler: smart reminder job done | "
            f"sent={result['sent']} skipped={result['skipped']} errors={result['errors']}"
        )
    except Exception as exc:
        logger.error(f"APScheduler: smart reminder job raised exception | error={exc}", exc_info=True)
        db.rollback()
    finally:
        db.close()
