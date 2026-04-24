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
    # Interactive Learning Engine (CB-ILE-001)
    "ile_session_complete": {"xp": 15, "daily_cap": 45},
    "ile_first_attempt_correct": {"xp": 5, "daily_cap": 50},
    "ile_testing_correct": {"xp": 10, "daily_cap": 50},
    "ile_parent_teaching": {"xp": 10, "daily_cap": 30},
    # Short learning cycle (CB-TUTOR-002 Phase 2)
    # cycle_question_correct amount is variable (100/70/40 per attempt), so "xp"
    # is informational only — the award path below supplies the amount directly.
    # Daily caps tuned to ~2 sessions/day target:
    #   - cycle_question_correct: 600 (≈2 sessions of 3 correct attempts)
    #   - cycle_chunk_bonus: 300 (≈6 chunks × 50)
    "cycle_question_correct": {"xp": 100, "daily_cap": 600},
    "cycle_chunk_bonus": {"xp": 50, "daily_cap": 300},
}

# Per-question diminishing returns for the short learning cycle (#4072).
# Attempts past 3 award 0.
CYCLE_QUESTION_XP_BY_ATTEMPT: dict[int, int] = {1: 100, 2: 70, 3: 40}

# Fixed bonus when a chunk (set of questions) is fully completed.
CYCLE_CHUNK_BONUS_XP = 50

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

# Anti-gaming constants (#2009)
_FLASHCARD_COOLDOWN_SECONDS = 30
_DEDUP_WINDOW_SECONDS = 60
_QUIZ_REPEAT_WINDOW_HOURS = 4
_RAPID_UPLOAD_THRESHOLD = 5
_RAPID_UPLOAD_WINDOW_SECONDS = 120


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
# Anti-gaming checks (#2009)
# ---------------------------------------------------------------------------

_FLASHCARD_ACTIONS = {"flashcard_review", "flashcard_got_it"}


def _check_flashcard_cooldown(db: Session, student_id: int, action_type: str) -> bool:
    """Return True if flashcard cooldown (30s) has NOT elapsed — i.e. reject."""
    if action_type not in _FLASHCARD_ACTIONS:
        return False
    from app.models.xp import XpLedger

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_FLASHCARD_COOLDOWN_SECONDS)
    recent = (
        db.query(XpLedger.id)
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.action_type == action_type,
            XpLedger.created_at >= cutoff,
        )
        .first()
    )
    return recent is not None


def _check_dedup_window(db: Session, student_id: int, action_type: str) -> bool:
    """Return True if a duplicate event exists within the 60-second window — i.e. reject."""
    from app.models.xp import XpLedger

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_DEDUP_WINDOW_SECONDS)
    recent = (
        db.query(XpLedger.id)
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.action_type == action_type,
            XpLedger.created_at >= cutoff,
        )
        .first()
    )
    return recent is not None


def _check_quiz_repeat(
    db: Session, student_id: int, action_type: str, context_id: Optional[str],
) -> bool:
    """Return True if quiz_complete was awarded for the same context within 4 hours — reject."""
    if action_type != "quiz_complete" or not context_id:
        return False
    from app.models.xp import XpLedger

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_QUIZ_REPEAT_WINDOW_HOURS)
    recent = (
        db.query(XpLedger.id)
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.action_type == "quiz_complete",
            XpLedger.context_id == context_id,
            XpLedger.created_at >= cutoff,
        )
        .first()
    )
    return recent is not None


def _check_rapid_uploads(db: Session, student_id: int, action_type: str) -> None:
    """Log a warning if > 5 uploads in 2 minutes. Does NOT block."""
    if action_type != "upload":
        return
    from app.models.xp import XpLedger

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_RAPID_UPLOAD_WINDOW_SECONDS)
    count = (
        db.query(func.count(XpLedger.id))
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.action_type == "upload",
            XpLedger.created_at >= cutoff,
        )
        .scalar()
    ) or 0
    if count >= _RAPID_UPLOAD_THRESHOLD:
        logger.warning(
            "RAPID_UPLOAD_FLAG | student_id=%s | %d uploads in %ds window",
            student_id, count, _RAPID_UPLOAD_WINDOW_SECONDS,
        )


# ---------------------------------------------------------------------------
# Core service functions
# ---------------------------------------------------------------------------

