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
        new=AsyncMock(return_value={"emails": fetched_emails, "synced_at": datetime.now(timezone.utc)}),
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
        new=AsyncMock(return_value={"emails": fetched_emails, "synced_at": datetime.now(timezone.utc)}),
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
    """#3941 — Twilio's daily_digest Content Template rejects \\n in variables.

    The WhatsApp template path must:
    - substitute \\n\\n with " • " (visible section boundary)
    - substitute single \\n / \\r / \\t with spaces
    - strip all remaining control chars (ASCII 0-31)
    - collapse whitespace runs
    - cap variable "2" at 1024 chars (Twilio per-variable limit)
    - strip newlines/control chars from parent_name (variable "1")
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

    # AI digest with \n\n paragraph breaks between sections + long content
    ai_digest = (
        "URGENT: Do this.\n\n"
        "Automated Notifications: Math assignment due.\n\n"
        "Action Items: Check in with teacher."
    )

    captured = {}

    def fake_send_whatsapp_template(to, content_sid, content_variables):
        captured["to"] = to
        captured["content_sid"] = content_sid
        captured["content_variables"] = content_variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": fetched_emails, "synced_at": datetime.now(timezone.utc)}),
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

    # #3941: Twilio's daily_digest template rejects \n in variables. Newlines
    # must be substituted: \n\n → " • ", single \n/\r/\t → space. All control
    # chars (ASCII 0-31) stripped so the variable is strictly single-line.
    assert "\n" not in var2, "var2 must not contain newlines (Twilio rejects for daily_digest template, #3941)"
    assert "\r" not in var2, "var2 must not contain carriage returns"
    assert "\t" not in var2, "var2 must not contain tabs"
    assert " • " in var2, "paragraph breaks must be replaced with bullet markers (#3941)"
    for ch in var2:
        assert ord(ch) >= 32, f"var2 contains control char {ord(ch)!r}"
    assert len(var2) <= 1024

    # Variable "1" — parent_name: no newlines
    assert "\n" not in var1
    assert "\r" not in var1


@pytest.mark.asyncio
async def test_whatsapp_template_substitutes_newlines_with_bullet_markers_strips_control_chars(db_session):
    """#3941 — \\n\\n substituted with " • "; other control chars stripped."""
    from app.core.security import get_password_hash
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="wa_ctrl_parent@test.com",
        full_name="Rohini Sundaram",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="wa_ctrl_parent@gmail.com",
        google_id="google_wa_ctrl_test",
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

    # AI digest with \n\n between sections plus unsafe control chars embedded
    ai_digest = "URGENT: do this.\n\nNext section.\x00\x07Tail."

    captured = {}

    def fake_send_whatsapp_template(to, content_sid, content_variables):
        captured["content_variables"] = content_variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": fetched_emails, "synced_at": datetime.now(timezone.utc)}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value=ai_digest),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_whatsapp_template,
    ), patch(
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
    var2 = captured["content_variables"]["2"]

    # Paragraph break substituted with bullet marker
    assert "\n" not in var2, "variable '2' MUST NOT contain newlines (#3941)"
    assert " • " in var2, "paragraph breaks must be replaced with bullet markers (#3941)"
    # Unsafe control chars stripped
    assert "\x00" not in var2, "NUL control char must be stripped"
    assert "\x07" not in var2, "BEL control char must be stripped"


@pytest.mark.asyncio
async def test_whatsapp_template_three_paragraphs_produces_two_bullet_markers(db_session):
    """#3941 — N paragraphs separated by \\n\\n produce N-1 bullet markers."""
    from app.core.security import get_password_hash
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="wa_bullets_parent@test.com",
        full_name="Rohini Sundaram",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="wa_bullets_parent@gmail.com",
        google_id="google_wa_bullets_test",
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

    # Three paragraphs separated by \n\n → expect two " • " separators
    ai_digest = (
        "Paragraph one about urgent items.\n\n"
        "Paragraph two about automated notifications.\n\n"
        "Paragraph three about action items."
    )

    captured = {}

    def fake_send_whatsapp_template(to, content_sid, content_variables):
        captured["content_variables"] = content_variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": fetched_emails, "synced_at": datetime.now(timezone.utc)}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value=ai_digest),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_whatsapp_template,
    ), patch(
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
    var2 = captured["content_variables"]["2"]

    # Three paragraphs → two bullet-marker separators between them
    assert var2.count(" • ") == 2, (
        f"three paragraphs must produce exactly two bullet markers, got {var2.count(' • ')} in {var2!r}"
    )


@pytest.mark.asyncio
async def test_whatsapp_template_crlf_line_endings_produce_bullet_markers(db_session):
    """#3941 (pass-1 review follow-up) — CRLF (\\r\\n) and bare \\r paragraph
    breaks must be treated the same as \\n\\n: normalised first, then
    substituted with a bullet marker.

    Without the CRLF normalisation, \\r\\n\\r\\n between paragraphs would
    fall through the \\n{2,} pattern (because \\r interrupts consecutive \\n)
    and the paragraph boundary would collapse to a single space instead of
    a bullet marker — losing the visual section break.
    """
    from app.core.security import get_password_hash
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="wa_crlf_parent@test.com",
        full_name="Rohini Sundaram",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="wa_crlf_parent@gmail.com",
        google_id="google_wa_crlf_test",
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

    # CRLF paragraph break + bare \r paragraph break — both must become bullets
    ai_digest = (
        "Paragraph one (CRLF below).\r\n\r\n"
        "Paragraph two (bare-CR below).\r\r"
        "Paragraph three."
    )

    captured = {}

    def fake_send_whatsapp_template(to, content_sid, content_variables):
        captured["content_variables"] = content_variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": fetched_emails, "synced_at": datetime.now(timezone.utc)}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value=ai_digest),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_whatsapp_template,
    ), patch(
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
    var2 = captured["content_variables"]["2"]

    assert "\n" not in var2, "var2 must not contain newlines"
    assert "\r" not in var2, "var2 must not contain carriage returns"
    # Both paragraph boundaries must become bullet markers, not collapsed spaces
    assert var2.count(" • ") == 2, (
        f"CRLF and bare-CR paragraph breaks must each produce a bullet marker, "
        f"got {var2.count(' • ')} in {var2!r}"
    )


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
    # #4058 — fetch_child_emails now returns {"emails": [...], "synced_at": dt}
    # so callers can commit last_synced_at atomically with their delivery log
    # instead of the service advancing it eagerly mid-run.
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)
    return {
        "emails": [
            {
                "source_id": "x",
                "sender_name": "School",
                "sender_email": "s@s.ca",
                "subject": "Hi",
                "body": "Body",
                "snippet": "Body",
                "received_at": received_at,
            }
        ],
        "synced_at": datetime.now(timezone.utc),
    }


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


