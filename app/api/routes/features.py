"""Public feature flags endpoint.

Returns config-based flags for all callers. Authenticated users
also receive DB-backed flags. The frontend useFeatureToggles() hook
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
    """Return feature flags as {key: bool} plus a `_variants` map.

    The boolean top-level entries are kept for backwards compatibility
    with existing `useFeatureToggles()` consumers. DB-backed flags also
    have their A/B variant exposed under `_variants` (#3601):
    `{ _variants: { flag_key: "off" | "on_50" | "on_for_all" } }`.
    """
    # Config-based flags (always available)
    result: dict = {
        "google_classroom": settings.google_classroom_enabled,
        "waitlist_enabled": settings.waitlist_enabled,
    }
    variants: dict[str, str] = {}

    # DB-backed flags (require authentication)
    if current_user is not None:
        from app.models.feature_flag import FeatureFlag

        db_flags = db.query(FeatureFlag).all()
        for flag in db_flags:
            result[flag.key] = flag.enabled
            variants[flag.key] = getattr(flag, "variant", None) or "off"

    result["_variants"] = variants
    return result
