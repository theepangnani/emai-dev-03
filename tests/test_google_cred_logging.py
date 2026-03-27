"""Tests for Google credential refresh warning logs (#2215)."""

import logging
from unittest.mock import MagicMock, patch

from app.services.google_classroom import get_classroom_service, get_gmail_service


def _make_creds(refresh_token="tok"):
    """Return a mock Credentials object with a refresh token."""
    creds = MagicMock()
    creds.refresh_token = refresh_token
    creds.token = "access"
    creds.expiry = None
    return creds


@patch("app.services.google_classroom.build")
@patch("app.services.google_classroom.get_credentials")
def test_classroom_refresh_failure_logs_warning(mock_get_creds, mock_build, caplog):
    creds = _make_creds()
    creds.refresh.side_effect = Exception("token revoked")
    mock_get_creds.return_value = creds

    with caplog.at_level(logging.WARNING, logger="app.services.google_classroom"):
        get_classroom_service("at", "rt")

    assert any("token refresh failed" in m for m in caplog.messages)
    assert any("token revoked" in m for m in caplog.messages)


@patch("app.services.google_classroom.build")
@patch("app.services.google_classroom.get_credentials")
def test_gmail_refresh_failure_logs_warning(mock_get_creds, mock_build, caplog):
    creds = _make_creds()
    creds.refresh.side_effect = Exception("invalid_grant")
    mock_get_creds.return_value = creds

    with caplog.at_level(logging.WARNING, logger="app.services.google_classroom"):
        get_gmail_service("at", "rt")

    assert any("token refresh failed" in m for m in caplog.messages)
    assert any("invalid_grant" in m for m in caplog.messages)


@patch("app.services.google_classroom.build")
@patch("app.services.google_classroom.get_credentials")
def test_classroom_refresh_success_no_warning(mock_get_creds, mock_build, caplog):
    creds = _make_creds()
    mock_get_creds.return_value = creds

    with caplog.at_level(logging.WARNING, logger="app.services.google_classroom"):
        get_classroom_service("at", "rt")

    assert not any("credential refresh failed" in m for m in caplog.messages)
