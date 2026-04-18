"""Public (unauthenticated) routes (CB-DEMO-001 B2, #3604).

Currently exposes ``GET /api/v1/public/waitlist-stats`` — a cached
privacy-preserving view of waitlist size for the marketing site
(FR-101/104/105/106).
"""
from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.waitlist import Waitlist

router = APIRouter(prefix="/public", tags=["public"])


# FR-106 — hide total until we pass the visibility threshold.
_MIN_TOTAL_FOR_DISPLAY = 50

# FR-105 — cache responses for ~1h to absorb traffic spikes.
_CACHE_TTL_SECONDS = 3600

# (value, expires_at) tuple, protected by a lock so concurrent workers
# don't race on the initial fetch.
_cache: dict[str, Any] = {"value": None, "expires_at": 0.0}
_cache_lock = threading.Lock()


def _clear_cache_for_tests() -> None:
    """Reset the waitlist-stats cache. For use by tests only."""
    with _cache_lock:
        _cache["value"] = None
        _cache["expires_at"] = 0.0


def _compute_stats(db: Session) -> dict[str, Any]:
    total = db.query(Waitlist).count()

    # FR-104 — top 20 municipalities.
    # DEVIATION: the current ``Waitlist`` model exposes no location
    # column (name/email/roles/status/admin_notes/invite_token/... only).
    # Until a city/region/municipality field is added we return an empty
    # list so the response shape stays stable for the frontend.
    by_municipality: list[dict[str, Any]] = []

    # FR-106 — suppress total until it reaches the display threshold,
    # but keep the (possibly empty) municipality array.
    display_total: int | None = total if total >= _MIN_TOTAL_FOR_DISPLAY else None

    return {"total": display_total, "by_municipality": by_municipality}


@router.get("/waitlist-stats")
def waitlist_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Public, cached waitlist statistics (FR-101/104/105/106)."""
    now = time.monotonic()
    with _cache_lock:
        cached_value = _cache["value"]
        expires_at = _cache["expires_at"]
        if cached_value is not None and now < expires_at:
            return cached_value

    # Compute outside the lock (DB I/O); last writer wins.
    stats = _compute_stats(db)
    with _cache_lock:
        _cache["value"] = stats
        _cache["expires_at"] = time.monotonic() + _CACHE_TTL_SECONDS
    return stats
