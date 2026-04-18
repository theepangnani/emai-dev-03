"""Unit tests for M2 digest services and job (#2997).

Tests:
- ParentGmailService: fetch_child_emails, verify_forwarding
- ParentDigestAIService: generate_parent_digest
- WhatsAppService: send_whatsapp_message, generate_otp, send_otp, is_whatsapp_enabled
- DigestJob: process_parent_email_digests
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# TestParentGmailService
# ---------------------------------------------------------------------------


class TestParentGmailService:
    """Tests for app.services.parent_gmail_service."""

    def _make_integration(self, **overrides):
        """Create a mock ParentGmailIntegration."""
        integration = MagicMock()
        integration.id = overrides.get("id", 1)
        integration.parent_id = overrides.get("parent_id", 10)
        integration.child_school_email = overrides.get("child_school_email", "child@school.ca")
        integration.access_token = overrides.get("access_token", "enc_access")
        integration.refresh_token = overrides.get("refresh_token", "enc_refresh")
        integration.last_synced_at = overrides.get("last_synced_at", None)
        integration.is_active = overrides.get("is_active", True)
        integration.whatsapp_verified = overrides.get("whatsapp_verified", False)
        integration.whatsapp_phone = overrides.get("whatsapp_phone", None)
        return integration

    @pytest.mark.asyncio
    async def test_fetch_child_emails_no_school_email(self):
        """Integration with no child_school_email returns []."""
        from app.services.parent_gmail_service import fetch_child_emails

        db = MagicMock()
        integration = self._make_integration(child_school_email=None)

        result = await fetch_child_emails(db, integration)
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_child_emails_no_access_token(self):
        """Integration with no access_token returns []."""
        from app.services.parent_gmail_service import fetch_child_emails

        db = MagicMock()
        integration = self._make_integration(access_token=None)

        with patch("app.services.parent_gmail_service.decrypt_token", return_value=None):
            result = await fetch_child_emails(db, integration)
        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service.get_gmail_service")
    @patch("app.services.parent_gmail_service.decrypt_token")
    async def test_fetch_child_emails_gmail_auth_failure(self, mock_decrypt, mock_get_gmail):
        """Gmail 401 sets is_active to False."""
        from googleapiclient.errors import HttpError
        from app.services.parent_gmail_service import fetch_child_emails

        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "decrypted_token"
        mock_get_gmail.return_value = (mock_service, mock_creds)

        # Simulate 401 on messages().list()
        resp = MagicMock()
        resp.status = 401
        http_err = HttpError(resp=resp, content=b"Unauthorized")
        mock_service.users().messages().list().execute.side_effect = http_err

        db = MagicMock()
        integration = self._make_integration()

        result = await fetch_child_emails(db, integration)
        assert result == []
        assert integration.is_active is False
        db.commit.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service._parse_gmail_message")
    @patch("app.services.parent_gmail_service.get_gmail_service")
    @patch("app.services.parent_gmail_service.decrypt_token")
    async def test_fetch_child_emails_success(self, mock_decrypt, mock_get_gmail, mock_parse):
        """Gmail API returning 2 messages parses correctly."""
        from app.services.parent_gmail_service import fetch_child_emails

        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "decrypted_token"
        mock_get_gmail.return_value = (mock_service, mock_creds)

        # messages().list() returns 2 message stubs
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        # messages().get().execute() returns full message
        mock_service.users().messages().get().execute.return_value = {"id": "msg1", "payload": {}}

        mock_parse.side_effect = [
            {"source_id": "msg1", "subject": "Test 1"},
            {"source_id": "msg2", "subject": "Test 2"},
        ]

        db = MagicMock()
        integration = self._make_integration()

        result = await fetch_child_emails(db, integration)
        assert len(result) == 2
        assert mock_parse.call_count == 2
        db.commit.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service._parse_gmail_message")
    @patch("app.services.parent_gmail_service.get_gmail_service")
    @patch("app.services.parent_gmail_service.decrypt_token")
    async def test_fetch_child_emails_from_name_filter(self, mock_decrypt, mock_get_gmail, mock_parse):
        """Gmail query mixes email_address and sender_name entries (#3652)."""
        from app.services.parent_gmail_service import fetch_child_emails

        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "decrypted_token"
        mock_get_gmail.return_value = (mock_service, mock_creds)
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        # Build integration with mixed monitored_emails entries
        db = MagicMock()
        integration = self._make_integration(child_school_email=None)

        entry_email_only = MagicMock()
        entry_email_only.email_address = "office@school.ca"
        entry_email_only.sender_name = None

        entry_name_only = MagicMock()
        entry_name_only.email_address = None
        entry_name_only.sender_name = "Mrs. Smith"

        entry_both = MagicMock()
        entry_both.email_address = "principal@school.ca"
        entry_both.sender_name = "Principal Jones"

        integration.monitored_emails = [entry_email_only, entry_name_only, entry_both]

        await fetch_child_emails(db, integration)

        # Inspect the q= kwarg passed to messages().list()
        call_args = mock_service.users().messages().list.call_args_list[-1]
        q = call_args.kwargs.get("q") or call_args.args
        q_str = q if isinstance(q, str) else str(q)
        # Should include ALL four from:"..." parts joined by OR
        assert 'from:"office@school.ca"' in q_str
        assert 'from:"Mrs. Smith"' in q_str
        assert 'from:"principal@school.ca"' in q_str
        assert 'from:"Principal Jones"' in q_str
        assert " OR " in q_str

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service._parse_gmail_message")
    @patch("app.services.parent_gmail_service.get_gmail_service")
    @patch("app.services.parent_gmail_service.decrypt_token")
    async def test_fetch_child_emails_deduplication(self, mock_decrypt, mock_get_gmail, mock_parse):
        """Duplicate message IDs are deduplicated."""
        from app.services.parent_gmail_service import fetch_child_emails

        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "decrypted_token"
        mock_get_gmail.return_value = (mock_service, mock_creds)

        # Return duplicate IDs
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg1"}, {"id": "msg2"}]
        }
        mock_service.users().messages().get().execute.return_value = {"id": "msg1", "payload": {}}

        mock_parse.return_value = {"source_id": "msg1", "subject": "Test"}

        db = MagicMock()
        integration = self._make_integration()

        result = await fetch_child_emails(db, integration)
        # Only 2 unique IDs should be fetched
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_verify_forwarding_no_school_email(self):
        """Returns verified: False when no school email configured."""
        from app.services.parent_gmail_service import verify_forwarding

        db = MagicMock()
        integration = self._make_integration(child_school_email=None)

        result = await verify_forwarding(db, integration)
        assert result["verified"] is False

    @pytest.mark.asyncio
    async def test_verify_forwarding_no_access_token(self):
        """Returns verified: False when no access token."""
        from app.services.parent_gmail_service import verify_forwarding

        db = MagicMock()
        integration = self._make_integration(access_token=None)

        with patch("app.services.parent_gmail_service.decrypt_token", return_value=None):
            result = await verify_forwarding(db, integration)
        assert result["verified"] is False

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service.get_gmail_service")
    @patch("app.services.parent_gmail_service.decrypt_token")
    async def test_verify_forwarding_found_emails(self, mock_decrypt, mock_get_gmail):
        """Returns verified: True when Gmail returns messages."""
        from app.services.parent_gmail_service import verify_forwarding

        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "decrypted_token"
        mock_get_gmail.return_value = (mock_service, mock_creds)

        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}]
        }
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg1",
            "payload": {"headers": [{"name": "Date", "value": "2026-04-01"}]},
        }

        db = MagicMock()
        integration = self._make_integration()

        result = await verify_forwarding(db, integration)
        assert result["verified"] is True
        assert result["email_count"] == 1

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service.get_gmail_service")
    @patch("app.services.parent_gmail_service.decrypt_token")
    async def test_verify_forwarding_no_emails(self, mock_decrypt, mock_get_gmail):
        """Returns verified: False when Gmail returns no messages."""
        from app.services.parent_gmail_service import verify_forwarding

        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "decrypted_token"
        mock_get_gmail.return_value = (mock_service, mock_creds)

        mock_service.users().messages().list().execute.return_value = {"messages": []}

        db = MagicMock()
        integration = self._make_integration()

        result = await verify_forwarding(db, integration)
        assert result["verified"] is False
        assert result["email_count"] == 0


