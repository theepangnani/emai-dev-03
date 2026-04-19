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


# DB-backed flags whose variant must be exposed to unauthenticated callers
# because they gate public-facing UX (e.g., the CB-DEMO-001 landing-page
# A/B wedge is only rendered to unauthenticated visitors). Other DB-backed
# flags remain authenticated-only (#3715).
_PUBLIC_DB_FLAGS: frozenset[str] = frozenset({"demo_landing_v1_1"})


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

    Authenticated callers receive every DB-backed flag. Unauthenticated
    callers only receive flags listed in `_PUBLIC_DB_FLAGS` — this is
    required because the CB-DEMO-001 landing-page A/B is gated by the
    flag's variant but the landing page is only rendered to
    unauthenticated visitors (#3715).
    """
    # Config-based flags (always available)
    result: dict = {
        "google_classroom": settings.google_classroom_enabled,
        "waitlist_enabled": settings.waitlist_enabled,
    }
    variants: dict[str, str] = {}

    from app.models.feature_flag import FeatureFlag

    if current_user is not None:
        db_flags = db.query(FeatureFlag).all()
    else:
        db_flags = (
            db.query(FeatureFlag)
            .filter(FeatureFlag.key.in_(_PUBLIC_DB_FLAGS))
            .all()
        )

    for flag in db_flags:
        result[flag.key] = flag.enabled
        variants[flag.key] = getattr(flag, "variant", None) or "off"

    result["_variants"] = variants
    return result
