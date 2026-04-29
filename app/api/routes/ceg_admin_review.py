"""CB-CMCP-001 M0-B 0B-3a — Curriculum-admin review backend (#4428).

Backend endpoints used by the OCT-certified curriculum reviewer (locked
decision D5=B) to **accept**, **reject**, or **edit** pending CEG
expectations that the 0B-2 extractor wrote into ``ceg_expectations`` with
``review_state='pending'`` and ``active=False``.

Endpoints (all under ``/api/ceg/admin/review/*``)
-------------------------------------------------
- ``GET    /pending``                          — list pending expectations
- ``POST   /{expectation_id}/accept``          — set ``review_state='accepted'`` + ``active=True``
- ``POST   /{expectation_id}/reject``          — set ``review_state='rejected'`` + ``active=False``
- ``PATCH  /{expectation_id}``                 — edit reviewable fields

Auth + RBAC
-----------
Every endpoint composes two gates:

1. ``require_role(UserRole.CURRICULUM_ADMIN)`` — reject anyone else with 403.
2. ``cmcp.enabled`` feature flag — when OFF, 403 short-circuits before any DB
   work. Default OFF; toggled via the same flag every other CB-CMCP-001
   stripe uses (``app.services.feature_flag_service.CMCP_ENABLED``).

Audit log
---------
Every accept / reject / edit writes one row to ``audit_logs`` via
``app.services.audit_service.log_action``. We do NOT invent a new log table;
the existing service already wraps inserts in a SAVEPOINT so a failed audit
write cannot corrupt the caller's transaction (CLAUDE.md MFIPPA rule).

Schema decisions
----------------
The model picked up four new review columns in this stripe (also #4428):

- ``review_state``       VARCHAR(20)  ('pending' | 'accepted' | 'rejected')
- ``reviewed_by_user_id`` FK users.id (SET NULL on user delete)
- ``reviewed_at``         TIMESTAMPTZ / DATETIME
- ``review_notes``        TEXT

Legacy / seeded rows default to ``review_state='accepted'`` so they are not
surfaced as pending. The 0B-2 extractor inserts new rows with
``review_state='pending'`` + ``active=False``.

No frontend code lives here — stripe 0B-3b owns the ``/admin/ceg/review``
page.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.database import get_db
from app.models.curriculum import (
    EXPECTATION_TYPE_OVERALL,
    EXPECTATION_TYPE_VALUES,
    CEGExpectation,
)
from app.models.user import User, UserRole
from app.services.audit_service import log_action
from app.services.feature_flag_service import CMCP_ENABLED, is_feature_enabled

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ceg/admin/review",
    tags=["CMCP CEG Admin Review"],
)


# ---------------------------------------------------------------------------
# review_state values (single source of truth — match the model CHECK
# constraint). Centralising avoids drift between the route validator and
# the DB constraint.
# ---------------------------------------------------------------------------

REVIEW_STATE_PENDING = "pending"
REVIEW_STATE_ACCEPTED = "accepted"
REVIEW_STATE_REJECTED = "rejected"

AUDIT_RESOURCE_TYPE = "ceg_expectation"
AUDIT_ACTION_ACCEPT = "ceg_review_accept"
AUDIT_ACTION_REJECT = "ceg_review_reject"
AUDIT_ACTION_EDIT = "ceg_review_edit"


# ---------------------------------------------------------------------------
# Combined CMCP-flag + CURRICULUM_ADMIN dependency
# ---------------------------------------------------------------------------


def require_curriculum_admin_with_flag(
    current_user: User = Depends(require_role(UserRole.CURRICULUM_ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    """Compose RBAC + feature-flag gating in one dependency.

    ``require_role`` runs first (its own ``Depends(get_current_user)`` resolves
    ahead of this body), so an unauth request always sees 401, a non-admin
    user always sees 403 ("Insufficient permissions"), and only an authed
    CURRICULUM_ADMIN reaches the flag check. Flag-OFF returns 403 with a
    ``CB-CMCP-001`` detail so the response is distinguishable from a
    role-mismatch 403 in logs / tests.
    """
    if not is_feature_enabled(CMCP_ENABLED, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CB-CMCP-001 is not enabled",
        )
    return current_user


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PendingExpectationResponse(BaseModel):
    """Read shape returned by ``GET /pending`` and the action endpoints."""

    id: int
    ministry_code: str
    cb_code: Optional[str] = None
    subject_id: int
    strand_id: int
    grade: int
    expectation_type: str
    parent_oe_id: Optional[int] = None
    description: str
    curriculum_version_id: int
    active: bool
    review_state: str
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RejectExpectationRequest(BaseModel):
    """Optional rejection notes captured for the audit trail."""

    review_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description=(
            "Free-text rejection reason. Stored on the row and copied "
            "into the audit-log details."
        ),
    )


class EditExpectationRequest(BaseModel):
    """Writable fields the curriculum admin may edit on review.

    All fields are optional — the route applies only those the caller sets.
    Unknown keys are rejected (``extra='forbid'``) to avoid silent drops:
    a reviewer who PATCHes a typo'd field name should get a 422, not a
    200 with the field silently ignored. This is the MFIPPA / curriculum-
    accuracy posture for this product (no silent drops, no silent
    overrides).

    The list is intentionally narrow (per #4428 scope): description
    paraphrase, ministry_code, strand_id, expectation_type, parent_oe_id,
    review_notes. ``topic`` is NOT in this schema — re-add it the day a
    ``topic`` column lands on ``ceg_expectations``.
    """

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    ministry_code: Optional[str] = Field(default=None, min_length=1, max_length=40)
    strand_id: Optional[int] = Field(default=None, gt=0)
    expectation_type: Optional[str] = Field(default=None)
    parent_oe_id: Optional[int] = Field(default=None, gt=0)
    review_notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("expectation_type")
    @classmethod
    def _check_expectation_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in EXPECTATION_TYPE_VALUES:
            raise ValueError(
                "expectation_type must be one of "
                f"{', '.join(EXPECTATION_TYPE_VALUES)}"
            )
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_expectation_or_404(
    db: Session, expectation_id: int
) -> CEGExpectation:
    """Look up an expectation by id or raise 404 with a stable detail."""
    expectation = (
        db.query(CEGExpectation)
        .filter(CEGExpectation.id == expectation_id)
        .first()
    )
    if expectation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CEG expectation {expectation_id} not found",
        )
    return expectation


def _client_ip(request: Request) -> Optional[str]:
    """Return the client IP for audit logging (best-effort)."""
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# GET /pending — list pending expectations
# ---------------------------------------------------------------------------


@router.get("/pending", response_model=list[PendingExpectationResponse])
def list_pending_expectations(
    _current_user: User = Depends(require_curriculum_admin_with_flag),
    db: Session = Depends(get_db),
):
    """Return all CEG expectations awaiting review.

    Pending = ``review_state='pending'``. Ordered by ``created_at`` (oldest
    first) so the reviewer naturally works the queue from the top down.
    """
    rows = (
        db.query(CEGExpectation)
        .filter(CEGExpectation.review_state == REVIEW_STATE_PENDING)
        .order_by(CEGExpectation.created_at.asc(), CEGExpectation.id.asc())
        .all()
    )
    return rows


# ---------------------------------------------------------------------------
# POST /{expectation_id}/accept
# ---------------------------------------------------------------------------


@router.post(
    "/{expectation_id}/accept",
    response_model=PendingExpectationResponse,
)
def accept_expectation(
    expectation_id: int,
    request: Request,
    current_user: User = Depends(require_curriculum_admin_with_flag),
    db: Session = Depends(get_db),
):
    """Accept a pending expectation: set ``active=True`` + ``review_state='accepted'``.

    Stamps ``reviewed_by_user_id`` and ``reviewed_at``. Writes one
    ``ceg_review_accept`` audit-log row.
    """
    expectation = _get_expectation_or_404(db, expectation_id)

    expectation.review_state = REVIEW_STATE_ACCEPTED
    expectation.active = True
    expectation.reviewed_by_user_id = current_user.id
    expectation.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db,
        user_id=current_user.id,
        action=AUDIT_ACTION_ACCEPT,
        resource_type=AUDIT_RESOURCE_TYPE,
        resource_id=expectation.id,
        details={
            "ministry_code": expectation.ministry_code,
            "curriculum_version_id": expectation.curriculum_version_id,
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(expectation)
    return expectation


# ---------------------------------------------------------------------------
# POST /{expectation_id}/reject
# ---------------------------------------------------------------------------


@router.post(
    "/{expectation_id}/reject",
    response_model=PendingExpectationResponse,
)
def reject_expectation(
    expectation_id: int,
    request: Request,
    payload: Optional[RejectExpectationRequest] = None,
    current_user: User = Depends(require_curriculum_admin_with_flag),
    db: Session = Depends(get_db),
):
    """Reject a pending expectation: keep ``active=False`` + set ``review_state='rejected'``.

    Optional ``review_notes`` is persisted on the row and echoed into the
    audit-log details (the audit row is the durable record; the column is a
    convenience for the review UI).
    """
    expectation = _get_expectation_or_404(db, expectation_id)

    notes = payload.review_notes if payload else None

    expectation.review_state = REVIEW_STATE_REJECTED
    expectation.active = False
    expectation.reviewed_by_user_id = current_user.id
    expectation.reviewed_at = datetime.now(timezone.utc)
    if notes is not None:
        expectation.review_notes = notes

    log_action(
        db,
        user_id=current_user.id,
        action=AUDIT_ACTION_REJECT,
        resource_type=AUDIT_RESOURCE_TYPE,
        resource_id=expectation.id,
        details={
            "ministry_code": expectation.ministry_code,
            "curriculum_version_id": expectation.curriculum_version_id,
            "review_notes": notes,
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(expectation)
    return expectation


# ---------------------------------------------------------------------------
# PATCH /{expectation_id} — edit reviewable fields
# ---------------------------------------------------------------------------


# Whitelist of editable column names on CEGExpectation. Must mirror
# the ``EditExpectationRequest`` schema — drift between the two would be
# a no-op silent drop, which the schema's ``extra='forbid'`` is meant to
# prevent at the API boundary. ``review_notes`` is editable so the
# reviewer can attach notes during a paraphrase pass without having to
# call /reject.
_EDITABLE_FIELDS = {
    "description",
    "ministry_code",
    "strand_id",
    "expectation_type",
    "parent_oe_id",
    "review_notes",
}


@router.patch(
    "/{expectation_id}",
    response_model=PendingExpectationResponse,
)
def edit_expectation(
    expectation_id: int,
    payload: EditExpectationRequest,
    request: Request,
    current_user: User = Depends(require_curriculum_admin_with_flag),
    db: Session = Depends(get_db),
):
    """Edit reviewable fields on an expectation. Idempotent; partial updates."""
    expectation = _get_expectation_or_404(db, expectation_id)

    # Pydantic v2: ``model_dump(exclude_unset=True)`` returns only fields
    # the caller actually set, so we don't clobber unrelated columns.
    incoming = payload.model_dump(exclude_unset=True)

    if not incoming:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one editable field must be provided",
        )

    # Validate parent_oe_id (DD §2.1 invariant: SE → OE only, same version,
    # no self-loop). The DB-level FK only checks existence, not the type /
    # version / self-loop invariants — a reviewer fat-fingering an id can
    # corrupt the SE→OE tree silently. Catch it at the API layer.
    if "parent_oe_id" in incoming and incoming["parent_oe_id"] is not None:
        new_parent_id = incoming["parent_oe_id"]
        if new_parent_id == expectation.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_oe_id cannot reference the row itself",
            )
        parent = (
            db.query(CEGExpectation)
            .filter(CEGExpectation.id == new_parent_id)
            .first()
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"parent_oe_id {new_parent_id} does not exist",
            )
        if parent.expectation_type != EXPECTATION_TYPE_OVERALL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_oe_id must point to an 'overall' expectation",
            )
        if parent.curriculum_version_id != expectation.curriculum_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_oe_id must be in the same curriculum_version",
            )

    # Capture before/after diff for the audit row. Only fields actually
    # changing the persisted value are recorded. Values are stringified
    # so non-JSON-native types (e.g., a future datetime column) cannot
    # silently break the audit-log JSON encode (Bill 194 silent-fail
    # guard, see #4249).
    diff: dict[str, dict[str, object]] = {}
    for field, new_value in incoming.items():
        if field not in _EDITABLE_FIELDS:
            # Defensive — the Pydantic ``extra='forbid'`` config rejects
            # unknown fields before we get here, so this is unreachable
            # in normal operation. Kept as a belt-and-suspenders guard
            # for the case where the schema and whitelist diverge in
            # future edits.
            continue
        old_value = getattr(expectation, field, None)
        if old_value == new_value:
            continue
        setattr(expectation, field, new_value)
        diff[field] = {
            "old": str(old_value) if old_value is not None else None,
            "new": str(new_value) if new_value is not None else None,
        }

    if not diff:
        # Nothing actually changed — skip the audit-log write entirely.
        # Return the current row as a no-op.
        return expectation

    expectation.reviewed_by_user_id = current_user.id
    expectation.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db,
        user_id=current_user.id,
        action=AUDIT_ACTION_EDIT,
        resource_type=AUDIT_RESOURCE_TYPE,
        resource_id=expectation.id,
        details={
            "ministry_code": expectation.ministry_code,
            "curriculum_version_id": expectation.curriculum_version_id,
            "changes": diff,
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(expectation)
    return expectation