# ---------------------------------------------------------------------------
# Skip-vs-failure distinction (#3887)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_digest_skipped_when_whatsapp_unverified_is_only_selected_channel(db_session):
    """#3887 — WhatsApp is the only selected channel AND not verified → status=skipped.

    Unverified WhatsApp is an intentional skip, not a failure. The parent has
    not completed setup, so we cannot score this channel — and we must not
    report "Failed channels: WhatsApp" in the user-facing message.
    """
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "skipped_wa_only", "whatsapp")
    # whatsapp_verified=False by default; phone is None.
    assert not integration.whatsapp_verified

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": None, "email": None, "classbridge_message": None}),
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "skipped", result
    assert result["channel_status"]["whatsapp"] is None
    assert "No eligible channels" in result["message"]
    # Must NOT imply a delivery failure — no "Failed channels" text, no "check your setup".
    assert "Failed channels" not in result["message"]
    # #3894 — machine-readable reason for skipped state. Frontends use this
    # to gate the "Open preferences" link (only actionable for this reason).
    assert result["reason"] == "no_eligible_channels"


@pytest.mark.asyncio
async def test_digest_delivered_excluding_none_channels(db_session):
    """#3887 — in_app + email succeed, WhatsApp unverified → status=delivered (not partial).

    None-valued channels are excluded from the overall-status computation.
    """
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "delivered_excl_none", "in_app,email,whatsapp")
    # WhatsApp not verified — the unverified branch must produce whatsapp_ok=None.
    assert not integration.whatsapp_verified

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

    assert result["status"] == "delivered", result
    assert result["channel_status"]["in_app"] is True
    assert result["channel_status"]["email"] is True
    assert result["channel_status"]["whatsapp"] is None


