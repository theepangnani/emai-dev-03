"""Tests for account deletion & data anonymization (#964)."""

import pytest
from datetime import datetime, timedelta, timezone

from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def deletion_users(db_session):
    """Create users for deletion tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    admin_email = "del_admin@test.com"
    admin = db_session.query(User).filter(User.email == admin_email).first()
    if admin:
        target = db_session.query(User).filter(User.email == "del_target@test.com").first()
        return {"admin": admin, "target": target}

    admin = User(
        email=admin_email,
        full_name="Del Admin",
        role=UserRole.ADMIN,
        roles="admin",
        hashed_password=hashed,
    )
    target = User(
        email="del_target@test.com",
        full_name="Del Target",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=hashed,
    )
    db_session.add_all([admin, target])
    db_session.commit()
    for u in [admin, target]:
        db_session.refresh(u)
    return {"admin": admin, "target": target}


# ── Request deletion ──────────────────────────────────────────

class TestRequestDeletion:
    def test_request_deletion_success(self, client, deletion_users):
        headers = _auth(client, deletion_users["target"].email)
        resp = client.delete("/api/users/me/account", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["deletion_requested"] is True
        assert data["deletion_confirmed"] is False
        assert "confirmation" in data["message"].lower() or "email" in data["message"].lower()

    def test_request_deletion_already_confirmed(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed_at = datetime.now(timezone.utc)
        user.is_active = False
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.delete("/api/users/me/account", headers=headers)
        assert resp.status_code == 400

        # Reset for other tests
        user.deletion_requested_at = None
        user.deletion_confirmed_at = None
        user.is_active = True
        db_session.commit()

    def test_request_deletion_unauthenticated(self, client):
        resp = client.delete("/api/users/me/account")
        assert resp.status_code in (401, 403)


# ── Confirm deletion ─────────────────────────────────────────

class TestConfirmDeletion:
    def test_confirm_with_valid_token(self, client, deletion_users, db_session):
        from app.core.security import create_deletion_confirmation_token

        user = deletion_users["target"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed_at = None
        user.is_active = True
        user.is_deleted = False
        db_session.commit()

        token = create_deletion_confirmation_token(user.id)
        resp = client.post("/api/users/me/confirm-deletion", json={"token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["deletion_confirmed"] is True

        # Verify user is deactivated
        db_session.refresh(user)
        assert user.is_active is False
        assert user.deletion_confirmed_at is not None

        # Reset for other tests
        user.deletion_requested_at = None
        user.deletion_confirmed_at = None
        user.is_active = True
        user.is_deleted = False
        db_session.commit()

    def test_confirm_with_invalid_token(self, client):
        resp = client.post("/api/users/me/confirm-deletion", json={"token": "invalid.token.here"})
        assert resp.status_code == 400

    def test_confirm_no_prior_request(self, client, deletion_users, db_session):
        from app.core.security import create_deletion_confirmation_token

        user = deletion_users["target"]
        user.deletion_requested_at = None
        user.deletion_confirmed_at = None
        db_session.commit()

        token = create_deletion_confirmation_token(user.id)
        resp = client.post("/api/users/me/confirm-deletion", json={"token": token})
        assert resp.status_code == 400


# ── Cancel deletion ──────────────────────────────────────────

class TestCancelDeletion:
    def test_cancel_pending_request(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed_at = None
        user.is_active = True
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.post("/api/users/me/cancel-deletion", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["deletion_requested"] is False
        assert data["deletion_confirmed"] is False

        db_session.refresh(user)
        assert user.deletion_requested_at is None
        assert user.is_active is True

    def test_cancel_confirmed_deletion(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed_at = datetime.now(timezone.utc)
        user.is_active = False
        user.is_deleted = False
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.post("/api/users/me/cancel-deletion", headers=headers)
        assert resp.status_code == 200

        db_session.refresh(user)
        assert user.deletion_requested_at is None
        assert user.deletion_confirmed_at is None
        assert user.is_active is True

    def test_cancel_no_pending_request(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = None
        user.deletion_confirmed_at = None
        user.is_active = True
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.post("/api/users/me/cancel-deletion", headers=headers)
        assert resp.status_code == 400


# ── Deletion status ──────────────────────────────────────────

class TestDeletionStatus:
    def test_status_no_request(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = None
        user.deletion_confirmed_at = None
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.get("/api/users/me/deletion-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["deletion_requested"] is False
        assert data["deletion_confirmed"] is False

    def test_status_with_request(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.get("/api/users/me/deletion-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["deletion_requested"] is True

        # Reset
        user.deletion_requested_at = None
        db_session.commit()


# ── Admin endpoints ──────────────────────────────────────────

class TestAdminDeletion:
    def test_list_deletion_requests(self, client, deletion_users, db_session):
        user = deletion_users["target"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        db_session.commit()

        headers = _auth(client, deletion_users["admin"].email)
        resp = client.get("/api/admin/deletion-requests", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

        # Reset
        user.deletion_requested_at = None
        db_session.commit()

    def test_list_deletion_requests_non_admin(self, client, deletion_users):
        headers = _auth(client, deletion_users["target"].email)
        resp = client.get("/api/admin/deletion-requests", headers=headers)
        assert resp.status_code == 403

    def test_process_deletion(self, client, deletion_users, db_session):
        # Create a throw-away user to anonymize
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        throwaway = User(
            email="del_throwaway@test.com",
            full_name="Throwaway User",
            role=UserRole.STUDENT,
            roles="student",
            hashed_password=get_password_hash(PASSWORD),
            deletion_requested_at=datetime.now(timezone.utc),
        )
        db_session.add(throwaway)
        db_session.commit()
        db_session.refresh(throwaway)

        headers = _auth(client, deletion_users["admin"].email)
        resp = client.post(
            f"/api/admin/deletion-requests/{throwaway.id}/process",
            headers=headers,
        )
        assert resp.status_code == 200

        db_session.refresh(throwaway)
        assert throwaway.is_deleted is True
        assert "anonymized" in throwaway.email
        assert throwaway.full_name.startswith("Deleted User")

    def test_process_nonexistent_user(self, client, deletion_users):
        headers = _auth(client, deletion_users["admin"].email)
        resp = client.post("/api/admin/deletion-requests/99999/process", headers=headers)
        assert resp.status_code == 404

    def test_process_already_deleted(self, client, deletion_users, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        already_deleted = User(
            email="del_already@anonymized.local",
            full_name="Deleted User 0",
            role=UserRole.PARENT,
            roles="parent",
            hashed_password="!DELETED",
            is_deleted=True,
            deletion_requested_at=datetime.now(timezone.utc),
        )
        db_session.add(already_deleted)
        db_session.commit()
        db_session.refresh(already_deleted)

        headers = _auth(client, deletion_users["admin"].email)
        resp = client.post(
            f"/api/admin/deletion-requests/{already_deleted.id}/process",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_admin_cannot_delete_self(self, client, deletion_users):
        admin = deletion_users["admin"]
        headers = _auth(client, admin.email)
        resp = client.post(
            f"/api/admin/deletion-requests/{admin.id}/process",
            headers=headers,
        )
        assert resp.status_code == 400


# ── Anonymization service ────────────────────────────────────

class TestAnonymization:
    def test_anonymize_user(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.account_deletion_service import anonymize_user

        user = User(
            email="anon_test@test.com",
            full_name="Anonymize Me",
            role=UserRole.PARENT,
            roles="parent",
            hashed_password=get_password_hash(PASSWORD),
            google_id="google123",
            google_access_token="token123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        anonymize_user(db_session, user)

        db_session.refresh(user)
        assert "anonymized" in user.email
        assert user.full_name.startswith("Deleted User")
        assert user.hashed_password == "!DELETED"
        assert user.google_id is None
        assert user.google_access_token is None
        assert user.is_deleted is True
        assert user.is_active is False

    def test_process_expired_deletions(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.account_deletion_service import process_expired_deletions

        # User with confirmed deletion 31 days ago
        expired_user = User(
            email="expired_del@test.com",
            full_name="Expired Deletion",
            role=UserRole.STUDENT,
            roles="student",
            hashed_password=get_password_hash(PASSWORD),
            deletion_requested_at=datetime.now(timezone.utc) - timedelta(days=35),
            deletion_confirmed_at=datetime.now(timezone.utc) - timedelta(days=31),
        )
        db_session.add(expired_user)
        db_session.commit()

        count = process_expired_deletions(db_session)
        assert count >= 1

        db_session.refresh(expired_user)
        assert expired_user.is_deleted is True


# ── Security tokens ──────────────────────────────────────────

class TestDeletionTokens:
    def test_create_and_decode_token(self):
        from app.core.security import (
            create_deletion_confirmation_token,
            decode_deletion_confirmation_token,
        )

        token = create_deletion_confirmation_token(42)
        user_id = decode_deletion_confirmation_token(token)
        assert user_id == 42

    def test_invalid_token_returns_none(self):
        from app.core.security import decode_deletion_confirmation_token

        assert decode_deletion_confirmation_token("invalid.token") is None

    def test_wrong_type_token_returns_none(self):
        from app.core.security import (
            create_email_verification_token,
            decode_deletion_confirmation_token,
        )

        # An email verification token should not work as a deletion token
        token = create_email_verification_token("test@test.com")
        assert decode_deletion_confirmation_token(token) is None


# ── Deleted user blocked from auth ───────────────────────────

class TestDeletedUserBlocked:
    def test_deleted_user_cannot_access_api(self, client, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        deleted_user = User(
            email="blocked_del@test.com",
            full_name="Blocked User",
            role=UserRole.PARENT,
            roles="parent",
            hashed_password=get_password_hash(PASSWORD),
            is_deleted=True,
        )
        db_session.add(deleted_user)
        db_session.commit()

        # Login to get a token (login itself works since it uses a separate flow)
        token = _login(client, "blocked_del@test.com")

        # But accessing protected endpoints should be blocked
        resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
