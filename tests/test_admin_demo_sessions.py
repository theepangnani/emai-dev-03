"""Tests for admin demo-sessions endpoints (CB-DEMO-001 B4, #3606)."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timezone

import pytest
from conftest import PASSWORD, _auth


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@pytest.fixture()
def admin_users(db_session):
    """Create admin and non-admin users (idempotent across tests)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    existing_admin = db_session.query(User).filter(
        User.email == "ds_admin@test.com"
    ).first()
    if existing_admin:
        parent = db_session.query(User).filter(
            User.email == "ds_parent@test.com"
        ).first()
        return {"admin": existing_admin, "parent": parent}

    hashed = get_password_hash(PASSWORD)
    admin = User(
        email="ds_admin@test.com",
        full_name="Demo Admin",
        role=UserRole.ADMIN,
        hashed_password=hashed,
    )
    parent = User(
        email="ds_parent@test.com",
        full_name="Demo Parent",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    db_session.add_all([admin, parent])
    db_session.commit()
    for u in (admin, parent):
        db_session.refresh(u)
    return {"admin": admin, "parent": parent}


@pytest.fixture()
def seeded_sessions(db_session):
    """Insert a few known demo_sessions rows. Returns list of created ids."""
    from app.models.demo_session import DemoSession

    # Clean slate for predictable counts
    db_session.query(DemoSession).delete()
    db_session.commit()

    rows = [
        DemoSession(
            email_hash=_email_hash("alice@example.com"),
            email="alice@example.com",
            full_name="Alice A",
            role="parent",
            verified=True,
            verified_ts=datetime.now(timezone.utc),
            generations_count=2,
            admin_status="pending",
            moat_engagement_json={
                "tm_beats_seen": 3,
                "rs_roles_switched": 1,
                "pw_viewport_reached": True,
            },
        ),
        DemoSession(
            email_hash=_email_hash("bob@example.com"),
            email="bob@example.com",
            full_name="Bob B",
            role="teacher",
            verified=False,
            generations_count=0,
            admin_status="pending",
        ),
        DemoSession(
            email_hash=_email_hash("carol@example.com"),
            email="carol@example.com",
            full_name="Carol C",
            role="student",
            verified=True,
            verified_ts=datetime.now(timezone.utc),
            generations_count=5,
            admin_status="approved",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    for r in rows:
        db_session.refresh(r)
    return rows


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_non_admin_cannot_list(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["parent"].email)
        resp = client.get("/api/admin/demo-sessions", headers=headers)
        assert resp.status_code == 403

    def test_unauth_cannot_list(self, client, seeded_sessions):
        resp = client.get("/api/admin/demo-sessions")
        assert resp.status_code == 401

    def test_admin_can_list(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get("/api/admin/demo-sessions", headers=headers)
        assert resp.status_code == 200

    def test_non_admin_cannot_approve(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["parent"].email)
        sid = seeded_sessions[0].id
        resp = client.post(
            f"/api/admin/demo-sessions/{sid}/approve", headers=headers
        )
        assert resp.status_code == 403

    def test_non_admin_cannot_export(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["parent"].email)
        resp = client.get("/api/admin/demo-sessions/export.csv", headers=headers)
        assert resp.status_code == 403


# ── List endpoint ────────────────────────────────────────────────────────────

class TestList:
    def test_returns_seeded_rows(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get("/api/admin/demo-sessions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["page"] == 1
        assert data["per_page"] == 50

        ids = {item["id"] for item in data["items"]}
        assert ids == {s.id for s in seeded_sessions}

    def test_pagination(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?page=1&per_page=2", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["per_page"] == 2

        resp2 = client.get(
            "/api/admin/demo-sessions?page=2&per_page=2", headers=headers
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["items"]) == 1
        assert data2["page"] == 2

    def test_per_page_cap(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?per_page=500", headers=headers
        )
        assert resp.status_code == 422  # Query max=200

    def test_filter_by_status(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?status=approved", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["admin_status"] == "approved"

    def test_filter_status_invalid(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?status=bogus", headers=headers
        )
        assert resp.status_code == 400

    def test_filter_by_verified_true(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?verified=true", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["verified"] is True

    def test_filter_by_verified_false(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?verified=false", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["verified"] is False

    def test_search_by_email(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?search=alice", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["email"] == "alice@example.com"

    def test_search_by_name(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?search=Bob", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["full_name"] == "Bob B"

    def test_moat_engagement_surfaced(self, client, admin_users, seeded_sessions):
        """FR-065: list should expose moat engagement fields."""
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions?search=alice", headers=headers
        )
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        # Either raw JSON or a flattened summary, per task spec.
        assert "moat_engagement_json" in item or "moat_summary" in item
        if "moat_summary" in item:
            summary = item["moat_summary"]
            assert summary["tm_beats_seen"] == 3
            assert summary["rs_roles_switched"] == 1
            assert summary["pw_viewport_reached"] is True


# ── Mutations ────────────────────────────────────────────────────────────────

class TestApproveRejectBlocklist:
    def test_approve_flips_status(self, client, admin_users, seeded_sessions, db_session):
        from app.models.demo_session import DemoSession

        headers = _auth(client, admin_users["admin"].email)
        sid = seeded_sessions[1].id  # bob, pending
        resp = client.post(
            f"/api/admin/demo-sessions/{sid}/approve", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["admin_status"] == "approved"

        db_session.expire_all()
        row = db_session.query(DemoSession).filter_by(id=sid).first()
        assert row.admin_status == "approved"

    def test_reject_flips_status(self, client, admin_users, seeded_sessions, db_session):
        from app.models.demo_session import DemoSession

        headers = _auth(client, admin_users["admin"].email)
        sid = seeded_sessions[0].id  # alice, pending
        resp = client.post(
            f"/api/admin/demo-sessions/{sid}/reject", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["admin_status"] == "rejected"

        db_session.expire_all()
        row = db_session.query(DemoSession).filter_by(id=sid).first()
        assert row.admin_status == "rejected"

    def test_blocklist_flips_status(self, client, admin_users, seeded_sessions, db_session):
        from app.models.demo_session import DemoSession

        headers = _auth(client, admin_users["admin"].email)
        sid = seeded_sessions[2].id  # carol, approved
        resp = client.post(
            f"/api/admin/demo-sessions/{sid}/blocklist", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["admin_status"] == "blocklisted"

        db_session.expire_all()
        row = db_session.query(DemoSession).filter_by(id=sid).first()
        assert row.admin_status == "blocklisted"

    def test_unknown_id_returns_404(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.post(
            "/api/admin/demo-sessions/does-not-exist/approve", headers=headers
        )
        assert resp.status_code == 404

    def test_audit_log_written_on_mutation(
        self, client, admin_users, seeded_sessions, db_session
    ):
        from app.models.audit_log import AuditLog

        headers = _auth(client, admin_users["admin"].email)
        sid = seeded_sessions[1].id
        before = db_session.query(AuditLog).filter(
            AuditLog.resource_type == "demo_session"
        ).count()

        resp = client.post(
            f"/api/admin/demo-sessions/{sid}/approve", headers=headers
        )
        assert resp.status_code == 200

        db_session.expire_all()
        after = db_session.query(AuditLog).filter(
            AuditLog.resource_type == "demo_session"
        ).count()
        assert after == before + 1


# ── CSV export ───────────────────────────────────────────────────────────────

class TestCsvExport:
    def test_export_returns_csv(self, client, admin_users, seeded_sessions):
        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions/export.csv", headers=headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        header_row = rows[0]
        assert header_row == [
            "id",
            "created_at",
            "email",
            "full_name",
            "role",
            "verified",
            "verified_ts",
            "generations_count",
            "admin_status",
        ]
        # 3 data rows
        assert len(rows) == 1 + 3

        data_emails = {r[2] for r in rows[1:]}
        assert data_emails == {
            "alice@example.com",
            "bob@example.com",
            "carol@example.com",
        }

    def test_export_rows_match_db(
        self, client, admin_users, seeded_sessions, db_session
    ):
        from app.models.demo_session import DemoSession

        headers = _auth(client, admin_users["admin"].email)
        resp = client.get(
            "/api/admin/demo-sessions/export.csv", headers=headers
        )
        assert resp.status_code == 200

        reader = csv.DictReader(io.StringIO(resp.text))
        by_email = {r["email"]: r for r in reader}

        for s in seeded_sessions:
            row = by_email[s.email]
            assert row["id"] == s.id
            assert row["role"] == s.role
            assert row["verified"] == ("true" if s.verified else "false")
            assert int(row["generations_count"]) == (s.generations_count or 0)
            assert row["admin_status"] == s.admin_status
