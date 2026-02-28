"""Tests for progressive account lockout and admin unlock (#796)."""

from datetime import datetime, timedelta, timezone

import pytest
from conftest import PASSWORD, _login


def _create_user(db_session, email="lockout@test.com"):
    """Create a user for lockout testing."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        full_name="Lockout Test User",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_admin(db_session, email="lockout_admin@test.com"):
    """Create an admin user for unlock testing."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        full_name="Lockout Admin",
        role=UserRole.ADMIN,
        roles="admin",
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _fail_login(client, email, n=1):
    """Attempt N failed logins for the given email."""
    for _ in range(n):
        client.post("/api/auth/login", data={"username": email, "password": "WrongPassword999!"})


class TestProgressiveLockout:
    """Test progressive lockout thresholds."""

    def test_no_lockout_under_5_failures(self, client, db_session):
        user = _create_user(db_session, "lockout_under5@test.com")
        _fail_login(client, user.email, 4)

        # 5th login with correct password should succeed
        resp = client.post("/api/auth/login", data={"username": user.email, "password": PASSWORD})
        assert resp.status_code == 200

    def test_lockout_after_5_failures(self, client, db_session):
        user = _create_user(db_session, "lockout_5@test.com")
        _fail_login(client, user.email, 5)

        # User should now be locked
        db_session.refresh(user)
        assert user.failed_login_attempts == 5
        assert user.locked_until is not None

        # Correct password should return 423
        resp = client.post("/api/auth/login", data={"username": user.email, "password": PASSWORD})
        assert resp.status_code == 423
        assert "locked" in resp.json()["detail"].lower()
        assert "Retry-After" in resp.headers

    def test_lockout_after_10_failures(self, client, db_session):
        user = _create_user(db_session, "lockout_10@test.com")

        # Directly set 9 failures with expired lock (simulating past lockouts that expired)
        user.failed_login_attempts = 9
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        # 1 more failure triggers the 10th and 1-hour lockout
        _fail_login(client, user.email, 1)
        db_session.refresh(user)
        assert user.failed_login_attempts == 10
        assert user.locked_until is not None

    def test_lockout_after_15_failures_creates_admin_notification(self, client, db_session):
        user = _create_user(db_session, "lockout_15@test.com")
        admin = _create_admin(db_session, "lockout_notif_admin@test.com")

        # Directly set 14 failures with expired lock
        user.failed_login_attempts = 14
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        # 1 more failure triggers the 15th and 24-hour lockout + admin notification
        _fail_login(client, user.email, 1)
        db_session.refresh(user)
        assert user.failed_login_attempts == 15

        # Check admin notification was created
        from app.models.notification import Notification
        notifs = db_session.query(Notification).filter(
            Notification.user_id == admin.id,
            Notification.title == "Account Lockout Alert",
        ).all()
        assert len(notifs) >= 1
        assert user.email in notifs[0].content


class TestSuccessfulLoginResets:
    """Test that successful login resets lockout state."""

    def test_successful_login_resets_failed_attempts(self, client, db_session):
        user = _create_user(db_session, "lockout_reset@test.com")
        _fail_login(client, user.email, 3)

        db_session.refresh(user)
        assert user.failed_login_attempts == 3

        # Successful login
        resp = client.post("/api/auth/login", data={"username": user.email, "password": PASSWORD})
        assert resp.status_code == 200

        db_session.refresh(user)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.last_failed_login is None

    def test_successful_login_after_expired_lockout(self, client, db_session):
        user = _create_user(db_session, "lockout_expired@test.com")
        # Set expired lockout
        user.failed_login_attempts = 5
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        # Login should succeed now
        resp = client.post("/api/auth/login", data={"username": user.email, "password": PASSWORD})
        assert resp.status_code == 200

        db_session.refresh(user)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


class TestLockoutExpiry:
    """Test that lockout clears after duration."""

    def test_lock_clears_after_duration(self, client, db_session):
        user = _create_user(db_session, "lockout_expiry@test.com")

        # Simulate lockout that has expired
        user.failed_login_attempts = 5
        user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()

        # Should be able to attempt login (not get 423)
        resp = client.post("/api/auth/login", data={"username": user.email, "password": "WrongPassword999!"})
        # Should get 401 (not 423) because lock has expired
        assert resp.status_code == 401

    def test_active_lock_returns_423(self, client, db_session):
        user = _create_user(db_session, "lockout_active@test.com")

        # Simulate active lockout
        user.failed_login_attempts = 5
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        db_session.commit()

        resp = client.post("/api/auth/login", data={"username": user.email, "password": PASSWORD})
        assert resp.status_code == 423
        retry_after = int(resp.headers.get("Retry-After", 0))
        assert retry_after > 0


class TestAdminUnlock:
    """Test admin unlock endpoint."""

    def test_admin_can_unlock_locked_account(self, client, db_session):
        user = _create_user(db_session, "lockout_unlock@test.com")
        admin = _create_admin(db_session, "lockout_unlock_admin@test.com")

        # Lock the account
        user.failed_login_attempts = 10
        user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
        user.last_failed_login = datetime.now(timezone.utc)
        db_session.commit()

        # Admin unlocks
        admin_token = _login(client, admin.email)
        resp = client.post(
            f"/api/admin/users/{user.id}/unlock",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "unlocked" in resp.json()["message"].lower()

        # Verify user can now login
        db_session.refresh(user)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.last_failed_login is None

        login_resp = client.post("/api/auth/login", data={"username": user.email, "password": PASSWORD})
        assert login_resp.status_code == 200

    def test_non_admin_cannot_unlock(self, client, db_session):
        user = _create_user(db_session, "lockout_nonadmin@test.com")
        parent = _create_user(db_session, "lockout_parent@test.com")

        parent_token = _login(client, parent.email)
        resp = client.post(
            f"/api/admin/users/{user.id}/unlock",
            headers={"Authorization": f"Bearer {parent_token}"},
        )
        assert resp.status_code == 403

    def test_unlock_nonexistent_user_returns_404(self, client, db_session):
        admin = _create_admin(db_session, "lockout_404_admin@test.com")
        admin_token = _login(client, admin.email)
        resp = client.post(
            "/api/admin/users/999999/unlock",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


class TestRemainingAttemptsInfo:
    """Test that remaining attempts info is returned to the client."""

    def test_remaining_attempts_shown_after_3_failures(self, client, db_session):
        user = _create_user(db_session, "lockout_remaining@test.com")
        _fail_login(client, user.email, 3)

        # 4th failure should show remaining attempts
        resp = client.post("/api/auth/login", data={"username": user.email, "password": "WrongPassword999!"})
        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert "attempt" in detail.lower() or "remaining" in detail.lower()


class TestNonexistentUser:
    """Test that nonexistent user login doesn't leak info."""

    def test_nonexistent_user_returns_401(self, client):
        resp = client.post("/api/auth/login", data={"username": "nobody@nowhere.com", "password": "WrongPass123!"})
        assert resp.status_code == 401
        assert "incorrect" in resp.json()["detail"].lower()
