import secrets
from datetime import datetime, timedelta

import pytest
from jose import jwt

PASSWORD = "password123!"


def _register(client, email, role="parent", full_name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


# ── Original tests ────────────────────────────────────────────

def test_register_login_me(client):
    payload = {
        "email": "testuser@example.com",
        "password": "password123!",
        "full_name": "Test User",
        "role": "parent",
    }
    register = client.post("/api/auth/register", json=payload)
    assert register.status_code == 200, register.text

    login = client.post(
        "/api/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == payload["email"]
    assert body["role"] == payload["role"]


def test_login_rejects_invalid_password(client, db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email="loginfail@example.com",
        full_name="Login Fail",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("password123!"),
    )
    db_session.add(user)
    db_session.commit()

    login = client.post(
        "/api/auth/login",
        data={"username": user.email, "password": "wrong-password"},
    )
    assert login.status_code == 401


# ── Registration tests ────────────────────────────────────────

class TestRegistration:
    def test_duplicate_email_rejected(self, client):
        email = "auth_dup@test.com"
        resp1 = _register(client, email)
        assert resp1.status_code == 200

        resp2 = _register(client, email)
        assert resp2.status_code == 400
        assert "already registered" in resp2.json()["detail"].lower()

    def test_register_teacher_creates_teacher_record(self, client, db_session):
        from app.models.teacher import Teacher
        from app.models.user import User

        email = "auth_teacher@test.com"
        resp = _register(client, email, role="teacher", full_name="Auth Teacher")
        assert resp.status_code == 200
        user_id = resp.json()["id"]

        teacher = db_session.query(Teacher).filter(Teacher.user_id == user_id).first()
        assert teacher is not None

    def test_register_student_creates_student_record(self, client, db_session):
        from app.models.student import Student
        from app.models.user import User

        email = "auth_student@test.com"
        resp = _register(client, email, role="student", full_name="Auth Student")
        assert resp.status_code == 200
        user_id = resp.json()["id"]

        student = db_session.query(Student).filter(Student.user_id == user_id).first()
        assert student is not None


# ── Token validation tests ────────────────────────────────────

class TestTokenValidation:
    def test_expired_token_rejected(self, client):
        from app.core.config import settings

        expired_token = jwt.encode(
            {"sub": "999", "exp": datetime.utcnow() - timedelta(minutes=5)},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, client):
        resp = client.get("/api/users/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    def test_token_for_nonexistent_user(self, client):
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "999999", "exp": datetime.utcnow() + timedelta(minutes=30)},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


# ── Accept-invite tests ──────────────────────────────────────

class TestAcceptInvite:
    @pytest.fixture()
    def parent_user(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        email = "auth_inviter@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if user:
            return user
        user = User(
            email=email, full_name="Auth Inviter", role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_accept_student_invite(self, client, db_session, parent_user):
        from app.models.invite import Invite, InviteType
        from app.models.student import Student, parent_students

        token = secrets.token_urlsafe(32)
        invite = Invite(
            email="auth_invited_student@test.com",
            invite_type=InviteType.STUDENT,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=7),
            invited_by_user_id=parent_user.id,
        )
        db_session.add(invite)
        db_session.commit()

        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "password": PASSWORD,
            "full_name": "Invited Student",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

        # Verify student record was created
        from app.models.user import User
        new_user = db_session.query(User).filter(User.email == "auth_invited_student@test.com").first()
        assert new_user is not None
        assert new_user.role.value == "student"

        student = db_session.query(Student).filter(Student.user_id == new_user.id).first()
        assert student is not None

        # Verify parent-student link
        link = db_session.execute(
            parent_students.select().where(
                parent_students.c.parent_id == parent_user.id,
                parent_students.c.student_id == student.id,
            )
        ).first()
        assert link is not None

    def test_expired_invite_rejected(self, client, db_session, parent_user):
        from app.models.invite import Invite, InviteType

        token = secrets.token_urlsafe(32)
        invite = Invite(
            email="auth_expired_invite@test.com",
            invite_type=InviteType.STUDENT,
            token=token,
            expires_at=datetime.utcnow() - timedelta(days=1),
            invited_by_user_id=parent_user.id,
        )
        db_session.add(invite)
        db_session.commit()

        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "password": PASSWORD,
            "full_name": "Expired Invite",
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()
