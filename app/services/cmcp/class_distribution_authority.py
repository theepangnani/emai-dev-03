"""CB-CMCP-001 M3α 3B-1 (#4577) — class-distribution authority guard.

Companion to ``artifact_persistence._resolve_state`` (Wave 0). The
state machine resolves PENDING_REVIEW for ``TEACHER + course_id`` and
SELF_STUDY for everyone else; this module enforces the *authority*
half of D3=C — only the teacher who owns the course may class-
distribute an artifact through the review queue.

D3=C authority rules
--------------------
- PARENT / STUDENT requestor with ``course_id`` set → 403. Parents
  can request distribution to a class, but only via a teacher hand-
  off (out of scope for M3α — see #4577 acceptance § "PARENT cross-
  class denied"). The simple rule for now is "no direct path".
- TEACHER requestor with ``course_id`` not owned by them → 403.
  Ownership is checked against ``Course.created_by_user_id`` (the
  same column journey-hint, csv-import, and timeline services use
  for teacher-of-course attribution).
- ADMIN / BOARD_ADMIN / CURRICULUM_ADMIN with ``course_id`` →
  allowed. Admins can author class-distributed artifacts on behalf
  of teachers; the review queue itself is still teacher-driven, so
  this is a narrow path used by curriculum-admin workflows.
- All other shapes (no ``course_id``, or non-teacher self-init) →
  no-op. The state resolver routes them to SELF_STUDY automatically.

Pure function, no side effects beyond raising HTTPException. Lives
in ``app.services.cmcp`` so the route + stream + future MCP surface
share one rule set.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


# Roles permitted to author a class-distributed (PENDING_REVIEW) artifact
# when ``course_id`` is supplied. PARENT + STUDENT are deliberately *not*
# in this set — they can self-initiate (SELF_STUDY) but not class-
# distribute. ADMIN tier is included so curriculum-admin workflows can
# author on behalf of a teacher; the review queue itself remains the
# teacher's surface.
_CLASS_DISTRIBUTE_ROLES: frozenset[UserRole] = frozenset(
    {
        UserRole.TEACHER,
        UserRole.ADMIN,
        UserRole.BOARD_ADMIN,
        UserRole.CURRICULUM_ADMIN,
    }
)


def validate_class_distribution_authority(
    *,
    user: User,
    course_id: int | None,
    db: Session,
) -> None:
    """Raise 403 if *user* is not authorized to class-distribute a
    CMCP artifact for *course_id*.

    No-op when ``course_id`` is ``None`` — the state resolver routes
    those to SELF_STUDY without authority checks.

    Raises
    ------
    HTTPException(403)
        - Requestor is PARENT or STUDENT and ``course_id`` is set.
        - Requestor is TEACHER and does not own ``course_id``.
        - Requestor's role is not in the class-distribute allowlist
          (defensive — covers a NULL role on a pending-onboarding user
          attempting the class-distribute path).
    HTTPException(404)
        - ``course_id`` is set but no matching ``Course`` row exists.
          404 (not 403) so we don't leak whether a course exists to
          callers who should have been able to access one.
    """
    if course_id is None:
        return

    if user.role in (UserRole.PARENT, UserRole.STUDENT):
        # Parents can request class distribution via a teacher hand-off
        # path (post-M3α), but never directly. Surface a 403 with a
        # message that points at the route, not at the user's role —
        # keeps the error human-readable while still being deterministic
        # for tests.
        logger.info(
            "cmcp.authority.deny role=%s user_id=%s course_id=%s "
            "reason=parent_or_student_class_distribute",
            user.role.value if user.role else None,
            user.id,
            course_id,
            extra={
                "event": "cmcp.authority.deny",
                "role": user.role.value if user.role else None,
                "user_id": user.id,
                "course_id": course_id,
                "reason": "parent_or_student_class_distribute",
            },
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Only teachers (or admins on their behalf) may submit a "
                "class-distributed artifact for review. Drop course_id "
                "to generate a self-study artifact instead."
            ),
        )

    if user.role not in _CLASS_DISTRIBUTE_ROLES:
        # Defensive — covers NULL role (pending-onboarding) trying to
        # class-distribute. The state resolver would still bucket this
        # into SELF_STUDY since the role isn't TEACHER, but we deny
        # explicitly so the row never even gets a course_id stamped.
        logger.info(
            "cmcp.authority.deny role=%s user_id=%s course_id=%s "
            "reason=role_not_in_class_distribute_allowlist",
            user.role.value if user.role else None,
            user.id,
            course_id,
            extra={
                "event": "cmcp.authority.deny",
                "role": user.role.value if user.role else None,
                "user_id": user.id,
                "course_id": course_id,
                "reason": "role_not_in_class_distribute_allowlist",
            },
        )
        raise HTTPException(
            status_code=403,
            detail="Role not authorized to class-distribute artifacts.",
        )

    # ADMIN / BOARD_ADMIN / CURRICULUM_ADMIN bypass the per-course
    # ownership check — they can author on any course in their scope.
    # M3-E will narrow this to board-scoped admins; for M3α we accept
    # the broader scope per the D3=C locked decision.
    if user.role != UserRole.TEACHER:
        return

    course = (
        db.query(Course).filter(Course.id == course_id).first()
    )
    if course is None:
        # 404 not 403 so we don't disclose existence to callers who
        # already failed the role gate above. Same shape as the
        # cmcp parent-companion GET endpoint's "no leak" 404 pattern.
        raise HTTPException(
            status_code=404, detail=f"Course {course_id} not found"
        )

    if course.created_by_user_id != user.id:
        logger.info(
            "cmcp.authority.deny role=teacher user_id=%s course_id=%s "
            "owner_id=%s reason=teacher_not_course_owner",
            user.id,
            course_id,
            course.created_by_user_id,
            extra={
                "event": "cmcp.authority.deny",
                "role": "teacher",
                "user_id": user.id,
                "course_id": course_id,
                "owner_id": course.created_by_user_id,
                "reason": "teacher_not_course_owner",
            },
        )
        raise HTTPException(
            status_code=403,
            detail=(
                f"Teacher {user.id} does not own course {course_id}; "
                "cannot class-distribute."
            ),
        )


__all__ = ["validate_class_distribution_authority"]
