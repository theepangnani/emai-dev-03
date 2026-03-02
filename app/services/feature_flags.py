"""
Feature flag evaluation service.

Priority order for is_enabled():
1. UserFeatureOverride (highest priority; respects expires_at)
2. GLOBAL scope  → flag.is_enabled  (with rollout_percentage hash-based bucketing)
3. TIER scope    → user.subscription_tier in flag.enabled_tiers
4. ROLE scope    → any user role in flag.enabled_roles
5. USER scope    → user.id in flag.enabled_user_ids
6. BETA scope    → user.id in flag.enabled_user_ids
7. Default       → flag.is_enabled

Results are cached in a simple in-process dict with a 60-second TTL.
Call invalidate_cache() after any flag/override mutation to ensure
subsequent reads see fresh data.
"""

import hashlib
import json
import logging
import time
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.feature_flag import FeatureFlag, FlagScope, UserFeatureOverride
from app.models.user import User

logger = logging.getLogger(__name__)

# ─── Pre-defined flag key constants ───────────────────────────────────────────

# Phase 1 Core
FLAG_GOOGLE_CLASSROOM = "google_classroom"
FLAG_AI_STUDY_TOOLS = "ai_study_tools"
FLAG_MESSAGING = "messaging"
FLAG_TEACHER_EMAIL_MONITORING = "teacher_email_monitoring"
FLAG_NOTIFICATION_SYSTEM = "notification_system"
FLAG_INSPIRATION_MESSAGES = "inspiration_messages"

# Phase 1.5-2
FLAG_GOOGLE_CALENDAR = "google_calendar"
FLAG_DOCUMENT_REPOSITORY = "document_repository"
FLAG_GRADE_TRACKING = "grade_tracking"
FLAG_PWA_OFFLINE = "pwa_offline"
FLAG_NOTES_PROJECTS = "notes_projects"
FLAG_FAQ_KNOWLEDGE_BASE = "faq_knowledge_base"

# Phase 2+
FLAG_PUSH_NOTIFICATIONS = "push_notifications"
FLAG_MULTI_LMS = "multi_lms"

# Phase 3
FLAG_SCHOOL_BOARD_INTEGRATION = "school_board_integration"
FLAG_COURSE_PLANNING = "course_planning"
FLAG_AI_WRITING_ASSISTANT = "ai_writing_assistant"
FLAG_AI_MOCK_EXAMS = "ai_mock_exams"
FLAG_PARENT_FORUM = "parent_forum"
FLAG_TEACHER_RESOURCES = "teacher_resources"
FLAG_STUDENT_ENGAGEMENT = "student_engagement"

# Phase 4+ (original 8 flags)
FLAG_AI_EMAIL_AGENT = "ai_email_agent"
FLAG_TUTOR_MARKETPLACE = "tutor_marketplace"
FLAG_LESSON_PLANNER = "lesson_planner"
FLAG_AI_PERSONALIZATION = "ai_personalization"
FLAG_BRIGHTSPACE_LMS = "brightspace_lms"
FLAG_STRIPE_BILLING = "stripe_billing"
FLAG_MCP_TOOLS = "mcp_tools"
FLAG_BETA_FEATURES = "beta_features"

# ─── Simple in-process cache (TTL: 60 seconds) ────────────────────────────────

_CACHE_TTL = 60  # seconds

# Structure: { cache_key: (value, expiry_timestamp) }
_cache: dict[str, tuple[object, float]] = {}


def _cache_get(key: str) -> object:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.monotonic() > expiry:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (value, time.monotonic() + _CACHE_TTL)


def invalidate_cache() -> None:
    """Clear all cached flag evaluations. Call after any flag/override mutation."""
    _cache.clear()


# ─── Rollout bucketing ────────────────────────────────────────────────────────


def _in_rollout(user_id: int, flag_key: str, rollout_percentage: int) -> bool:
    """Return True if the user falls within the rollout bucket."""
    if rollout_percentage >= 100:
        return True
    if rollout_percentage <= 0:
        return False
    # Deterministic hash: consistent for the same (user, flag) pair
    digest = hashlib.md5(f"{user_id}:{flag_key}".encode()).hexdigest()
    bucket = int(digest[:4], 16) % 100
    return bucket < rollout_percentage