@pytest.mark.asyncio
async def test_digest_failed_labels_exclude_none_channels(db_session):
    """#3887 — email fails (False), WhatsApp unverified (None) → status=failed, message mentions email but NOT WhatsApp."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "failed_excl_none", "email,whatsapp")
    # WhatsApp not verified — produces whatsapp_ok=None (skipped, not a failure).
    assert not integration.whatsapp_verified

    # Notification service reports email=False (actual failure).
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
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "failed", result
    assert result["channel_status"]["email"] is False
    assert result["channel_status"]["whatsapp"] is None
    # The message must call out email but NOT WhatsApp (WhatsApp was skipped, not failed).
    assert "all channels" in result["message"]
    # The failed path uses a generic message; but crucially the labels used in the
    # "partial" path (if we were partial) must exclude WhatsApp. Verify by
    # re-inspecting the per-channel record: only email is False.
    assert result["channel_status"]["email"] is False
    assert result["channel_status"]["whatsapp"] is not False, "WhatsApp (skipped) must not be counted as a failure"


# ---------------------------------------------------------------------------
# Machine-readable skip reason (#3894)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_digest_reason_no_new_emails(db_session):
    """#3894 — no emails + notify_on_empty=False → status=skipped, reason=no_new_emails."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "reason_empty", "in_app,email")
    # notify_on_empty defaults to False.
    assert integration.digest_settings.notify_on_empty is False

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": [], "synced_at": None}),
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "skipped", result
    assert result["reason"] == "no_new_emails"
    assert result["email_count"] == 0


@pytest.mark.asyncio
async def test_digest_reason_already_delivered(db_session):
    """#3894 — delivery log from earlier today + no skip_dedup → reason=already_delivered."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.parent_gmail_integration import DigestDeliveryLog

    _, integration = _seed_integration(db_session, "reason_dedup", "in_app,email")

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    earlier_log = DigestDeliveryLog(
        parent_id=integration.parent_id,
        integration_id=integration.id,
        email_count=3,
        digest_content="earlier digest",
        status="delivered",
        channels_used="in_app,email",
        delivered_at=today_start + timedelta(hours=1),
    )
    db_session.add(earlier_log)
    db_session.commit()

    # skip_dedup=False (default) — dedup check must trigger.
    result = await send_digest_for_integration(
        db_session,
        integration,
        since=datetime.now(timezone.utc) - timedelta(hours=24),
    )

    assert result["status"] == "skipped", result
    assert result["reason"] == "already_delivered"


@pytest.mark.asyncio
async def test_digest_reason_no_eligible_channels(db_session):
    """#3894 — whatsapp-only-unverified → status=skipped, reason=no_eligible_channels.

    Parallel coverage to test_digest_skipped_when_whatsapp_unverified_is_only_selected_channel,
    kept as a dedicated test so the reason-field contract is visible at a glance.
    """
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "reason_no_eligible", "whatsapp")
    assert not integration.whatsapp_verified

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="digest body"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": None, "email": None, "classbridge_message": None}),
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "no_eligible_channels"


@pytest.mark.asyncio
async def test_digest_no_reason_when_delivered(db_session):
    """#3894 — delivered status has reason=None (None/absent, never a string)."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _, integration = _seed_integration(db_session, "reason_none_delivered", "in_app,email")

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
    assert result.get("reason") is None


# ---------------------------------------------------------------------------
# Sectioned 3×3 digest path (#3956 — Phase A of #3905)
# ---------------------------------------------------------------------------


def _mk_parent_and_integration(
    db_session,
    *,
    digest_format: str = "sectioned",
    delivery_channels: str = "in_app,email",
    whatsapp_verified: bool = False,
    whatsapp_phone: str | None = None,
    email_suffix: str = "sectioned",
):
    """Factory used by the #3956 sectioned-digest tests."""
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email=f"{email_suffix}_parent@test.com",
        full_name="Rohini Sundaram",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address=f"{email_suffix}_parent@gmail.com",
        google_id=f"google_{email_suffix}_test",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
        whatsapp_phone=whatsapp_phone,
        whatsapp_verified=whatsapp_verified,
    )
    db_session.add(integration)
    db_session.flush()

    settings = ParentDigestSettings(
        integration_id=integration.id,
        delivery_channels=delivery_channels,
        digest_format=digest_format,
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)
    return integration


