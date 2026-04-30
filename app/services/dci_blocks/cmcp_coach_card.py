"""CB-CMCP-001 M3α 3C-2 (#4579) — DCI ``cb_cmcp_coach_card`` block renderer.

Produces a 5-min coach-card payload from a CMCP parent-persona artifact
(``study_guides`` row with ``requested_persona='parent'`` or
``guide_type='parent_companion'``). The block is consumed by the
Daily Check-In ingest contract (CB-DCI-001) so a parent's evening
ritual surfaces *one* curriculum-aligned coaching card per relevant
artifact.

Wave-0 persistence (#4596) stashes the 5-section
``ParentCompanionContent`` as JSON in ``study_guides.parent_summary``;
this renderer deserializes that JSON, picks the top 3 talking points,
and returns a flat dict keyed by ``block_type``.

Returns ``None`` (block omitted, **not** an error) when:
  * the artifact id resolves to no row;
  * the row's state is not in {APPROVED, SELF_STUDY};
  * the row is not a parent-persona artifact;
  * ``parent_summary`` is empty / unparseable / has no talking points.

Out of scope (per #4579):
  * surface dispatcher fan-out (3C-1, Wave 2).

Telemetry (3C-5): the renderer calls
:func:`app.services.cmcp.surface_telemetry.log_rendered` with
``surface=SURFACE_DCI`` immediately before returning the payload, so
the M3 acceptance metric "render rate per surface" is computable from
the standard ``cmcp.surface.rendered`` log feed. The legacy
``dci.block.rendered`` info line is kept for backwards-compat with any
extractors that already match it.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)

# Public block_type identifier — the same string lands in the rendered
# payload so the surface dispatcher can route by string match.
CMCP_COACH_CARD_BLOCK_TYPE = "cb_cmcp_coach_card"

# Renderable artifact states (per D3=C). APPROVED covers teacher-reviewed
# class-distribute artifacts; SELF_STUDY covers parent / student self-
# initiated artifacts. Any other state (DRAFT, PENDING_REVIEW, REJECTED,
# ARCHIVED, etc.) is intentionally invisible to the coach-card surface.
_RENDERABLE_STATES: frozenset[str] = frozenset(
    {ArtifactState.APPROVED, ArtifactState.SELF_STUDY}
)

# How many talking points to surface in the coach card. Kept small so the
# 5-min ritual stays glanceable. The underlying ``ParentCompanionContent``
# carries 3-5 talking_points (FR-02.6 band); we always show top 3.
_TALKING_POINTS_LIMIT = 3

# Hard cap on the topic summary length — protects the coach-card UI from
# a runaway model output. Picks the first sentence of ``se_explanation``
# (which the prompt restricts to 2 sentences).
_TOPIC_SUMMARY_MAX_CHARS = 240

# Pattern: ``CB-G{grade}-{SUBJECT}-...`` (see CEGExpectation.cb_code).
# Used to derive a subject label from the artifact's stamped se_codes
# without an extra DB lookup. Falls back to the raw token when match
# fails so we always emit *some* subject string.
_SE_CODE_SUBJECT_RE = re.compile(r"^CB-G\d+-([A-Z0-9]+)-", re.IGNORECASE)


def _is_parent_persona(artifact: Any) -> bool:
    """Return ``True`` iff this row is a parent-facing CMCP artifact.

    Two signals — either is sufficient:
      * ``requested_persona == 'parent'`` (M1+ stamps this on every
        CMCP-generated artifact, regardless of guide_type).
      * ``guide_type == 'parent_companion'`` (HTTP content-type
        PARENT_COMPANION lowercased — set by ``persist_cmcp_artifact``).
    """
    persona = (artifact.requested_persona or "").strip().lower()
    if persona == "parent":
        return True
    guide_type = (artifact.guide_type or "").strip().lower()
    return guide_type == "parent_companion"


def _first_sentence(text: str, *, max_chars: int = _TOPIC_SUMMARY_MAX_CHARS) -> str:
    """Pull the first sentence out of *text*, capped at ``max_chars``.

    Falls back to a hard char cap if no sentence-ending punctuation is
    present in the slice — better to truncate cleanly than emit a
    multi-paragraph blob into the coach-card UI.
    """
    if not text:
        return ""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    # Look for the first sentence terminator inside the cap.
    window = cleaned[:max_chars]
    boundary = -1
    for terminator in (". ", "! ", "? "):
        idx = window.find(terminator)
        if idx >= 0 and (boundary < 0 or idx < boundary):
            # +1 keeps the terminator on the kept slice.
            boundary = idx + 1
    if boundary > 0:
        return window[:boundary].strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return window.rstrip() + "…"


def _derive_subject(artifact: Any) -> str:
    """Best-effort subject label for the coach card.

    Resolution order:
      1. First entry in ``se_codes`` parsed with ``_SE_CODE_SUBJECT_RE``.
      2. Trim of ``artifact.title`` (typically ``"CMCP STUDY_GUIDE"`` —
         falls back to the canonical content-type label).
      3. Hard fallback: ``"General"`` so the coach card always has a
         non-empty subject string.
    """
    se_codes = artifact.se_codes
    if isinstance(se_codes, list) and se_codes:
        first = se_codes[0]
        if isinstance(first, str):
            match = _SE_CODE_SUBJECT_RE.match(first.strip())
            if match:
                return match.group(1).upper()
    title = (artifact.title or "").strip()
    if title:
        # Strip leading "CMCP " if present so the surface doesn't show the
        # internal artifact-class prefix.
        if title.upper().startswith("CMCP "):
            title = title[5:].strip()
        if title:
            return title[:60]
    return "General"


def _resolve_child_name(*, db: Session, kid_id: int) -> str:
    """Resolve a friendly child name for the coach card.

    Looks up ``students.id == kid_id`` and falls back to the linked
    user's full_name. Returns a safe placeholder if the row / user is
    missing — the coach card always renders SOMETHING so the parent
    isn't shown a blank field. The DCI ritual is parent-facing only,
    so a generic "Your kid" fallback is acceptable for the rare
    orphan-row case.
    """
    if kid_id is None:
        return "Your kid"
    # Lazy-import the ORM models: importing them at module-top breaks
    # under the conftest's `app.models` reload (the cached references go
    # stale, leading to ``Mapper`` failures like "expression 'Assignment'
    # failed to locate a name"). Lazy import re-resolves against the
    # currently-registered registry on every call. Pure-Python overhead
    # is a single dict lookup per import after the first call.
    from app.models.student import Student  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    student = db.query(Student).filter(Student.id == int(kid_id)).first()
    if student is None:
        return "Your kid"
    user = (
        db.query(User).filter(User.id == student.user_id).first()
        if student.user_id
        else None
    )
    full_name = (user.full_name or "").strip() if user is not None else ""
    if not full_name:
        return "Your kid"
    # First name only — coach-card style is informal.
    return full_name.split()[0]


def _select_talking_points(content: dict[str, Any]) -> list[str]:
    """Pull the top N non-empty talking points from the persisted content."""
    raw = content.get("talking_points")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            out.append(text)
        if len(out) >= _TALKING_POINTS_LIMIT:
            break
    return out


def _topic_summary(content: dict[str, Any]) -> str:
    """One-line plain-language summary of what the kid is learning."""
    raw = content.get("se_explanation")
    if not isinstance(raw, str):
        return ""
    return _first_sentence(raw)


def render_cmcp_coach_card(
    artifact_id: int,
    kid_id: int,
    db: Session,
) -> Optional[dict]:
    """Render a ``cb_cmcp_coach_card`` block for *artifact_id* + *kid_id*.

    Args:
        artifact_id: ``study_guides.id`` of the CMCP parent-persona row.
        kid_id: ``students.id`` of the kid whose check-in carries this
            block. Used purely to surface a friendly first name on the
            card — visibility / RBAC happens upstream in the surface
            dispatcher (3C-1) not here.
        db: SQLAlchemy session bound to the request scope.

    Returns:
        A flat ``dict`` payload with the agreed ingest-contract fields,
        OR ``None`` when the artifact is missing / wrong state / has no
        renderable parent-companion content. ``None`` is the canonical
        "block omitted, not an error" signal — the dispatcher must
        treat it as a soft skip, not a 500.

    Payload shape (returned dict):
        {
          "block_type": "cb_cmcp_coach_card",
          "artifact_id": <int>,
          "child_name": <str>,
          "subject": <str>,
          "topic_summary": <str>,        # 1-line plain-language explanation
          "talking_points": <list[str]>, # top 3, non-empty
          "open_link": "/parent/companion/<artifact_id>"
        }
    """
    if artifact_id is None:
        return None
    # Lazy import — see comment in ``_resolve_child_name`` for why.
    from app.models.study_guide import StudyGuide  # noqa: PLC0415

    try:
        artifact = (
            db.query(StudyGuide)
            .filter(StudyGuide.id == int(artifact_id))
            .first()
        )
    except (TypeError, ValueError):
        return None
    if artifact is None:
        return None

    state = (artifact.state or "").strip()
    if state not in _RENDERABLE_STATES:
        logger.debug(
            "cb_cmcp_coach_card skipped: state=%s not renderable artifact_id=%s",
            state,
            artifact_id,
        )
        return None

    if not _is_parent_persona(artifact):
        logger.debug(
            "cb_cmcp_coach_card skipped: not a parent-persona artifact "
            "artifact_id=%s persona=%s guide_type=%s",
            artifact_id,
            artifact.requested_persona,
            artifact.guide_type,
        )
        return None

    raw_summary = (artifact.parent_summary or "").strip()
    if not raw_summary:
        logger.debug(
            "cb_cmcp_coach_card skipped: empty parent_summary artifact_id=%s",
            artifact_id,
        )
        return None

    try:
        content = json.loads(raw_summary)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning(
            "cb_cmcp_coach_card skipped: parent_summary JSON parse failed "
            "artifact_id=%s",
            artifact_id,
        )
        return None
    if not isinstance(content, dict):
        return None

    talking_points = _select_talking_points(content)
    if not talking_points:
        logger.debug(
            "cb_cmcp_coach_card skipped: no usable talking_points artifact_id=%s",
            artifact_id,
        )
        return None

    payload = {
        "block_type": CMCP_COACH_CARD_BLOCK_TYPE,
        "artifact_id": int(artifact.id),
        "child_name": _resolve_child_name(db=db, kid_id=kid_id),
        "subject": _derive_subject(artifact),
        "topic_summary": _topic_summary(content),
        "talking_points": talking_points,
        "open_link": f"/parent/companion/{int(artifact.id)}",
    }

    # Legacy structured render log — kept for backwards-compat with any
    # extractors that already match ``dci.block.rendered``. Do not remove
    # without coordinating with the metrics pipeline.
    logger.info(
        "cb_cmcp_coach_card rendered artifact_id=%s kid_id=%s subject=%s "
        "talking_points=%d",
        payload["artifact_id"],
        kid_id,
        payload["subject"],
        len(talking_points),
        extra={
            "event": "dci.block.rendered",
            "block_type": CMCP_COACH_CARD_BLOCK_TYPE,
            "artifact_id": payload["artifact_id"],
            "kid_id": kid_id,
        },
    )

    # Canonical surface-telemetry render line (3C-5). The M3 acceptance
    # metric "render rate per surface" is derived from this event. The
    # ``user_id`` field in the helper is the *viewer*'s user row id — for
    # the DCI surface the viewer is the kid, so we resolve
    # ``Student.user_id`` from the supplied ``kid_id`` (which is a
    # ``students.id``, not a ``users.id``). Lazy-import the model — see
    # the ``_resolve_child_name`` comment for why module-top imports
    # break under conftest reloads. If the kid is unmapped (None or no
    # row), pass ``user_id=None`` — telemetry must never raise and break
    # the render path.
    from app.services.cmcp.surface_telemetry import (  # noqa: PLC0415
        SURFACE_DCI,
        log_rendered,
    )

    viewer_id: Optional[int] = None
    if kid_id is not None:
        from app.models.student import Student  # noqa: PLC0415

        student_row = (
            db.query(Student).filter(Student.id == int(kid_id)).first()
        )
        if student_row is not None and student_row.user_id is not None:
            viewer_id = int(student_row.user_id)
    # NOTE: ``log_rendered`` types ``user_id`` as ``int`` but per the
    # M3α task spec for #4632 we deliberately pass ``None`` when the
    # kid is unmapped — telemetry must never raise on the render path.
    # The helper formats the value verbatim into the structured log
    # line + ``extra`` dict; ``None``-coalescing is the metric
    # extractor's concern downstream. A future M3-followups round can
    # widen the helper signature to ``int | None``; tracked alongside
    # other M3-followups telemetry hardening.
    log_rendered(
        artifact_id=int(artifact.id),
        surface=SURFACE_DCI,
        user_id=viewer_id,  # type: ignore[arg-type]
    )
    return payload


__all__ = [
    "CMCP_COACH_CARD_BLOCK_TYPE",
    "render_cmcp_coach_card",
]
