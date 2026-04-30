"""Digest block renderers (CB-CMCP-001 M3α 3C-3, #4580).

This module is the home for **digest block renderers** — small pure-ish
helpers that take an artifact id (or other surface anchor), look the row
up, apply the parent's visibility matrix, and return a JSON-friendly
dict the unified Email Digest (CB-PEDI-002 V2) can drop into a parent's
daily digest.

3C-3 (this stripe) seeds the file with one renderer:

* ``render_cb_cmcp_artifact_summary`` — surfaces a CMCP artifact
  (``study_guides`` row) as a summary block keyed by ``block_type =
  "cb_cmcp_artifact_summary"``.

The companion renderer ``cb_dci_coach_card`` lands in sibling stripe
3C-2 (DCI block) and the surface dispatcher (3C-1, Wave 2) wires the
collection of renderers into the unified digest worker. **3C-3 must not
modify the CB-PEDI-002 core digest logic** — its scope is limited to
adding the renderer + registering it in the local block registry below.

Visibility model
----------------

For ``cb_cmcp_artifact_summary`` the parent is visible to the artifact
when **any** of the following hold (mirrors
:func:`app.api.deps.can_access_parent_companion` + the
:class:`StudyGuide` parent-of-child rules used by
``app.mcp.tools.get_artifact``):

1. The parent is the artifact's creator
   (``artifact.user_id == parent_id``).
2. The artifact's ``user_id`` belongs to one of the parent's linked
   children (resolved via ``parent_students`` → ``students.user_id``).
3. The artifact's ``course_id`` is one the parent's linked child is
   enrolled in (``student_courses`` join).

In all three cases the artifact's ``state`` must be in
``{APPROVED, SELF_STUDY}`` — DRAFT / IN_REVIEW / PENDING_REVIEW /
REJECTED / GENERATING / ARCHIVED / APPROVED_VERIFIED are intentionally
excluded:

* DRAFT / GENERATING / IN_REVIEW / PENDING_REVIEW — not yet ready for
  parent surfacing.
* REJECTED — review-queue rejection; should not surface.
* ARCHIVED — terminal removed state; never surface.
* APPROVED_VERIFIED — admin spot-check is upstream of APPROVED in the
  state graph; intentionally **not** surfaced via this digest block in
  M3α to keep the contract narrow. A future stripe can opt it in.

Returning ``None`` means "skip this block"; callers (the surface
dispatcher in 3C-1) MUST treat ``None`` as "do not include in digest"
without raising.

Optional ``kid_id`` / ``kid_name`` arguments
---------------------------------------------

The dispatcher passes ``kid_id`` (the child's User row id, or ``None``
when the surfaced artifact is parent-self-generated). This is used to
label the digest block ONLY — the visibility gate is artifact-driven
(via ``artifact.user_id`` + ``artifact.course_id``) and never trusts
the dispatcher-provided ``kid_id`` for security decisions.

When ``kid_id`` is supplied **and** matches the artifact's ``user_id``,
the block's ``kid_name`` is the linked child's first name. Otherwise
— parent-self-generated artifact, no parent↔child link, ``kid_id``
mismatch, or missing User row — ``kid_name`` is ``None``. The
dispatcher (3C-1) is free to fall back to the parent's first name in
its own render layer; this module never invents a name from the
artifact alone.

Out of scope (per #4580)
------------------------

* Surface dispatcher / fan-out (3C-1, Wave 2).
* DCI coach-card renderer (3C-2 sibling, Wave 1).
* Any change to the V2 unified-digest worker shape — the renderer is a
  pure dict producer; the dispatcher is responsible for dropping the
  produced dicts into the digest payload.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Block constants
# ---------------------------------------------------------------------------

BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY: str = "cb_cmcp_artifact_summary"

# Visible-to-parent state set. APPROVED comes from the teacher review
# queue; SELF_STUDY comes from the parent/student self-initiated path
# (D3=C). Everything else is intentionally excluded — see module
# docstring.
_PARENT_VISIBLE_STATES: frozenset[str] = frozenset(
    {ArtifactState.APPROVED, ArtifactState.SELF_STUDY}
)

# Maximum length of the auto-derived 1-line description fed into the
# block payload. Keeps the digest body compact and avoids leaking full
# artifact bodies into email render. Picked as a soft cap (not a hard
# truncate at the storage layer) so the digest stays short without
# losing the artifact title's context.
_DESCRIPTION_MAX_CHARS: int = 140


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _derive_one_line_description(artifact: Any) -> str:
    """Project the artifact to a single human-readable sentence.

    Ordering of fallbacks (first non-empty wins):

    1. The first non-empty line of ``artifact.content``, trimmed and
       capped at ``_DESCRIPTION_MAX_CHARS``.
    2. ``artifact.title`` (always populated — a NOT NULL column).

    The renderer never returns the full ``content`` body.
    """
    content = getattr(artifact, "content", None) or ""
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if len(line) > _DESCRIPTION_MAX_CHARS:
            cut = line[: _DESCRIPTION_MAX_CHARS - 1]
            # Back up to the previous word boundary when the cut lands
            # mid-word, so the digest doesn't show "Mitosis and meio…".
            # Only back up if doing so doesn't strip more than half the
            # cap (otherwise a single-word over-long line would truncate
            # to the empty string).
            last_space = cut.rfind(" ")
            if last_space > _DESCRIPTION_MAX_CHARS // 2:
                cut = cut[:last_space]
            return cut.rstrip() + "…"
        return line
    # Fallback to title — guaranteed non-null by schema.
    title = getattr(artifact, "title", None) or ""
    return title


def _build_open_link(artifact_id: int) -> str:
    """Build the ``Open in Bridge`` deep link for a CMCP artifact.

    The frontend route is ``/parent/companion/:artifact_id``
    (``ParentCompanionPage`` — wired in #4575). We prefix with
    ``settings.frontend_url`` (stripped of trailing slash) so the link
    works for both the local dev origin and the deployed origin.
    """
    base = (settings.frontend_url or "").rstrip("/")
    return f"{base}/parent/companion/{artifact_id}"


def _resolve_linked_children(
    db: Session, *, parent_id: int
) -> tuple[list[int], list[int]]:
    """Resolve the parent's linked-children id sets in one pair of queries.

    Returns ``(student_ids, user_ids)`` where:

    - ``student_ids`` are rows from ``parent_students`` whose
      ``parent_id`` matches.
    - ``user_ids`` are the corresponding ``students.user_id`` values.

    Both lists are returned together so callers (visibility gate +
    kid-name resolver) don't double-issue the same query. Both can be
    empty (parent has no linked children).
    """
    from app.models.student import Student, parent_students

    student_ids = [
        row[0]
        for row in db.query(parent_students.c.student_id)
        .filter(parent_students.c.parent_id == parent_id)
        .all()
    ]
    if not student_ids:
        return [], []
    user_ids = [
        row[0]
        for row in db.query(Student.user_id)
        .filter(Student.id.in_(student_ids))
        .all()
    ]
    return student_ids, user_ids


def _resolve_kid_name(
    db: Session,
    *,
    parent_id: int,
    kid_id: int | None,
    artifact: Any,
    linked_child_user_ids: list[int],
) -> str | None:
    """Resolve the child's first name when the artifact is for a kid.

    Returns ``None`` for parent-self-generated artifacts (artifact is
    owned by the parent themselves) or when no linked-child match
    applies. The dispatcher (3C-1) can render the block without a kid
    label in that case.

    ``linked_child_user_ids`` is the precomputed list from
    :func:`_resolve_linked_children` — passing it in dedupes the
    parent_students + students lookups that the visibility gate has
    already issued for this same parent.
    """
    # Lazy import — match the rest of the CMCP service layer (avoids
    # registry-load order issues under conftest reloads).
    from app.models.user import User

    artifact_user_id = getattr(artifact, "user_id", None)
    if artifact_user_id is None:
        return None
    if artifact_user_id == parent_id:
        # Self-generated by the parent — no kid label needed.
        return None

    if artifact_user_id not in linked_child_user_ids:
        return None
    if kid_id is not None and kid_id != artifact_user_id:
        # Dispatcher passed a kid_id that doesn't match the artifact
        # owner — return None for the name. The visibility gate has
        # already approved the artifact based on its own user_id /
        # course_id, so this branch only suppresses the label.
        return None

    kid = db.query(User).filter(User.id == artifact_user_id).first()
    if kid is None:
        return None
    full_name = (kid.full_name or "").strip()
    if not full_name:
        return None
    # First name only — the digest stays informal ("Maya's quiz", not
    # "Maya Smith's quiz").
    return full_name.split()[0]


def _parent_can_see_artifact(
    db: Session,
    *,
    parent_id: int,
    artifact: Any,
    linked_child_student_ids: list[int],
    linked_child_user_ids: list[int],
) -> bool:
    """Apply the parent visibility matrix for a single artifact row.

    Mirrors :func:`app.api.deps.can_access_parent_companion` for the
    PARENT branch (creator + linked-child + course-enrollment) without
    pulling in role-resolution helpers — the renderer is invoked with
    a parent id, not a User row, so role checks are owned by the
    dispatcher.

    ``linked_child_student_ids`` + ``linked_child_user_ids`` come from
    :func:`_resolve_linked_children`. Passing them in lets the caller
    issue the parent_students + students queries once and share the
    result with :func:`_resolve_kid_name`.
    """
    from app.models.course import student_courses

    # 1) Parent is the artifact's creator.
    if getattr(artifact, "user_id", None) == parent_id:
        return True

    if not linked_child_student_ids:
        return False

    # 2) Artifact owner is one of the parent's linked children.
    if getattr(artifact, "user_id", None) in linked_child_user_ids:
        return True

    # 3) Artifact's course has one of the parent's linked children
    #    enrolled. Course-less artifacts never trip this branch.
    course_id = getattr(artifact, "course_id", None)
    if course_id is None:
        return False
    enrolled = (
        db.query(student_courses.c.student_id)
        .filter(
            student_courses.c.student_id.in_(linked_child_student_ids),
            student_courses.c.course_id == course_id,
        )
        .first()
    )
    return enrolled is not None


def render_cb_cmcp_artifact_summary(
    artifact_id: int,
    parent_id: int,
    kid_id: int | None,
    db: Session,
) -> dict | None:
    """Render the ``cb_cmcp_artifact_summary`` digest block for a parent.

    Args:
        artifact_id: The ``study_guides.id`` of the CMCP artifact.
        parent_id: The parent's User row id (the digest recipient).
        kid_id: The child's User row id this surface is anchored to,
            or ``None`` for parent-self-generated artifacts. The
            renderer uses this only to label the block — the
            visibility check is independent.
        db: SQLAlchemy session.

    Returns:
        A JSON-friendly dict shaped like::

            {
                "block_type": "cb_cmcp_artifact_summary",
                "artifact_id": <int>,
                "subject": <str>,                  # artifact.title
                "content_type": <str>,             # artifact.guide_type
                "description": <str>,              # 1-line summary
                "open_link": <str>,                # /parent/companion/<id>
                "kid_name": <str | None>,          # first name or None
            }

        Returns ``None`` when:
        - The artifact does not exist.
        - The artifact's state is not in ``{APPROVED, SELF_STUDY}``
          (DRAFT, IN_REVIEW, ARCHIVED, etc. are skipped).
        - The parent has no visibility to the artifact (cross-family
          / unrelated).
    """
    # Lazy import to keep the renderer module light and to avoid
    # eager-loading the SQLAlchemy registry at process start (mirrors
    # CB-CMCP-001 service layer convention).
    from app.models.study_guide import StudyGuide

    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
    )
    if artifact is None:
        logger.debug(
            "digest.cmcp_summary.skip reason=missing artifact_id=%s parent_id=%s",
            artifact_id,
            parent_id,
        )
        return None

    state = getattr(artifact, "state", None)
    if state not in _PARENT_VISIBLE_STATES:
        logger.debug(
            "digest.cmcp_summary.skip reason=state artifact_id=%s state=%s parent_id=%s",
            artifact_id,
            state,
            parent_id,
        )
        return None

    # Compute the parent's linked-children id sets once and share
    # across the visibility gate + kid-name resolver. The dispatcher
    # (3C-1) calls this renderer per-artifact-per-parent, so cutting
    # the per-call query count from 4 → 2 directly trims the digest
    # worker's hot-path latency.
    linked_student_ids, linked_user_ids = _resolve_linked_children(
        db, parent_id=parent_id
    )

    if not _parent_can_see_artifact(
        db,
        parent_id=parent_id,
        artifact=artifact,
        linked_child_student_ids=linked_student_ids,
        linked_child_user_ids=linked_user_ids,
    ):
        logger.info(
            "digest.cmcp_summary.skip reason=visibility artifact_id=%s parent_id=%s",
            artifact_id,
            parent_id,
        )
        return None

    description = _derive_one_line_description(artifact)
    kid_name = _resolve_kid_name(
        db,
        parent_id=parent_id,
        kid_id=kid_id,
        artifact=artifact,
        linked_child_user_ids=linked_user_ids,
    )
    open_link = _build_open_link(artifact_id)

    block: dict[str, Any] = {
        "block_type": BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY,
        "artifact_id": artifact_id,
        "subject": getattr(artifact, "title", "") or "",
        "content_type": getattr(artifact, "guide_type", "") or "",
        "description": description,
        "open_link": open_link,
        "kid_name": kid_name,
    }
    logger.info(
        "digest.cmcp_summary.rendered artifact_id=%s parent_id=%s kid_name=%s state=%s",
        artifact_id,
        parent_id,
        kid_name,
        state,
        extra={
            "event": "digest.cmcp_summary.rendered",
            "artifact_id": artifact_id,
            "parent_id": parent_id,
            "state": state,
        },
    )
    return block


# ---------------------------------------------------------------------------
# Local block registry
# ---------------------------------------------------------------------------

# Maps ``block_type`` → renderer callable. The unified-digest surface
# dispatcher (3C-1, Wave 2) is the single consumer of this mapping. The
# registry shape is intentionally a plain dict so 3C-1 can read it
# directly without taking a hard import dependency on the renderer
# module beyond ``DIGEST_BLOCK_RENDERERS``.
#
# Sibling stripe 3C-2 will add ``cb_dci_coach_card`` to this dict when
# its renderer lands; do not gate that addition on this stripe.
DIGEST_BLOCK_RENDERERS: dict[str, Any] = {
    BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY: render_cb_cmcp_artifact_summary,
}


__all__ = [
    "BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY",
    "DIGEST_BLOCK_RENDERERS",
    "render_cb_cmcp_artifact_summary",
]
