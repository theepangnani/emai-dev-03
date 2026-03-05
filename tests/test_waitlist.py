"""Tests for the Waitlist feature (issue #1122).

Covers:
- POST /api/waitlist — join the waitlist
- GET /api/waitlist/verify/{token} — verify an invitation token
- Admin CRUD on /api/admin/waitlist
"""
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from conftest import PASSWORD, _auth


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    admin_email = "wl_admin@test.com"
    admin = db_session.query(User).filter(User.email == admin_email).first()
    if admin:
        parent = db_session.query(User).filter(User.email == "wl_parent@test.com").first()
        return {"admin": admin, "parent": parent}

    hashed = get_password_hash(PASSWORD)
    admin = User(email=admin_email, full_name="WL Admin", role=UserRole.ADMIN, hashed_password=hashed)
    parent = User(email="wl_parent@test.com", full_name="WL Parent", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([admin, parent])
    db_session.commit()
    for u in [admin, parent]:
        db_session.refresh(u)
    return {"admin": admin, "parent": parent}


@pytest.fixture()
def waitlist_entry(db_session):
    """Create a waitlist entry directly in the DB for verification tests."""
    from app.models.waitlist import WaitlistEntry

    token = secrets.token_urlsafe(32)
    entry = WaitlistEntry(
        full_name="Existing Waiter",
        email="wl_existing@test.com",
        roles="parent",
        status="pending",
        token=token,
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    # Avoid duplicates across test runs
    existing = db_session.query(WaitlistEntry).filter(WaitlistEntry.email == entry.email).first()
    if existing:
        return existing
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture()
def expired_entry(db_session):
    """Create a waitlist entry with an expired token."""
    from app.models.waitlist import WaitlistEntry

    token = secrets.token_urlsafe(32)
    entry = WaitlistEntry(
        full_name="Expired Waiter",
        email="wl_expired@test.com",
        roles="teacher",
        status="approved",
        token=token,
        token_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    existing = db_session.query(WaitlistEntry).filter(WaitlistEntry.email == entry.email).first()
    if existing:
        return existing
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


# ── Join Waitlist (POST /api/waitlist) ────────────────────────

class TestJoinWaitlist:
    def test_join_waitlist_success(self, client):
        resp = client.post("/api/waitlist", json={
            "full_name": "Alice Waitlist",
            "email": "wl_alice@test.com",
            "roles": ["parent"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "wl_alice@test.com"
        assert data["status"] == "pending"

    def test_join_waitlist_duplicate_email(self, client):
        email = "wl_dup@test.com"
        payload = {"full_name": "Dup User", "email": email, "roles": ["parent"]}
        resp1 = client.post("/api/waitlist", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/waitlist", json=payload)
        assert resp2.status_code == 409
        assert "already" in resp2.json()["detail"].lower()

    def test_join_waitlist_missing_name(self, client):
        resp = client.post("/api/waitlist", json={
            "email": "wl_noname@test.com",
            "roles": ["parent"],
        })
        assert resp.status_code == 422

    def test_join_waitlist_invalid_email(self, client):
        resp = client.post("/api/waitlist", json={
            "full_name": "Bad Email",
            "email": "not-an-email",
            "roles": ["parent"],
        })
        assert resp.status_code == 422

    def test_join_waitlist_no_roles(self, client):
        resp = client.post("/api/waitlist", json={
            "full_name": "No Roles",
            "email": "wl_noroles@test.com",
            "roles": [],
        })
        assert resp.status_code == 422

    def test_join_waitlist_invalid_role(self, client):
        resp = client.post("/api/waitlist", json={
            "full_name": "Bad Role",
            "email": "wl_badrole@test.com",
            "roles": ["superadmin"],
        })
        assert resp.status_code == 422


# ── Verify Token (GET /api/waitlist/verify/{token}) ──────────

class TestVerifyToken:
    def test_verify_token_valid(self, client, waitlist_entry):
        resp = client.get(f"/api/waitlist/verify/{waitlist_entry.token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == waitlist_entry.email

    def test_verify_token_invalid(self, client):
        resp = client.get("/api/waitlist/verify/totally-bogus-token-xyz")
        assert resp.status_code == 404

    def test_verify_token_expired(self, client, expired_entry):
        resp = client.get(f"/api/waitlist/verify/{expired_entry.token}")
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()


# ── Admin Endpoints ──────────────────────────────────────────

class TestAdminWaitlist:
    def test_admin_list_waitlist(self, client, users, waitlist_entry):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/waitlist", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_admin_waitlist_stats(self, client, users, waitlist_entry):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/waitlist/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "pending" in data
        assert "approved" in data
        assert "declined" in data

    def test_admin_approve(self, client, users, db_session):
        from app.models.waitlist import WaitlistEntry

        # Create a fresh entry to approve
        entry = WaitlistEntry(
            full_name="To Approve",
            email="wl_approve_me@test.com",
            roles="student",
            status="pending",
        )
        existing = db_session.query(WaitlistEntry).filter(WaitlistEntry.email == entry.email).first()
        if existing:
            entry = existing
            entry.status = "pending"
            db_session.commit()
        else:
            db_session.add(entry)
            db_session.commit()
            db_session.refresh(entry)

        headers = _auth(client, users["admin"].email)
        resp = client.post(f"/api/admin/waitlist/{entry.id}/approve", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["token"] is not None

    def test_admin_decline(self, client, users, db_session):
        from app.models.waitlist import WaitlistEntry

        entry = WaitlistEntry(
            full_name="To Decline",
            email="wl_decline_me@test.com",
            roles="parent",
            status="pending",
        )
        existing = db_session.query(WaitlistEntry).filter(WaitlistEntry.email == entry.email).first()
        if existing:
            entry = existing
            entry.status = "pending"
            db_session.commit()
        else:
            db_session.add(entry)
            db_session.commit()
            db_session.refresh(entry)

        headers = _auth(client, users["admin"].email)
        resp = client.post(f"/api/admin/waitlist/{entry.id}/decline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "declined"

    def test_admin_remind(self, client, users, db_session):
        from app.models.waitlist import WaitlistEntry

        entry = WaitlistEntry(
            full_name="Remind Me",
            email="wl_remind_me@test.com",
            roles="parent",
            status="approved",
            token=secrets.token_urlsafe(32),
            token_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        existing = db_session.query(WaitlistEntry).filter(WaitlistEntry.email == entry.email).first()
        if existing:
            entry = existing
        else:
            db_session.add(entry)
            db_session.commit()
            db_session.refresh(entry)

        old_token = entry.token
        headers = _auth(client, users["admin"].email)
        resp = client.post(f"/api/admin/waitlist/{entry.id}/remind", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Token should be refreshed
        assert data["token"] is not None

    def test_admin_non_admin_forbidden(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/admin/waitlist", headers=headers)
        assert resp.status_code == 403