def award_xp(
    db: Session,
    student_id: int,
    action_type: str,
    context_id: Optional[str] = None,
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

        # Anti-gaming checks (#2009) — fail-safe: if check itself errors, award XP
        try:
            # 1. Flashcard cooldown (30s minimum between flashcard XP)
            if _check_flashcard_cooldown(db, student_id, action_type):
                logger.debug(
                    "Flashcard cooldown | student_id=%s | action=%s",
                    student_id, action_type,
                )
                return None

            # 2. 60-second dedup (same student + action within 60s)
            if _check_dedup_window(db, student_id, action_type):
                logger.debug(
                    "Dedup window | student_id=%s | action=%s",
                    student_id, action_type,
                )
                return None

            # 3. Quiz 4-hour repeat cap (same quiz within 4 hours)
            if _check_quiz_repeat(db, student_id, action_type, context_id):
                logger.debug(
                    "Quiz repeat cap | student_id=%s | context_id=%s",
                    student_id, context_id,
                )
                return None

            # 4. Rapid upload flag (log warning, do NOT block)
            _check_rapid_uploads(db, student_id, action_type)
        except Exception:
            logger.exception(
                "Anti-gaming check failed (fail-safe, awarding XP) | student_id=%s | action=%s",
                student_id, action_type,
            )

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
            context_id=context_id,
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

        # Check and award badges (non-blocking)
        try:
            from app.services.badge_service import BadgeService
            BadgeService.check_and_award(db, student_id, action_type)
        except Exception:
            logger.exception("Badge check failed (non-blocking) | student_id=%s", student_id)

        return entry

    except Exception:
        logger.exception("XP award failed | student_id=%s | action=%s", student_id, action_type)
        try:
            db.rollback()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Short learning cycle — per-question + chunk bonus awards (#4072)
# ---------------------------------------------------------------------------

def _check_context_dedup(db: Session, student_id: int, context_id: str) -> bool:
    """Return True if an XP entry for this exact context_id already exists — reject.

    Unlike the 60s dedup window, this is a lifetime dedup keyed on context_id,
    used for cycle question/chunk awards where each question or chunk may be
    rewarded at most once.
    """
    from app.models.xp import XpLedger

    existing = (
        db.query(XpLedger.id)
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.context_id == context_id,
        )
        .first()
    )
    return existing is not None


def _award_cycle_xp(
    db: Session,
    student_id: int,
    action_type: str,
    base_xp: int,
    context_id: str,
) -> int:
    """Shared internal helper for cycle XP awards.

    Uses lifetime dedup (context_id), respects daily caps + streak multipliers.
    Returns XP awarded (0 if capped or duplicate).

    FAIL-SAFE: never raises — logs errors and returns 0.
    """
    try:
        from app.core.config import settings
        if not settings.xp_enabled:
            return 0

        from app.models.xp import XpLedger

        action = XP_ACTIONS.get(action_type)
        if action is None:
            logger.warning(
                "Unknown cycle XP action_type=%s for student_id=%s",
                action_type, student_id,
            )
            return 0

        # Lifetime dedup on context_id — each question/chunk awarded at most once
        try:
            if _check_context_dedup(db, student_id, context_id):
                logger.debug(
                    "Cycle XP dedup | student_id=%s | action=%s | context=%s",
                    student_id, action_type, context_id,
                )
                return 0
        except Exception:
            logger.exception(
                "Cycle XP dedup check failed (fail-safe, awarding) | student_id=%s | context=%s",
                student_id, context_id,
            )

        # Daily cap for this action
        today_xp = _get_today_xp(db, student_id, action_type)
        if today_xp >= action["daily_cap"]:
            logger.debug(
                "Daily cap reached | student_id=%s | action=%s | today=%d | cap=%d",
                student_id, action_type, today_xp, action["daily_cap"],
            )
            return 0

        # Streak multiplier
        summary = _get_or_create_summary(db, student_id)
        multiplier = get_streak_multiplier(summary.current_streak)

        final_xp = int(base_xp * multiplier)

        # Clamp to remaining daily cap
        remaining_cap = action["daily_cap"] - today_xp
        if final_xp > remaining_cap:
            final_xp = remaining_cap
        if final_xp <= 0:
            return 0

        entry = XpLedger(
            student_id=student_id,
            action_type=action_type,
            xp_awarded=final_xp,
            multiplier=multiplier,
            context_id=context_id,
        )
        db.add(entry)
        db.flush()

        summary.total_xp = (summary.total_xp or 0) + final_xp
        level_info = get_level_for_xp(summary.total_xp)
        summary.current_level = level_info["level"]
        summary.last_qualifying_action_date = date.today()
        db.flush()

        logger.info(
            "Cycle XP awarded | student_id=%s | action=%s | xp=%d | multiplier=%.2f | context=%s",
            student_id, action_type, final_xp, multiplier, context_id,
        )

        # Badge check (non-blocking)
        try:
            from app.services.badge_service import BadgeService
            BadgeService.check_and_award(db, student_id, action_type)
        except Exception:
            logger.exception("Badge check failed (non-blocking) | student_id=%s", student_id)

        return final_xp

    except Exception:
        logger.exception(
            "Cycle XP award failed | student_id=%s | action=%s | context=%s",
            student_id, action_type, context_id,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return 0


def award_cycle_question_xp(
    db: Session,
    student_id: int,
    question_id: str,
    attempt_number,
    user_role: str,
) -> int:
    """Award XP for a correct answer in the short learning cycle.

    Students only. Returns 0 (no XP) for teacher or parent roles — the
    students-only gate is enforced INSIDE the function, so every caller is
    safe by default (single source of truth).

    Amounts diminish: 100 / 70 / 40 for tries 1 / 2 / 3; 0 after.
    Uses context_id=cycle_question_{question_id} for lifetime dedup.
    Respects existing daily caps + streak multipliers.
    Returns XP awarded (0 if not a student, capped, duplicate, or past attempt 3).

    ``attempt_number`` is coerced via ``int()`` so callers passing strings
    (e.g. ``"1"``) or floats (e.g. ``1.0``) still get XP instead of a silent
    0. Values that cannot be coerced log a warning and return 0.
    """
    if (user_role or "").lower() != "student":
        return 0
    try:
        attempt_int = int(attempt_number)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid attempt_number %r for question %s", attempt_number, question_id,
        )
        return 0
    amount = CYCLE_QUESTION_XP_BY_ATTEMPT.get(attempt_int, 0)
    if amount == 0:
        return 0
    context_id = f"cycle_question_{question_id}"
    return _award_cycle_xp(
        db, student_id, "cycle_question_correct", amount, context_id,
    )


def award_cycle_chunk_bonus(
    db: Session,
    student_id: int,
    chunk_id: str,
    user_role: str,
) -> int:
    """Award 50 XP bonus when a chunk is fully completed.

    Students only. Returns 0 (no XP) for teacher or parent roles — the
    students-only gate is enforced INSIDE the function, so every caller is
    safe by default (single source of truth).

    Uses context_id=cycle_chunk_bonus_{chunk_id} for lifetime dedup.
    Respects daily caps + streak multipliers.
    Returns XP awarded (0 if not a student, capped, or duplicate).
    """
    if (user_role or "").lower() != "student":
        return 0
    context_id = f"cycle_chunk_bonus_{chunk_id}"
    return _award_cycle_xp(
        db, student_id, "cycle_chunk_bonus", CYCLE_CHUNK_BONUS_XP, context_id,
    )


def get_summary(db: Session, student_id: int):
    """Build an XpSummaryResponse for the student."""
    from app.models.xp import Badge, XpLedger
    from app.schemas.xp import XpSummaryResponse

    summary = _get_or_create_summary(db, student_id)
    total_xp = summary.total_xp or 0
    level_info = get_level_for_xp(total_xp)
    today_xp = _get_today_total_xp(db, student_id)
    current_streak = summary.current_streak or 0

    # xp_in_level / xp_for_next_level: progress within current level band
    level_start_xp = level_info["xp_required"]
    next_level_info = None
    for lvl in LEVELS:
        if lvl["level"] == level_info["level"] + 1:
            next_level_info = lvl
            break
    if next_level_info:
        xp_for_next = next_level_info["xp_required"] - level_start_xp
        xp_in = total_xp - level_start_xp
    else:
        # Max level
        xp_for_next = 0
        xp_in = 0

    # weekly_xp: sum of last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    weekly_xp = int(
        db.query(func.coalesce(func.sum(XpLedger.xp_awarded), 0))
        .filter(XpLedger.student_id == student_id, XpLedger.created_at >= week_ago)
        .scalar()
    )

    # recent_badges: last 3 earned badges
    from app.services.badge_service import BADGE_DEFINITIONS
    _BADGE_CATALOG = {
        b["badge_id"]: {"name": b["badge_name"], "description": b["badge_description"], "icon": b["icon"]}
        for b in BADGE_DEFINITIONS
    }
    recent_badge_rows = (
        db.query(Badge)
        .filter(Badge.student_id == student_id)
        .order_by(Badge.awarded_at.desc())
        .limit(3)
        .all()
    )
    recent_badges = []
    for b in recent_badge_rows:
        info = _BADGE_CATALOG.get(b.badge_id, {"name": b.badge_id, "description": ""})
        recent_badges.append({
            "id": b.badge_id,
            "name": info["name"],
            "description": info["description"],
            "icon": info.get("icon", b.badge_id),
            "earned": True,
            "earned_at": b.awarded_at.isoformat() if b.awarded_at else None,
        })

    return XpSummaryResponse(
        user_id=student_id,
        total_xp=total_xp,
        level=level_info["level"],
        current_level=level_info["level"],
        level_title=level_info["title"],
        current_streak=current_streak,
        longest_streak=summary.longest_streak or 0,
        freeze_tokens_remaining=summary.freeze_tokens_remaining if summary.freeze_tokens_remaining is not None else 1,
        xp_to_next_level=get_xp_to_next_level(total_xp),
        today_xp=today_xp,
        today_cap=_TOTAL_DAILY_CAP,
        streak_days=current_streak,
        xp_in_level=xp_in,
        xp_for_next_level=xp_for_next,
        today_max_xp=_TOTAL_DAILY_CAP,
        weekly_xp=weekly_xp,
        recent_badges=recent_badges,
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
    def award_xp(db, student_id: int, action_type: str, context_id: Optional[str] = None):
        return award_xp(db, student_id, action_type, context_id=context_id)

    @staticmethod
    def award_cycle_question_xp(
        db, student_id: int, question_id: str, attempt_number: int, user_role: str,
    ) -> int:
        return award_cycle_question_xp(
            db, student_id, question_id, attempt_number, user_role,
        )

    @staticmethod
    def award_cycle_chunk_bonus(db, student_id: int, chunk_id: str, user_role: str) -> int:
        return award_cycle_chunk_bonus(db, student_id, chunk_id, user_role)

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
