"""MCP tool: ``get_artifact`` — role-scoped artifact retrieval.

CB-CMCP-001 M2-B 2B-2 (#4553) — fetch a single ``study_guides`` row by id
with FR-05-aligned visibility checks.

CB-CMCP-001 M3α 3B-3 (#4585) — SELF_STUDY artifacts (D3=C parent/student
self-initiated) are visible only to the requestor + their parent/child
family pair. They are NOT visible to the broader class roster, the
course teacher, BOARD_ADMIN, or CURRICULUM_ADMIN.

Storage note (M3 dependency)
----------------------------
Per locked decision D2=B and ``requirements/features-part7.md §6.150``,
**M1 is no-persistence**: there are NO CMCP-generated ``study_guides``
rows yet — generation pipelines compose + return artifacts in-memory.
Persistence lands in M3. This tool MUST therefore work for *non-CMCP
study_guides too* (existing CB-ASGF-001 / CB-UTDF-001 artifacts already
in the table) — visibility scoping uses the existing ``StudyGuide``
columns + parent/student/course relationships rather than CMCP-specific
markers.

The full row dict returned to the caller includes every M0/M1-stamped
column (``se_codes``, ``alignment_score``, ``state``, ``board_id``,
``voice_module_hash``, ``ai_engine``, etc.) so MCP clients can drive
both legacy and CMCP-aware UI surfaces from one tool result.

Failure modes
-------------
- Unknown ``artifact_id``                         → :class:`MCPToolNotFoundError`
  (the route layer maps to 404).
- Caller's role lacks visibility to the artifact  → :class:`MCPToolAccessDeniedError`
  (the route layer maps to 403).

We intentionally raise distinct exceptions (rather than returning the
same ``404 not found`` for both unknown-id and access-denied) because the
MCP transport surface is for authenticated callers with already-vetted
role allowlists — the catalog filter has already gated which roles can
even invoke ``get_artifact``. Differentiating 403 vs 404 inside the
authenticated surface gives operators clean telemetry on access-denied
events without leaking artifact-existence to anonymous probers (which
the ``mcp.enabled`` flag + auth dependency already block).

Visibility matrix
-----------------
======================  ================================================
Role                    Access
======================  ================================================
PARENT                   own artifacts (``user_id == self.id``) OR any
                         artifact whose ``user_id`` is one of the
                         caller's linked-children user_ids (via the
                         ``parent_students`` join)
STUDENT                  own artifacts only (``user_id == self.id``)
TEACHER                  own artifacts, OR artifacts whose ``course_id``
                         is a course the caller teaches (matched via
                         ``courses.teacher_id == teachers.id`` for the
                         caller's ``Teacher`` row, or
                         ``courses.created_by_user_id == self.id``)
BOARD_ADMIN              artifacts whose ``board_id`` matches the
                         caller's board. ``board_id`` is M3-E and may be
                         ``None`` on legacy rows — to avoid a permissive
                         "BOARD_ADMIN sees everything unscoped" failure
                         mode, BOARD_ADMINs are *denied* artifacts with
                         ``board_id IS NULL`` until M3-E ships per-row
                         board stamping. CURRICULUM_ADMIN / ADMIN remain
                         the catch-all "see everything" roles.
CURRICULUM_ADMIN         all artifacts (catalog + curriculum work needs
                         cross-board read).
ADMIN                    all artifacts.
======================  ================================================

SELF_STUDY override (3B-3 / #4585)
----------------------------------
When ``artifact.state == 'SELF_STUDY'`` (D3=C parent/student self-init),
the matrix above is *narrowed* to a family-only window:

- The requestor (``artifact.user_id == user.id``) — always.
- If the requestor is a STUDENT, that student's linked PARENTS (via
  ``parent_students``) — so a parent can see their kid's self-study
  artifact.
- If the requestor is a PARENT, that parent's linked CHILDREN'S user
  ids — so a child can see their parent's self-study artifact (rare in
  practice, but the relationship is symmetric).
- ADMIN — kept as the catch-all override (debug + ops).
- CURRICULUM_ADMIN, BOARD_ADMIN, TEACHER (incl. course teacher) →
  DENIED. SELF_STUDY is not class-distributable; the class roster +
  ministry roles don't need read access to private learner artifacts.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.mcp.tools._errors import (
    MCPToolAccessDeniedError,
    MCPToolNotFoundError,
)
from app.mcp.tools._visibility import resolve_caller_board_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool-specific exceptions — translated to HTTP statuses by the route layer.
# ---------------------------------------------------------------------------
#
# CB-CMCP-001 M2 follow-up (#4566) — the artifact-specific exception
# names were consolidated into the shared
# :mod:`app.mcp.tools._errors` module so every M2-B tool raises the
# same domain exception types. The dispatcher's translation layer is
# the single source of truth for the exception → HTTP-status mapping.


# ---------------------------------------------------------------------------
# Visibility matrix
# ---------------------------------------------------------------------------


def _self_study_family_can_view(
    artifact: Any, user: Any, db: Session
) -> bool:
    """Family-only visibility check for SELF_STUDY artifacts (3B-3 / #4585).

    SELF_STUDY artifacts (D3=C self-initiated by parent or student) are
    private to a family pair. This helper returns True iff:

    - ``user`` is the requestor (``artifact.user_id == user.id``), OR
    - ``user`` is a PARENT linked to the STUDENT requestor (the
      artifact's ``user_id`` is one of the caller's linked-children
      user_ids), OR
    - ``user`` is a STUDENT whose linked PARENT is the requestor (the
      artifact's ``user_id`` belongs to a parent that this student is
      linked to via ``parent_students``).

    BOARD_ADMIN, CURRICULUM_ADMIN, and TEACHER are intentionally NOT
    granted access — SELF_STUDY is a private learner workspace and the
    class/board roster has no audit need on it. ADMIN is checked
    *before* this helper is consulted so the catch-all bypass still
    works for ops/debug. This matches the M3α 3B-3 acceptance:

      "Visible only to requestor + their parent/child. Not the broader
       class roster, not BOARD_ADMIN."
    """
    from app.models.student import Student, parent_students
    from app.models.user import User, UserRole

    # Creator always sees their own artifact.
    if artifact.user_id == user.id:
        return True

    # The owner of a SELF_STUDY artifact may be either a STUDENT or a
    # PARENT (D3=C lets either self-initiate). We resolve the owner's
    # role from the User row so we know which direction to walk the
    # parent_students association.
    owner = (
        db.query(User).filter(User.id == artifact.user_id).first()
    )
    if owner is None:
        # Defensive — a SELF_STUDY artifact whose owner row was deleted
        # has no family pair to consult, fail closed.
        return False

    # Caller is a PARENT — grant if the artifact owner is one of the
    # caller's linked children. We map parent → child Student rows →
    # child User ids, then check membership.
    if user.has_role(UserRole.PARENT) and owner.has_role(UserRole.STUDENT):
        child_student_ids = [
            row[0]
            for row in db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == user.id)
            .all()
        ]
        if child_student_ids:
            child_user_ids = [
                row[0]
                for row in db.query(Student.user_id)
                .filter(Student.id.in_(child_student_ids))
                .all()
            ]
            if artifact.user_id in child_user_ids:
                return True

    # Caller is a STUDENT — grant if the artifact owner is one of the
    # caller's linked parents. Symmetric to the PARENT branch above:
    # student → own Student row → parent_students → parent User ids,
    # then check membership.
    if user.has_role(UserRole.STUDENT) and owner.has_role(UserRole.PARENT):
        student_record = (
            db.query(Student).filter(Student.user_id == user.id).first()
        )
        if student_record is not None:
            parent_user_ids = [
                row[0]
                for row in db.query(parent_students.c.parent_id)
                .filter(parent_students.c.student_id == student_record.id)
                .all()
            ]
            if artifact.user_id in parent_user_ids:
                return True

    return False


def _user_can_view(artifact: Any, user: Any, db: Session) -> bool:
    """Apply the FR-05-aligned visibility matrix.

    ``user`` is expected to be a ``User`` row (with ``has_role`` /
    ``role`` / ``id``). ``artifact`` is a ``StudyGuide`` row. We rely on
    ``user.has_role(...)`` so multi-role users get the union of their
    roles' permissions (matches the existing
    :func:`can_access_parent_companion` semantics).

    SELF_STUDY override (#4585): when the artifact is in the SELF_STUDY
    state, only the requestor + their parent/child family pair (and
    ADMIN as catch-all) get access — TEACHER / BOARD_ADMIN /
    CURRICULUM_ADMIN are denied. The override is applied BEFORE the
    standard matrix below so non-family roles don't pick up access via
    the broader rules (e.g. CURRICULUM_ADMIN's "see everything").
    """
    # Lazy imports — keep the tool module importable without dragging in
    # the SQLAlchemy model layer at import time, mirrors how
    # ``app/mcp/tools/__init__.py`` keeps the registry decoupled.
    from app.models.course import Course
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState

    # ADMIN is the only catch-all that survives SELF_STUDY narrowing —
    # ops + debug visibility on private learner artifacts is intentional.
    # CURRICULUM_ADMIN does NOT get this bypass because SELF_STUDY is
    # not curriculum work; class-distributable APPROVED artifacts are
    # the curriculum admin's domain.
    if user.has_role(UserRole.ADMIN):
        return True

    # SELF_STUDY override — narrow to family + creator. Applied before
    # the standard matrix so e.g. CURRICULUM_ADMIN doesn't see SELF_STUDY
    # via the catch-all, and TEACHER doesn't see it via the course link.
    if artifact.state == ArtifactState.SELF_STUDY:
        return _self_study_family_can_view(artifact, user, db)

    # Non-SELF_STUDY: the standard FR-05 matrix.
    # CURRICULUM_ADMIN is the catch-all "see everything" role for
    # non-SELF_STUDY artifacts (catalog + curriculum work needs
    # cross-board read).
    if user.has_role(UserRole.CURRICULUM_ADMIN):
        return True

    # Creator always sees their own artifact, irrespective of role —
    # matches every existing study_guide route's first-pass check (see
    # ``app/api/routes/study.py``).
    if artifact.user_id == user.id:
        return True

    # PARENT — visibility extends to artifacts created by the caller's
    # linked children (the user_id on the artifact is the child's
    # User row id, which Student.user_id maps back to).
    if user.has_role(UserRole.PARENT):
        child_student_ids = [
            row[0]
            for row in db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == user.id)
            .all()
        ]
        if child_student_ids:
            child_user_ids = [
                row[0]
                for row in db.query(Student.user_id)
                .filter(Student.id.in_(child_student_ids))
                .all()
            ]
            if artifact.user_id in child_user_ids:
                return True

    # TEACHER — visibility via the artifact's course. Two valid links:
    # 1) ``courses.teacher_id`` references a Teacher row whose
    #    ``user_id`` is the caller, OR
    # 2) ``courses.created_by_user_id`` is the caller (parent-first
    #    teachers who created the course manually).
    if user.has_role(UserRole.TEACHER) and artifact.course_id is not None:
        course = (
            db.query(Course).filter(Course.id == artifact.course_id).first()
        )
        if course is not None:
            if course.created_by_user_id == user.id:
                return True
            teacher = (
                db.query(Teacher).filter(Teacher.user_id == user.id).first()
            )
            if teacher is not None and course.teacher_id == teacher.id:
                return True

    # BOARD_ADMIN — visibility scoped to the caller's board. ``board_id``
    # is nullable today (M3-E hasn't stamped legacy rows) so we
    # conservatively deny access to ``board_id IS NULL`` rows; otherwise
    # a BOARD_ADMIN with no resolvable board_id (the common case until
    # M3-E ships) would be granted blanket read on every legacy
    # artifact, which is the wrong direction for a least-privilege role.
    if user.has_role(UserRole.BOARD_ADMIN):
        caller_board = resolve_caller_board_id(user)
        if caller_board is not None and artifact.board_id is not None:
            if str(caller_board) == str(artifact.board_id):
                return True

    # STUDENT — owned artifacts only. Already handled by the
    # ``artifact.user_id == user.id`` short-circuit above; falling
    # through here means the student is requesting someone else's row,
    # which is denied.
    return False


# ---------------------------------------------------------------------------
# Row → dict serializer
# ---------------------------------------------------------------------------

# Columns surfaced in the response. Listed explicitly (rather than
# ``__table__.columns``) so the public shape stays stable as new columns
# land in M3+ — adding a column to ``StudyGuide`` should be an explicit
# decision to expose it via MCP, not an automatic side effect.
_ARTIFACT_FIELDS: tuple[str, ...] = (
    "id",
    "user_id",
    "assignment_id",
    "course_id",
    "course_content_id",
    "title",
    "content",
    "guide_type",
    "focus_prompt",
    "is_truncated",
    "version",
    "parent_guide_id",
    "content_hash",
    "relationship_type",
    "generation_context",
    "template_key",
    "num_questions",
    "difficulty",
    "answer_key_markdown",
    "weak_topics",
    "ai_engine",
    "parent_summary",
    "curriculum_codes",
    "suggestion_topics",
    "shared_with_user_id",
    "shared_at",
    "viewed_at",
    "viewed_count",
    # CB-CMCP-001 M0/M1-stamped curriculum columns
    "se_codes",
    "alignment_score",
    "ceg_version",
    "state",
    "board_id",
    "voice_module_hash",
    "class_context_envelope_summary",
    "requested_persona",
    "created_at",
    "archived_at",
)


def _serialize(artifact: Any) -> dict[str, Any]:
    """Project a ``StudyGuide`` row to a JSON-serializable dict.

    Datetime + Decimal fields are coerced to JSON-friendly forms
    (ISO-8601 / float) so the route layer's response model can encode
    the result without a custom encoder. ``None`` columns pass through
    unchanged so callers can distinguish "not yet stamped" (M0/M1
    columns on legacy rows) from explicit values.
    """
    from datetime import datetime
    from decimal import Decimal

    out: dict[str, Any] = {}
    for field in _ARTIFACT_FIELDS:
        value = getattr(artifact, field, None)
        if isinstance(value, datetime):
            out[field] = value.isoformat()
        elif isinstance(value, Decimal):
            # Numeric(4,3) — float is fine for JSON; preserves precision
            # to the column's defined scale.
            out[field] = float(value)
        else:
            out[field] = value
    return out


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def get_artifact_handler(
    arguments: Mapping[str, Any],
    current_user: Any,
    db: Session,
) -> dict[str, Any]:
    """Dispatch entry for the ``get_artifact`` MCP tool.

    Validates the arguments shape (``artifact_id`` must be an int — the
    registry's JSON Schema already enforces this for normal callers, but
    we re-check here so unit tests calling the handler directly cannot
    sidestep validation), looks up the artifact, applies the visibility
    matrix, and returns a ``{"artifact": {...}}`` envelope.

    The envelope (rather than returning the row dict directly) leaves
    room for non-breaking additions in later stripes — e.g. a
    ``provenance`` block surfacing CMCP generation metadata, or a
    ``related`` block linking sibling versions.
    """
    from app.models.study_guide import StudyGuide

    raw_id = arguments.get("artifact_id") if arguments else None
    if not isinstance(raw_id, int) or isinstance(raw_id, bool):
        # ``bool`` is a subclass of ``int`` in Python; reject it
        # explicitly so ``True``/``False`` doesn't silently become
        # ``1``/``0`` row lookups.
        raise MCPToolNotFoundError(
            "Argument 'artifact_id' must be an integer"
        )

    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == raw_id).first()
    )
    if artifact is None:
        raise MCPToolNotFoundError(
            f"No artifact with id={raw_id}"
        )

    if not _user_can_view(artifact, current_user, db):
        # Log at INFO so ops can spot access-denied events without
        # routing them to WARN/ERROR (the user is authenticated; this
        # is an authorization-layer outcome, not a bug).
        logger.info(
            "mcp.get_artifact.denied artifact_id=%s user_id=%s role=%s",
            raw_id,
            current_user.id,
            getattr(current_user.role, "value", None),
        )
        raise MCPToolAccessDeniedError(
            f"Access denied to artifact {raw_id}"
        )

    return {"artifact": _serialize(artifact)}


__all__ = [
    "_self_study_family_can_view",
    "_user_can_view",
    "get_artifact_handler",
]
