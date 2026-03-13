"""
AI usage limit enforcement helpers.

Provides check_ai_usage() and increment_ai_usage() to enforce per-user
AI credit limits across all generation paths.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.user import User

logger = get_logger(__name__)


def check_ai_usage(user: User, db: Session) -> None:
    """Check if user has remaining AI credits. Raises 429 if at limit.

    If ai_usage_limit is 0 or None, the user is treated as having
    unlimited credits (e.g. admin users or before migration runs).
    """
    limit = getattr(user, "ai_usage_limit", None)
    count = getattr(user, "ai_usage_count", None)

    # Treat NULL / 0 limit as unlimited (admin users, pre-migration rows)
    if not limit:
        return

    if count is None:
        count = 0

    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"AI usage limit reached. You have used all {limit} of your "
                f"AI credits. Request more from the admin panel."
            ),
        )


def log_ai_usage(
    user: User,
    db: Session,
    generation_type: str,
    course_material_id: int | None = None,
    credits_used: int = 1,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    model_name: str | None = None,
    is_regeneration: bool = False,
    parent_generation_id: int | None = None,
) -> None:
    """Insert a row into ai_usage_history for audit trail."""
    from app.models.ai_usage_history import AIUsageHistory

    entry = AIUsageHistory(
        user_id=user.id,
        generation_type=generation_type,
        course_material_id=course_material_id,
        credits_used=credits_used,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model_name=model_name,
        is_regeneration=is_regeneration,
        parent_generation_id=parent_generation_id,
    )
    db.add(entry)
    logger.debug(
        "AI usage history logged | user_id=%s | type=%s | material=%s | regen=%s | tokens=%s | cost=$%.6f",
        user.id, generation_type, course_material_id, is_regeneration,
        total_tokens, estimated_cost_usd or 0,
    )


def increment_ai_usage(
    user: User,
    db: Session,
    generation_type: str = "unknown",
    course_material_id: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    model_name: str | None = None,
    is_regeneration: bool = False,
    parent_generation_id: int | None = None,
) -> None:
    """Increment user's AI usage count after successful generation.

    Also logs an entry to ai_usage_history for the audit trail.
    """
    log_ai_usage(
        user, db, generation_type, course_material_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model_name=model_name,
        is_regeneration=is_regeneration,
        parent_generation_id=parent_generation_id,
    )

    limit = getattr(user, "ai_usage_limit", None)

    # Only track count if limits are active (non-zero, non-null)
    if not limit:
        db.commit()
        return

    current = getattr(user, "ai_usage_count", None) or 0
    user.ai_usage_count = current + 1
    db.commit()
    logger.info(
        "AI usage incremented | user_id=%s | count=%s/%s",
        user.id, user.ai_usage_count, user.ai_usage_limit,
    )
