"""
XP service — business logic for the Gamification XP system (#2001).

Handles XP awarding, daily caps, streak multipliers, level calculation,
and summary maintenance.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

XP_ACTIONS: dict[str, dict] = {
    "upload": {"xp": 10, "daily_cap": 30},
    "upload_lms": {"xp": 15, "daily_cap": 30},
    "study_guide": {"xp": 20, "daily_cap": 40},
    "flashcard_deck": {"xp": 15, "daily_cap": 15},
    "flashcard_review": {"xp": 10, "daily_cap": 30},
    "ai_chat": {"xp": 5, "daily_cap": 20},
    "pomodoro": {"xp": 15, "daily_cap": 30},
    "flashcard_got_it": {"xp": 1, "daily_cap": 20},
    "daily_login": {"xp": 5, "daily_cap": 5},
    "weekly_review": {"xp": 25, "daily_cap": 25},
    "quiz_complete": {"xp": 15, "daily_cap": 30},
    "quiz_improvement": {"xp": 10, "daily_cap": 10},
}

LEVELS: list[dict] = [
    {"level": 1, "title": "Curious Learner", "xp_required": 0},
    {"level": 2, "title": "Note Taker", "xp_required": 200},
    {"level": 3, "title": "Study Starter", "xp_required": 500},
    {"level": 4, "title": "Focused Scholar", "xp_required": 1000},
    {"level": 5, "title": "Deep Diver", "xp_required": 2000},
    {"level": 6, "title": "Guide Master", "xp_required": 3500},
    {"level": 7, "title": "Exam Champion", "xp_required": 5500},
    {"level": 8, "title": "ClassBridge Elite", "xp_required": 8000},
]

STREAK_MULTIPLIERS: list[dict] = [
    {"min_days": 60, "multiplier": 2.0},
    {"min_days": 30, "multiplier": 1.75},
    {"min_days": 14, "multiplier": 1.5},
    {"min_days": 7, "multiplier": 1.25},
    {"min_days": 1, "multiplier": 1.0},
]

# Sum of all daily caps — absolute ceiling for a single day
_TOTAL_DAILY_CAP = sum(v["daily_cap"] for v in XP_ACTIONS.values())


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_level_for_xp(total_xp: int) -> dict:
    """Return the level info dict for a given XP total."""
    result = LEVELS[0]
    for lvl in LEVELS:
        if total_xp >= lvl["xp_required"]:
            result = lvl
        else:
            break
    return result


def get_xp_to_next_level(total_xp: int) -> int:
    """Return how much XP is needed to reach the next level."""
    current = get_level_for_xp(total_xp)
    for lvl in LEVELS:
        if lvl["level"] == current["level"] + 1:
            return lvl["xp_required"] - total_xp
    return 0  # already max level


def get_streak_multiplier(streak_days: int) -> float:
    """Return the multiplier for the current streak length."""
    for tier in STREAK_MULTIPLIERS:
        if streak_days >= tier["min_days"]:
            return tier["multiplier"]
    return 1.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_week_start() -> datetime:
    """Return the start of the current week (Monday 00:00 UTC)."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _get_today_xp(db: Session, student_id: int, action_type: str) -> int:
    """Sum of today's XP for a given action type."""
    from app.models.xp import XpLedger

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = (
        db.query(func.coalesce(func.sum(XpLedger.xp_awarded), 0))
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.action_type == action_type,
            XpLedger.created_at >= today_start,
        )
        .scalar()
    )
    return int(result)


def _get_today_total_xp(db: Session, student_id: int) -> int:
    """Sum of all XP earned today across all action types."""
    from app.models.xp import XpLedger

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = (
        db.query(func.coalesce(func.sum(XpLedger.xp_awarded), 0))
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.created_at >= today_start,
        )
        .scalar()
    )
    return int(result)


def _get_or_create_summary(db: Session, student_id: int):
    """Return XpSummary row, creating if missing."""
    from app.models.xp import XpSummary

    summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
    if not summary:
        summary = XpSummary(student_id=student_id)
        db.add(summary)
        db.flush()
        logger.info("Auto-created XP summary for student_id=%s", student_id)
    return summary


# ---------------------------------------------------------------------------
# Core service functions
# ---------------------------------------------------------------------------