# ---------------------------------------------------------------------------
# TestParentDigestAIService
# ---------------------------------------------------------------------------


class TestParentDigestAIService:
    """Tests for app.services.parent_digest_ai_service."""

    @pytest.mark.asyncio
    async def test_generate_digest_empty_emails(self):
        """Empty email list returns friendly 'no new emails' message."""
        from app.services.parent_digest_ai_service import generate_parent_digest

        result = await generate_parent_digest([], "Alex", "Sarah")
        assert "no new school emails" in result.lower() or "no new" in result.lower()
        assert "Sarah" in result
        assert "Alex" in result

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_generate_digest_full_format(self, mock_get_client):
        """Full format digest includes 'FULL digest' in prompt."""
        from app.services.parent_digest_ai_service import generate_parent_digest

        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="<h3>Digest</h3>")]
        mock_message.usage.input_tokens = 100
        mock_message.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_message
        mock_get_client.return_value = mock_client

        emails = [{
            "sender_name": "Ms. Johnson",
            "sender_email": "teacher@school.ca",
            "subject": "Homework",
            "body": "Due Friday",
        }]
        result = await generate_parent_digest(emails, "Alex", "Sarah", "full")

        assert result == "<h3>Digest</h3>"
        # Verify prompt contains FULL digest instruction
        call_kwargs = mock_client.messages.create.call_args
        user_msg = call_kwargs[1]["messages"][0]["content"] if call_kwargs[1] else call_kwargs.kwargs["messages"][0]["content"]
        assert "FULL digest" in user_msg
        # Sender name should appear in the prompt so the AI can attribute emails
        assert "Ms. Johnson" in user_msg
        assert call_kwargs[1].get("max_tokens", call_kwargs.kwargs.get("max_tokens")) == 1200

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_generate_digest_brief_format(self, mock_get_client):
        """Brief format uses max_tokens=400."""
        from app.services.parent_digest_ai_service import generate_parent_digest

        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Brief digest")]
        mock_message.usage.input_tokens = 80
        mock_message.usage.output_tokens = 30
        mock_client.messages.create.return_value = mock_message
        mock_get_client.return_value = mock_client

        emails = [{
            "sender_name": "Ms. Johnson",
            "sender_email": "teacher@school.ca",
            "subject": "Test",
            "snippet": "Snippet",
        }]
        result = await generate_parent_digest(emails, "Alex", "Sarah", "brief")

        assert result == "Brief digest"
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs[1].get("max_tokens", call_kwargs.kwargs.get("max_tokens")) == 400

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_generate_digest_actions_only(self, mock_get_client):
        """Actions_only format uses max_tokens=300."""
        from app.services.parent_digest_ai_service import generate_parent_digest

        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Action items")]
        mock_message.usage.input_tokens = 60
        mock_message.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_message
        mock_get_client.return_value = mock_client

        emails = [{
            "sender_name": "School Admin",
            "sender_email": "admin@school.ca",
            "subject": "Forms due",
            "body": "Sign by Friday",
        }]
        result = await generate_parent_digest(emails, "Alex", "Sarah", "actions_only")

        assert result == "Action items"
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs[1].get("max_tokens", call_kwargs.kwargs.get("max_tokens")) == 300

    def test_resolve_sender_display_uses_name_when_present(self):
        """When sender_name is set, it is returned verbatim."""
        from app.services.parent_digest_ai_service import _resolve_sender_display

        assert _resolve_sender_display("Ms. Johnson", "teacher@school.ca") == "Ms. Johnson"

    def test_resolve_sender_display_falls_back_to_local_part(self):
        """Empty sender_name falls back to the email local-part."""
        from app.services.parent_digest_ai_service import _resolve_sender_display

        assert _resolve_sender_display("", "grade3.teacher@school.ca") == "grade3.teacher"

    def test_resolve_sender_display_unknown_when_no_data(self):
        """Empty name AND no valid email returns 'Unknown sender'."""
        from app.services.parent_digest_ai_service import _resolve_sender_display

        assert _resolve_sender_display("", "") == "Unknown sender"
        assert _resolve_sender_display("", "no-at-sign") == "Unknown sender"

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_generate_digest_uses_sender_local_part_when_name_empty(self, mock_get_client):
        """Digest prompt uses email local-part when sender_name is empty."""
        from app.services.parent_digest_ai_service import generate_parent_digest

        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Digest")]
        mock_message.usage.input_tokens = 50
        mock_message.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_message
        mock_get_client.return_value = mock_client

        emails = [{
            "sender_name": "",
            "sender_email": "grade3.teacher@school.ca",
            "subject": "Field trip",
            "body": "Permission slip due Friday",
        }]
        await generate_parent_digest(emails, "Alex", "Sarah", "full")

        call_kwargs = mock_client.messages.create.call_args
        user_msg = call_kwargs[1]["messages"][0]["content"] if call_kwargs[1] else call_kwargs.kwargs["messages"][0]["content"]
        # Local-part of email should be used as sender display
        assert "grade3.teacher" in user_msg

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_generate_digest_ai_failure(self, mock_get_client):
        """AI exception propagates."""
        from app.services.parent_digest_ai_service import generate_parent_digest

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API down")
        mock_get_client.return_value = mock_client

        emails = [{
            "sender_name": "",
            "sender_email": "t@school.ca",
            "subject": "X",
            "body": "Y",
        }]
        with pytest.raises(RuntimeError, match="API down"):
            await generate_parent_digest(emails, "Alex", "Sarah")