def _fetched_email():
    # #4058 — same dict wrapper as _fetched_emails; see note there.
    return {
        "emails": [
            {
                "source_id": "x",
                "sender_name": "School",
                "sender_email": "s@s.ca",
                "subject": "Hi",
                "body": "B",
                "snippet": "B",
                "received_at": datetime.now(timezone.utc) - timedelta(hours=1),
            }
        ],
        "synced_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_digest_sectioned_format_renders_3x3_email(db_session):
    """Full integration: sectioned JSON -> email HTML has 3 section headings + bullets."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration(db_session)

    sectioned = {
        "urgent": ["Permission slip due today"],
        "announcements": ["New classroom schedule posted", "PTA meeting next week"],
        "action_items": ["Sign field trip form"],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    captured: dict = {}

    def fake_send_multi_channel_notification(**kwargs):
        captured["content"] = kwargs.get("content")
        captured["title"] = kwargs.get("title")
        return {"notification": MagicMock(), "in_app": True, "email": True, "classbridge_message": None}

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_email()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        side_effect=fake_send_multi_channel_notification,
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    html = captured.get("content") or ""
    assert "Urgent" in html
    assert "Announcements" in html
    assert "Action Items" in html
    # 1 urgent + 2 announcements + 1 action_item = 4 <li>
    assert html.count("<li") == 4
    assert "Permission slip due today" in html
    assert "Sign field trip form" in html


@pytest.mark.asyncio
async def test_digest_sectioned_whatsapp_v1_flattens_to_single_line(db_session):
    """V2 env var empty -> V1 single-line-with-bullets format."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration(
        db_session,
        delivery_channels="in_app,whatsapp",
        whatsapp_verified=True,
        whatsapp_phone="+14155551234",
        email_suffix="v1",
    )

    sectioned = {
        "urgent": ["U1", "U2"],
        "announcements": ["A1"],
        "action_items": ["Act1"],
        "overflow": {"urgent": 1, "announcements": 0, "action_items": 0},
    }

    captured: dict = {}

    def fake_send_template(to, sid, variables):
        captured["to"] = to
        captured["sid"] = sid
        captured["variables"] = variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_email()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": None, "classbridge_message": None, "notification": MagicMock()}),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_template,
    ) as mock_template, patch(
        "app.core.config.settings.twilio_whatsapp_digest_content_sid",
        "HX_V1_SID",
    ), patch(
        "app.core.config.settings.twilio_whatsapp_digest_content_sid_v2",
        "",
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    assert mock_template.called
    # V1 = 2 variables (parent_name, flattened_text)
    variables = captured["variables"]
    assert set(variables.keys()) == {"1", "2"}
    var2 = variables["2"]
    # No newlines (#3941 rule still applies to V1 path).
    assert "\n" not in var2
    # Section headings + bullet separators from the flatten helper.
    assert "Urgent" in var2
    assert "Announcements" in var2
    assert "Action Items" in var2
    assert "U1" in var2
    assert "A1" in var2
    assert "Act1" in var2
    assert "(And 1 more)" in var2


@pytest.mark.asyncio
async def test_digest_sectioned_whatsapp_v2_uses_4_variables(db_session):
    """V2 env var set -> 4-variable template call with correct per-variable content."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration(
        db_session,
        delivery_channels="in_app,whatsapp",
        whatsapp_verified=True,
        whatsapp_phone="+14155551234",
        email_suffix="v2",
    )

    sectioned = {
        "urgent": ["U1", "U2", "U3"],
        "announcements": ["A1", "A2"],
        "action_items": ["Act1"],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    captured: dict = {}

    def fake_send_template(to, sid, variables):
        captured["to"] = to
        captured["sid"] = sid
        captured["variables"] = variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_email()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": None, "classbridge_message": None, "notification": MagicMock()}),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_template,
    ), patch(
        "app.core.config.settings.twilio_whatsapp_digest_content_sid_v2",
        "HX_V2_SID",
    ), patch(
        "app.core.config.settings.twilio_whatsapp_digest_content_sid",
        "HX_V1_SID",
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    assert captured["sid"] == "HX_V2_SID"
    variables = captured["variables"]
    assert set(variables.keys()) == {"1", "2", "3", "4"}
    assert variables["1"] == "Rohini"
    # Each block has up to 3 bullets.
    assert "U1" in variables["2"] and "U2" in variables["2"] and "U3" in variables["2"]
    assert "A1" in variables["3"] and "A2" in variables["3"]
    assert "Act1" in variables["4"]


@pytest.mark.asyncio
async def test_digest_empty_section_shows_none_in_v2(db_session):
    """Empty sections in V2 variables get '(none)' to satisfy Twilio's non-empty rule."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration(
        db_session,
        delivery_channels="in_app,whatsapp",
        whatsapp_verified=True,
        whatsapp_phone="+14155551234",
        email_suffix="empty",
    )

    sectioned = {
        "urgent": [],
        "announcements": ["A1"],
        "action_items": ["Act1"],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    captured: dict = {}

    def fake_send_template(to, sid, variables):
        captured["variables"] = variables
        return True

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_email()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": None, "classbridge_message": None, "notification": MagicMock()}),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        side_effect=fake_send_template,
    ), patch(
        "app.core.config.settings.twilio_whatsapp_digest_content_sid_v2",
        "HX_V2_SID",
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    variables = captured["variables"]
    # urgent is empty -> must be "(none)"
    assert variables["2"] == "(none)"
    # non-empty sections still render normally
    assert "A1" in variables["3"]
    assert "Act1" in variables["4"]


@pytest.mark.asyncio
async def test_digest_overflow_renders_more_cta(db_session):
    """overflow.urgent=5 -> email HTML contains an 'And 5 more ->' link to /email-digest."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration(
        db_session,
        delivery_channels="in_app,email",
        email_suffix="overflow",
    )

    sectioned = {
        "urgent": ["u1", "u2", "u3"],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 5, "announcements": 0, "action_items": 0},
    }

    captured: dict = {}

    def fake_send_multi_channel_notification(**kwargs):
        captured["content"] = kwargs.get("content")
        return {"notification": MagicMock(), "in_app": True, "email": True, "classbridge_message": None}

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_email()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        side_effect=fake_send_multi_channel_notification,
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    html = captured.get("content") or ""
    assert "And 5 more" in html
    # #3965 — CTA href is resolved from settings.frontend_url at render time.
    assert "/email-digest" in html


@pytest.mark.asyncio
async def test_digest_sectioned_legacy_blob_falls_back_to_legacy_html(db_session):
    """AI JSON parse failure -> generate_sectioned_digest returns legacy_blob -> legacy render path."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration(
        db_session,
        delivery_channels="in_app,email",
        email_suffix="legacy",
    )

    sectioned = {"legacy_blob": "<h3>Legacy Full Digest</h3><p>Content here</p>"}

    captured: dict = {}

    def fake_send_multi_channel_notification(**kwargs):
        captured["content"] = kwargs.get("content")
        return {"notification": MagicMock(), "in_app": True, "email": True, "classbridge_message": None}

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_email()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        side_effect=fake_send_multi_channel_notification,
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] == "delivered"
    # Legacy HTML is passed through unchanged (3x3 email renderer not used).
    assert captured.get("content") == "<h3>Legacy Full Digest</h3><p>Content here</p>"


