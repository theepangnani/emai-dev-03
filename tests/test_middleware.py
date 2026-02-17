"""Tests for custom middleware (domain redirect, security headers)."""

import pytest
from unittest.mock import patch


def test_health_no_redirect(client):
    """Health endpoint should never redirect, even with canonical domain set."""
    with patch("app.core.config.settings.canonical_domain", "www.classbridge.ca"):
        resp = client.get("/health", headers={"host": "clazzbridge.com"})
        assert resp.status_code == 200


def test_canonical_domain_no_redirect(client):
    """Requests to the canonical domain should not redirect."""
    with patch("app.core.config.settings.canonical_domain", "www.classbridge.ca"):
        resp = client.get(
            "/api/users/me",
            headers={"host": "www.classbridge.ca"},
            follow_redirects=False,
        )
        # Should get 401 (no auth), not 301
        assert resp.status_code == 401


def test_non_canonical_redirects(client):
    """Requests to non-canonical domains should 301 redirect."""
    with patch("app.core.config.settings.canonical_domain", "www.classbridge.ca"):
        for host in ["clazzbridge.com", "www.clazzbridge.com", "classbridge.ca"]:
            resp = client.get(
                "/api/courses/",
                headers={"host": host},
                follow_redirects=False,
            )
            assert resp.status_code == 301, f"Expected 301 for host={host}, got {resp.status_code}"
            assert "www.classbridge.ca" in resp.headers["location"]


def test_redirect_preserves_path_and_query(client):
    """Redirect should preserve the original path and query string."""
    with patch("app.core.config.settings.canonical_domain", "www.classbridge.ca"):
        resp = client.get(
            "/api/search?q=math&limit=10",
            headers={"host": "clazzbridge.com"},
            follow_redirects=False,
        )
        assert resp.status_code == 301
        location = resp.headers["location"]
        assert "/api/search" in location
        assert "q=math" in location
        assert "limit=10" in location


def test_no_redirect_when_canonical_not_set(client):
    """When canonical_domain is empty, no redirects should happen."""
    with patch("app.core.config.settings.canonical_domain", ""):
        resp = client.get(
            "/api/users/me",
            headers={"host": "clazzbridge.com"},
            follow_redirects=False,
        )
        # Should get 401 (no auth), not 301
        assert resp.status_code == 401


def test_security_headers_present(client):
    """Security headers should be present on responses."""
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in resp.headers.get("Permissions-Policy", "")
