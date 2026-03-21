"""Tests for CASL-compliant email opt-in and one-click unsubscribe (#2022)."""

from datetime import datetime, timezone

import pytest
from conftest import PASSWORD


def _register_with_consent(client, email, consent=False):
    return client.post("/api/auth/register", json={
        "email": email,
        "password": PASSWORD,
        "full_name": "Test User",
        "role": "parent",
        "email_consent": consent,
    })


# ── Registration consent tests ──────────────────────────────


def test_register_with_consent_true_enables_digest(client, db_session):
    """email_consent=True should set daily_digest_enabled, email_marketing_consent, and email_consent_date."""
    resp = _register_with_consent(client, "casl_yes@example.com", consent=True)
    assert resp.status_code == 200, resp.text

    from app.models.user import User
    user = db_session.query(User).filter(User.email == "casl_yes@example.com").first()
    assert user is not None
    assert user.daily_digest_enabled is True
    assert user.email_marketing_consent is True
    assert user.email_consent_date is not None


def test_register_with_consent_false_no_digest(client, db_session):
    """email_consent=False (default) should NOT enable digest or consent."""
    resp = _register_with_consent(client, "casl_no@example.com", consent=False)
    assert resp.status_code == 200, resp.text

    from app.models.user import User
    user = db_session.query(User).filter(User.email == "casl_no@example.com").first()
    assert user is not None
    assert user.daily_digest_enabled is False
    assert user.email_marketing_consent is False
    assert user.email_consent_date is None


def test_register_default_no_consent(client, db_session):
    """Omitting email_consent entirely should default to no consent (CASL)."""
    resp = client.post("/api/auth/register", json={
        "email": "casl_default@example.com",
        "password": PASSWORD,
        "full_name": "Default User",
        "role": "parent",
    })
    assert resp.status_code == 200, resp.text

    from app.models.user import User
    user = db_session.query(User).filter(User.email == "casl_default@example.com").first()
    assert user.daily_digest_enabled is False
    assert user.email_marketing_consent is False


# ── Unsubscribe endpoint tests ──────────────────────────────


def test_unsubscribe_valid_token(client, db_session):
    """Valid unsubscribe token should disable digest and consent."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash, create_unsubscribe_token

    user = User(
        email="unsub_valid@example.com",
        full_name="Unsub Valid",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
        daily_digest_enabled=True,
        email_marketing_consent=True,
        email_consent_date=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()

    token = create_unsubscribe_token(user.id)
    resp = client.get(f"/api/auth/unsubscribe/{token}")
    assert resp.status_code == 200
    assert "unsubscribed" in resp.text.lower()

    db_session.refresh(user)
    assert user.daily_digest_enabled is False
    assert user.email_marketing_consent is False


def test_unsubscribe_invalid_token(client):
    """Invalid token should return 400."""
    resp = client.get("/api/auth/unsubscribe/invalid.token.here")
    assert resp.status_code == 400
    assert "invalid" in resp.text.lower() or "expired" in resp.text.lower()


def test_unsubscribe_expired_token(client, db_session):
    """Expired token should return 400."""
    from jose import jwt
    from app.core.config import settings
    from datetime import timedelta

    expired_payload = {
        "sub": "999",
        "exp": datetime.now(timezone.utc) - timedelta(days=1),
        "type": "unsubscribe",
    }
    token = jwt.encode(expired_payload, settings.secret_key, algorithm=settings.algorithm)
    resp = client.get(f"/api/auth/unsubscribe/{token}")
    assert resp.status_code == 400


def test_unsubscribe_wrong_type_token(client, db_session):
    """Token with wrong type should be rejected."""
    from app.core.security import create_password_reset_token

    token = create_password_reset_token("test@example.com")
    resp = client.get(f"/api/auth/unsubscribe/{token}")
    assert resp.status_code == 400


# ── Digest job filter tests ─────────────────────────────────


def test_digest_jobs_skip_users_without_consent(db_session):
    """Users with daily_digest_enabled=False should not be queried by digest jobs."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    # Create opted-in user
    opted_in = User(
        email="opted_in@example.com",
        full_name="Opted In",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=get_password_hash(PASSWORD),
        daily_digest_enabled=True,
        email_marketing_consent=True,
        is_active=True,
    )
    # Create opted-out user
    opted_out = User(
        email="opted_out@example.com",
        full_name="Opted Out",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=get_password_hash(PASSWORD),
        daily_digest_enabled=False,
        email_marketing_consent=False,
        is_active=True,
    )
    db_session.add_all([opted_in, opted_out])
    db_session.commit()

    # Simulate the same query used by digest jobs
    parents = (
        db_session.query(User)
        .filter(
            User.role == UserRole.PARENT,
            User.is_active == True,
            User.daily_digest_enabled == True,
            User.email == "opted_in@example.com",  # narrow to our test data
        )
        .all()
    )
    assert len(parents) == 1
    assert parents[0].email == "opted_in@example.com"

    # Opted-out user should not appear
    parents_out = (
        db_session.query(User)
        .filter(
            User.role == UserRole.PARENT,
            User.is_active == True,
            User.daily_digest_enabled == True,
            User.email == "opted_out@example.com",
        )
        .all()
    )
    assert len(parents_out) == 0
