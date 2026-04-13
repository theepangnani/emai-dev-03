"""Regression tests for /api/features endpoint.

The endpoint must work without authentication (regression for #3239
login loop fix) and return expected config-based flags.
"""

from conftest import PASSWORD, _auth


def _register(client, email, role="parent", full_name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


def test_features_unauthenticated(client):
    """Regression: /api/features must work without auth (fixes #3239)."""
    response = client.get("/api/features")
    assert response.status_code == 200
    data = response.json()
    assert "waitlist_enabled" in data
    assert "google_classroom" in data


def test_features_authenticated(client):
    """Authenticated users should get feature flags including DB-backed ones."""
    email = "features-auth@example.com"
    reg = _register(client, email)
    assert reg.status_code == 200, reg.text
    headers = _auth(client, email)

    response = client.get("/api/features", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "waitlist_enabled" in data
    assert "google_classroom" in data