def award_xp(
    db: Session,
    student_id: int,
    action_type: str,
) -> Optional["XpLedger"]:  # noqa: F821
    """Award XP for an action. Returns the ledger entry, or None if capped.

    FAIL-SAFE: never raises — logs errors and returns None so the calling
    endpoint is never blocked by gamification failures.
    """
    try:
        from app.core.config import settings
        if not settings.xp_enabled:
            return None

        from app.models.xp import XpLedger

        action = XP_ACTIONS.get(action_type)
        if action is None:
            logger.warning("Unknown XP action_type=%s for student_id=%s", action_type, student_id)
            return None

        # Check daily cap for this action type
        today_xp = _get_today_xp(db, student_id, action_type)
        if today_xp >= action["daily_cap"]:
            logger.debug(
                "Daily cap reached | student_id=%s | action=%s | today=%d | cap=%d",
                student_id, action_type, today_xp, action["daily_cap"],
            )
            return None

        # Get streak multiplier from summary
        summary = _get_or_create_summary(db, student_id)
        multiplier = get_streak_multiplier(summary.current_streak)

        base_xp = action["xp"]
        final_xp = int(base_xp * multiplier)

        # Clamp so we don't exceed daily cap
        remaining_cap = action["daily_cap"] - today_xp
        if final_xp > remaining_cap:
            final_xp = remaining_cap

        # Create ledger entry
        entry = XpLedger(
            student_id=student_id,
            action_type=action_type,
            xp_awarded=final_xp,
            multiplier=multiplier,
        )
        db.add(entry)
        db.flush()

        # Update summary
        summary.total_xp = (summary.total_xp or 0) + final_xp
        level_info = get_level_for_xp(summary.total_xp)
        summary.current_level = level_info["level"]
        summary.last_qualifying_action_date = date.today()
        db.flush()

        logger.info(
            "XP awarded | student_id=%s | action=%s | xp=%d | multiplier=%.2f | total=%d",
            student_id, action_type, final_xp, multiplier, summary.total_xp,
        )
        return entry

    except Exception:
        logger.exception("XP award failed | student_id=%s | action=%s", student_id, action_type)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def get_summary(db: Session, student_id: int):
    """Build an XpSummaryResponse for the student."""
    from app.schemas.xp import XpSummaryResponse

    summary = _get_or_create_summary(db, student_id)
    total_xp = summary.total_xp or 0
    level_info = get_level_for_xp(total_xp)
    today_xp = _get_today_total_xp(db, student_id)

    return XpSummaryResponse(
        user_id=student_id,
        total_xp=total_xp,
        level=level_info["level"],
        current_level=level_info["level"],
        level_title=level_info["title"],
        current_streak=summary.current_streak or 0,
        longest_streak=summary.longest_streak or 0,
        freeze_tokens_remaining=summary.freeze_tokens_remaining if summary.freeze_tokens_remaining is not None else 1,
        xp_to_next_level=get_xp_to_next_level(total_xp),
        today_xp=today_xp,
        today_cap=_TOTAL_DAILY_CAP,
    )