# ─── Service ──────────────────────────────────────────────────────────────────


class FeatureFlagService:
    """Evaluate feature flags for a user."""

    def get_flag(self, flag_key: str, db: Session) -> Optional[FeatureFlag]:
        """Return the FeatureFlag record for *flag_key*, or None."""
        return db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()

    def is_enabled(self, flag_key: str, user: User, db: Session) -> bool:
        """
        Evaluate a single feature flag for a user.

        Checks the cache first; falls back to the DB evaluation logic.
        """
        cache_key = f"flag:{flag_key}:user:{user.id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return bool(cached)

        result = self._evaluate(flag_key, user, db)
        _cache_set(cache_key, result)
        return result

    def _evaluate(self, flag_key: str, user: User, db: Session) -> bool:
        """Core evaluation logic (no caching)."""
        # 1. Check per-user override
        override: Optional[UserFeatureOverride] = (
            db.query(UserFeatureOverride)
            .filter(
                UserFeatureOverride.user_id == user.id,
                UserFeatureOverride.flag_key == flag_key,
            )
            .first()
        )
        if override is not None:
            # Respect expiry
            if override.expires_at is not None:
                from datetime import datetime, timezone
                if datetime.now(timezone.utc) > override.expires_at:
                    # Expired override — fall through to flag logic
                    pass
                else:
                    return override.is_enabled
            else:
                return override.is_enabled

        flag = self.get_flag(flag_key, db)
        if flag is None:
            return False

        scope = flag.scope

        # Parse JSON lists
        try:
            enabled_tiers: list[str] = json.loads(flag.enabled_tiers or "[]")
        except Exception:
            enabled_tiers = []
        try:
            enabled_roles: list[str] = json.loads(flag.enabled_roles or "[]")
        except Exception:
            enabled_roles = []
        try:
            enabled_user_ids: list[int] = json.loads(flag.enabled_user_ids or "[]")
        except Exception:
            enabled_user_ids = []

        # 2. Global scope
        if scope == FlagScope.GLOBAL.value:
            if not flag.is_enabled:
                return False
            return _in_rollout(user.id, flag_key, flag.rollout_percentage)

        # 3. Tier scope
        if scope == FlagScope.TIER.value:
            user_tier = (user.subscription_tier or "free").lower()
            return user_tier in [t.lower() for t in enabled_tiers]

        # 4. Role scope
        if scope == FlagScope.ROLE.value:
            user_roles = [r.value.lower() for r in user.get_roles_list()]
            return any(r.lower() in user_roles for r in enabled_roles)

        # 5. User scope
        if scope == FlagScope.USER.value:
            return user.id in enabled_user_ids

        # 6. Beta scope
        if scope == FlagScope.BETA.value:
            return user.id in enabled_user_ids

        # 7. Default
        return flag.is_enabled

    def get_all_flags_for_user(self, user: User, db: Session) -> dict[str, bool]:
        """Return {flag_key: is_enabled} for every flag in the DB for this user."""
        cache_key = f"allflags:user:{user.id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return dict(cached)  # type: ignore[arg-type]

        flags = db.query(FeatureFlag).all()
        result = {flag.key: self._evaluate(flag.key, user, db) for flag in flags}
        _cache_set(cache_key, result)
        return result


# ─── Singleton ────────────────────────────────────────────────────────────────

_service = FeatureFlagService()


def get_feature_flag_service() -> FeatureFlagService:
    return _service


# ─── FastAPI dependency ───────────────────────────────────────────────────────


async def get_feature_flags(
    current_user: User = Depends(lambda: None),  # replaced at import time below
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """
    FastAPI dependency — returns all flags evaluated for the current user.
    Inject into route handlers with:  flags: dict = Depends(get_feature_flags)
    """
    return _service.get_all_flags_for_user(current_user, db)


# Patch the dependency to use the real get_current_user at import time to avoid
# circular imports. We do this lazily via a wrapper instead.
def get_feature_flags_dependency():
    """Return the FastAPI dependency callable (lazy to avoid circular imports)."""
    from app.api.deps import get_current_user

    async def _dep(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> dict[str, bool]:
        return _service.get_all_flags_for_user(current_user, db)

    return _dep
