"""Regression test for #3839 — parent email digest job crashed on parent.first_name.

The User model has full_name, not first_name. Using a real User object (not a
MagicMock) ensures the AttributeError that broke both the manual Send Digest
Now endpoint and the 4-hour scheduled job does not regress.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_send_digest_for_integration_uses_full_name_not_first_name(db_session):
    from app.core.security import get_password_hash
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="digest_job_parent@test.com",
        full_name="Rohini Sundaram",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="digest_job_parent@gmail.com",
        google_id="google_digest_job_test",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
    )
    db_session.add(integration)
    db_session.flush()

    settings = ParentDigestSettings(integration_id=integration.id)
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)

    fetched_emails = [
        {
            "source_id": "x",
            "sender_name": "School",
            "sender_email": "s@s.ca",
            "subject": "Hi",
            "body": "B",
            "snippet": "B",
            "received_at": received_at,
        }
    ]

    mock_generate = AsyncMock(return_value="digest body")
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=fetched_emails),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=mock_generate,
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ) as mock_notify:
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=since,
        )

    assert result["status"] == "delivered"
    assert mock_notify.called
    # Verify personalization: parsed first name passed to digest generator.
    # generate_parent_digest(emails, child_name, parent_name, digest_format)
    gen_args = mock_generate.call_args.args
    assert gen_args[2] == "Rohini", gen_args


@pytest.mark.asyncio
async def test_send_digest_for_integration_whitespace_only_full_name(db_session):
    """#3845 — whitespace-only full_name must not IndexError; falls back to 'Parent'."""
    from app.core.security import get_password_hash
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="ws_parent@test.com",
        full_name="   ",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="ws_parent@gmail.com",
        google_id="google_ws_test",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
    )
    db_session.add(integration)
    db_session.flush()

    settings = ParentDigestSettings(integration_id=integration.id)
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)

    fetched_emails = [
        {
            "source_id": "x",
            "sender_name": "School",
            "sender_email": "s@s.ca",
            "subject": "Hi",
            "body": "B",
            "snippet": "B",
            "received_at": received_at,
        }
    ]

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=fetched_emails),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=since,
        )

    assert result["status"] == "delivered"



@pytest.mark.asyncio
async def test_whatsapp_template_variables_sanitised(db_session):
    """#3879 — Twilio Content Variables reject newlines / >1024 char values.

    The WhatsApp template path must:
    - strip control chars (\\n, \\r, \\t, ASCII < 32) from the plain_text variable
    - collapse runs of whitespace
    - cap variable "2" at 1024 chars (Twilio per-variable limit)
    - strip newlines from parent_name (variable "1")
    """
    from app.core.security import get_password_hash
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="wa_sanitise_parent@test.com",
        full_name="Rohini Sundaram",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="wa_sanitise_parent@gmail.com",
        google_id="google_wa_sanitise_test",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
        whatsapp_phone="+14155551234",
        whatsapp_verified=True,
    )
    db_session.add(integration)
    db_session.flush()

    settings = ParentDigestSettings(
        integration_id=integration.id,
        delivery_channels="in_app,whatsapp",
        digest_format="brief",
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)

    fetched_emails = [
        {
            "source_id": "x",
            "sender_name": "School",
            "sender_email": "s@s.ca",
            "subject": "Hi",
            "body": "B",
            "snippet": "B",
            "received_at": received_at,
        }
    ]

    # AI digest with multiple newlines between per-email summaries + long content
    ai_digest = (
        "Email 1: Field trip next week.\n\n"
        "Email 2: Report card released.\r\n"
        "Email 3: Lunch menu changes.\t\tExtra details follow.\n"
        + ("x" * 2000)
    )

    captured = {}

    def fake_send_whatsapp_template(to, content_sid, content_variables):
        captured["to"] = to
        captured["content_sid"] = content_sid
        captured["content_variables"] = content_variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=fetched_emails),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value=ai_digest),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_whatsapp_template,
    ) as mock_template, patch(
        "app.core.config.settings.twilio_whatsapp_digest_content_sid",
        "HX_TEST_SID",
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=since,
        )

    assert result["status"] == "delivered"
    assert mock_template.called, "send_whatsapp_template should be invoked when content_sid is configured"

    content_variables = captured["content_variables"]
    var1 = content_variables["1"]
    var2 = content_variables["2"]

    # Variable "2" — plain_text: no control characters, and ≤ 1024 chars
    assert "\n" not in var2, "variable '2' must not contain newlines"
    assert "\r" not in var2, "variable '2' must not contain carriage returns"
    assert "\t" not in var2, "variable '2' must not contain tabs"
    # No other ASCII control chars (0x00-0x1f)
    for ch in var2:
        assert ord(ch) >= 32, f"variable '2' contains control char {ord(ch)!r}"
    assert len(var2) <= 1024, f"variable '2' must be ≤ 1024 chars (got {len(var2)})"

    # Variable "1" — parent_name: no newlines
    assert "\n" not in var1
    assert "\r" not in var1


