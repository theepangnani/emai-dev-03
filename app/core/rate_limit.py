"""Rate limiting configuration using slowapi."""

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind Cloud Run proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def get_user_id_or_ip(request: Request) -> str:
    """Use authenticated user ID if available, otherwise fall back to IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_client_ip(request)


def _create_limiter() -> Limiter:
    """Create rate limiter, falling back to memory if Redis is unavailable."""
    storage_url = settings.rate_limit_storage_url
    if storage_url and storage_url != "memory://":
        try:
            limiter = Limiter(
                key_func=get_client_ip,
                default_limits=[],
                storage_uri=storage_url,
            )
            logger.info("Rate limiter using storage: %s", storage_url.split("@")[-1])
            return limiter
        except Exception:
            logger.warning(
                "Failed to connect to rate limit storage %s, falling back to memory",
                storage_url.split("@")[-1],
                exc_info=True,
            )

    limiter = Limiter(
        key_func=get_client_ip,
        default_limits=[],
        storage_uri="memory://",
    )
    logger.info("Rate limiter using in-memory storage")
    return limiter


limiter = _create_limiter()
