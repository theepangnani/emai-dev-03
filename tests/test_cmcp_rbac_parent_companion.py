"""Tests for CB-CMCP-001 M1-F 1F-5 — Parent Companion RBAC matrix (#4499).

Covers the FR-05 access-control matrix amendment for
``content_type=PARENT_COMPANION`` artifacts:

============================  =====================================
Role                          Access
============================  =====================================
STUDENT                        NO
PARENT (own child only)        yes — child enrolled in artifact's
                               course, OR parent is the creator
PARENT (other child)           NO
TEACHER (assigned class)       yes
TEACHER (other class)          NO
CURRICULUM_ADMIN               yes (any artifact)
BOARD_ADMIN                    NO
ADMIN                          yes (any artifact)
============================  =====================================

Tests use the shared SQLite test app from ``conftest.py``.

Implementation note: model imports happen *inside* each test/fixture
rather than at module top — see ``test_cmcp_auth_roles.py`` for the
rationale (session-scoped ``app`` fixture reloads ``app.models``).
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from conftest import PASSWORD


# ───────────────────────────────────────────────────────────────────────────
# User fixtures — one per role on the matrix
# ───────────────────────────────────────────────────────────────────────────


def _make_user(db_session, role, *, full_name=None, email_prefix=None):
    """Build + persist a User with the given role. Returns the User row."""
    from app.core.security import get_password_hash
    from app.models.user import User

    prefix = email_prefix or f"cmcp_pc_{role.name.lower()}"
    user = User(
        email=f"{prefix}_{uuid4().hex[:8]}@test.com",
        full_name=full_name or f"Companion Test {role.name}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student_user(db_session):
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.PARENT)


@pytest.fixture()
def unrelated_parent_user(db_session):
    """A second parent who has NO link to the test student."""
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.PARENT, email_prefix="cmcp_pc_unrelated_parent")


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def other_teacher_user(db_session):
    """A second teacher who is NOT assigned to the artifact's course."""
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.TEACHER, email_prefix="cmcp_pc_other_teacher")


@pytest.fixture()
def curriculum_admin_user(db_session):
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.CURRICULUM_ADMIN)


@pytest.fixture()
def board_admin_user(db_session):
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.BOARD_ADMIN)


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole
    return _make_user(db_session, UserRole.ADMIN)


# ───────────────────────────────────────────────────────────────────────────
# Student / parent linkage / course / artifact fixtures
# ───────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def student_record(db_session, student_user):
    from app.models.student import Student

    s = Student(
        user_id=student_user.id,
        grade_level=8,
        school_name="CMCP Companion Test School",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture()
def linked_parent(db_session, parent_user, student_record):
    """Parent linked to the test student via ``parent_students``."""
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=student_record.id,
        )
    )
    db_session.commit()
    return parent_user


@pytest.fixture()
def teacher_record(db_session, teacher_user):
    from app.models.teacher import Teacher

    t = Teacher(user_id=teacher_user.id, school_name="CMCP Companion Test School")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def other_teacher_record(db_session, other_teacher_user):
    """A Teacher row for the unrelated teacher fixture."""
    from app.models.teacher import Teacher

    t = Teacher(user_id=other_teacher_user.id, school_name="Different School")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def course_with_student(db_session, student_record, teacher_record):
    """Course assigned to ``teacher_record`` and enrolling ``student_record``."""
    from app.models.course import Course, student_courses

    c = Course(
        name="Companion Test Course",
        subject="Math",
        teacher_id=teacher_record.id,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    db_session.execute(
        student_courses.insert().values(
            student_id=student_record.id,
            course_id=c.id,
        )
    )
    db_session.commit()
    return c


@pytest.fixture()
def companion_artifact(db_session, course_with_student, teacher_user):
    """A PARENT_COMPANION artifact (StudyGuide row) for the test course.

    Created by the assigned teacher, attached to ``course_with_student``.
    Other tests vary the ``user_id`` / ``course_id`` directly when they
    need a different ownership shape.
    """
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=teacher_user.id,
        course_id=course_with_student.id,
        title="Parent Companion: Cell Division",
        content="# Companion summary",
        guide_type="study_guide",  # M1-F maps PARENT_COMPANION → study_guide
        state="DRAFT",
        requested_persona="parent",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


# ───────────────────────────────────────────────────────────────────────────
# can_access_parent_companion — the matrix, role by role
# ───────────────────────────────────────────────────────────────────────────


def test_student_denied(db_session, student_user, companion_artifact):
    """STUDENT role gets NO Parent Companion access (FR-05)."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, student_user, companion_artifact.id)
        is False
    )


def test_parent_with_linked_child_allowed(
    db_session, linked_parent, companion_artifact
):
    """PARENT with a linked child enrolled in the course → access granted."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, linked_parent, companion_artifact.id)
        is True
    )


