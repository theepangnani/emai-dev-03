"""Public feature flags endpoint.

Returns merged dict of config-based flags and DB-backed flags
for authenticated users. The frontend useFeatureToggles() hook
consumes this as {key: boolean}.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user_optional
from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User

router = APIRouter(tags=["Features"])


@router.get("/features")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_public_features(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Return feature flags as {key: bool}.

    Config-based flags are returned for all callers (including
    unauthenticated). DB-backed flags are added when the caller is
    authenticated.  Making this endpoint work without auth prevents the
    login-loop regression described in #3239.
    """
    from app.models.feature_flag import FeatureFlag

    # Config-based flags (always available)
    result: dict[str, bool] = {
        "google_classroom": settings.google_classroom_enabled,
        "waitlist_enabled": settings.waitlist_enabled,
    }

    # DB-backed flags (only when authenticated)
    if current_user is not None:
        db_flags = db.query(FeatureFlag).all()
        for flag in db_flags:
            result[flag.key] = flag.enabled

    return result