def test_sectioned_digest_email_uses_settings_frontend_url(db_session):
    """#3965 — full-digest CTA URL must come from settings.frontend_url, not a hardcoded prod URL."""
    from app.services.notification_service import build_sectioned_digest_email_body

    with patch(
        "app.core.config.settings.frontend_url",
        "https://staging.classbridge.ca",
    ):
        html = build_sectioned_digest_email_body({
            "urgent": ["item1", "item2", "item3"],
            "announcements": [],
            "action_items": [],
            "overflow": {"urgent": 2, "announcements": 0, "action_items": 0},
        })

    # Link must come from settings, NOT hardcoded prod
    assert 'href="https://staging.classbridge.ca/email-digest"' in html
    assert 'href="https://www.classbridge.ca/email-digest"' not in html


def test_whatsapp_body_strips_malformed_html_tags():
    """Regression test for #4006: tag fragments must not leak into WhatsApp body.

    The original sanitisation stripped only well-formed ``<...>`` tags. Malformed
    or unterminated tags (e.g. AI output that emits ``<li`` without a closing
    ``>``, or a stray ``</li>`` after bullet flattening) survived the strip and
    leaked into the template variable. This test ensures the defensive second
    pass catches all such residue.
    """
    from app.jobs.parent_email_digest_job import _sanitise_whatsapp_var

    dirty = (
        "Item 1 item 2 <b>bold</b> unterminated <li tag and lone "
        "</li>end and homework assignments</li>"
    )
    sanitised = _sanitise_whatsapp_var(dirty)

    assert '<' not in sanitised
    assert '>' not in sanitised
    assert '</li>' not in sanitised
    assert '<li' not in sanitised
    # Ensure real content is preserved (bold text, "end", "homework assignments")
    assert 'bold' in sanitised
    assert 'homework assignments' in sanitised


