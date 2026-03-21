"""
Background job: nightly streak evaluation for all active students (#2002).

Runs daily at 00:30 via APScheduler.
"""
import logging

from app.db.database import SessionLocal

logger = logging.getLogger(__name__)


async def check_all_streaks():
    """Nightly cron: evaluate streaks for all active students."""
    db = SessionLocal()
    evaluated = 0
    broken = 0
    try:
        from app.models.xp import XpSummary
        from app.services.streak_service import StreakService

        # Query all students who have an xp_summary with an active streak
        summaries = db.query(XpSummary).filter(XpSummary.current_streak > 0).all()

        for summary in summaries:
            result = StreakService.evaluate_streak(db, summary.student_id)
            evaluated += 1
            if result == "broken":
                broken += 1

        logger.info(
            "Streak check completed: evaluated=%d broken=%d",
            evaluated, broken,
        )
    except Exception:
        db.rollback()
        logger.exception("Streak check failed")
    finally:
        db.close()


async def refresh_freeze_tokens():
    """Monthly cron (1st of month): reset freeze tokens to 1 for all students."""
    db = SessionLocal()
    try:
        from app.services.streak_service import StreakService

        count = StreakService.refresh_monthly_freeze_tokens(db)
        logger.info("Monthly freeze token refresh completed: %d students", count)
    except Exception:
        db.rollback()
        logger.exception("Freeze token refresh failed")
    finally:
        db.close()