def test_parent_without_linked_child_denied(
    db_session, unrelated_parent_user, companion_artifact
):
    """PARENT not linked to any child in the course → no access."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(
            db_session, unrelated_parent_user, companion_artifact.id
        )
        is False
    )


def test_parent_whose_child_is_not_enrolled_denied(
    db_session, parent_user, course_with_student, companion_artifact
):
    """PARENT linked to a *different* child not enrolled in the course → denied.

    Locks the "own child only" half of FR-05: a parent linked to some
    student who is NOT in the artifact's course must still be denied.
    """
    from app.core.security import get_password_hash
    from app.models.student import Student, parent_students
    from app.models.user import User, UserRole

    # Backing User for the other-child Student row (NOT NULL on user_id).
    other_student_user = User(
        email=f"cmcp_pc_other_kid_{uuid4().hex[:8]}@test.com",
        full_name="Other Kid",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(other_student_user)
    db_session.commit()
    db_session.refresh(other_student_user)

    # Create an unrelated student NOT enrolled in the companion's course.
    other_student = Student(
        user_id=other_student_user.id,
        grade_level=7,
        school_name="Other School",
    )
    db_session.add(other_student)
    db_session.commit()
    db_session.refresh(other_student)

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=other_student.id,
        )
    )
    db_session.commit()

    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, parent_user, companion_artifact.id)
        is False
    )


def test_teacher_owns_class_allowed(db_session, teacher_user, companion_artifact):
    """TEACHER assigned to the artifact's course → access granted."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, teacher_user, companion_artifact.id)
        is True
    )


def test_teacher_other_class_denied(
    db_session, other_teacher_user, other_teacher_record, companion_artifact
):
    """TEACHER not assigned to the artifact's course → denied."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(
            db_session, other_teacher_user, companion_artifact.id
        )
        is False
    )


def test_curriculum_admin_allowed(
    db_session, curriculum_admin_user, companion_artifact
):
    """CURRICULUM_ADMIN gets access to any Parent Companion artifact."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(
            db_session, curriculum_admin_user, companion_artifact.id
        )
        is True
    )


def test_board_admin_denied(db_session, board_admin_user, companion_artifact):
    """BOARD_ADMIN gets NO Parent Companion access (FR-05)."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(
            db_session, board_admin_user, companion_artifact.id
        )
        is False
    )


def test_admin_allowed(db_session, admin_user, companion_artifact):
    """ADMIN gets access to any Parent Companion artifact."""
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, admin_user, companion_artifact.id)
        is True
    )


# ───────────────────────────────────────────────────────────────────────────
# can_access_parent_companion — edge cases
# ───────────────────────────────────────────────────────────────────────────


def test_missing_artifact_returns_false(db_session, admin_user):
    """Helper returns False (not raise) when the artifact does not exist.

    Routes that need to distinguish 404 from 403 should check first.
    The dependency factory below converts this to a 404.
    """
    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, admin_user, artifact_id=999_999)
        is False
    )


def test_multi_role_parent_plus_board_admin_allowed(
    db_session, student_record, companion_artifact
):
    """A user with BOTH PARENT and BOARD_ADMIN roles still gets access via PARENT.

    The matrix says BOARD_ADMIN alone is denied, but BOARD_ADMIN is not a
    *veto* — it is just not a grant. A multi-role user passes through any
    role that grants access.
    """
    from app.core.security import get_password_hash
    from app.models.student import parent_students
    from app.models.user import User, UserRole

    # Create a multi-role user: primary PARENT + BOARD_ADMIN in roles col.
    user = User(
        email=f"cmcp_pc_multi_{uuid4().hex[:8]}@test.com",
        full_name="Multi Role Parent + Board Admin",
        role=UserRole.PARENT,
        roles="parent,BOARD_ADMIN",
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Link as parent of the enrolled student.
    db_session.execute(
        parent_students.insert().values(
            parent_id=user.id,
            student_id=student_record.id,
        )
    )
    db_session.commit()

    from app.api.deps import can_access_parent_companion

    assert user.has_role(UserRole.PARENT) is True
    assert user.has_role(UserRole.BOARD_ADMIN) is True
    assert (
        can_access_parent_companion(db_session, user, companion_artifact.id) is True
    )


def test_multi_role_student_plus_admin_allowed(
    db_session, companion_artifact
):
    """A user with both STUDENT (primary) and ADMIN role gets access via ADMIN.

    Pure-STUDENT is denied; STUDENT + ADMIN passes via ADMIN bypass.
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"cmcp_pc_stu_admin_{uuid4().hex[:8]}@test.com",
        full_name="Student + Admin",
        role=UserRole.STUDENT,
        roles="student,admin",
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, user, companion_artifact.id) is True
    )


