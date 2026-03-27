"""Tests for send_emails_batch partial-send tracking (#2444)."""

from unittest.mock import patch, MagicMock
import smtplib

from app.services.email_service import send_emails_batch


EMAILS = [
    ("a@test.com", "Subject A", "<p>A</p>"),
    ("b@test.com", "Subject B", "<p>B</p>"),
    ("c@test.com", "Subject C", "<p>C</p>"),
]


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
def test_empty_list(mock_settings, _mock_sg):
    result = send_emails_batch([])
    assert result == {"sent": 0, "failed": 0, "failed_emails": []}


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
@patch("app.services.email_service.smtplib")
def test_all_sent(mock_smtplib, mock_settings, _mock_sg):
    mock_settings.smtp_user = "user"
    mock_settings.smtp_password = "pass"
    mock_settings.smtp_host = "localhost"
    mock_settings.smtp_port = 587

    mock_server = MagicMock()
    mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

    result = send_emails_batch(EMAILS)
    assert result["sent"] == 3
    assert result["failed"] == 0
    assert result["failed_emails"] == []


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
@patch("app.services.email_service.smtplib")
def test_connection_failure_after_partial_send(mock_smtplib, mock_settings, _mock_sg):
    """SMTP connection drop mid-batch should count only unsent emails as failed."""
    mock_settings.smtp_user = "user"
    mock_settings.smtp_password = "pass"
    mock_settings.smtp_host = "localhost"
    mock_settings.smtp_port = 587

    call_count = 0

    def send_side_effect(msg):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise smtplib.SMTPServerDisconnected("Connection lost")

    mock_server = MagicMock()
    mock_server.send_message.side_effect = send_side_effect
    mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

    result = send_emails_batch(EMAILS)
    # First email sent, second and third failed
    assert result["sent"] == 1
    assert result["failed"] == 2
    assert "a@test.com" not in result["failed_emails"]


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
def test_smtp_connection_failure_no_partial(mock_settings, _mock_sg):
    """SMTP connection failure at connect time should mark all as failed."""
    mock_settings.smtp_user = "user"
    mock_settings.smtp_password = "pass"
    mock_settings.smtp_host = "localhost"
    mock_settings.smtp_port = 587

    with patch("app.services.email_service.smtplib.SMTP", side_effect=ConnectionRefusedError("refused")):
        result = send_emails_batch(EMAILS)

    assert result["sent"] == 0
    assert result["failed"] == 3
    assert set(result["failed_emails"]) == {"a@test.com", "b@test.com", "c@test.com"}


@patch("app.services.email_service._has_valid_sendgrid_key", return_value=False)
@patch("app.services.email_service.settings")
def test_no_provider_configured(mock_settings, _mock_sg):
    mock_settings.smtp_user = ""
    mock_settings.smtp_password = ""

    result = send_emails_batch(EMAILS)
    assert result["sent"] == 0
    assert result["failed"] == 3
