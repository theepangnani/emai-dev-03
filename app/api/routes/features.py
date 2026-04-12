"""Public feature flags endpoint.

Returns merged dict of config-based flags and DB-backed flags
for authenticated users. The frontend useFeatureToggles() hook
consumes this as {key: boolean}.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User

router = APIRouter(tags=["Features"])


@router.get("/features")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_public_features(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all feature flags as {key: bool} for the current user."""
    from app.models.feature_flag import FeatureFlag

    # Config-based flags (legacy)
    result: dict[str, bool] = {
        "google_classroom": settings.google_classroom_enabled,
        "waitlist_enabled": settings.waitlist_enabled,
    }

    # DB-backed flags
    db_flags = db.query(FeatureFlag).all()
    for flag in db_flags:
        result[flag.key] = flag.enabled

    return result
