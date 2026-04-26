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

    Performance (#4179): the per-kid loop pre-resolves
    ``yesterday is school day?`` once and pre-fetches the StreakLog
    "yesterday check-in" rows + the ``students.id → users.id`` map in a
    single batched query each, then passes the cached values into
    ``evaluate_checkin_streak``. Reduces the per-kid query count from 4
    (summary + holiday + student + streaklog) to 0 hot SELECTs.
    """
    db = SessionLocal()
    evaluated = 0
    broken = 0
    skipped = 0
    try:
        from datetime import date, timedelta

        from app.models.dci import CheckinStreakSummary
        from app.models.student import Student
        from app.models.xp import StreakLog
        from app.services.dci_streak_service import (
            ACTION_TYPE_DAILY_CHECKIN,
            evaluate_checkin_streak,
            is_school_day,
        )

        summaries = (
            db.query(CheckinStreakSummary)
            .filter(CheckinStreakSummary.current_streak > 0)
            .all()
        )

        # Pre-fetch shared state for the whole batch (#4179).
        yesterday = date.today() - timedelta(days=1)
        yesterday_is_school_day = is_school_day(db, yesterday)

        kid_ids = [s.kid_id for s in summaries]
        # students.id → users.id, batched.
        student_rows = (
            db.query(Student.id, Student.user_id)
            .filter(Student.id.in_(kid_ids))
            .all()
            if kid_ids
            else []
        )
        kid_to_user = {row[0]: row[1] for row in student_rows}

        # Set of user_ids that DID check in yesterday on the daily_checkin
        # stream — single query, in-memory membership test per kid.
        checked_in_user_ids: set[int] = set()
        if yesterday_is_school_day and kid_to_user:
            user_ids = [u for u in kid_to_user.values() if u is not None]
            if user_ids:
                rows = (
                    db.query(StreakLog.student_id)
                    .filter(
                        StreakLog.student_id.in_(user_ids),
                        StreakLog.log_date == yesterday,
                        StreakLog.qualifying_action == ACTION_TYPE_DAILY_CHECKIN,
                    )
                    .all()
                )
                checked_in_user_ids = {row[0] for row in rows}

        for summary in summaries:
            user_id = kid_to_user.get(summary.kid_id)
            checked_in = (
                user_id is not None and user_id in checked_in_user_ids
            )
            result = evaluate_checkin_streak(
                db,
                summary.kid_id,
                _summary=summary,
                _yesterday_is_school_day=yesterday_is_school_day,
                _checked_in_yesterday=checked_in,
            )
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
