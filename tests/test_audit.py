"""Tests for audit logging feature."""
import pytest
from conftest import PASSWORD, _login, _auth


def _register(client, email, role="parent", full_name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


def _setup_admin(client, db_session):
    """Create an admin user directly in DB (admin self-registration is blocked)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"admin-audit-{id(client)}@test.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if not existing:
        admin = User(
            email=email,
            full_name="Admin Audit",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(admin)
        db_session.commit()
    return _auth(client, email)


class TestAuditOnLogin:
    def test_successful_login_creates_audit_entry(self, client, db_session):
        email = "audit-login-ok@test.com"
        _register(client, email)
        _login(client, email)

        from app.models.audit_log import AuditLog
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "login",
            AuditLog.resource_type == "user",
        ).order_by(AuditLog.id.desc()).first()
        assert entry is not None
        assert entry.user_id is not None

    def test_failed_login_creates_audit_entry(self, client, db_session):
        resp = client.post("/api/auth/login", data={
            "username": "nonexistent@test.com", "password": "wrong",
        })
        assert resp.status_code == 401

        from app.models.audit_log import AuditLog
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "login_failed",
        ).order_by(AuditLog.id.desc()).first()
        assert entry is not None
        assert entry.user_id is None

    def test_register_creates_audit_entry(self, client, db_session):
        email = "audit-register@test.com"
        resp = _register(client, email)
        assert resp.status_code == 200

        from app.models.audit_log import AuditLog
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "create",
            AuditLog.resource_type == "user",
        ).order_by(AuditLog.id.desc()).first()
        assert entry is not None
        assert entry.resource_id == resp.json()["id"]


class TestAdminAuditEndpoint:
    def test_admin_can_list_audit_logs(self, client, db_session):
        headers = _setup_admin(client, db_session)
        resp = client.get("/api/admin/audit-logs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 0

    def test_non_admin_cannot_access_audit_logs(self, client, db_session):
        email = "audit-parent@test.com"
        _register(client, email, role="parent")
        headers = _auth(client, email)
        resp = client.get("/api/admin/audit-logs", headers=headers)
        assert resp.status_code == 403

    def test_filter_by_action(self, client, db_session):
        headers = _setup_admin(client, db_session)
        resp = client.get("/api/admin/audit-logs", headers=headers, params={"action": "login"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["action"] == "login"

    def test_filter_by_resource_type(self, client, db_session):
        headers = _setup_admin(client, db_session)
        resp = client.get("/api/admin/audit-logs", headers=headers, params={"resource_type": "user"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resource_type"] == "user"

    def test_pagination(self, client, db_session):
        headers = _setup_admin(client, db_session)
        resp = client.get("/api/admin/audit-logs", headers=headers, params={"limit": 2, "skip": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2

    def test_audit_entry_has_user_name(self, client, db_session):
        headers = _setup_admin(client, db_session)
        resp = client.get("/api/admin/audit-logs", headers=headers, params={"action": "login"})
        assert resp.status_code == 200
        data = resp.json()
        # At least one login entry should have a user_name resolved
        login_entries = [i for i in data["items"] if i["user_id"] is not None]
        if login_entries:
            assert login_entries[0]["user_name"] is not None


class TestAuditOnTaskCreate:
    def test_task_create_audited(self, client, db_session):
        email = "audit-task@test.com"
        _register(client, email, role="parent")
        headers = _auth(client, email)

        resp = client.post("/api/tasks/", headers=headers, json={
            "title": "Audit test task",
        })
        assert resp.status_code == 201

        from app.models.audit_log import AuditLog
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "create",
            AuditLog.resource_type == "task",
        ).order_by(AuditLog.id.desc()).first()
        assert entry is not None
        assert entry.resource_id == resp.json()["id"]