def test_parent_creator_self_generated_companion_allowed(
    db_session, linked_parent, course_with_student
):
    """A parent who self-generated the companion (D3=C SELF_STUDY) keeps access.

    Even if the artifact has no course (SELF_STUDY case), the creator
    gets access provided their role is PARENT or TEACHER (not pure-STUDENT).
    """
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=linked_parent.id,
        course_id=None,  # SELF_STUDY case — no course
        title="Self-generated companion",
        content="# Self companion",
        guide_type="study_guide",
        state="SELF_STUDY",
        requested_persona="parent",
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)

    from app.api.deps import can_access_parent_companion

    assert (
        can_access_parent_companion(db_session, linked_parent, sg.id) is True
    )


# ───────────────────────────────────────────────────────────────────────────
# require_parent_companion_access — dependency factory wired into a route
# ───────────────────────────────────────────────────────────────────────────


def _build_companion_app(app, artifact_id):
    """Mount a tiny isolated route that uses ``require_parent_companion_access``.

    Mirrors the helper in ``test_cmcp_auth_roles.py`` — copies the test app's
    dependency overrides (so ``get_db`` keeps pointing at the SQLite fixture).
    """
    from app.api.deps import require_parent_companion_access

    sub_app = FastAPI()

    @sub_app.get("/probe-companion")
    def probe(user=Depends(require_parent_companion_access(artifact_id))):
        return {"ok": True, "user_id": user.id}

    sub_app.dependency_overrides = dict(app.dependency_overrides)
    return sub_app


def test_require_parent_companion_access_403_for_student(
    app, db_session, student_user, companion_artifact
):
    """The dependency 403s for a pure-STUDENT user."""
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, companion_artifact.id)
    sub_app.dependency_overrides[get_current_user] = lambda: student_user

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 403, resp.text
        assert "Parent Companion" in resp.json().get("detail", "")


def test_require_parent_companion_access_403_for_board_admin(
    app, db_session, board_admin_user, companion_artifact
):
    """The dependency 403s for a BOARD_ADMIN user (FR-05)."""
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, companion_artifact.id)
    sub_app.dependency_overrides[get_current_user] = lambda: board_admin_user

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 403, resp.text


def test_require_parent_companion_access_200_for_linked_parent(
    app, db_session, linked_parent, companion_artifact
):
    """The dependency 200s for a parent linked to an enrolled child."""
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, companion_artifact.id)
    sub_app.dependency_overrides[get_current_user] = lambda: linked_parent

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 200, resp.text
        assert resp.json()["ok"] is True


def test_require_parent_companion_access_200_for_teacher(
    app, db_session, teacher_user, companion_artifact
):
    """The dependency 200s for the assigned teacher of the artifact's course."""
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, companion_artifact.id)
    sub_app.dependency_overrides[get_current_user] = lambda: teacher_user

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 200, resp.text


def test_require_parent_companion_access_200_for_curriculum_admin(
    app, db_session, curriculum_admin_user, companion_artifact
):
    """The dependency 200s for CURRICULUM_ADMIN."""
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, companion_artifact.id)
    sub_app.dependency_overrides[get_current_user] = lambda: curriculum_admin_user

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 200, resp.text


def test_require_parent_companion_access_200_for_admin(
    app, db_session, admin_user, companion_artifact
):
    """The dependency 200s for ADMIN."""
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, companion_artifact.id)
    sub_app.dependency_overrides[get_current_user] = lambda: admin_user

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 200, resp.text


def test_require_parent_companion_access_404_for_missing_artifact(
    app, db_session, admin_user
):
    """The dependency 404s when the artifact id does not exist.

    This is independent of role — even ADMIN gets 404 (not 403) so the
    error mode mirrors a typical REST resource lookup.
    """
    from app.api.deps import get_current_user

    sub_app = _build_companion_app(app, artifact_id=999_999)
    sub_app.dependency_overrides[get_current_user] = lambda: admin_user

    with TestClient(sub_app) as client:
        resp = client.get("/probe-companion")
        assert resp.status_code == 404, resp.text