def get_history(db: Session, student_id: int, limit: int = 50, offset: int = 0):
    """Return paginated XP history for the student."""
    from app.models.xp import XpLedger
    from app.schemas.xp import XpHistoryResponse, XpLedgerEntry

    total_count = (
        db.query(func.count(XpLedger.id))
        .filter(XpLedger.student_id == student_id)
        .scalar()
    ) or 0

    rows = (
        db.query(XpLedger)
        .filter(XpLedger.student_id == student_id)
        .order_by(XpLedger.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    entries = [
        XpLedgerEntry(
            action_type=r.action_type,
            xp_awarded=r.xp_awarded,
            multiplier=r.multiplier,
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return XpHistoryResponse(items=entries, total=total_count, limit=limit, offset=offset)


class XpService:
    """Class-based wrapper for XP service functions (used by API routes)."""

    @staticmethod
    def award_xp(db, student_id: int, action_type: str):
        return award_xp(db, student_id, action_type)

    @staticmethod
    def get_summary(db, student_id: int):
        return get_summary(db, student_id)

    @staticmethod
    def get_history(db, student_id: int, limit: int = 50, offset: int = 0):
        return get_history(db, student_id, limit=limit, offset=offset)

    @staticmethod
    def get_badges(db, student_id: int):
        """Get all badges for a student."""
        from app.models.xp import Badge
        earned = db.query(Badge).filter(Badge.student_id == student_id).all()
        earned_ids = {b.badge_id for b in earned}
        all_badges = [
            {"badge_id": "first_upload", "badge_name": "First Upload", "badge_description": "Upload first document"},
            {"badge_id": "first_guide", "badge_name": "First Study Guide", "badge_description": "Generate first study guide"},
            {"badge_id": "streak_7", "badge_name": "7-Day Streak", "badge_description": "Achieve a 7-day streak"},
            {"badge_id": "streak_30", "badge_name": "30-Day Streak", "badge_description": "Achieve a 30-day streak"},
            {"badge_id": "flashcard_fanatic", "badge_name": "Flashcard Fanatic", "badge_description": "Review 100 flashcards"},
            {"badge_id": "lms_linker", "badge_name": "LMS Linker", "badge_description": "Upload 5 docs from LMS"},
            {"badge_id": "exam_ready", "badge_name": "Exam Ready", "badge_description": "Generate guide from past exam"},
            {"badge_id": "quiz_improver", "badge_name": "Quiz Improver", "badge_description": "Score higher 3 times"},
        ]
        result = []
        for b in all_badges:
            earned_badge = next((e for e in earned if e.badge_id == b["badge_id"]), None)
            result.append({
                "badge_id": b["badge_id"],
                "badge_name": b["badge_name"],
                "badge_description": b["badge_description"],
                "earned": b["badge_id"] in earned_ids,
                "awarded_at": earned_badge.awarded_at if earned_badge else None,
            })
        return result

    @staticmethod
    def award_brownie_points(
        db: Session,
        student_user_id: int,
        points: int,
        awarder_id: int,
        reason: Optional[str] = None,
        weekly_cap: int = 50,
    ):
        """Award brownie points from a parent/teacher to a student.

        weekly_cap: max XP this awarder can give this student per week
        (50 for parents, 30 for teachers).
        """
        from app.models.xp import XpLedger
        from app.schemas.xp import BrowniePointResponse

        # Check weekly cap
        week_start = _get_week_start()
        awarded_this_week = (
            db.query(func.coalesce(func.sum(XpLedger.xp_awarded), 0))
            .filter(
                XpLedger.awarder_id == awarder_id,
                XpLedger.student_id == student_user_id,
                XpLedger.action_type == "brownie_points",
                XpLedger.created_at >= week_start,
            )
            .scalar()
        )
        awarded_this_week = int(awarded_this_week)
        remaining = weekly_cap - awarded_this_week

        if remaining <= 0:
            return BrowniePointResponse(
                awarded=0,
                student_user_id=student_user_id,
                new_total_xp=0,
                remaining_weekly_cap=0,
                message=f"Weekly cap of {weekly_cap} XP reached for this student",
            )

        # Clamp to remaining cap
        actual_points = min(points, remaining)

        summary = _get_or_create_summary(db, student_user_id)

        entry = XpLedger(
            student_id=student_user_id,
            action_type="brownie_points",
            xp_awarded=actual_points,
            multiplier=1.0,
            awarder_id=awarder_id,
            reason=reason,
        )
        db.add(entry)
        db.flush()

        summary.total_xp = (summary.total_xp or 0) + actual_points
        level_info = get_level_for_xp(summary.total_xp)
        summary.current_level = level_info["level"]
        db.flush()

        # Create notification for student
        try:
            from app.models.notification import Notification, NotificationType
            from app.models.user import User
            awarder = db.query(User).filter(User.id == awarder_id).first()
            awarder_name = awarder.full_name if awarder else "Someone"
            db.add(Notification(
                user_id=student_user_id,
                type=NotificationType.SYSTEM,
                title="You earned brownie points!",
                content=f"{awarder_name} awarded you {actual_points} XP" + (f": {reason}" if reason else ""),
            ))
            db.flush()
        except Exception:
            logger.warning("Failed to create brownie points notification for student=%s", student_user_id)

        logger.info(
            "Brownie points awarded | student=%s | points=%d | awarder=%s",
            student_user_id, actual_points, awarder_id,
        )
        return BrowniePointResponse(
            awarded=actual_points,
            student_user_id=student_user_id,
            new_total_xp=summary.total_xp,
            remaining_weekly_cap=remaining - actual_points,
            message=f"Awarded {actual_points} brownie points",
        )

    @staticmethod
    def get_streak(db, student_id: int):
        """Get streak info for a student."""
        summary = _get_or_create_summary(db, student_id)
        streak = summary.current_streak
        multiplier = get_streak_multiplier(streak)
        if streak >= 60:
            tier = "gold"
        elif streak >= 30:
            tier = "red_glow"
        elif streak >= 14:
            tier = "red"
        elif streak >= 7:
            tier = "orange"
        else:
            tier = "grey"
        return {
            "current_streak": streak,
            "longest_streak": summary.longest_streak,
            "freeze_tokens_remaining": summary.freeze_tokens_remaining,
            "multiplier": multiplier,
            "tier": tier,
            "streak_tier": tier,
        }

    @staticmethod
    def get_weekly_brownie_remaining(
        db: Session,
        awarder_id: int,
        student_user_id: int,
        weekly_cap: int = 50,
    ) -> int:
        """Return how many brownie points the awarder can still give this student this week."""
        from app.models.xp import XpLedger

        week_start = _get_week_start()
        awarded = (
            db.query(func.coalesce(func.sum(XpLedger.xp_awarded), 0))
            .filter(
                XpLedger.awarder_id == awarder_id,
                XpLedger.student_id == student_user_id,
                XpLedger.action_type == "brownie_points",
                XpLedger.created_at >= week_start,
            )
            .scalar()
        )
        return max(0, weekly_cap - int(awarded))
