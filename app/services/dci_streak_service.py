"""DCI Check-in Streak Service (CB-DCI-001 M0-8, #4145).

Separate stream from the study streak managed by ``StreakService``.

Design § 13:
- Reuses ``StreakLog`` writes via the existing ``qualifying_action`` column
  (constant ``ACTION_TYPE_DAILY_CHECKIN``) — no schema change to ``streak_log``.
- Owns its own per-kid aggregate in ``checkin_streak_summary`` so a kid who
  studies via Tutor but never checks in does NOT have a "DCI streak"
  (and vice versa).
- School-day-aware: weekends + holidays + PD days skip without breaking the
  streak. Reuses the ``HolidayDate`` table that already powers the study
  streak nightly job.
- Never-guilt: break events are logged but NEVER surfaced to the kid. The
  ``get_streak`` payload only ever contains ``current``, ``longest``,
  ``last_checkin_date``, and ``days_until_next_milestone``.

ID semantics (important):
- ``kid_id`` here means ``students.id`` (matches the new
  ``checkin_streak_summary`` PK in design § 10).
- ``StreakLog.student_id`` historically references ``users.id`` for the study
  streak. We translate ``kid_id → user_id`` when writing ``StreakLog`` rows so
  the existing study-streak code path is untouched.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.checkin_streak import CheckinStreakSummary
from app.models.holiday import HolidayDate
from app.models.student import Student
from app.models.xp import StreakLog

logger = logging.getLogger(__name__)

# Action-type constant used in ``StreakLog.qualifying_action`` so the row can
# be filtered out from study-streak aggregates and into the DCI stream.
ACTION_TYPE_DAILY_CHECKIN = "daily_checkin"

# Milestones celebrated in the kid affirmation screen (design § 7). Kept in
# sync with study-streak tiers but used here only to compute
# ``days_until_next_milestone`` — never to gate features or shame the kid.
CHECKIN_STREAK_MILESTONES = (3, 7, 14, 30, 60, 100)

# Maximum number of days ``_previous_school_day`` walks back before giving up.
# Bounded so a pathological holiday calendar (e.g. 4-week winter break +
# back-to-back PD days) cannot loop forever; on exhaustion we log a warning
# and return a deterministic anchor minus the bound.
MAX_BACKFILL_DAYS = 30


# ── School-day helpers ──────────────────────────────────────────────


def _is_weekend(d: date) -> bool:
    # Monday = 0 ... Sunday = 6
    return d.weekday() >= 5


def is_school_day(db: Session, d: date) -> bool:
    """Return True if ``d`` should count toward the streak window.

    Mirrors the study-streak nightly logic: weekends + holidays + PD days
    (anything in ``holiday_dates``) are skipped. Both streams use the same
    calendar source so they stay aligned.
    """
    if _is_weekend(d):
        return False
    holiday = db.query(HolidayDate).filter(HolidayDate.date == d).first()
    if holiday is not None:
        return False
    return True


def _previous_school_day(db: Session, anchor: date) -> date:
    """Walk backward from ``anchor - 1`` until we land on a school day.

    Bounded walk (``MAX_BACKFILL_DAYS``) — protects against pathological
    holiday data. On exhaustion we log a warning and return a deterministic
    anchor (``anchor - MAX_BACKFILL_DAYS``) so the streak math never compares
    against a non-school cursor that drifted past the bound.
    """
    cursor = anchor - timedelta(days=1)
    for _ in range(MAX_BACKFILL_DAYS):
        if is_school_day(db, cursor):
            return cursor
        cursor -= timedelta(days=1)
    logger.warning(
        "DCI: no school day found in past %d days from %s — using fallback anchor",
        MAX_BACKFILL_DAYS, anchor.isoformat(),
    )
    return anchor - timedelta(days=MAX_BACKFILL_DAYS)


# ── Internal aggregate helpers ──────────────────────────────────────


def _get_or_create_summary(db: Session, kid_id: int) -> CheckinStreakSummary:
    summary = (
        db.query(CheckinStreakSummary)
        .filter(CheckinStreakSummary.kid_id == kid_id)
        .first()
    )
    if summary is None:
        summary = CheckinStreakSummary(
            kid_id=kid_id,
            current_streak=0,
            longest_streak=0,
            last_checkin_date=None,
        )
        db.add(summary)
        db.flush()
    return summary


def _resolve_user_id(db: Session, kid_id: int) -> Optional[int]:
    """Translate ``students.id → users.id`` for ``StreakLog`` writes."""
    row = db.query(Student.user_id).filter(Student.id == kid_id).first()
    return row[0] if row else None


def _days_until_next_milestone(current: int) -> Optional[int]:
    for milestone in CHECKIN_STREAK_MILESTONES:
        if current < milestone:
            return milestone - current
    return None


# ── Public API ──────────────────────────────────────────────────────


def record_checkin(
    db: Session,
    kid_id: int,
    checkin_date: Optional[date] = None,
) -> CheckinStreakSummary:
    """Record a kid check-in for ``checkin_date`` (default: today).

    Idempotent for the same ``(kid_id, checkin_date)`` — re-recording the same
    day is a no-op that returns the existing summary.

    Side effects:
    - Inserts a ``StreakLog`` row with ``qualifying_action='daily_checkin'``
      (translating ``kid_id → user_id``) iff one does not already exist for
      the given date.
    - Recomputes ``checkin_streak_summary`` (current + longest +
      last_checkin_date) using school-day-aware "previous day" logic.
    """
    if checkin_date is None:
        checkin_date = date.today()

    summary = _get_or_create_summary(db, kid_id)

    # Idempotency: same date already recorded → no-op.
    if summary.last_checkin_date == checkin_date:
        return summary

    user_id = _resolve_user_id(db, kid_id)

    # StreakLog write — only if not already present for this user/date+action.
    # ``qualifying_action`` is the discriminator that keeps the DCI stream
    # separate from study-streak aggregates (see #4183 for the constraint
    # widening that makes this safe on the same day as a study action).
    log_row_to_insert: Optional[StreakLog] = None
    if user_id is not None:
        existing_log = (
            db.query(StreakLog)
            .filter(
                StreakLog.student_id == user_id,
                StreakLog.log_date == checkin_date,
                StreakLog.qualifying_action == ACTION_TYPE_DAILY_CHECKIN,
            )
            .first()
        )
        if existing_log is None:
            log_row_to_insert = StreakLog(
                student_id=user_id,
                log_date=checkin_date,
                qualifying_action=ACTION_TYPE_DAILY_CHECKIN,
                streak_value=None,  # set after the math below
                multiplier=None,
            )
            db.add(log_row_to_insert)
            db.flush()

    # Streak math:
    # - first ever check-in → 1
    # - last check-in was the previous SCHOOL day (or any day after it that
    #   was a non-school day) → continue
    # - otherwise → reset to 1
    if summary.last_checkin_date is None:
        new_current = 1
    else:
        prev_school = _previous_school_day(db, checkin_date)
        if summary.last_checkin_date >= prev_school:
            new_current = summary.current_streak + 1
        else:
            # Streak broken — log break event for telemetry but never surface.
            logger.info(
                "DCI streak break: kid_id=%d previous=%s last_checkin=%s",
                kid_id,
                summary.current_streak,
                summary.last_checkin_date.isoformat(),
            )
            new_current = 1

    summary.current_streak = new_current
    if new_current > summary.longest_streak:
        summary.longest_streak = new_current
    summary.last_checkin_date = checkin_date

    # Backfill streak_value on the row we just inserted (if any) using the
    # held reference — no extra SELECT (#4184).
    if log_row_to_insert is not None:
        log_row_to_insert.streak_value = new_current

    db.commit()
    return summary


def evaluate_checkin_streak(
    db: Session,
    kid_id: int,
    *,
    _summary: Optional[CheckinStreakSummary] = None,
    _yesterday_is_school_day: Optional[bool] = None,
    _checked_in_yesterday: Optional[bool] = None,
) -> str:
    """Nightly cron hook: decide whether yesterday's missed check-in should
    break the streak.

    Returns one of ``'active'``, ``'skip'`` (weekend / holiday / PD),
    ``'broken'``.

    The keyword-only ``_summary`` / ``_yesterday_is_school_day`` /
    ``_checked_in_yesterday`` overrides exist so the nightly batch job
    (#4179) can pre-fetch all three pieces of state in a small fixed
    number of queries and skip the per-kid SELECTs. Single-kid callers
    omit them and get the original 1-summary + 1-holiday + 1-student +
    1-streaklog behaviour.
    """
    if _summary is not None:
        summary = _summary
    else:
        summary = (
            db.query(CheckinStreakSummary)
            .filter(CheckinStreakSummary.kid_id == kid_id)
            .first()
        )
    if summary is None or summary.current_streak == 0:
        return "active"  # nothing to evaluate

    yesterday = date.today() - timedelta(days=1)

    # Weekend / holiday / PD — never breaks. We don't bump
    # ``last_checkin_date`` either; the next real check-in will compare
    # against the previous school day via ``_previous_school_day``.
    if _yesterday_is_school_day is None:
        yesterday_is_school_day = is_school_day(db, yesterday)
    else:
        yesterday_is_school_day = _yesterday_is_school_day
    if not yesterday_is_school_day:
        return "skip"

    # School day — was there a check-in? ``StreakLog`` is the single source
    # of truth for "did this kid actually check in yesterday" — the summary
    # aggregate is derived state and must NOT short-circuit this decision.
    if _checked_in_yesterday is None:
        user_id = _resolve_user_id(db, kid_id)
        checked_in_yesterday = False
        if user_id is not None:
            log = (
                db.query(StreakLog)
                .filter(
                    StreakLog.student_id == user_id,
                    StreakLog.log_date == yesterday,
                    StreakLog.qualifying_action == ACTION_TYPE_DAILY_CHECKIN,
                )
                .first()
            )
            checked_in_yesterday = log is not None
    else:
        checked_in_yesterday = _checked_in_yesterday

    if checked_in_yesterday:
        return "active"

    # Missed school day → break (silently — never surface to the kid).
    logger.info(
        "DCI streak broken (silent): kid_id=%d previous=%d",
        kid_id,
        summary.current_streak,
    )
    summary.current_streak = 0
    db.commit()
    return "broken"


def get_streak(db: Session, kid_id: int) -> dict:
    """Return the kid-facing streak payload (never-guilt — no break info)."""
    summary = (
        db.query(CheckinStreakSummary)
        .filter(CheckinStreakSummary.kid_id == kid_id)
        .first()
    )
    if summary is None:
        return {
            "current": 0,
            "longest": 0,
            "last_checkin_date": None,
            "days_until_next_milestone": _days_until_next_milestone(0),
        }
    return {
        "current": summary.current_streak,
        "longest": summary.longest_streak,
        "last_checkin_date": (
            summary.last_checkin_date.isoformat()
            if summary.last_checkin_date
            else None
        ),
        "days_until_next_milestone": _days_until_next_milestone(
            summary.current_streak
        ),
    }
