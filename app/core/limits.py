"""
Per-user limit resolution based on subscription tier (#1007).

Usage:
    from app.core.limits import get_limits
    limits = get_limits(current_user)
"""
from app.core.config import settings


def get_limits(user) -> dict:
    """Return the applicable upload/generation limits for *user* based on their subscription tier.

    Returns a dict with keys:
        max_upload_size_mb  — per-file upload ceiling in megabytes
        max_session_files   — max files per upload session
        max_study_guides    — max study guides the user may own
    """
    if getattr(user, "subscription_tier", "free") == "premium":
        return {
            "max_upload_size_mb": settings.PREMIUM_MAX_UPLOAD_SIZE_MB,
            "max_session_files": settings.PREMIUM_MAX_SESSION_FILES,
            "max_study_guides": settings.PREMIUM_MAX_STUDY_GUIDES,
        }
    return {
        "max_upload_size_mb": settings.FREE_MAX_UPLOAD_SIZE_MB,
        "max_session_files": settings.FREE_MAX_SESSION_FILES,
        "max_study_guides": settings.FREE_MAX_STUDY_GUIDES,
    }
