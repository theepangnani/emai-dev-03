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

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.feature_flag import FeatureFlag

logger = logging.getLogger(__name__)


def is_feature_enabled(key: str, db: Optional[Session] = None) -> bool:
    """Return True iff the DB-backed feature flag ``key`` exists and is ON.

    Fails closed — any exception (missing table/column/row) yields False
    so callers can safely gate new features behind a flag during rollout.
    """
    if not key:
        return False

    owns_session = db is None
    session = db or SessionLocal()
    try:
        flag = (
            session.query(FeatureFlag)
            .filter(FeatureFlag.key == key)
            .first()
        )
        if flag is None:
            return False
        return bool(flag.enabled)
    except Exception:
        logger.warning("is_feature_enabled('%s') failed — defaulting to False", key)
        return False
    finally:
        if owns_session:
            session.close()
