"""Tests for account deletion and data anonymization (#964)."""

import pytest
from datetime import datetime, timedelta, timezone

from conftest import PASSWORD, _login, _auth


_del_counter = 0


@pytest.fixture()
def deletion_users(db_session):
    """Create fresh users for deletion tests (unique per invocation)."""
    global _del_counter
    _del_counter += 1
    suffix = _del_counter

    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    admin = User(
        email=f"del_admin_{suffix}@test.com", full_name="Del Admin", role=UserRole.ADMIN,
        roles="admin", hashed_password=hashed,
    )
    parent = User(
        email=f"del_parent_{suffix}@test.com", full_name="Del Parent", role=UserRole.PARENT,
        roles="parent", hashed_password=hashed,
    )
    student = User(
        email=f"del_student_{suffix}@test.com", full_name="Del Student", role=UserRole.STUDENT,
        roles="student", hashed_password=hashed,
    )
    db_session.add_all([admin, parent, student])
    db_session.commit()
    for u in [admin, parent, student]:
        db_session.refresh(u)
    return {"admin": admin, "parent": parent, "student": student}


# ── Request deletion ──────────────────────────────────────────

class TestRequestDeletion:
    def test_request_deletion_success(self, client, deletion_users):
        headers = _auth(client, deletion_users["parent"].email)
        resp = client.delete("/api/users/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "30 days" in data["message"]
        assert data["deletion_requested_at"] is not None
        assert data["grace_period_ends_at"] is not None

    def test_request_deletion_idempotent(self, client, deletion_users):
        headers = _auth(client, deletion_users["parent"].email)
        # First request
        resp1 = client.delete("/api/users/me", headers=headers)
        assert resp1.status_code == 200

        # Second request should return "already pending"
        resp2 = client.delete("/api/users/me", headers=headers)
        assert resp2.status_code == 200
        assert "already pending" in resp2.json()["message"]

    def test_request_deletion_unauthenticated(self, client):
        resp = client.delete("/api/users/me")
        assert resp.status_code == 401


# ── Deletion status ───────────────────────────────────────────

class TestDeletionStatus:
    def test_no_pending_deletion(self, client, deletion_users):
        headers = _auth(client, deletion_users["student"].email)
        resp = client.get("/api/users/me/deletion-status", headers=headers)
        assert resp.status_code == 200
        assert "No deletion request" in resp.json()["message"]

    def test_pending_deletion_status(self, client, deletion_users, db_session):
        user = deletion_users["student"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed = True
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.get("/api/users/me/deletion-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "pending" in data["message"]
        assert data["deletion_requested_at"] is not None


# ── Cancel deletion ───────────────────────────────────────────

class TestCancelDeletion:
    def test_cancel_deletion_success(self, client, deletion_users, db_session):
        user = deletion_users["parent"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed = True
        db_session.commit()

        headers = _auth(client, user.email)
        resp = client.post("/api/users/me/cancel-deletion", headers=headers)
        assert resp.status_code == 200
        assert "cancelled" in resp.json()["message"]

        # Verify state is cleared
        db_session.refresh(user)
        assert user.deletion_requested_at is None
        assert user.deletion_confirmed is False

    def test_cancel_deletion_no_pending(self, client, deletion_users):
        headers = _auth(client, deletion_users["student"].email)
        resp = client.post("/api/users/me/cancel-deletion", headers=headers)
        assert resp.status_code == 400
        assert "No pending" in resp.json()["detail"]

    def test_cancel_deletion_already_deleted(self, client, deletion_users, db_session):
        user = deletion_users["student"]
        user.is_deleted = True
        user.deletion_confirmed = True
        user.deletion_requested_at = datetime.now(timezone.utc)
        db_session.commit()

        headers = _auth(client, user.email)
        # Deleted users are blocked at auth level
        resp = client.post("/api/users/me/cancel-deletion", headers=headers)
        assert resp.status_code == 401


# ── Admin deletion requests ───────────────────────────────────

class TestAdminDeletionRequests:
    def test_list_deletion_requests(self, client, deletion_users, db_session):
        user = deletion_users["parent"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed = True
        user.is_deleted = False
        db_session.commit()

        headers = _auth(client, deletion_users["admin"].email)
        resp = client.get("/api/admin/deletion-requests", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        found = [i for i in data["items"] if i["user_id"] == user.id]
        assert len(found) == 1

    def test_list_deletion_requests_requires_admin(self, client, deletion_users):
        headers = _auth(client, deletion_users["parent"].email)
        resp = client.get("/api/admin/deletion-requests", headers=headers)
        assert resp.status_code == 403

    def test_admin_force_process_deletion(self, client, deletion_users, db_session):
        user = deletion_users["student"]
        user.deletion_requested_at = datetime.now(timezone.utc)
        user.deletion_confirmed = True
        user.is_deleted = False
        user.is_active = True
        db_session.commit()

        headers = _auth(client, deletion_users["admin"].email)
        resp = client.post(
            f"/api/admin/deletion-requests/{user.id}/process",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user.id
        assert "anonymized" in data["message"]

        # Verify user is anonymized
        db_session.refresh(user)
        assert user.is_deleted is True
        assert user.is_active is False
        assert "deleted_user_" in (user.email or "")
        assert user.full_name == "Deleted User"

    def test_admin_process_nonexistent_user(self, client, deletion_users):
        headers = _auth(client, deletion_users["admin"].email)
        resp = client.post("/api/admin/deletion-requests/99999/process", headers=headers)
        assert resp.status_code == 400


# ── Deletion service unit tests ───────────────────────────────

class TestDeletionService:
    def test_process_expired_deletions(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.deletion_service import process_expired_deletions

        hashed = get_password_hash(PASSWORD)
        user = User(
            email="expired_del@test.com", full_name="Expired User",
            role=UserRole.PARENT, roles="parent", hashed_password=hashed,
            deletion_requested_at=datetime.now(timezone.utc) - timedelta(days=31),
            deletion_confirmed=True, is_deleted=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        count = process_expired_deletions(db_session)
        assert count >= 1

        db_session.refresh(user)
        assert user.is_deleted is True
        assert user.is_active is False
        assert "Deleted User" == user.full_name

    def test_process_does_not_touch_non_expired(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.deletion_service import process_expired_deletions

        hashed = get_password_hash(PASSWORD)
        user = User(
            email="notexpired_del@test.com", full_name="Not Expired",
            role=UserRole.PARENT, roles="parent", hashed_password=hashed,
            deletion_requested_at=datetime.now(timezone.utc) - timedelta(days=5),
            deletion_confirmed=True, is_deleted=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        process_expired_deletions(db_session)

        db_session.refresh(user)
        assert user.is_deleted is False
        assert user.full_name == "Not Expired"


# ── Blocked auth for deleted users ────────────────────────────

class TestDeletedUserAuth:
    def test_deleted_user_cannot_access_api(self, client, deletion_users, db_session):
        user = deletion_users["student"]
        # First get a token while still active
        token = _login(client, user.email)

        # Now mark as deleted
        user.is_deleted = True
        db_session.commit()

        # Token should no longer work
        resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
