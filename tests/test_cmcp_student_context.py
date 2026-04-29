"""Tests for CB-CMCP-001 M1-B 1B-1 student-context service (#4460).

Covers
------

- ``get_student_profile`` happy path returns enrolled courses for a
  parent linked via ``parent_students``.
- RBAC: PARENT not linked to the student → 403.
- RBAC: PARENT linked to the student → 200.
- RBAC: TEACHER assigned to the course where the student is enrolled
  → 200.
- 404 when ``student_id`` is unknown.
- The 5-minute cache returns the same payload on a second call without
  re-querying — verified by counting ``Session.query`` invocations
  through a wrapped session.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD


# ── User / Student / Teacher fixtures ──


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"cmcp_parent_{uuid4().hex[:8]}@test.com",
        full_name="CMCP Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def unrelated_parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"cmcp_unrelated_{uuid4().hex[:8]}@test.com",
        full_name="CMCP Unrelated Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"cmcp_student_{uuid4().hex[:8]}@test.com",
        full_name="CMCP Student",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student(db_session, student_user):
    from app.models.student import Student

    s = Student(
        user_id=student_user.id,
        grade_level=8,
        school_name="CMCP Test School",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture()
def linked_parent(db_session, parent_user, student):
    """Parent linked to ``student`` via ``parent_students``."""
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=student.id,
        )
    )
    db_session.commit()
    return parent_user


@pytest.fixture()
def teacher_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"cmcp_teacher_{uuid4().hex[:8]}@test.com",
        full_name="CMCP Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher(db_session, teacher_user):
    from app.models.teacher import Teacher

    t = Teacher(user_id=teacher_user.id, school_name="CMCP Test School")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def course_with_student(db_session, student, teacher):
    """Course taught by ``teacher`` and enrolling ``student``."""
    from app.models.course import Course, student_courses

    c = Course(
        name="CMCP Math",
        subject="Math",
        teacher_id=teacher.id,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    db_session.execute(
        student_courses.insert().values(
            student_id=student.id,
            course_id=c.id,
        )
    )
    db_session.commit()
    return c


# ── Cache helper ──


@pytest.fixture(autouse=True)
def _clear_cmcp_cache():
    """Wipe the module-level cache before and after each test.

    Without this, the session-scoped DB fixture lets cached profile
    payloads leak across tests, masking 403/404 paths and the cache-hit
    test below.
    """
    from app.services.cmcp import student_context

    student_context._cache.clear()
    yield
    student_context._cache.clear()


# ── get_student_profile happy path ──


def test_get_student_profile_returns_enrolled_courses(
    db_session, student, linked_parent, course_with_student
):
    from app.services.cmcp.student_context import get_student_profile

    result = get_student_profile(student.id, db_session, linked_parent)

    assert result["student_id"] == student.id
    assert result["resource_uri"] == f"student://profile/{student.id}"
    assert result["grade_level"] == 8
    assert result["school_name"] == "CMCP Test School"
    course_ids = {c["id"] for c in result["enrolled_courses"]}
    assert course_with_student.id in course_ids


# ── RBAC paths ──


def test_get_student_profile_403_for_unrelated_parent(
    db_session, student, unrelated_parent_user
):
    from fastapi import HTTPException

    from app.services.cmcp.student_context import get_student_profile

    with pytest.raises(HTTPException) as exc:
        get_student_profile(student.id, db_session, unrelated_parent_user)
    assert exc.value.status_code == 403


def test_get_student_profile_200_for_linked_parent(
    db_session, student, linked_parent
):
    from app.services.cmcp.student_context import get_student_profile

    result = get_student_profile(student.id, db_session, linked_parent)
    assert result["student_id"] == student.id


def test_get_student_profile_200_for_course_teacher(
    db_session, student, teacher_user, course_with_student
):
    from app.services.cmcp.student_context import get_student_profile

    result = get_student_profile(student.id, db_session, teacher_user)
    assert result["student_id"] == student.id


# ── 404 ──


def test_get_student_profile_404_for_unknown_student(
    db_session, linked_parent
):
    from fastapi import HTTPException

    from app.services.cmcp.student_context import get_student_profile

    with pytest.raises(HTTPException) as exc:
        get_student_profile(999_999, db_session, linked_parent)
    assert exc.value.status_code == 404


# ── Cache ──


class _QueryCountingSession:
    """Wrap a ``Session`` and count ``query()`` invocations.

    Only ``query`` is intercepted; everything else delegates to the
    underlying session via ``__getattr__``.
    """

    def __init__(self, real_session):
        self._real = real_session
        self.query_calls = 0

    def query(self, *args, **kwargs):
        self.query_calls += 1
        return self._real.query(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_get_student_profile_cache_skips_db_on_second_call(
    db_session, student, linked_parent, course_with_student
):
    """Second call returns the same payload while skipping the
    payload-construction queries (course list + report card).

    Access checks (`Student` lookup + `parent_students` link) still run
    on every call so RBAC stays enforced — only the inner data fetch
    is short-circuited by the cache.
    """
    from app.services.cmcp.student_context import get_student_profile

    counting = _QueryCountingSession(db_session)

    first = get_student_profile(student.id, counting, linked_parent)
    queries_after_first = counting.query_calls
    assert queries_after_first > 0

    second = get_student_profile(student.id, counting, linked_parent)

    assert second == first
    # Second call still runs access checks (Student lookup + parent link),
    # but must skip the payload queries.  The contract is "fewer queries
    # on cache hit" — not a specific number; pinning an absolute upper
    # bound here couples the test to internal query layout and fights
    # benign refactors (e.g. eager-loads added later).
    delta = counting.query_calls - queries_after_first
    assert delta < queries_after_first, (
        f"Cache had no effect: first call ran {queries_after_first} queries, "
        f"second call ran {delta} more (expected far fewer)."
    )


# ── Cache role-scoping ──


def test_cache_key_includes_role(
    db_session, student, linked_parent, course_with_student
):
    """Cache entries are role-scoped — a parent payload must not be
    served to an admin (or vice versa) once role-conditional fields
    land in M2-A.  Verified by checking that two callers with
    different roles produce two distinct cache entries.
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.services.cmcp import student_context
    from app.services.cmcp.student_context import get_student_profile

    # Create an admin caller alongside the linked parent
    admin = User(
        email=f"cmcp_admin_{uuid4().hex[:8]}@test.com",
        full_name="CMCP Admin",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    student_context._cache.clear()
    get_student_profile(student.id, db_session, linked_parent)
    get_student_profile(student.id, db_session, admin)

    # Pin the exact cache keys so a future change that loosens
    # role-scoping (e.g. role tag becomes a substring like "parent" of
    # "co-parent") fails this test instead of silently passing.
    expected_keys = {
        f"profile:{student.id}:parent",
        f"profile:{student.id}:admin",
    }
    assert set(student_context._cache.keys()) == expected_keys


# ── Other-function smoke coverage ──


def test_get_student_assignments_smoke(db_session, student, linked_parent):
    """Smoke test: function returns a dict with the documented shape."""
    from app.services.cmcp.student_context import get_student_assignments

    result = get_student_assignments(student.id, db_session, linked_parent)
    assert result["student_id"] == student.id
    assert result["resource_uri"] == f"student://assignments/{student.id}"
    assert isinstance(result["assignments"], list)
    assert result["total"] == 0


def test_get_student_study_history_smoke(db_session, student, linked_parent):
    """Smoke test: function returns a dict with the documented shape."""
    from app.services.cmcp.student_context import get_student_study_history

    result = get_student_study_history(student.id, db_session, linked_parent)
    assert result["student_id"] == student.id
    assert result["resource_uri"] == f"student://study-history/{student.id}"
    assert result["summary"]["total_study_guides"] == 0
    assert result["summary"]["average_quiz_score"] is None


def test_get_student_weak_areas_smoke(db_session, student, linked_parent):
    """Smoke test: function returns a dict with the documented shape."""
    from app.services.cmcp.student_context import get_student_weak_areas

    result = get_student_weak_areas(student.id, db_session, linked_parent)
    assert result["student_id"] == student.id
    assert result["resource_uri"] == f"student://weak-areas/{student.id}"
    assert result["weak_areas"] == []
    assert result["total_weak_areas"] == 0


def test_smoke_functions_enforce_rbac(
    db_session, student, unrelated_parent_user
):
    """All four context functions enforce the same RBAC contract."""
    from fastapi import HTTPException

    from app.services.cmcp.student_context import (
        get_student_assignments,
        get_student_study_history,
        get_student_weak_areas,
    )

    for fn in (get_student_assignments, get_student_study_history, get_student_weak_areas):
        with pytest.raises(HTTPException) as exc:
            fn(student.id, db_session, unrelated_parent_user)
        assert exc.value.status_code == 403, (
            f"{fn.__name__} did not enforce 403 for unrelated parent"
        )
