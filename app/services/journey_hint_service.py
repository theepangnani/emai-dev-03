"""
Journey hint behaviour-signal service (#2609).

Determines whether contextual hints should be suppressed based on user
behaviour signals:
  - Nuclear suppress flag
  - Two-strike cooldown (2+ consecutive dismissals in 14 days)
  - Self-directed user (visited help/tutorial pages recently)
  - Account age > 30 days
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.audit_log import AuditLog
from app.models.journey_hint import JourneyHint
from app.models.user import User

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────
COOLDOWN_WINDOW_DAYS = 14
COOLDOWN_STRIKE_THRESHOLD = 2
RECENT_HINTS_LIMIT = 5
SELF_DIRECTED_WINDOW_DAYS = 7
ACCOUNT_AGE_THRESHOLD_DAYS = 30
SELF_DIRECTED_ACTIONS = ("page_view_help", "page_view_tutorial")


def check_behavior_signals(db: Session, user_id: int) -> bool:
    """Return True if hints should be SUPPRESSED for this user.

    Checks are ordered from cheapest to most expensive.
    """
    # (a) Nuclear suppress — user explicitly opted out
    suppress_row = (
        db.query(JourneyHint.id)
        .filter(
            JourneyHint.user_id == user_id,
            JourneyHint.hint_key == "suppress_all",
        )
        .first()
    )
    if suppress_row:
        logger.debug("Hint suppressed: nuclear suppress flag for user %s", user_id)
        return True

    # (b) Two-strike cooldown — 2+ consecutive dismissals in the last 14 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_WINDOW_DAYS)
    recent_hints = (
        db.query(JourneyHint)
        .filter(
            JourneyHint.user_id == user_id,
            JourneyHint.created_at >= cutoff,
        )
        .order_by(desc(JourneyHint.created_at))
        .limit(RECENT_HINTS_LIMIT)
        .all()
    )

    consecutive_dismissals = 0
    for hint in recent_hints:
        if hint.status == "dismissed" or hint.engaged is False:
            consecutive_dismissals += 1
        else:
            break  # streak broken

    if consecutive_dismissals >= COOLDOWN_STRIKE_THRESHOLD:
        logger.debug(
            "Hint suppressed: %d consecutive dismissals for user %s",
            consecutive_dismissals,
            user_id,
        )
        return True

    # (c) Self-directed user — visited help/tutorial pages in last 7 days
    self_directed_cutoff = datetime.now(timezone.utc) - timedelta(
        days=SELF_DIRECTED_WINDOW_DAYS
    )
    help_visit = (
        db.query(AuditLog.id)
        .filter(
            AuditLog.user_id == user_id,
            AuditLog.action.in_(SELF_DIRECTED_ACTIONS),
            AuditLog.created_at >= self_directed_cutoff,
        )
        .first()
    )
    if help_visit:
        logger.debug("Hint suppressed: self-directed user %s", user_id)
        return True

    # (d) Account age > 30 days
    user = db.query(User.created_at).filter(User.id == user_id).first()
    if user and user.created_at:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - created
        if age > timedelta(days=ACCOUNT_AGE_THRESHOLD_DAYS):
            logger.debug("Hint suppressed: account age %d days for user %s", age.days, user_id)
            return True

    return False


def record_hint_engagement(
    db: Session,
    user_id: int,
    hint_key: str,
    engaged: bool,
) -> None:
    """Record whether the user engaged with or dismissed a hint.

    Updates the most recent matching journey_hint entry for this user/key.
    If no entry exists, creates one.
    """
    hint = (
        db.query(JourneyHint)
        .filter(
            JourneyHint.user_id == user_id,
            JourneyHint.hint_key == hint_key,
        )
        .order_by(desc(JourneyHint.created_at))
        .first()
    )

    if hint:
        hint.engaged = engaged
        hint.status = "engaged" if engaged else "dismissed"
    else:
        hint = JourneyHint(
            user_id=user_id,
            hint_key=hint_key,
            status="engaged" if engaged else "dismissed",
            engaged=engaged,
        )
        db.add(hint)

    db.flush()
    logger.info(
        "Hint engagement recorded: user=%s key=%s engaged=%s",
        user_id,
        hint_key,
        engaged,
    )
