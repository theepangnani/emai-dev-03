"""CB-CMCP-001 M3α follow-up #4635 — class-distribute fan-out.

Covers
------
- A TEACHER-authored APPROVED artifact with ``course_id`` set fans out to
  EVERY enrolled student's linked parent (one row per parent per surface
  per kid), plus an audit row for the teacher (owner).
- Co-parents on the same enrolled student both get a row.
- Multiple enrolled students all get rows.
- A class with zero enrolled students still records the teacher's owner
  audit row (preserves legacy contract).

Per-row visibility checks in 3C-2 / 3C-3 renderers gate the actual
delivery; this stripe asserts only that the ``cmcp_surface_dispatches``
table has rows the unified digest worker (CB-PEDI-002 V2) can scan.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD


# ── User + course + artifact helpers ──────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcpfanout_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPFanout {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher_user(db_session):
    from app.models.teacher import Teacher
    from app.models.user import UserRole

    user = _make_user(db_session, UserRole.TEACHER)
    teacher = Teacher(user_id=user.id, full_name=user.full_name)
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return user


def _make_course(db_session, teacher_user):
    from app.models.course import Course

    course = Course(
        name=f"CMCP Fanout Course {uuid4().hex[:6]}",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


def _make_student(db_session, *, grade_level=5):
    from app.models.student import Student
    from app.models.user import UserRole

    user = _make_user(db_session, UserRole.STUDENT)
    student = Student(user_id=user.id, grade_level=grade_level)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


def _link_parent(db_session, *, parent_user, student):
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id, student_id=student.id
        )
    )
    db_session.commit()


def _enroll(db_session, *, student, course):
    from app.models.course import student_courses

    db_session.execute(
        student_courses.insert().values(
            student_id=student.id, course_id=course.id
        )
    )
    db_session.commit()


def _seed_artifact(
    db_session,
    *,
    user_id: int,
    course_id: int | None,
    state: str,
    title: str | None = None,
    content: str = "Some prompt body.",
    requested_persona: str = "teacher",
    se_codes: list[str] | None = None,
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title or f"Fanout test {uuid4().hex[:6]}",
        content=content,
        guide_type="quiz",
        state=state,
        requested_persona=requested_persona,
        se_codes=se_codes or ["B2.1"],
        voice_module_hash="b" * 64,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ── Tests ─────────────────────────────────────────────────────────────


def test_class_fanout_to_enrolled_parents(db_session, teacher_user):
    """Teacher approves class-distributed artifact → fan out to enrolled parents."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)

    # Two students enrolled, each with a single parent.
    student_a = _make_student(db_session)
    student_b = _make_student(db_session)
    parent_a = _make_user(db_session, UserRole.PARENT)
    parent_b = _make_user(db_session, UserRole.PARENT)
    _link_parent(db_session, parent_user=parent_a, student=student_a)
    _link_parent(db_session, parent_user=parent_b, student=student_b)
    _enroll(db_session, student=student_a, course=course)
    _enroll(db_session, student=student_b, course=course)

    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    # 3 surfaces × (1 owner + 2 parents) = 9 rows.
    assert len(rows) == 9

    # Per-surface: parent_a + parent_b should both have a row, plus one
    # owner-only row keyed by the teacher.
    by_surface: dict[str, list[CMCPSurfaceDispatch]] = {}
    for row in rows:
        by_surface.setdefault(row.surface, []).append(row)

    for surface in ("bridge", "dci", "digest"):
        surface_rows = by_surface[surface]
        # 1 owner + 2 enrolled parents = 3.
        assert len(surface_rows) == 3, surface

        owner_rows = [
            r
            for r in surface_rows
            if r.parent_id == teacher_user.id and r.kid_id is None
        ]
        assert len(owner_rows) == 1, f"{surface} missing owner audit row"

        parent_rows = [r for r in surface_rows if r.kid_id is not None]
        kids_by_parent = {(r.parent_id, r.kid_id) for r in parent_rows}
        assert kids_by_parent == {
            (parent_a.id, student_a.id),
            (parent_b.id, student_b.id),
        }, f"{surface} parent fan-out mismatch: {kids_by_parent}"

        for r in surface_rows:
            assert r.status == "ok"


def test_class_fanout_co_parents_both_get_rows(db_session, teacher_user):
    """Co-parents on the same enrolled student both get a row."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)

    student = _make_student(db_session)
    parent_a = _make_user(db_session, UserRole.PARENT)
    parent_b = _make_user(db_session, UserRole.PARENT)
    _link_parent(db_session, parent_user=parent_a, student=student)
    _link_parent(db_session, parent_user=parent_b, student=student)
    _enroll(db_session, student=student, course=course)

    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    # 3 surfaces × (1 owner + 2 co-parents) = 9 rows.
    assert len(rows) == 9

    # Per-surface, both co-parents must have a row keyed to the same kid.
    for surface in ("bridge", "dci", "digest"):
        s_rows = [r for r in rows if r.surface == surface]
        parent_kid = {
            (r.parent_id, r.kid_id)
            for r in s_rows
            if r.kid_id is not None
        }
        assert parent_kid == {
            (parent_a.id, student.id),
            (parent_b.id, student.id),
        }, f"{surface}: {parent_kid}"


def test_class_fanout_empty_enrollment_keeps_owner_only(
    db_session, teacher_user
):
    """Class with zero enrolled students → only owner audit row remains."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)

    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    # 3 surfaces × 1 owner-only = 3 rows.
    assert len(rows) == 3
    for row in rows:
        assert row.parent_id == teacher_user.id
        assert row.kid_id is None


def test_class_fanout_enrolled_student_with_no_parents_skipped(
    db_session, teacher_user
):
    """Enrolled student with no linked parents → only owner row recorded.

    The join (student_courses ⋈ parent_students) yields no rows for an
    orphan student, so the dispatcher writes only the owner's audit row
    for that surface. Parent fan-out for ANY linked enrolled student
    still works.
    """
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)

    # Student A: linked to a parent. Student B: orphan (no parent link).
    student_a = _make_student(db_session)
    student_b = _make_student(db_session)
    parent_a = _make_user(db_session, UserRole.PARENT)
    _link_parent(db_session, parent_user=parent_a, student=student_a)
    _enroll(db_session, student=student_a, course=course)
    _enroll(db_session, student=student_b, course=course)

    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    # 3 surfaces × (1 owner + 1 linked-parent) = 6 rows. Orphan
    # student B contributes no rows because the join finds no match.
    assert len(rows) == 6
    for surface in ("bridge", "dci", "digest"):
        s_rows = [r for r in rows if r.surface == surface]
        kid_rows = [r for r in s_rows if r.kid_id is not None]
        assert len(kid_rows) == 1
        assert kid_rows[0].parent_id == parent_a.id
        assert kid_rows[0].kid_id == student_a.id


def test_teacher_authored_no_course_keeps_owner_only(db_session, teacher_user):
    """Teacher artifact without ``course_id`` → legacy single-owner behavior."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=None,
        state=ArtifactState.APPROVED,
    )

    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    assert len(rows) == 3
    for row in rows:
        assert row.parent_id == teacher_user.id
        assert row.kid_id is None
