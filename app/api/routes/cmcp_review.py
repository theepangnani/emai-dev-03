"""CB-CMCP-001 M3-A 3A-1 (#4576) — Teacher Review Queue backend.

Six endpoints under ``/api/cmcp/review/*`` that drive the teacher review
flow over CMCP-generated artifacts persisted in ``study_guides``:

- ``GET    /api/cmcp/review/queue``               — list PENDING_REVIEW
- ``GET    /api/cmcp/review/{artifact_id}``       — full artifact + metadata
- ``PATCH  /api/cmcp/review/{artifact_id}``       — apply edit delta + log
- ``POST   /api/cmcp/review/{artifact_id}/approve``    — PENDING_REVIEW → APPROVED
- ``POST   /api/cmcp/review/{artifact_id}/reject``     — → REJECTED (reason required)
- ``POST   /api/cmcp/review/{artifact_id}/regenerate`` — re-run prompt build,
  replace content, keep state=PENDING_REVIEW + same id

Role gating
-----------
Allowed roles: ``TEACHER``, ``ADMIN``. ``CURRICULUM_ADMIN`` is intentionally
NOT allowed here — curriculum admins manage CEG/curriculum, not the
class-level review queue. Per-row visibility for TEACHER is "own classes
only" (artifact created by the teacher OR pinned to a course where the
teacher is the assigned teacher / course creator). ADMIN sees everything.

Visibility deny → 404 (not 403) on the GET / PATCH / POST surface to
match the public-REST "no existence oracle" convention used by
``GET /api/cmcp/artifacts/{id}/parent-companion`` (Wave 0 #4575).

State-machine note
------------------
The review queue ships its own narrow transitions on top of the M1
``ArtifactStateMachine`` graph (``app/services/cmcp/artifact_state.py``).
The graph models ``PENDING_REVIEW → IN_REVIEW → APPROVED/REJECTED`` —
this stripe collapses approve/reject into a single hop from
``PENDING_REVIEW`` (per the issue's plain-language transitions) so the
frontend doesn't need a no-op "open" call before a verdict. The
``IN_REVIEW`` transient is therefore not used by the review-queue REST
surface; it's reserved for any future surface that needs an "I'm
looking at this" claim signal.

Out of scope (deferred)
-----------------------
- Frontend (3A-2 stripe — list view + edit page).
- SE-tag editor (3A-3).
- Surface dispatcher fan-out on approve (3C-1).
- Tasks emit on approve (3D-1).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.routes.cmcp_generate import generate_cmcp_preview_sync
from app.api.routes.curriculum import require_cmcp_enabled
from app.db.database import get_db
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.schemas.cmcp import CMCPGenerateRequest
from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cmcp/review", tags=["CMCP Review Queue"])


# ---------------------------------------------------------------------------
# Role gate
# ---------------------------------------------------------------------------


def _require_review_role(
    current_user: User = Depends(require_cmcp_enabled),
) -> User:
    """403 unless the caller is TEACHER or ADMIN.

    Layered on top of ``require_cmcp_enabled`` so unauth → 401, flag-off
    → 403, and not-allowlisted-role → 403. Keeps the gating semantics
    aligned with the rest of the CMCP REST surface.
    """
    if not (
        current_user.has_role(UserRole.TEACHER)
        or current_user.has_role(UserRole.ADMIN)
    ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions for CMCP review queue",
        )
    return current_user


# ---------------------------------------------------------------------------
# Visibility helper — "TEACHER own classes only", ADMIN sees everything
# ---------------------------------------------------------------------------


def _teacher_owned_course_ids(db: Session, user: User) -> list[int]:
    """Return the course ids a TEACHER owns (assigned + creator).

    Matches ``app/mcp/tools/list_catalog.py``'s TEACHER scope:
    course is owned when ``courses.created_by_user_id == user.id`` OR
    ``courses.teacher_id`` resolves through ``teachers.user_id == user.id``.
    """
    from sqlalchemy import select

    from app.models.course import Course
    from app.models.teacher import Teacher

    teacher_pk_select = (
        select(Teacher.id).where(Teacher.user_id == user.id)
    )
    rows = (
        db.query(Course.id)
        .filter(
            (Course.created_by_user_id == user.id)
            | (Course.teacher_id.in_(teacher_pk_select))
        )
        .all()
    )
    return [r[0] for r in rows]


def _user_can_review(artifact: StudyGuide, user: User, db: Session) -> bool:
    """Visibility check for the review queue.

    ADMIN → True (catch-all).
    TEACHER → True when the artifact is creator-owned OR pinned to a
    course the teacher owns (assigned + course creator). ``course_id``
    being None on the artifact denies TEACHER access via the course
    branch — only the creator-owned branch covers it. This matches the
    issue's "TEACHER only their classes" wording and is consistent with
    M2-B's row-level visibility for TEACHERs (``_user_can_view``).
    Other roles → False (the route layer 403s before reaching here, but
    keep the defence-in-depth).

    SELF_STUDY denial (3B-3 / #4585): the review queue is for
    PENDING_REVIEW class-distributable artifacts — SELF_STUDY rows are
    private learner workspace and never enter the review pipeline. We
    deny here as defence-in-depth even for ADMIN so a stray
    PATCH/approve/reject targeted at a SELF_STUDY artifact (e.g. via a
    direct id guess) cannot mutate state. The list endpoint already
    filters ``state == PENDING_REVIEW`` so SELF_STUDY rows never
    surface in the queue itself; this guards the by-id endpoints.
    """
    if artifact.state == ArtifactState.SELF_STUDY:
        return False

    if user.has_role(UserRole.ADMIN):
        return True

    if user.has_role(UserRole.TEACHER):
        if artifact.user_id == user.id:
            return True
        if artifact.course_id is None:
            return False
        owned = _teacher_owned_course_ids(db, user)
        return artifact.course_id in owned

    return False


def _load_review_artifact(
    artifact_id: int, user: User, db: Session
) -> StudyGuide:
    """Load a study_guides row for review or raise 404.

    Collapses "no row" + "no access" to the same 404 — the public REST
    surface deliberately does not differentiate, mirroring
    ``GET /api/cmcp/artifacts/{id}/parent-companion``.
    """
    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
    )
    if artifact is None:
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )
    if not _user_can_review(artifact, user, db):
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )
    return artifact


# ---------------------------------------------------------------------------
# Response / request schemas
# ---------------------------------------------------------------------------


_SortField = Literal["created_at", "content_type", "subject"]


# States in which the review queue allows mutating the artifact (PATCH +
# regenerate). APPROVED / APPROVED_VERIFIED / ARCHIVED are intentionally
# excluded — those are downstream-consumed by surface stripes (parent
# companion fetch, dispatcher fan-out, Tasks emit) and silent body
# mutation would break the audit + consumption invariants.
_MUTABLE_REVIEW_STATES: frozenset[str] = frozenset(
    {
        ArtifactState.PENDING_REVIEW,
        ArtifactState.REJECTED,
        ArtifactState.DRAFT,
    }
)


class ReviewQueueItem(BaseModel):
    """Compact row shape for the review-queue list endpoint."""

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    guide_type: str
    state: str
    course_id: int | None = None
    user_id: int
    se_codes: list[str] = Field(default_factory=list)
    requested_persona: str | None = None
    created_at: str | None = None


class ReviewQueueResponse(BaseModel):
    """Paginated list response for ``GET /api/cmcp/review/queue``."""

    model_config = ConfigDict(extra="forbid")

    items: list[ReviewQueueItem]
    total: int
    page: int
    limit: int


class EditHistoryEntry(BaseModel):
    """One ``edit_history`` row stamped on PATCH."""

    model_config = ConfigDict(extra="forbid")

    editor_id: int
    edit_at: str
    before_snippet: str
    after_snippet: str


class ReviewArtifactDetail(BaseModel):
    """Full artifact + review metadata for the GET-by-id endpoint."""

    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    course_id: int | None = None
    title: str
    content: str
    guide_type: str
    state: str
    se_codes: list[str] = Field(default_factory=list)
    voice_module_hash: str | None = None
    requested_persona: str | None = None
    board_id: str | None = None
    alignment_score: float | None = None
    ceg_version: int | None = None
    class_context_envelope_summary: dict[str, Any] | None = None
    edit_history: list[EditHistoryEntry] = Field(default_factory=list)
    reviewed_by_user_id: int | None = None
    reviewed_at: str | None = None
    rejection_reason: str | None = None
    created_at: str | None = None


class EditDeltaRequest(BaseModel):
    """Request body for ``PATCH /api/cmcp/review/{id}``.

    The frontend sends the new full Markdown body (not a textual diff)
    so the route doesn't need a 3-way merge. We persist a ``before /
    after`` snippet pair on ``edit_history`` so the audit trail still
    captures the intent of each edit without storing the full content
    twice per edit.
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1, max_length=200_000)


