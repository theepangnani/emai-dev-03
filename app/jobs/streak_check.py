"""
Background job: nightly streak evaluation for all active students (#2002).

Runs daily at 00:30 via APScheduler.

CB-DCI-001 M0-8 (#4145): now parameterized by ``action_type`` so the same
nightly cron can compute one summary per stream — study (existing behavior,
``XpSummary`` + ``StreakService.evaluate_streak``) and DCI daily check-in
(new ``CheckinStreakSummary`` + ``dci_streak_service.evaluate_checkin_streak``).

The existing ``check_all_streaks()`` entrypoint is preserved exactly so the
APScheduler hook in ``main.py`` keeps the existing study-streak behavior with
zero regression risk; DCI streams via the new ``check_all_checkin_streaks()``
entrypoint.
"""
import logging

from app.db.database import SessionLocal

logger = logging.getLogger(__name__)


async def check_all_streaks():
    """Nightly cron: evaluate STUDY streaks for all active students.

    Behavior preserved bit-for-bit from #2002 — do not change without
    verifying the full ``tests/test_streaks.py`` suite still passes.
    """
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
            "Streak check completed: action=study evaluated=%d broken=%d",
            evaluated, broken,
        )
    except Exception:
        db.rollback()
        logger.exception("Streak check failed (action=study)")
    finally:
        db.close()


async def check_all_checkin_streaks():
    """Nightly cron: evaluate DCI daily-check-in streaks for all kids with an
    active check-in streak (CB-DCI-001 M0-8, #4145).

    Mirrors ``check_all_streaks`` but operates on the separate
    ``checkin_streak_summary`` aggregate via ``dci_streak_service``. Kept as a
    distinct function so the existing study-streak job is untouched and
    failures in one stream cannot cascade into the other.
    """
    db = SessionLocal()
    evaluated = 0
    broken = 0
    skipped = 0
    try:
        from app.models.checkin_streak import CheckinStreakSummary
        from app.services.dci_streak_service import evaluate_checkin_streak

        summaries = (
            db.query(CheckinStreakSummary)
            .filter(CheckinStreakSummary.current_streak > 0)
            .all()
        )

        for summary in summaries:
            result = evaluate_checkin_streak(db, summary.kid_id)
            evaluated += 1
            if result == "broken":
                broken += 1
            elif result == "skip":
                skipped += 1

        logger.info(
            "Streak check completed: action=daily_checkin evaluated=%d broken=%d skipped=%d",
            evaluated, broken, skipped,
        )
    except Exception:
        db.rollback()
        logger.exception("Streak check failed (action=daily_checkin)")
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
