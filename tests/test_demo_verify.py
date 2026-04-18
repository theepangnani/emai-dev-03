"""Tests for /api/v1/demo/verify + /api/v1/demo/verify/code (CB-DEMO-001 B2, #3604)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _reset_demo_sessions(db_session):
    """Clean demo_sessions before and after each test."""
    from app.models.demo_session import DemoSession

    db_session.query(DemoSession).delete()
    db_session.commit()
    yield
    db_session.query(DemoSession).delete()
    db_session.commit()


def _make_session(
    db_session,
    *,
    email: str,
    source_ip_hash: str | None = None,
    role: str = "parent",
) -> tuple[object, str, str]:
    """Create a DemoSession with magic-link + fallback-code credentials set.

    Returns ``(session, raw_token, raw_code)``.
    """
    from app.models.demo_session import DemoSession
    from app.services.demo_verification import (
        create_fallback_code,
        create_magic_link_token,
        set_verification_credentials,
    )

    session = DemoSession(
        email_hash=_email_hash(email),
        email=email,
        full_name=email.split("@")[0].title(),
        role=role,
        source_ip_hash=source_ip_hash,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    raw_token, token_hash = create_magic_link_token(session.id, email)
    raw_code, code_hash = create_fallback_code()
    set_verification_credentials(
        db_session, session, token_hash=token_hash, code_hash=code_hash
    )
    db_session.commit()
    db_session.refresh(session)
    return session, raw_token, raw_code


# ── /demo/verify (magic link) ────────────────────────────────────────────────


class TestMagicLinkVerify:
    def test_valid_token_redirects_to_verified(self, client, db_session):
        from app.models.demo_session import DemoSession

        session, raw_token, _ = _make_session(
            db_session, email="mlink@example.com"
        )
        resp = client.get(
            f"/api/v1/demo/verify?token={raw_token}", follow_redirects=False
        )
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "/demo/verified?pos=" in loc

        db_session.expire_all()
        refreshed = db_session.query(DemoSession).filter_by(id=session.id).first()
        assert refreshed.verified is True
        assert refreshed.admin_status == "approved"

    def test_invalid_token_redirects_to_failed(self, client):
        resp = client.get(
            "/api/v1/demo/verify?token=not-a-real-token", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/demo/verify-failed" in resp.headers["location"]

    def test_missing_token_redirects_to_failed(self, client):
        resp = client.get("/api/v1/demo/verify", follow_redirects=False)
        assert resp.status_code == 302
        assert "/demo/verify-failed" in resp.headers["location"]

    def test_expired_token_redirects_to_failed(self, client, db_session):
        session, raw_token, _ = _make_session(
            db_session, email="expired@example.com"
        )
        # Force expiry into the past.
        session.verification_expires_at = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        db_session.commit()

        resp = client.get(
            f"/api/v1/demo/verify?token={raw_token}", follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/demo/verify-failed" in resp.headers["location"]

    def test_anomaly_leaves_status_pending(self, client, db_session):
        """3+ distinct emails from same ip_hash in 24h → pending."""
        from app.models.demo_session import DemoSession

        ip_hash = "a" * 64
        # Two "sibling" sessions from same IP (these don't need valid creds).
        for i in range(2):
            sibling = DemoSession(
                email_hash=_email_hash(f"sib{i}@example.com"),
                email=f"sib{i}@example.com",
                full_name=f"Sib {i}",
                role="parent",
                source_ip_hash=ip_hash,
            )
            db_session.add(sibling)
        db_session.commit()

        session, raw_token, _ = _make_session(
            db_session, email="target@example.com", source_ip_hash=ip_hash
        )
        resp = client.get(
            f"/api/v1/demo/verify?token={raw_token}", follow_redirects=False
        )
        assert resp.status_code == 302

        db_session.expire_all()
        refreshed = db_session.query(DemoSession).filter_by(id=session.id).first()
        assert refreshed.verified is True
        assert refreshed.admin_status == "pending"

    def test_no_anomaly_auto_approves(self, client, db_session):
        from app.models.demo_session import DemoSession

        session, raw_token, _ = _make_session(
            db_session, email="solo@example.com", source_ip_hash="b" * 64
        )
        resp = client.get(
            f"/api/v1/demo/verify?token={raw_token}", follow_redirects=False
        )
        assert resp.status_code == 302

        db_session.expire_all()
        refreshed = db_session.query(DemoSession).filter_by(id=session.id).first()
        assert refreshed.admin_status == "approved"


# ── /demo/verify/code ───────────────────────────────────────────────────────


class TestFallbackCodeVerify:
    def test_valid_code_returns_position(self, client, db_session):
        session, _, raw_code = _make_session(
            db_session, email="code@example.com"
        )
        resp = client.post(
            "/api/v1/demo/verify/code",
            json={"email": "code@example.com", "code": raw_code},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["verified"] is True
        assert isinstance(body["waitlist_position"], int)
        assert body["waitlist_position"] >= 1
        assert body["anomaly_flagged"] is False

    def test_wrong_code_returns_400(self, client, db_session):
        _make_session(db_session, email="bad@example.com")
        resp = client.post(
            "/api/v1/demo/verify/code",
            json={"email": "bad@example.com", "code": "000000"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == {"error": "invalid_code"}

    def test_code_anomaly_flagged(self, client, db_session):
        from app.models.demo_session import DemoSession

        ip_hash = "c" * 64
        for i in range(2):
            sibling = DemoSession(
                email_hash=_email_hash(f"csib{i}@example.com"),
                email=f"csib{i}@example.com",
                full_name=f"CSib {i}",
                role="parent",
                source_ip_hash=ip_hash,
            )
            db_session.add(sibling)
        db_session.commit()

        _, _, raw_code = _make_session(
            db_session, email="flag@example.com", source_ip_hash=ip_hash
        )
        resp = client.post(
            "/api/v1/demo/verify/code",
            json={"email": "flag@example.com", "code": raw_code},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["verified"] is True
        assert body["anomaly_flagged"] is True