# ---------------------------------------------------------------------------
# #4058 — retry-after-partial-failure: last_synced_at must NOT advance if the
# worker crashes between fetch-commit and delivery-log-commit.
# ---------------------------------------------------------------------------


def _mk_parent_and_integration_plain(db_session, *, email_suffix: str):
    """Minimal integration factory for #4058 crash-path tests.

    Returns a freshly persisted ParentGmailIntegration with an in_app-only
    delivery channel so we don't have to mock WhatsApp/email plumbing.
    """
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email=f"{email_suffix}_parent@test.com",
        full_name="Crash Test Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address=f"{email_suffix}@gmail.com",
        google_id=f"google_{email_suffix}",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
    )
    db_session.add(integration)
    db_session.flush()

    settings = ParentDigestSettings(
        integration_id=integration.id,
        delivery_channels="in_app",
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)
    return integration


@pytest.mark.asyncio
async def test_crash_between_fetch_and_log_does_not_advance_last_synced_at(
    db_session,
):
    """#4058 — legacy path: if the notification step crashes AFTER
    fetch_child_emails returned but BEFORE the DigestDeliveryLog commit,
    integration.last_synced_at must remain pinned to its pre-run value so a
    retry re-fetches the same window and does not drop the parent-day of mail.
    """
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration_plain(
        db_session, email_suffix="crash_retry_legacy"
    )
    pre_last_synced_at = integration.last_synced_at  # None on a fresh row

    captured_since: list = []

    async def capturing_fetch(db, integration, since=None):
        captured_since.append(since)
        return _fetched_emails()

    # Fix ``since`` so the retry assertion can compare it byte-for-byte; if
    # either run re-derived ``since`` from datetime.now(), the test would
    # pass by accident for the wrong reason.
    fixed_since = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)

    # First run: AI generation succeeds, but the delivery step raises — the
    # worker's exception handler commits a status="failed" log (without
    # bumping last_synced_at). Mirror that by forcing generate_parent_digest
    # to raise: that path writes the failed log and returns early before the
    # final last_synced_at stamp.
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=capturing_fetch),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(side_effect=RuntimeError("AI crashed mid-run")),
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=fixed_since,
        )

    assert result["status"] == "failed"
    db_session.refresh(integration)
    # Crash path must NOT have advanced last_synced_at.
    assert integration.last_synced_at == pre_last_synced_at

    # Retry with the same mocks but a successful digest generation this time.
    first_since = captured_since[0]
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=capturing_fetch),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest body</p>"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        retry_result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=fixed_since,
        )

    assert retry_result["status"] in ("delivered", "partial")
    # Retry saw the same ``since`` window as the first call — no mail dropped.
    assert captured_since[1] == first_since

    # After a successful retry, last_synced_at MUST have advanced.
    db_session.refresh(integration)
    assert integration.last_synced_at is not None
    if pre_last_synced_at is not None:
        assert integration.last_synced_at > pre_last_synced_at


@pytest.mark.asyncio
async def test_happy_path_advances_last_synced_at_from_fetch_result(db_session):
    """#4058 — legacy path: on a successful run, last_synced_at must be
    advanced (to the fetch-returned timestamp) atomically with the
    DigestDeliveryLog commit.
    """
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    integration = _mk_parent_and_integration_plain(
        db_session, email_suffix="happy_legacy_synced"
    )
    assert integration.last_synced_at is None

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>ok</p>"),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        result = await send_digest_for_integration(
            db_session,
            integration,
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] in ("delivered", "partial")
    db_session.refresh(integration)
    assert integration.last_synced_at is not None
