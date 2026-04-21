"""Demo verification routes (CB-DEMO-001 B2, #3604).

Three public endpoints for demo-session verification and waitlist
promotion (PRD FR-042/FR-043):

* ``GET /api/v1/demo/verify?token=...`` — consume a magic link.
* ``POST /api/v1/demo/verify/code`` — consume a 6-digit fallback code.

Both paths share the same post-verify logic: auto-approve the session
for admin review unless an IP-hash anomaly is detected (≥3 distinct
emails from the same hashed source IP in the last 24h), in which case
the session stays in ``admin_status='pending'`` for manual review and a
WARN log is emitted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.demo_session import DemoSession
from app.services.demo_verification import (
    verify_fallback_code,
    verify_magic_link,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo-verify"])


_ANOMALY_THRESHOLD = 3
_ANOMALY_WINDOW_HOURS = 24


def _base_url() -> str:
    return getattr(settings, "app_base_url", "https://www.classbridge.ca")


def _is_anomalous(db: Session, source_ip_hash: str | None) -> bool:
    """Return True if the hashed source IP has seen >=3 distinct emails in 24h."""
    if not source_ip_hash:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_ANOMALY_WINDOW_HOURS)
    distinct_emails = (
        db.query(func.count(func.distinct(DemoSession.email)))
        .filter(DemoSession.source_ip_hash == source_ip_hash)
        .filter(DemoSession.created_at >= cutoff)
        .scalar()
    )
    return (distinct_emails or 0) >= _ANOMALY_THRESHOLD


def _waitlist_position(db: Session, session: DemoSession) -> int:
    """Rank by verification timestamp — position among all verified demos."""
    ts = session.verified_ts
    if ts is None:
        # Defensive: service should have set verified_ts already.
        return 0
    position = (
        db.query(func.count(DemoSession.id))
        .filter(DemoSession.verified.is_(True))
        .filter(DemoSession.verified_ts <= ts)
        .scalar()
    )
    return int(position or 0)


def _apply_post_verify(db: Session, session: DemoSession) -> tuple[int, bool]:
    """Apply anomaly check + auto-approve, commit, return (position, flagged)."""
    flagged = _is_anomalous(db, session.source_ip_hash)
    if flagged:
        # Leave admin_status='pending' for manual review.
        logger.warning(
            "demo_verify: anomaly flagged — session left pending | session_id=%s",
            session.id,
        )
    else:
        session.admin_status = "approved"

    position = _waitlist_position(db, session)
    db.commit()
    db.refresh(session)
    return position, flagged


@router.get("/verify")
def verify_magic_link_route(
    token: str = "",
    db: Session = Depends(get_db),
):
    """Consume a magic-link token and redirect to the frontend (FR-042/043)."""
    base = _base_url()
    session = verify_magic_link(db, token)
    if session is None:
        return RedirectResponse(
            url=f"{base}/demo/verify-failed", status_code=302
        )

    position, _flagged = _apply_post_verify(db, session)
    return RedirectResponse(
        url=f"{base}/demo/verified?pos={position}", status_code=302
    )


class VerifyCodePayload(BaseModel):
    email: EmailStr
    # Enforce exactly 6 digits at validation time (#3655).
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/verify/code")
def verify_code_route(
    payload: VerifyCodePayload,
    db: Session = Depends(get_db),
):
    """Consume a 6-digit fallback code (FR-042)."""
    session = verify_fallback_code(db, payload.email, payload.code)
    if session is None:
        raise HTTPException(status_code=400, detail={"error": "invalid_code"})

    position, flagged = _apply_post_verify(db, session)
    return {
        "verified": True,
        "waitlist_position": position,
        "anomaly_flagged": flagged,
    }
