"""Tests for simplified registration and post-login onboarding (#412, #413, #414)."""

from conftest import PASSWORD, _login, _auth


def _register_no_role(client, email, full_name="Test User"):
    """Register a user without any role (roleless registration)."""
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "roles": [],
    })


def _register_with_role(client, email, role="parent", full_name="Test User"):
    """Register a user with a role (traditional registration)."""
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


# ── Roleless Registration Tests ──────────────────────────────

class TestRolelessRegistration:
    def test_register_without_role_returns_needs_onboarding(self, client):
        email = "onb_norole@test.com"
        resp = _register_no_role(client, email)
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_onboarding"] is True
        assert data["role"] is None
        assert data["roles"] == []

    def test_register_without_role_no_profile_records(self, client, db_session):
        from app.models.teacher import Teacher
        from app.models.student import Student

        email = "onb_noprofile@test.com"
        resp = _register_no_role(client, email)
        assert resp.status_code == 200
        user_id = resp.json()["id"]

        teacher = db_session.query(Teacher).filter(Teacher.user_id == user_id).first()
        assert teacher is None

        student = db_session.query(Student).filter(Student.user_id == user_id).first()
        assert student is None

    def test_register_with_role_still_works(self, client):
        """Backward compatibility: registration with roles still works."""
        email = "onb_withrole@test.com"
        resp = _register_with_role(client, email, role="parent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_onboarding"] is False
        assert data["role"] == "parent"
        assert "parent" in data["roles"]

    def test_me_returns_needs_onboarding(self, client):
        email = "onb_me_flag@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)
        resp = client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["needs_onboarding"] is True


# ── Onboarding Endpoint Tests ────────────────────────────────

class TestOnboardingEndpoint:
    def test_onboarding_parent_happy_path(self, client, db_session):
        email = "onb_parent@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={"roles": ["parent"]}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "parent"
        assert "parent" in data["roles"]
        assert data["needs_onboarding"] is False

    def test_onboarding_teacher_with_type(self, client, db_session):
        from app.models.teacher import Teacher

        email = "onb_teacher@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={
            "roles": ["teacher"],
            "teacher_type": "school_teacher",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "teacher"
        assert data["needs_onboarding"] is False

        # Verify teacher record was created
        from app.models.user import User
        user = db_session.query(User).filter(User.email == email).first()
        teacher = db_session.query(Teacher).filter(Teacher.user_id == user.id).first()
        assert teacher is not None
        assert teacher.teacher_type.value == "school_teacher"

    def test_onboarding_student_creates_record(self, client, db_session):
        from app.models.student import Student

        email = "onb_student@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={"roles": ["student"]}, headers=headers)
        assert resp.status_code == 200

        from app.models.user import User
        user = db_session.query(User).filter(User.email == email).first()
        student = db_session.query(Student).filter(Student.user_id == user.id).first()
        assert student is not None

    def test_onboarding_multi_role(self, client):
        email = "onb_multi@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={
            "roles": ["parent", "teacher"],
            "teacher_type": "private_tutor",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "parent"  # First role becomes primary
        assert "parent" in data["roles"]
        assert "teacher" in data["roles"]

    def test_onboarding_rejects_duplicate(self, client):
        email = "onb_dup@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        # First onboarding should succeed
        resp = client.post("/api/auth/onboarding", json={"roles": ["parent"]}, headers=headers)
        assert resp.status_code == 200

        # Second onboarding should fail
        resp2 = client.post("/api/auth/onboarding", json={"roles": ["student"]}, headers=headers)
        assert resp2.status_code == 400
        assert "already completed" in resp2.json()["detail"].lower()

    def test_onboarding_rejects_empty_roles(self, client):
        email = "onb_empty@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={"roles": []}, headers=headers)
        assert resp.status_code == 400
        assert "at least one role" in resp.json()["detail"].lower()

    def test_onboarding_rejects_admin_role(self, client):
        email = "onb_admin@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={"roles": ["admin"]}, headers=headers)
        assert resp.status_code == 400

    def test_onboarding_teacher_without_type_rejected(self, client):
        email = "onb_notype@test.com"
        _register_no_role(client, email)
        headers = _auth(client, email)

        resp = client.post("/api/auth/onboarding", json={"roles": ["teacher"]}, headers=headers)
        assert resp.status_code == 400
        assert "teacher type" in resp.json()["detail"].lower()

    def test_onboarding_requires_auth(self, client):
        resp = client.post("/api/auth/onboarding", json={"roles": ["parent"]})
        assert resp.status_code == 401