# ---------------------------------------------------------------------------
# TestWhatsAppService
# ---------------------------------------------------------------------------


class TestWhatsAppService:
    """Tests for app.services.whatsapp_service."""

    @patch("app.services.whatsapp_service.TWILIO_AVAILABLE", True)
    @patch("app.services.whatsapp_service.settings")
    def test_is_whatsapp_enabled_true(self, mock_settings):
        """Enabled when all 3 Twilio values present."""
        from app.services.whatsapp_service import is_whatsapp_enabled

        mock_settings.twilio_account_sid = "AC123"
        mock_settings.twilio_auth_token = "token123"
        mock_settings.twilio_whatsapp_from = "+14155238886"

        assert is_whatsapp_enabled() is True

    @patch("app.services.whatsapp_service.TWILIO_AVAILABLE", True)
    @patch("app.services.whatsapp_service.settings")
    def test_is_whatsapp_enabled_false(self, mock_settings):
        """Disabled when Twilio values missing."""
        from app.services.whatsapp_service import is_whatsapp_enabled

        mock_settings.twilio_account_sid = "AC123"
        mock_settings.twilio_auth_token = None
        mock_settings.twilio_whatsapp_from = "+14155238886"

        assert is_whatsapp_enabled() is False

    def test_generate_otp_format(self):
        """OTP is 6 digits."""
        from app.services.whatsapp_service import generate_otp

        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_generate_otp_uniqueness(self):
        """100 OTPs are not all the same."""
        from app.services.whatsapp_service import generate_otp

        otps = {generate_otp() for _ in range(100)}
        assert len(otps) > 1

    @patch("app.services.whatsapp_service.settings")
    def test_send_whatsapp_success(self, mock_settings):
        """Successful send returns True."""
        import app.services.whatsapp_service as ws

        mock_settings.twilio_account_sid = "AC123"
        mock_settings.twilio_auth_token = "token"
        mock_settings.twilio_whatsapp_from = "+14155238886"

        mock_twilio_cls = MagicMock()
        mock_client = MagicMock()
        mock_twilio_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(sid="SM123")

        # Inject TwilioClient into module and mark as available
        orig_available = ws.TWILIO_AVAILABLE
        orig_client = getattr(ws, "TwilioClient", None)
        ws.TWILIO_AVAILABLE = True
        ws.TwilioClient = mock_twilio_cls
        try:
            result = ws.send_whatsapp_message("+14165551234", "Hello parent!")
            assert result is True
            mock_client.messages.create.assert_called_once()
        finally:
            ws.TWILIO_AVAILABLE = orig_available
            if orig_client is None:
                delattr(ws, "TwilioClient")
            else:
                ws.TwilioClient = orig_client

    @patch("app.services.whatsapp_service.settings")
    def test_send_whatsapp_truncation(self, mock_settings):
        """Message > 1600 chars is truncated."""
        import app.services.whatsapp_service as ws

        mock_settings.twilio_account_sid = "AC123"
        mock_settings.twilio_auth_token = "token"
        mock_settings.twilio_whatsapp_from = "+14155238886"

        mock_twilio_cls = MagicMock()
        mock_client = MagicMock()
        mock_twilio_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(sid="SM123")

        orig_available = ws.TWILIO_AVAILABLE
        orig_client = getattr(ws, "TwilioClient", None)
        ws.TWILIO_AVAILABLE = True
        ws.TwilioClient = mock_twilio_cls
        try:
            long_message = "A" * 2000
            ws.send_whatsapp_message("+14165551234", long_message)

            call_kwargs = mock_client.messages.create.call_args
            body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
            assert len(body) == 1600
            assert body.endswith("...")
        finally:
            ws.TWILIO_AVAILABLE = orig_available
            if orig_client is None:
                delattr(ws, "TwilioClient")
            else:
                ws.TwilioClient = orig_client

    @patch("app.services.whatsapp_service.settings")
    def test_send_whatsapp_failure(self, mock_settings):
        """Twilio exception returns False."""
        import app.services.whatsapp_service as ws

        mock_settings.twilio_account_sid = "AC123"
        mock_settings.twilio_auth_token = "token"
        mock_settings.twilio_whatsapp_from = "+14155238886"

        mock_twilio_cls = MagicMock()
        mock_client = MagicMock()
        mock_twilio_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Twilio error")

        orig_available = ws.TWILIO_AVAILABLE
        orig_client = getattr(ws, "TwilioClient", None)
        ws.TWILIO_AVAILABLE = True
        ws.TwilioClient = mock_twilio_cls
        try:
            result = ws.send_whatsapp_message("+14165551234", "Hello")
            assert result is False
        finally:
            ws.TWILIO_AVAILABLE = orig_available
            if orig_client is None:
                delattr(ws, "TwilioClient")
            else:
                ws.TwilioClient = orig_client


