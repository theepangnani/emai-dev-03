"""CB-DCI-001 M0-11 — DCI consent endpoints.

Routes:
- ``POST /api/dci/consent`` — upsert consent for a (parent, kid) pair
- ``GET /api/dci/consent/{kid_id}`` — read current consent state
- ``GET /api/dci/consent`` — list consent for all linked kids (used by Settings)

All endpoints require an authenticated PARENT user.
Spec: docs/design/CB-DCI-001-daily-checkin.md § 11.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.services.dci_consent_service import (
    ALLOWED_RETENTION_DAYS,
    ConsentSnapshot,
    get_consent,
    upsert_consent,
)

router = APIRouter(prefix="/dci/consent", tags=["DCI"])


# ── Schemas ────────────────────────────────────────────────────


class ConsentUpdate(BaseModel):
    """Body for ``POST /api/dci/consent``.

    Any field omitted = leave unchanged. ``kid_id`` is required.
    """

    kid_id: int = Field(..., gt=0)
    photo_ok: Optional[bool] = None
    voice_ok: Optional[bool] = None
    ai_ok: Optional[bool] = None
    retention_days: Optional[int] = Field(None, description="One of 90, 365, 1095")
    dci_enabled: Optional[bool] = None
    muted: Optional[bool] = None
    kid_push_time: Optional[str] = Field(None, description="HH:MM 24h, e.g. 15:15")
    parent_push_time: Optional[str] = Field(None, description="HH:MM 24h, e.g. 19:00")


class ConsentResponse(BaseModel):
    parent_id: int
    kid_id: int
    photo_ok: bool
    voice_ok: bool
    ai_ok: bool
    retention_days: int
    dci_enabled: bool
    muted: bool
    kid_push_time: str
    parent_push_time: str
    allowed_retention_days: list[int] = Field(default_factory=lambda: list(ALLOWED_RETENTION_DAYS))


class ConsentListResponse(BaseModel):
    items: list[ConsentResponse]


def _to_response(snapshot: ConsentSnapshot) -> ConsentResponse:
    return ConsentResponse(
        parent_id=snapshot.parent_id,
        kid_id=snapshot.kid_id,
        photo_ok=snapshot.photo_ok,
        voice_ok=snapshot.voice_ok,
        ai_ok=snapshot.ai_ok,
        retention_days=snapshot.retention_days,
        dci_enabled=snapshot.dci_enabled,
        muted=snapshot.muted,
        kid_push_time=snapshot.kid_push_time,
        parent_push_time=snapshot.parent_push_time,
    )


# ── Endpoints ──────────────────────────────────────────────────


@router.get("", response_model=ConsentListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_consent(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> ConsentListResponse:
    """Return consent snapshots for every kid linked to the parent."""
    rows = (
        db.query(Student.id)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    )
    items: list[ConsentResponse] = []
    for (kid_id,) in rows:
        snapshot = get_consent(db, parent_id=current_user.id, kid_id=kid_id)
        items.append(_to_response(snapshot))
    return ConsentListResponse(items=items)


@router.get("/{kid_id}", response_model=ConsentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_consent_for_kid(
    request: Request,
    kid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> ConsentResponse:
    snapshot = get_consent(db, parent_id=current_user.id, kid_id=kid_id)
    return _to_response(snapshot)


@router.post("", response_model=ConsentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def post_consent(
    request: Request,
    body: ConsentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> ConsentResponse:
    snapshot = upsert_consent(
        db,
        parent_id=current_user.id,
        kid_id=body.kid_id,
        photo_ok=body.photo_ok,
        voice_ok=body.voice_ok,
        ai_ok=body.ai_ok,
        retention_days=body.retention_days,
        dci_enabled=body.dci_enabled,
        muted=body.muted,
        kid_push_time=body.kid_push_time,
        parent_push_time=body.parent_push_time,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return _to_response(snapshot)
