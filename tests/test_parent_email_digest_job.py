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
    """#3879 / #3904 — Twilio Content Variables cap each variable at ~1024 chars.

    The WhatsApp template path must:
    - PRESERVE \\n / \\r / \\t in the plain_text variable (#3904 — paragraph
      breaks must survive so the digest doesn't render as a wall of text)
    - strip only other non-printable control chars (ASCII 0-8, 11-12, 14-31)
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

    # #3904: newlines (and tabs) must now be PRESERVED in variable "2" so the
    # WhatsApp digest renders with proper paragraph breaks. Only non-printable
    # control chars (other than \n, \r, \t) are stripped.
    assert "\n" in var2, "variable '2' MUST preserve newlines (#3904)"
    # Other ASCII control chars (0x00-0x08, 0x0b, 0x0c, 0x0e-0x1f) still stripped
    for ch in var2:
        code = ord(ch)
        # Allowed: printable ASCII, \t (9), \n (10), \r (13), and Unicode > 31
        assert code >= 32 or code in (9, 10, 13), (
            f"variable '2' contains disallowed control char {code!r}"
        )
    assert len(var2) <= 1024, f"variable '2' must be ≤ 1024 chars (got {len(var2)})"

    # Variable "1" — parent_name: no newlines
    assert "\n" not in var1
    assert "\r" not in var1


@pytest.mark.asyncio
async def test_whatsapp_template_strips_unsafe_control_chars_but_keeps_newlines(db_session):
    """#3904 — \\n / \\r / \\t are preserved; other control chars stripped."""
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

    # Paragraph break preserved
    assert "\n\n" in var2, "variable '2' MUST preserve paragraph-break newlines (#3904)"
    # Unsafe control chars stripped
    assert "\x00" not in var2, "NUL control char must be stripped"
    assert "\x07" not in var2, "BEL control char must be stripped"


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
        new=AsyncMock(return_value=[]),
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