# ---------------------------------------------------------------------------
# TestDigestJob
# ---------------------------------------------------------------------------


class TestDigestJob:
    """Tests for app.jobs.parent_email_digest_job."""

    def _make_integration(self, **overrides):
        integration = MagicMock()
        integration.id = overrides.get("id", 1)
        integration.parent_id = overrides.get("parent_id", 10)
        integration.is_active = overrides.get("is_active", True)
        integration.child_school_email = overrides.get("child_school_email", "child@school.ca")
        integration.child_first_name = overrides.get("child_first_name", "Alex")
        integration.paused_until = None
        integration.whatsapp_verified = overrides.get("whatsapp_verified", False)
        integration.whatsapp_phone = overrides.get("whatsapp_phone", None)
        integration.last_synced_at = None

        settings = MagicMock()
        settings.digest_enabled = True
        settings.delivery_channels = overrides.get("delivery_channels", "in_app,email")
        settings.digest_format = overrides.get("digest_format", "full")
        settings.notify_on_empty = overrides.get("notify_on_empty", False)
        integration.digest_settings = settings
        integration.parent = overrides.get("parent", None)

        return integration

    def _make_parent(self):
        parent = MagicMock()
        parent.id = 10
        parent.first_name = "Sarah"
        return parent

    @pytest.mark.asyncio
    @patch("app.jobs.parent_email_digest_job.SessionLocal")
    async def test_process_skips_already_delivered(self, mock_session_cls):
        """Skip integration with today's delivery log."""
        from app.jobs.parent_email_digest_job import process_parent_email_digests

        integration = self._make_integration()
        existing_log = MagicMock()
        db = self._setup_db_mock([integration], existing_log=existing_log)
        mock_session_cls.return_value = db

        await process_parent_email_digests()
        # No digest_content should be created — we just skip
        db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service.fetch_child_emails", return_value=[])
    @patch("app.jobs.parent_email_digest_job.SessionLocal")
    async def test_process_skips_no_emails_when_notify_off(self, mock_session_cls, mock_fetch):
        """Skip when no emails fetched and notify_on_empty=False."""
        from app.jobs.parent_email_digest_job import process_parent_email_digests

        integration = self._make_integration(notify_on_empty=False)
        db = self._setup_db_mock([integration], existing_log=None)
        mock_session_cls.return_value = db

        await process_parent_email_digests()

        db.close.assert_called_once()

    def _setup_db_mock(self, integrations, existing_log=None, parent=None):
        """Set up db mock with model-aware query routing."""
        from app.models.parent_gmail_integration import (
            ParentGmailIntegration,
            DigestDeliveryLog,
        )
        from app.models.user import User

        db = MagicMock()

        def query_side_effect(model):
            mock_query = MagicMock()
            if model is ParentGmailIntegration:
                # Chain: .join().options().options().filter().filter().all()
                mock_query.join.return_value.options.return_value.options.return_value.filter.return_value.filter.return_value.all.return_value = integrations
            elif model is DigestDeliveryLog:
                # Job uses single .filter() with 3 args then .first()
                mock_query.filter.return_value.first.return_value = existing_log
            elif model is User:
                mock_query.filter.return_value.first.return_value = parent
            return mock_query

        db.query.side_effect = query_side_effect
        return db

    @pytest.mark.asyncio
    @patch("app.services.notification_service.send_multi_channel_notification")
    @patch("app.services.parent_digest_ai_service.generate_parent_digest")
    @patch("app.services.parent_gmail_service.fetch_child_emails")
    @patch("app.jobs.parent_email_digest_job.SessionLocal")
    async def test_process_sends_digest(self, mock_session_cls, mock_fetch, mock_gen, mock_notify):
        """Successful flow: fetch emails, generate digest, send notification, create log."""
        from app.jobs.parent_email_digest_job import process_parent_email_digests

        parent = self._make_parent()
        integration = self._make_integration(parent=parent)
        db = self._setup_db_mock([integration], existing_log=None, parent=parent)
        mock_session_cls.return_value = db

        mock_fetch.return_value = [{"from": "teacher@school.ca", "subject": "Homework", "body": "Due Friday"}]
        mock_gen.return_value = "<h3>Your digest</h3>"

        await process_parent_email_digests()

        db.add.assert_called()
        db.commit.assert_called()
        db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.generate_parent_digest", side_effect=RuntimeError("AI down"))
    @patch("app.services.parent_gmail_service.fetch_child_emails")
    @patch("app.jobs.parent_email_digest_job.SessionLocal")
    async def test_process_handles_ai_failure(self, mock_session_cls, mock_fetch, mock_gen):
        """AI failure creates log with status='failed'."""
        from app.jobs.parent_email_digest_job import process_parent_email_digests

        parent = self._make_parent()
        integration = self._make_integration(parent=parent)
        db = self._setup_db_mock([integration], existing_log=None, parent=parent)
        mock_session_cls.return_value = db

        mock_fetch.return_value = [{"from": "t@school.ca", "subject": "X", "body": "Y"}]

        await process_parent_email_digests()

        # A log entry should be added with status="failed"
        db.add.assert_called()
        db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.parent_gmail_service.fetch_child_emails", side_effect=Exception("Token refresh failed"))
    @patch("app.jobs.parent_email_digest_job.SessionLocal")
    async def test_process_deactivates_on_token_failure(self, mock_session_cls, mock_fetch):
        """Token refresh failure deactivates integration."""
        from app.jobs.parent_email_digest_job import process_parent_email_digests

        integration = self._make_integration()
        db = self._setup_db_mock([integration], existing_log=None)
        mock_session_cls.return_value = db

        await process_parent_email_digests()

        db.close.assert_called_once()
