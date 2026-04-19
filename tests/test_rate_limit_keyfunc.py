"""Tests for get_email_hash_or_ip rate-limit keyfunc (CB-DEMO-001, #3636)."""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock


def _make_request(headers=None):
    """Build a lightweight mock Request with a headers dict."""
    request = MagicMock()
    request.headers = headers or {}
    # slowapi.get_remote_address reads request.client.host — provide a sane default.
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    return request


class TestGetEmailHashOrIp:
    def test_header_present_returns_hashed_email(self):
        """X-Demo-Email header → returns 'demo-email:<sha256>'."""
        from app.core.rate_limit import get_email_hash_or_ip

        email = "Alice@Example.com"
        req = _make_request(headers={"X-Demo-Email": email})
        result = get_email_hash_or_ip(req)

        expected_hash = hashlib.sha256(
            email.strip().lower().encode("utf-8")
        ).hexdigest()
        assert result == f"demo-email:{expected_hash}"

    def test_header_present_normalises_case_and_whitespace(self):
        """Email is lower-cased and stripped before hashing."""
        from app.core.rate_limit import get_email_hash_or_ip

        req = _make_request(headers={"X-Demo-Email": "  BOB@Example.com  "})
        result = get_email_hash_or_ip(req)
        expected_hash = hashlib.sha256(
            b"bob@example.com"
        ).hexdigest()
        assert result == f"demo-email:{expected_hash}"

    def test_header_absent_falls_back_to_client_ip(self):
        """No X-Demo-Email header → falls through to get_client_ip."""
        from app.core.rate_limit import get_email_hash_or_ip

        req = _make_request(headers={})
        result = get_email_hash_or_ip(req)
        # No demo-email: prefix — matches get_client_ip output.
        assert not result.startswith("demo-email:")
        assert result == "10.0.0.1"

    def test_header_absent_honors_x_forwarded_for(self):
        """Fallback path uses X-Forwarded-For via get_client_ip."""
        from app.core.rate_limit import get_email_hash_or_ip

        req = _make_request(headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"})
        result = get_email_hash_or_ip(req)
        assert result == "203.0.113.5"
