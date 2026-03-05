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


def increment_ai_usage(user: User, db: Session) -> None:
    """Increment user's AI usage count after successful generation."""
    limit = getattr(user, "ai_usage_limit", None)

    # Only track if limits are active (non-zero, non-null)
    if not limit:
        return

    current = getattr(user, "ai_usage_count", None) or 0
    user.ai_usage_count = current + 1
    db.commit()
    logger.info(
        "AI usage incremented | user_id=%s | count=%s/%s",
        user.id, user.ai_usage_count, user.ai_usage_limit,
    )
