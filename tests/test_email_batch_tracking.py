"""Tests for send_emails_batch() delivery tracking (issue #2216)."""

from unittest.mock import patch, MagicMock
import pytest

from app.services.email_service import send_emails_batch


EMAILS = [
    ("a@example.com", "Subject A", "<p>A</p>"),
    ("b@example.com", "Subject B", "<p>B</p>"),
    ("c@example.com", "Subject C", "<p>C</p>"),
]


def test_empty_list_returns_zero_counts():
    result = send_emails_batch([])
    assert result == {"sent": 0, "failed": 0, "failed_emails": []}


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=True)
@patch("app.services.email_service._send_via_sendgrid")
def test_all_succeed_via_sendgrid(mock_sg, mock_key):
    result = send_emails_batch(EMAILS)
    assert result["sent"] == 3
    assert result["failed"] == 0
    assert result["failed_emails"] == []


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=True)
@patch("app.services.email_service._send_via_sendgrid")
def test_partial_failure_via_sendgrid(mock_sg, mock_key):
    mock_sg.side_effect = [None, Exception("rate limit"), None]
    result = send_emails_batch(EMAILS)
    assert result["sent"] == 2
    assert result["failed"] == 1
    assert result["failed_emails"] == ["b@example.com"]


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=True)
@patch("app.services.email_service._send_via_sendgrid", side_effect=Exception("down"))
@patch("app.services.email_service.settings")
def test_sendgrid_all_fail_falls_back_to_smtp(mock_settings, mock_sg, mock_key):
    """When SendGrid fails for all, falls back to SMTP."""
    mock_settings.smtp_user = "user@test.com"
    mock_settings.smtp_password = "pass"
    mock_settings.smtp_host = "smtp.test.com"
    mock_settings.smtp_port = 587

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_emails_batch(EMAILS)
        assert result["sent"] == 3
        assert result["failed"] == 0
        assert result["failed_emails"] == []


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
def test_smtp_partial_failure(mock_settings, mock_key):
    mock_settings.smtp_user = "user@test.com"
    mock_settings.smtp_password = "pass"
    mock_settings.smtp_host = "smtp.test.com"
    mock_settings.smtp_port = 587

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        # Second send_message call raises
        mock_server.send_message.side_effect = [None, Exception("bad addr"), None]
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_emails_batch(EMAILS)
        assert result["sent"] == 2
        assert result["failed"] == 1
        assert result["failed_emails"] == ["b@example.com"]


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
def test_no_provider_configured(mock_settings, mock_key):
    mock_settings.smtp_user = ""
    mock_settings.smtp_password = ""

    result = send_emails_batch(EMAILS)
    assert result["sent"] == 0
    assert result["failed"] == 3
    assert set(result["failed_emails"]) == {"a@example.com", "b@example.com", "c@example.com"}


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
def test_smtp_connection_failure(mock_settings, mock_key):
    mock_settings.smtp_user = "user@test.com"
    mock_settings.smtp_password = "pass"
    mock_settings.smtp_host = "smtp.test.com"
    mock_settings.smtp_port = 587

    with patch("app.services.email_service.smtplib.SMTP", side_effect=Exception("connection refused")):
        result = send_emails_batch(EMAILS)
        assert result["sent"] == 0
        assert result["failed"] == 3
        assert len(result["failed_emails"]) == 3


def test_return_type_is_dict():
    result = send_emails_batch([])
    assert isinstance(result, dict)
    assert "sent" in result
    assert "failed" in result
    assert "failed_emails" in result
