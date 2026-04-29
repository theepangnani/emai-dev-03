"""CB-CMCP-001 M3α prequel (#4575) — persist a ``study_guides`` row after
M1 generation completes.

M1 ships in-memory generation only. Every M3 surface stripe (review
queue, self-study, surface dispatcher, Tasks emit, version cascade)
needs real ``study_guides`` rows. This module wires the missing INSERT
in one shared helper so the sync (1A-2) and stream (1E-1) routes use
identical column-population logic + state-machine logic.

State logic (per locked decision D3=C)
--------------------------------------
- TEACHER requestor with ``course_id`` (class-distribute path) →
  ``PENDING_REVIEW`` (lands on the review queue).
- Everyone else (PARENT / STUDENT, or TEACHER without a course_id) →
  ``SELF_STUDY`` (parent + student self-initiated).

This is intentionally narrow — admins, board admins, and curriculum
admins also fall into SELF_STUDY here; they're not the M3 review-queue
audience and the surface stripes will refine the matrix when they need
to. The primary D3=C bifurcation is parent/student vs teacher+class.

Out of scope
------------
- Surface dispatcher / fan-out (3C-1)
- Tasks emit (3D-1)
- Version cascade (3F-1)
- Real Claude calls in the sync route (M1 invariant)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)

# HTTP-side content-type → ``StudyGuide.guide_type`` literal. Mirrors the
# legacy CB-ASGF-001 convention (lowercase guide_type) so MCP clients
# and the existing ``study_guides`` consumers see one value space.
_GUIDE_TYPE_FROM_HTTP: dict[str, str] = {
    "STUDY_GUIDE": "study_guide",
    "WORKSHEET": "worksheet",
    "QUIZ": "quiz",
    "SAMPLE_TEST": "sample_test",
    "ASSIGNMENT": "assignment",
    "PARENT_COMPANION": "parent_companion",
}


def _resolve_state(
    *,
    user: User,
    target_persona: str,
    target_course_id: int | None,
) -> str:
    """Compute the artifact state per D3=C.

    TEACHER + course_id → PENDING_REVIEW (class-distribute → review queue).
    Otherwise → SELF_STUDY (parent + student self-initiated, plus
    teacher-without-course fallthrough).

    Note: ``target_persona`` is currently informational — the gate is
    purely on the requestor's role + presence of class context. The
    persona drives the prompt overlay, not the state. M3 may refine
    this if a surface stripe needs persona-aware state stamping.
    """
    if user.role == UserRole.TEACHER and target_course_id is not None:
        return ArtifactState.PENDING_REVIEW
    return ArtifactState.SELF_STUDY


def _envelope_summary(envelope: Any) -> dict[str, Any] | None:
    """Coerce the resolved class-context envelope to a JSON-friendly summary.

    Stores only the audit-metadata fields (``envelope_size``,
    ``cited_source_count``, ``fallback_used``, ``course_id``) — the full
    materials list is too large + too leaky to embed verbatim in the
    artifact row. M3 surface stripes that need the full envelope will
    re-resolve via ``ClassContextResolver`` rather than persisting it.

    Accepts either a Pydantic model (with ``model_dump``), a plain dict,
    or ``None``. Returns ``None`` when the envelope is missing.
    """
    if envelope is None:
        return None
    if hasattr(envelope, "model_dump"):
        data = envelope.model_dump()
    elif isinstance(envelope, dict):
        data = envelope
    else:
        return None
    summary: dict[str, Any] = {}
    for key in ("envelope_size", "cited_source_count", "fallback_used", "course_id"):
        if key in data:
            summary[key] = data[key]
    return summary or None


def persist_cmcp_artifact(
    *,
    db: Session,
    user: User,
    title: str,
    content: str,
    http_content_type: str,
    target_persona: str,
    se_codes: list[str],
    voice_module_hash: str | None,
    envelope: Any,
    course_id: int | None,
    alignment_score: float | None = None,
    parent_companion: dict[str, Any] | None = None,
    ceg_version: int | None = None,
) -> StudyGuide:
    """Insert a ``study_guides`` row for the just-built CMCP artifact.

    Returns the persisted (flushed + refreshed) row so the caller has
    the new ``id`` to surface on the response. Commits the row — the
    sync + stream routes are both end-of-request boundaries here.

    Column population rationale
    ---------------------------
    - ``user_id`` — the requestor (``current_user.id``).
    - ``course_id`` — request payload (None for non-class-distribute).
    - ``title`` — caller-supplied (route uses ``"CMCP <CONTENT_TYPE>"``).
    - ``content`` — caller-supplied (prompt for sync; full streamed
      content for stream).
    - ``guide_type`` — HTTP content type lowercased.
    - ``state`` — D3=C resolution.
    - ``se_codes`` / ``alignment_score`` / ``ceg_version`` /
      ``voice_module_hash`` / ``class_context_envelope_summary`` /
      ``requested_persona`` — M0/M1 stamped columns.
    - ``board_id`` — best-effort via
      :func:`app.mcp.tools._visibility.resolve_caller_board_id`. M3-E
      will properly stamp this when ``User.board_id`` lands.
    - ``parent_summary`` — JSON-serialized parent-companion 5-section
      content when the stream route auto-emitted one (None otherwise).
      The GET parent-companion endpoint (#4575) reads this back.
    """
    # Lazy-import the visibility helper. It lives in app.mcp.tools._visibility
    # and the mcp.tools package eagerly loads generate_content which imports
    # back from app.api.routes.cmcp_generate — module-top imports here would
    # form a circular dependency at startup. The helper is pure (single
    # ``getattr``), so the lazy import is essentially free per call.
    from app.mcp.tools._visibility import resolve_caller_board_id

    state = _resolve_state(
        user=user,
        target_persona=target_persona,
        target_course_id=course_id,
    )
    board_id = resolve_caller_board_id(user)

    parent_summary_json: str | None = None
    if parent_companion is not None:
        try:
            parent_summary_json = json.dumps(parent_companion)
        except (TypeError, ValueError):
            # Defensive — ``parent_companion`` is a Pydantic ``model_dump()``
            # result, but a future caller might pass something non-JSON-able.
            # Log + skip rather than crash the persistence path.
            logger.warning(
                "CMCP persist: parent_companion JSON-encode failed; "
                "storing artifact without parent_summary"
            )
            parent_summary_json = None

    artifact = StudyGuide(
        user_id=user.id,
        course_id=course_id,
        title=title,
        content=content,
        guide_type=_GUIDE_TYPE_FROM_HTTP.get(http_content_type, "study_guide"),
        state=state,
        se_codes=list(se_codes) if se_codes else None,
        alignment_score=alignment_score,
        ceg_version=ceg_version,
        voice_module_hash=voice_module_hash,
        class_context_envelope_summary=_envelope_summary(envelope),
        requested_persona=target_persona,
        board_id=str(board_id) if board_id is not None else None,
        parent_summary=parent_summary_json,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    logger.info(
        "cmcp.artifact.persisted id=%s user_id=%s state=%s persona=%s "
        "content_type=%s course_id=%s",
        artifact.id,
        user.id,
        state,
        target_persona,
        http_content_type,
        course_id,
        extra={
            "event": "cmcp.artifact.persisted",
            "artifact_id": artifact.id,
            "user_id": user.id,
            "state": state,
            "persona": target_persona,
            "content_type": http_content_type,
            "course_id": course_id,
        },
    )

    # M3α 3B-1 (#4577): write an audit-log entry for the initial INSERT so
    # the Bill 194 audit trail captures every CMCP artifact creation.
    # Lazy-import the audit service to keep the persistence module import
    # graph minimal — ``log_action`` is fail-soft (savepoint + warn) so a
    # missed audit row never corrupts the persistence transaction. The
    # trailing ``db.commit()`` flushes the savepoint to disk; matches the
    # ``log_action(...) → db.commit()`` pattern used in
    # ``app/api/routes/account_deletion.py``.
    from app.services.audit_service import log_action

    log_action(
        db,
        user_id=user.id,
        action="cmcp.artifact.created",
        resource_type="study_guide",
        resource_id=artifact.id,
        details={
            "state": state,
            "persona": target_persona,
            "content_type": http_content_type,
            "course_id": course_id,
            "role": user.role.value if user.role else None,
        },
    )
    db.commit()
    return artifact


__all__ = ["persist_cmcp_artifact"]