# ---------------------------------------------------------------------------
# Per-channel delivery status (#3880)
# ---------------------------------------------------------------------------

def _seed_integration(db_session, email_suffix: str, delivery_channels: str = "in_app,email"):
    """Create a parent + integration + digest settings fixture for #3880 tests."""
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email=f"digest_3880_{email_suffix}@test.com",
        full_name="Priya Ramanathan",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address=f"p_{email_suffix}@gmail.com",
        google_id=f"g_3880_{email_suffix}",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
    )
    db_session.add(integration)
    db_session.flush()

    settings = ParentDigestSettings(
        integration_id=integration.id,
        delivery_channels=delivery_channels,
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)
    return parent, integration


def _fetched_emails():
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)
    return [
        {
            "source_id": "x",
            "sender_name": "School",
            "sender_email": "s@s.ca",
            "subject": "Hi",
            "body": "Body",
            "snippet": "Body",
            "received_at": received_at,
        }
    ]


@pytest.mark.asyncio
async def test_digest_delivered_when_email_succeeds_no_whatsapp(db_session):
    """#3880 — email succeeds, WhatsApp not selected → status=delivered."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "delivered", "in_app,email")

    # Return per-channel dict indicating both channels succeeded.
    notify_success = MagicMock(
        return_value={"notification": MagicMock(), "in_app": True, "email": True, "classbridge_message": None}
    )

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=notify_success,
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    assert result["channel_status"]["in_app"] is True
    assert result["channel_status"]["email"] is True
    assert result["channel_status"]["whatsapp"] is None
    assert "Digest delivered" in result["message"]


@pytest.mark.asyncio
async def test_digest_partial_when_whatsapp_fails_but_email_succeeds(db_session):
    """#3880 — email succeeds, WhatsApp fails → status=partial."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "partial", "in_app,email,whatsapp")
    integration.whatsapp_verified = True
    integration.whatsapp_phone = "+14165551234"
    db_session.commit()

    notify_success = MagicMock(
        return_value={"notification": MagicMock(), "in_app": True, "email": True, "classbridge_message": None}
    )

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=notify_success,
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message",
        return_value=False,
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        return_value=False,
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "partial"
    assert result["channel_status"]["in_app"] is True
    assert result["channel_status"]["email"] is True
    assert result["channel_status"]["whatsapp"] is False
    assert "partially delivered" in result["message"]
    assert "WhatsApp" in result["message"]


@pytest.mark.asyncio
async def test_digest_failed_when_email_returns_false_and_whatsapp_fails(db_session):
    """#3880 — every selected channel fails → status=failed."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "failed", "email,whatsapp")
    integration.whatsapp_verified = True
    integration.whatsapp_phone = "+14165551234"
    db_session.commit()

    # Notification service reports email=False (send_email_sync returned False).
    notify_failure = MagicMock(
        return_value={"notification": None, "in_app": None, "email": False, "classbridge_message": None}
    )

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=notify_failure,
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message",
        return_value=False,
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        return_value=False,
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "failed"
    assert result["channel_status"]["in_app"] is None
    assert result["channel_status"]["email"] is False
    assert result["channel_status"]["whatsapp"] is False
    assert "failed on all channels" in result["message"]


@pytest.mark.asyncio
async def test_digest_persists_email_delivery_status_in_log(db_session):
    """#3880 — DigestDeliveryLog.email_delivery_status is populated with sent/failed."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import DigestDeliveryLog

    _, integration = _seed_integration(db_session, "emailstatus", "in_app,email")

    notify_failure = MagicMock(
        return_value={"notification": None, "in_app": True, "email": False, "classbridge_message": None}
    )

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=notify_failure,
    ):
        await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    log_entry = (
        db_session.query(DigestDeliveryLog)
        .filter(DigestDeliveryLog.integration_id == integration.id)
        .order_by(DigestDeliveryLog.id.desc())
        .first()
    )
    assert log_entry is not None
    assert log_entry.email_delivery_status == "failed"
    assert log_entry.status == "partial"
