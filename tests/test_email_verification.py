"""Tests for email verification (#417)."""
from unittest.mock import patch

PASSWORD = "Password123!"


def _register(client, email, full_name="Test User", google_id=None):
    payload = {
        "email": email, "password": PASSWORD, "full_name": full_name, "roles": [],
    }
    if google_id:
        payload["google_id"] = google_id
    return client.post("/api/auth/register", json=payload)


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


def _make_verify_token(email):
    """Import inside function to avoid early module import that breaks secret key alignment."""
    from app.core.security import create_email_verification_token
    return create_email_verification_token(email)


class TestRegistrationSendsVerification:
    @patch("app.api.routes.auth.send_email_sync")
    def test_register_sends_verification_email(self, mock_send, client):
        resp = _register(client, "verify_send@test.com")
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is False
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args.kwargs["to_email"] == "verify_send@test.com"
        assert "Verify Your Email" in call_args.kwargs["subject"]

    @patch("app.api.routes.auth.send_email_sync")
    def test_google_signup_auto_verified(self, mock_send, client):
        resp = _register(client, "google_verify@test.com", google_id="gid-123")
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is True
        # Should NOT send verification email for Google signups
        mock_send.assert_not_called()


class TestVerifyEmailEndpoint:
    def test_verify_valid_token(self, client):
        _register(client, "verify_valid@test.com")
        token = _make_verify_token("verify_valid@test.com")

        resp = client.post("/api/auth/verify-email", json={"token": token})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Email verified successfully"

        # Confirm via /me
        headers = _auth(client, "verify_valid@test.com")
        me = client.get("/api/users/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email_verified"] is True

    def test_verify_invalid_token(self, client):
        resp = client.post("/api/auth/verify-email", json={"token": "invalid-token"})
        assert resp.status_code == 400
        assert "invalid or expired" in resp.json()["detail"].lower()

    def test_verify_already_verified(self, client):
        _register(client, "verify_dup@test.com")
        token = _make_verify_token("verify_dup@test.com")

        # Verify once
        client.post("/api/auth/verify-email", json={"token": token})
        # Verify again
        resp = client.post("/api/auth/verify-email", json={"token": token})
        assert resp.status_code == 200
        assert "already verified" in resp.json()["message"].lower()

    def test_verify_nonexistent_email(self, client):
        token = _make_verify_token("nobody@test.com")
        resp = client.post("/api/auth/verify-email", json={"token": token})
        assert resp.status_code == 400


class TestResendVerification:
    def test_resend_requires_auth(self, client):
        resp = client.post("/api/auth/resend-verification")
        assert resp.status_code == 401

    @patch("app.api.routes.auth.send_email_sync")
    def test_resend_sends_email(self, mock_send, client):
        _register(client, "resend@test.com")
        mock_send.reset_mock()  # Clear the registration send
        headers = _auth(client, "resend@test.com")

        resp = client.post("/api/auth/resend-verification", headers=headers)
        assert resp.status_code == 200
        assert "sent" in resp.json()["message"].lower()
        mock_send.assert_called_once()

    def test_resend_rejected_if_already_verified(self, client):
        _register(client, "resend_done@test.com")
        # Verify email first
        token = _make_verify_token("resend_done@test.com")
        client.post("/api/auth/verify-email", json={"token": token})

        headers = _auth(client, "resend_done@test.com")
        resp = client.post("/api/auth/resend-verification", headers=headers)
        assert resp.status_code == 400
        assert "already verified" in resp.json()["detail"].lower()


class TestMeIncludesEmailVerified:
    def test_me_returns_email_verified_false(self, client):
        _register(client, "me_unverified@test.com")
        headers = _auth(client, "me_unverified@test.com")
        resp = client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is False

    def test_me_returns_email_verified_true_after_verify(self, client):
        _register(client, "me_verified@test.com")
        token = _make_verify_token("me_verified@test.com")
        client.post("/api/auth/verify-email", json={"token": token})

        headers = _auth(client, "me_verified@test.com")
        resp = client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is True