class RejectRequest(BaseModel):
    """Request body for ``POST /api/cmcp/review/{id}/reject``."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=2000)


class RegenerateRequest(BaseModel):
    """Request body for ``POST /api/cmcp/review/{id}/regenerate``.

    Wraps the standard ``CMCPGenerateRequest`` so the regenerate path
    re-runs the same prompt-build pipeline as the original generation.
    The current artifact's ``id`` + ``state=PENDING_REVIEW`` are kept;
    only ``content``, the SE list, the voice-module hash, and the
    persona may change.
    """

    model_config = ConfigDict(extra="forbid")

    request: CMCPGenerateRequest


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _envelope_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return None


def _alignment_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _edit_history_list(value: Any) -> list[EditHistoryEntry]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(value, list):
        return []
    out: list[EditHistoryEntry] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(EditHistoryEntry(**entry))
        except ValidationError as exc:
            # Defensive: a malformed legacy entry shouldn't 500 the GET.
            # Logged at DEBUG so ops can spot a recurring schema-drift
            # signal without polluting INFO/WARN streams.
            logger.debug(
                "Dropping malformed edit_history entry: %s", exc
            )
            continue
    return out


def _to_queue_item(row: StudyGuide) -> ReviewQueueItem:
    return ReviewQueueItem(
        id=row.id,
        title=row.title,
        guide_type=row.guide_type,
        state=row.state,
        course_id=row.course_id,
        user_id=row.user_id,
        se_codes=list(row.se_codes) if row.se_codes else [],
        requested_persona=row.requested_persona,
        created_at=_iso(row.created_at),
    )


def _to_detail(row: StudyGuide) -> ReviewArtifactDetail:
    return ReviewArtifactDetail(
        id=row.id,
        user_id=row.user_id,
        course_id=row.course_id,
        title=row.title,
        content=row.content,
        guide_type=row.guide_type,
        state=row.state,
        se_codes=list(row.se_codes) if row.se_codes else [],
        voice_module_hash=row.voice_module_hash,
        requested_persona=row.requested_persona,
        board_id=row.board_id,
        alignment_score=_alignment_float(row.alignment_score),
        ceg_version=row.ceg_version,
        class_context_envelope_summary=_envelope_dict(
            row.class_context_envelope_summary
        ),
        edit_history=_edit_history_list(row.edit_history),
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_at=_iso(row.reviewed_at),
        rejection_reason=row.rejection_reason,
        created_at=_iso(row.created_at),
    )


def _snippet(value: str, *, limit: int = 200) -> str:
    """Truncate to ``limit`` chars with an ellipsis suffix.

    Used to keep the edit_history JSONB row small — full content is
    already on the artifact's ``content`` column at the latest revision,
    so the audit trail stores intent (snippets) rather than full bodies.
    """
    if value is None:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=ReviewQueueResponse)
def list_review_queue(
    page: int = Query(1, ge=1, le=1000),
    limit: int = Query(20, ge=1, le=100),
    sort_by: _SortField = Query("created_at"),
    current_user: User = Depends(_require_review_role),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    """List PENDING_REVIEW artifacts the caller can review.

    Pagination: page+limit (1-indexed page, default 20 per page, max 100).
    Sort options:

    - ``created_at`` (default, descending so newest items lead the queue)
    - ``content_type`` (alpha asc, ``guide_type`` column)
    - ``subject`` (alpha asc on the first SE code's subject prefix —
      best-effort sort key; SQLite + PG both support text ordering on
      ``se_codes`` indirectly via Python-side post-sort because JSONB
      sort across dialects is finicky in SQLAlchemy 2.x)

    TEACHER → narrowed to artifacts they own (creator or course-pinned).
    ADMIN → all PENDING_REVIEW rows.
    """
    base = db.query(StudyGuide).filter(
        StudyGuide.state == ArtifactState.PENDING_REVIEW
    )

    if not current_user.has_role(UserRole.ADMIN):
        # TEACHER scope — creator-owned OR course-owned.
        owned_course_ids = _teacher_owned_course_ids(db, current_user)
        if owned_course_ids:
            base = base.filter(
                (StudyGuide.user_id == current_user.id)
                | (StudyGuide.course_id.in_(owned_course_ids))
            )
        else:
            base = base.filter(StudyGuide.user_id == current_user.id)

    total = base.count()

    if sort_by == "content_type":
        ordered = base.order_by(StudyGuide.guide_type.asc(), StudyGuide.id.desc())
    elif sort_by == "subject":
        # SE-code-prefix sort happens after the SQL fetch — see docstring.
        ordered = base.order_by(StudyGuide.created_at.desc(), StudyGuide.id.desc())
    else:
        ordered = base.order_by(StudyGuide.created_at.desc(), StudyGuide.id.desc())

    rows = (
        ordered.offset((page - 1) * limit).limit(limit).all()
    )
    items = [_to_queue_item(r) for r in rows]

    if sort_by == "subject":
        # Stable Python-side sort on the first SE code's subject prefix
        # (Ontario SE codes are namespaced ``<SUBJECT>.<...>``).
        def _key(it: ReviewQueueItem) -> str:
            if not it.se_codes:
                return ""
            first = it.se_codes[0]
            return first.split(".", 1)[0] if "." in first else first

        items.sort(key=_key)

    return ReviewQueueResponse(
        items=items, total=total, page=page, limit=limit
    )


@router.get("/{artifact_id}", response_model=ReviewArtifactDetail)
def get_review_artifact(
    artifact_id: int,
    current_user: User = Depends(_require_review_role),
    db: Session = Depends(get_db),
) -> ReviewArtifactDetail:
    """Return the full artifact + review metadata.

    404 covers both "no row" and "no access" so we don't leak existence.
    """
    artifact = _load_review_artifact(artifact_id, current_user, db)
    return _to_detail(artifact)


@router.patch("/{artifact_id}", response_model=ReviewArtifactDetail)
def patch_review_artifact(
    artifact_id: int,
    payload: EditDeltaRequest,
    current_user: User = Depends(_require_review_role),
    db: Session = Depends(get_db),
) -> ReviewArtifactDetail:
    """Apply an edit delta + append to ``edit_history``.

    Persists the new full Markdown body to ``content`` and stamps a
    ``{editor_id, edit_at, before_snippet, after_snippet}`` entry on
    ``edit_history`` (append-only). State is left untouched on the
    edit — but the edit is only permitted in ``_MUTABLE_REVIEW_STATES``
    (PENDING_REVIEW, REJECTED, DRAFT). Editing an APPROVED /
    APPROVED_VERIFIED / ARCHIVED artifact would silently mutate a
    published body and break the audit + downstream-consumption
    invariants, so we 409 instead.
    """
    artifact = _load_review_artifact(artifact_id, current_user, db)

    if artifact.state not in _MUTABLE_REVIEW_STATES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot edit artifact in state {artifact.state!r}; "
                f"expected one of PENDING_REVIEW/REJECTED/DRAFT"
            ),
        )

    before_snip = _snippet(artifact.content)
    after_snip = _snippet(payload.content)

    new_entry = {
        "editor_id": current_user.id,
        "edit_at": datetime.now(timezone.utc).isoformat(),
        "before_snippet": before_snip,
        "after_snippet": after_snip,
    }

    history = artifact.edit_history
    if history is None:
        history = []
    elif isinstance(history, str):
        try:
            history = json.loads(history)
        except (TypeError, ValueError, json.JSONDecodeError):
            history = []
    elif not isinstance(history, list):
        history = []
    else:
        # SQLAlchemy JSON types may return the same list reference; copy
        # so the new value is a distinct list (some dialects detect
        # "same object" and skip the UPDATE otherwise).
        history = list(history)
    history.append(new_entry)

    artifact.content = payload.content
    artifact.edit_history = history
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    logger.info(
        "cmcp.review.edit artifact_id=%s editor_id=%s history_len=%d",
        artifact.id,
        current_user.id,
        len(history),
        extra={
            "event": "cmcp.review.edit",
            "artifact_id": artifact.id,
            "editor_id": current_user.id,
            "history_len": len(history),
        },
    )

    return _to_detail(artifact)


@router.post("/{artifact_id}/approve", response_model=ReviewArtifactDetail)
def approve_review_artifact(
    artifact_id: int,
    current_user: User = Depends(_require_review_role),
    db: Session = Depends(get_db),
) -> ReviewArtifactDetail:
    """Transition PENDING_REVIEW → APPROVED + record reviewer + timestamp.

    409 on any other source state (the queue should never serve a row
    in a different state, but defence-in-depth).

    On successful state transition, fires the surface dispatcher
    (3C-1) in-process to fan-out the artifact to the three M3α
    surfaces (Bridge / DCI / Digest). The dispatcher is best-effort:
    a failure on any surface is logged + recorded in the audit table
    but never raised back to the caller — the approve still returns
    200 even when one or more surfaces fail. M3β can layer a cross-
    process worker on top of the same dispatch contract.
    """
    artifact = _load_review_artifact(artifact_id, current_user, db)

    if artifact.state != ArtifactState.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot approve artifact in state {artifact.state!r}; "
                f"expected {ArtifactState.PENDING_REVIEW!r}"
            ),
        )

    artifact.state = ArtifactState.APPROVED
    artifact.reviewed_by_user_id = current_user.id
    artifact.reviewed_at = datetime.now(timezone.utc)
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    logger.info(
        "cmcp.review.approved artifact_id=%s reviewer_id=%s",
        artifact.id,
        current_user.id,
        extra={
            "event": "cmcp.review.approved",
            "artifact_id": artifact.id,
            "reviewer_id": current_user.id,
        },
    )

    # CB-CMCP-001 M3-C 3C-1 (#4586) — fan-out to the three M3α surfaces.
    # Lazy import to keep the route module light + dodge any import-cycle
    # risk between routes ↔ services. Wrapped in try/except so a
    # dispatcher-internal blow-up never breaks the approve response —
    # dispatcher contract is "best-effort, failures are ops-only".
    try:
        from app.services.cmcp.surface_dispatcher import (  # noqa: PLC0415
            dispatch_artifact_to_surfaces,
        )

        dispatch_artifact_to_surfaces(artifact.id, db)
    except Exception:  # pragma: no cover — defence-in-depth
        logger.exception(
            "cmcp.review.approve dispatcher raised — swallowed so approve "
            "still returns 200 artifact_id=%s",
            artifact.id,
        )

    return _to_detail(artifact)


@router.post("/{artifact_id}/reject", response_model=ReviewArtifactDetail)
def reject_review_artifact(
    artifact_id: int,
    payload: RejectRequest,
    current_user: User = Depends(_require_review_role),
    db: Session = Depends(get_db),
) -> ReviewArtifactDetail:
    """Transition PENDING_REVIEW → REJECTED + record reviewer + reason.

    Pydantic enforces ``reason`` is a non-empty 1-2000 char string at
    the schema layer — a missing / empty body 422s before reaching here.
    """
    artifact = _load_review_artifact(artifact_id, current_user, db)

    if artifact.state != ArtifactState.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot reject artifact in state {artifact.state!r}; "
                f"expected {ArtifactState.PENDING_REVIEW!r}"
            ),
        )

    artifact.state = ArtifactState.REJECTED
    artifact.reviewed_by_user_id = current_user.id
    artifact.reviewed_at = datetime.now(timezone.utc)
    artifact.rejection_reason = payload.reason
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    logger.info(
        "cmcp.review.rejected artifact_id=%s reviewer_id=%s",
        artifact.id,
        current_user.id,
        extra={
            "event": "cmcp.review.rejected",
            "artifact_id": artifact.id,
            "reviewer_id": current_user.id,
        },
    )
    return _to_detail(artifact)


@router.post("/{artifact_id}/regenerate", response_model=ReviewArtifactDetail)
def regenerate_review_artifact(
    artifact_id: int,
    payload: RegenerateRequest,
    current_user: User = Depends(_require_review_role),
    db: Session = Depends(get_db),
) -> ReviewArtifactDetail:
    """Re-run the prompt-build pipeline + replace the artifact's content.

    Calls ``generate_cmcp_preview_sync`` to compose a fresh prompt with
    the supplied parameters. The persistence helper inside that service
    INSERTs a *new* ``study_guides`` row by design — we don't want to
    use it here because the contract is "same id". Instead, we run the
    preview, copy the resulting prompt + SE list + voice-module hash
    onto the existing row, and delete the freshly-inserted row so the
    DB state is left clean.

    State stays ``PENDING_REVIEW``. The freshly-inserted row inherits
    the CMCP persistence helper's state-machine logic (PENDING_REVIEW
    for teacher+course, SELF_STUDY otherwise), so we always need to
    delete it after copying — not just when the state happens to match.
    """
    artifact = _load_review_artifact(artifact_id, current_user, db)

    # Regenerate is only meaningful in mutable review states (same set
    # as PATCH — PENDING_REVIEW canonical, REJECTED + DRAFT included
    # since the contract keeps state=PENDING_REVIEW after regeneration).
    # Block APPROVED / APPROVED_VERIFIED / ARCHIVED so a caller can't
    # quietly mutate a published artifact.
    if artifact.state not in _MUTABLE_REVIEW_STATES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot regenerate artifact in state {artifact.state!r}; "
                f"expected one of PENDING_REVIEW/REJECTED/DRAFT"
            ),
        )

    # Capture the pre-regenerate snippet for the audit trail BEFORE we
    # mutate ``artifact.content`` below.
    before_snippet = _snippet(artifact.content)

    preview = generate_cmcp_preview_sync(
        payload=payload.request,
        current_user=current_user,
        db=db,
    )

    # ``generate_cmcp_preview_sync`` inserts a fresh row via
    # ``persist_cmcp_artifact``. Delete it so the regenerate contract
    # ("same id") holds. ``preview.id`` is None only when the insert
    # was skipped/failed — defensive None-check below. Wrap in its own
    # try/except so a failed cleanup (e.g., FK constraint when future
    # stripes add child relationships) doesn't roll back the artifact
    # update — leaking a fresh row is a soft cost, the artifact update
    # is the user-visible operation.
    if preview.id is not None and preview.id != artifact.id:
        phantom_artifact_id = preview.id
        try:
            stale = (
                db.query(StudyGuide)
                .filter(StudyGuide.id == phantom_artifact_id)
                .first()
            )
            if stale is not None:
                db.delete(stale)
                db.flush()
                # M3α IMP (#4634) — ``persist_cmcp_artifact`` already
                # wrote a ``cmcp.artifact.created`` audit row pointing
                # at the phantom id and committed it. Now that we're
                # cleaning up the phantom, write a compensating audit
                # entry so the Bill 194 trail doesn't reference a
                # deleted ``resource_id``. Lazy-import to mirror the
                # persistence module's convention.
                from app.services.audit_service import log_action

                log_action(
                    db,
                    user_id=current_user.id,
                    action="cmcp.artifact.deleted_during_regenerate",
                    resource_type="study_guide",
                    resource_id=phantom_artifact_id,
                    details={
                        "replaces_artifact_id": artifact_id,
                    },
                )
        except Exception:
            logger.exception(
                "cmcp.review.regenerate cleanup failed; leaking fresh row "
                "id=%s — will be cleaned up by a future janitor",
                phantom_artifact_id,
            )
            db.rollback()
            # Re-fetch the artifact since rollback detached it.
            artifact = (
                db.query(StudyGuide)
                .filter(StudyGuide.id == artifact_id)
                .first()
            )
            if artifact is None:
                # Defensive — the row existed at the start of the
                # request; vanishing mid-flight is a 500-class fault.
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Artifact {artifact_id} disappeared during "
                        f"regenerate cleanup"
                    ),
                )

    # Stamp the edit_history with a regenerate marker BEFORE the commit
    # so the audit trail records the entire-body replacement, not just
    # the in-place ``cmcp.review.regenerated`` ops log line.
    history = artifact.edit_history
    if history is None:
        history = []
    elif isinstance(history, str):
        try:
            history = json.loads(history)
        except (TypeError, ValueError, json.JSONDecodeError):
            history = []
    elif not isinstance(history, list):
        history = []
    else:
        history = list(history)
    history.append(
        {
            "editor_id": current_user.id,
            "edit_at": datetime.now(timezone.utc).isoformat(),
            "before_snippet": before_snippet,
            "after_snippet": _snippet(preview.prompt),
        }
    )

    artifact.content = preview.prompt
    artifact.se_codes = list(preview.se_codes_targeted) if preview.se_codes_targeted else None
    artifact.voice_module_hash = preview.voice_module_hash
    artifact.requested_persona = preview.persona
    artifact.state = ArtifactState.PENDING_REVIEW
    artifact.edit_history = history
    # A regeneration invalidates the previous review verdict.
    artifact.reviewed_by_user_id = None
    artifact.reviewed_at = None
    artifact.rejection_reason = None
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    logger.info(
        "cmcp.review.regenerated artifact_id=%s requester_id=%s",
        artifact.id,
        current_user.id,
        extra={
            "event": "cmcp.review.regenerated",
            "artifact_id": artifact.id,
            "requester_id": current_user.id,
        },
    )
    return _to_detail(artifact)


__all__ = ["router"]
