"""Feature-flag read helpers.

Provides `is_feature_enabled(key)` for services and background jobs
to gate behavior on DB-backed feature flags. DB-backed flags live in
the `feature_flags` table (seeded in `feature_seed_service`).

Notes
-----
- Returns ``False`` on any error (missing table, missing row, DB error)
  so callers can treat "unknown/unreachable flag" as "feature OFF".
- Accepts an optional pre-opened `Session`; if none is provided, the
  helper opens and closes its own short-lived session.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

# Flag-key constants — keep in sync with `feature_seed_service.per_key_seeds`.
DCI_V1_ENABLED = "dci_v1_enabled"
CMCP_ENABLED = "cmcp.enabled"


def is_feature_enabled(key: str, db: Optional[Session] = None) -> bool:
    """Return True iff the DB-backed feature flag ``key`` exists and is ON.

    Fails closed on database errors (missing table/column, pool exhausted,
    connection refused) so callers can safely gate new features behind a
    flag during rollout. Programming errors are intentionally NOT swallowed.
    """
    if not key or not key.strip():
        return False

    normalized_key = key.strip()

    owns_session = db is None
    session: Session
    if owns_session:
        try:
            session = SessionLocal()
        except SQLAlchemyError:
            logger.warning(
                "is_feature_enabled('%s') could not open session — defaulting to False",
                normalized_key,
                exc_info=True,
            )
            return False
    else:
        session = db  # type: ignore[assignment]

    try:
        # Lazy import — conftest reloads ``app.models.*`` after this
        # service module is already loaded; a module-top
        # ``from app.models.feature_flag import FeatureFlag`` would pin
        # the pre-reload class against an old registry, causing
        # ``KeyError: 'User'`` cascades on later queries. Per the
        # CLAUDE memory pattern (lazy-import ORM models inside services
        # that catch broadly).
        from app.models.feature_flag import FeatureFlag

        flag = (
            session.query(FeatureFlag)
            .filter(FeatureFlag.key == normalized_key)
            .first()
        )
        if flag is None:
            return False
        return bool(flag.enabled)
    except SQLAlchemyError:
        logger.warning(
            "is_feature_enabled('%s') DB error — defaulting to False",
            normalized_key,
            exc_info=True,
        )
        return False
    finally:
        if owns_session:
            session.close()


def is_dci_enabled(db: Optional[Session] = None) -> bool:
    """Return True iff the `dci_v1_enabled` flag is ON (CB-DCI-001 M0).

    Thin convenience wrapper over :func:`is_feature_enabled` so DCI route
    handlers and frontend gates have a single named entry point. Fails
    closed on DB errors via the underlying helper.
    """
    return is_feature_enabled(DCI_V1_ENABLED, db=db)


def require_cmcp_enabled_no_auth(db: Session) -> None:
    """Auth-free CMCP kill-switch gate (CB-CMCP-001 M3β follow-up #4695).

    Mirrors :func:`app.api.routes.curriculum.require_cmcp_enabled` but
    drops the ``get_current_user`` step. Public LTI launch + any other
    deliberately auth-free CMCP surface route MUST call this *before*
    doing token validation / DB lookups so flipping ``cmcp.enabled``
    OFF actually disables every CMCP entry point — not just the
    authenticated ones.

    Raises
    ------
    HTTPException
        ``status_code=403`` when the flag is OFF, matching the response
        every other CMCP surface emits when the kill-switch fires.
        Raised with a generic detail (``"CB-CMCP-001 is not enabled"``)
        identical to the authed gate so a caller can't pivot off the
        error body to distinguish flag-OFF from flag-ON-bad-sig — the
        LTI launch path uses 401 for any signature/structure failure
        regardless of flag state, so a probing caller learns nothing
        new about flag state from token shape variation.
    """
    # HTTPException is a FastAPI dep — keep the import local so this
    # service module stays usable from non-FastAPI contexts (background
    # jobs, scripts).
    from fastapi import HTTPException

    if not is_feature_enabled(CMCP_ENABLED, db=db):
        raise HTTPException(
            status_code=403, detail="CB-CMCP-001 is not enabled"
        )
