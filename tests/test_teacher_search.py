"""Regression tests for teacher search role-based access control (#2942).

The search_teachers endpoint (GET /api/courses/teachers/search) should enforce:
- Parents/students: exact email match only (no partial name/email search)
- Teachers/admins: partial name or email search allowed
- Empty query from parent/student: returns empty list

These tests are written against the role-restricted version of the endpoint
(PR #2940 / fix/2938-teacher-search-email-only). Some tests will fail on
master where no role restriction exists yet — that is expected.
"""

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def search_users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher

    # Check-or-create to handle shared session DB
    parent = db_session.query(User).filter(User.email == "tsearch_parent@test.com").first()
    if parent:
        student = db_session.query(User).filter(User.email == "tsearch_student@test.com").first()
        teacher_user = db_session.query(User).filter(User.email == "tsearch_teacher@test.com").first()
        admin = db_session.query(User).filter(User.email == "tsearch_admin@test.com").first()
        platform_teacher = db_session.query(Teacher).filter(Teacher.user_id == teacher_user.id).first()
        shadow_teacher = db_session.query(Teacher).filter(
            Teacher.google_email == "shadow.smith@school.edu"
        ).first()
        return {
            "parent": parent,
            "student": student,
            "teacher_user": teacher_user,
            "admin": admin,
            "platform_teacher": platform_teacher,
            "shadow_teacher": shadow_teacher,
        }

    hashed = get_password_hash(PASSWORD)

    parent = User(
        email="tsearch_parent@test.com",
        full_name="Search Parent",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    student = User(
        email="tsearch_student@test.com",
        full_name="Search Student",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    teacher_user = User(
        email="tsearch_teacher@test.com",
        full_name="Search Teacher",
        role=UserRole.TEACHER,
        hashed_password=hashed,
    )
    admin = User(
        email="tsearch_admin@test.com",
        full_name="Search Admin",
        role=UserRole.ADMIN,
        hashed_password=hashed,
    )
    db_session.add_all([parent, student, teacher_user, admin])
    db_session.flush()

    # Platform teacher (linked to a User)
    platform_teacher = Teacher(
        user_id=teacher_user.id,
        is_shadow=False,
        is_platform_user=True,
    )
    # Shadow teacher (no User account)
    shadow_teacher = Teacher(
        user_id=None,
        is_shadow=True,
        is_platform_user=False,
        google_email="shadow.smith@school.edu",
        full_name="Shadow Smith",
    )
    db_session.add_all([platform_teacher, shadow_teacher])
    db_session.commit()

    for u in [parent, student, teacher_user, admin]:
        db_session.refresh(u)
    db_session.refresh(platform_teacher)
    db_session.refresh(shadow_teacher)

    return {
        "parent": parent,
        "student": student,
        "teacher_user": teacher_user,
        "admin": admin,
        "platform_teacher": platform_teacher,
        "shadow_teacher": shadow_teacher,
    }


# ── Parent tests ─────────────────────────────────────────────


class TestParentTeacherSearch:
    def test_parent_exact_email_finds_teacher(self, client, search_users):
        """Parent searching by exact email should find the shadow teacher."""
        headers = _auth(client, search_users["parent"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "shadow.smith@school.edu"},
            headers=headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        emails = [r["email"] for r in results]
        assert "shadow.smith@school.edu" in emails

    def test_parent_partial_name_returns_empty(self, client, search_users):
        """Parent searching by partial name should get empty results (role restriction)."""
        headers = _auth(client, search_users["parent"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "Shadow"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_parent_partial_email_returns_empty(self, client, search_users):
        """Parent searching by partial email (e.g., domain) should get empty results."""
        headers = _auth(client, search_users["parent"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "school.edu"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_parent_empty_query_returns_empty(self, client, search_users):
        """Parent with empty query should get empty list."""
        headers = _auth(client, search_users["parent"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": ""},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── Student tests ────────────────────────────────────────────


class TestStudentTeacherSearch:
    def test_student_exact_email_finds_teacher(self, client, search_users):
        """Student searching by exact email should find the shadow teacher."""
        headers = _auth(client, search_users["student"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "shadow.smith@school.edu"},
            headers=headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        emails = [r["email"] for r in results]
        assert "shadow.smith@school.edu" in emails

    def test_student_partial_name_returns_empty(self, client, search_users):
        """Student searching by partial name should get empty results (role restriction)."""
        headers = _auth(client, search_users["student"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "Shadow"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── Teacher tests ────────────────────────────────────────────


class TestTeacherTeacherSearch:
    def test_teacher_partial_name_finds_teacher(self, client, search_users):
        """Teacher searching by partial name should find the shadow teacher."""
        headers = _auth(client, search_users["teacher_user"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "Shadow"},
            headers=headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        names = [r["name"] for r in results]
        assert any("Shadow" in n for n in names)


# ── Admin tests ──────────────────────────────────────────────


class TestAdminTeacherSearch:
    def test_admin_partial_name_finds_teacher(self, client, search_users):
        """Admin searching by partial name should find the shadow teacher."""
        headers = _auth(client, search_users["admin"].email)
        resp = client.get(
            "/api/courses/teachers/search",
            params={"q": "Shadow"},
            headers=headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        names = [r["name"] for r in results]
        assert any("Shadow" in n for n in names)
