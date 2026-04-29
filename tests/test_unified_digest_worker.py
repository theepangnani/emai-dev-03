"""Worker tests for unified digest v2 (#4012, #4015).

Covers:
- Feature flag OFF → legacy per-integration path is called, unified path
  is NOT.
- Feature flag ON → unified per-parent path is called, legacy path is
  NOT.
- ``send_unified_digest_for_parent`` groups integrations, attributes
  emails, and emits exactly one DigestDeliveryLog per parent run
  (keyed to integrations[0]) — #4052 removed the per-integration
  duplicate-history rows.
- Empty-inbox short-circuit skips delivery.
- Attribution counts land in the result dict.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Flag dispatch: OFF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_digests_flag_off_runs_legacy_path(app):
    # Depend on the ``app`` fixture so the conftest model reload has
    # happened before we import the job module — otherwise running this
    # test in isolation leaves the SQLAlchemy registry in a stale state
    # that corrupts later DB tests in the same session.
    from app.jobs import parent_email_digest_job as job

    mock_db = MagicMock()
    with patch.object(job, "SessionLocal", return_value=mock_db), patch(
        "app.services.feature_flag_service.is_feature_enabled",
        return_value=False,
    ), patch.object(
        job, "_process_legacy_parent_email_digests", new=AsyncMock()
    ) as mock_legacy, patch.object(
        job, "process_unified_parent_email_digests", new=AsyncMock()
    ) as mock_unified:
        await job.process_parent_email_digests()

    mock_legacy.assert_awaited_once_with(mock_db)
    mock_unified.assert_not_awaited()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_process_digests_flag_on_runs_unified_path(app):
    from app.jobs import parent_email_digest_job as job

    mock_db = MagicMock()
    with patch.object(job, "SessionLocal", return_value=mock_db), patch(
        "app.services.feature_flag_service.is_feature_enabled",
        return_value=True,
    ), patch.object(
        job, "_process_legacy_parent_email_digests", new=AsyncMock()
    ) as mock_legacy, patch.object(
        job, "process_unified_parent_email_digests", new=AsyncMock()
    ) as mock_unified:
        await job.process_parent_email_digests()

    mock_unified.assert_awaited_once_with(mock_db)
    mock_legacy.assert_not_awaited()
    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# send_unified_digest_for_parent — integration-level behavior
# ---------------------------------------------------------------------------


def _make_parent_with_integrations(db_session, email, child_emails):
    """Build parent + 1 integration per entry in ``child_emails`` + child
    profiles wired to ParentChildSchoolEmail so attribution matches.

    Returns (parent, [integration_id, ...], [profile_id, ...]).
    """
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email=email,
        full_name="Unified Worker Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.commit()

    integration_ids: list[int] = []
    profile_ids: list[int] = []
    for idx, child_email in enumerate(child_emails):
        integration = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address=f"{email}.gmail{idx}@gmail.com",
            google_id=f"google_{email}_{idx}",
            access_token="enc_access",
            refresh_token="enc_refresh",
            child_school_email=child_email,
            child_first_name=f"Kid{idx}",
        )
        db_session.add(integration)
        db_session.commit()
        db_session.add(ParentDigestSettings(integration_id=integration.id))
        db_session.commit()
        integration_ids.append(integration.id)

        profile = ParentChildProfile(
            parent_id=parent.id,
            first_name=f"Kid{idx}",
        )
        db_session.add(profile)
        db_session.commit()
        db_session.add(ParentChildSchoolEmail(
            child_profile_id=profile.id,
            email_address=child_email,
        ))
        db_session.commit()
        profile_ids.append(profile.id)

    return parent, integration_ids, profile_ids


@pytest.mark.asyncio
async def test_unified_digest_groups_integrations_and_attributes(db_session):
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import DigestDeliveryLog

    parent, int_ids, prof_ids = _make_parent_with_integrations(
        db_session,
        "unified1@test.com",
        ["kida@ocdsb.ca", "kidb@ocdsb.ca"],
    )

    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    # First integration yields 1 email to kida; second yields 1 email to kidb.
    call_count = {"n": 0}

    async def fake_fetch(db, integration, since=None):
        call_count["n"] += 1
        # #4058 — fetch_child_emails now returns {"emails": [...], "synced_at": dt}
        if integration.child_school_email == "kida@ocdsb.ca":
            return {
                "emails": [{
                    "source_id": "m1",
                    "sender_name": "Teacher A",
                    "sender_email": "ta@school.ca",
                    "subject": "Hello A",
                    "snippet": "body a",
                    "to_addresses": ["kida@ocdsb.ca"],
                    "delivered_to_addresses": [],
                    "received_at": since,
                }],
                "synced_at": datetime.now(timezone.utc),
            }
        return {
            "emails": [{
                "source_id": "m2",
                "sender_name": "Teacher B",
                "sender_email": "tb@school.ca",
                "subject": "Hello B",
                "snippet": "body b",
                "to_addresses": ["kidb@ocdsb.ca"],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "delivered"
    assert result["email_count"] == 2
    assert call_count["n"] == 2
    # Both emails attributed via school_email
    assert result["attribution_counts"]["school_email"] == 2
    assert result["attribution_counts"]["unattributed"] == 0
    # #4449 — channel_status mirrors legacy contract so the manual "Send
    # Now" UI keeps showing per-channel indicators when V2 dispatches.
    assert result["channel_status"] == {"in_app": True, "email": True}

    # #4052 — exactly ONE DigestDeliveryLog per unified run (was N-per-
    # integration under the legacy path). The row is keyed to the first
    # integration so the existing /logs endpoint still surfaces it.
    logs = (
        db_session.query(DigestDeliveryLog)
        .filter(DigestDeliveryLog.parent_id == parent.id)
        .all()
    )
    assert len(logs) == 1
    assert logs[0].integration_id == int_ids[0]
    assert logs[0].status == "delivered"
    assert logs[0].email_count == 2


@pytest.mark.asyncio
async def test_unified_digest_sends_one_notification_per_parent(db_session):
    """One parent with two integrations should trigger exactly ONE
    send_multi_channel_notification call, not one per integration."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, int_ids, _ = _make_parent_with_integrations(
        db_session,
        "unified_onenotif@test.com",
        ["x1@ocdsb.ca", "x2@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(db, integration, since=None):
        return {
            "emails": [{
                "source_id": f"m-{integration.id}",
                "sender_email": "t@school.ca",
                "subject": "s",
                "snippet": "b",
                "to_addresses": [integration.child_school_email],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    mock_notify = MagicMock(return_value={"in_app": True, "email": True})
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=mock_notify,
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "delivered"
    assert mock_notify.call_count == 1
    # Verify the call targeted the unified title, not a per-kid title.
    kwargs = mock_notify.call_args.kwargs
    assert "kids" in kwargs["title"].lower()


@pytest.mark.asyncio
async def test_unified_digest_skips_when_no_emails_and_notify_on_empty_false(db_session):
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _int, _prof = _make_parent_with_integrations(
        db_session,
        "unified_empty@test.com",
        ["solo@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": [], "synced_at": None}),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ) as mock_notify:
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "skipped"
    assert result["email_count"] == 0
    assert result["reason"] == "no_new_emails"
    # #4449 — early-return paths emit ``channel_status=None`` so callers
    # can rely on the key always being present.
    assert result["channel_status"] is None
    mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_unified_digest_counts_unattributed(db_session):
    """#4329 — an email with an unregistered school-looking To: + no
    monitored sender match should bin under ``unattributed``."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _int, _prof = _make_parent_with_integrations(
        db_session,
        "unified_unattrib@test.com",
        ["only@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(db, integration, since=None):
        # No recipient match, no monitored sender registered for this
        # parent → unattributed. Use a school-looking domain (gapps.*)
        # so the email isn't short-circuited as parent_direct.
        return {
            "emails": [{
                "source_id": "mx",
                "sender_email": "mystery@nowhere.ca",
                "subject": "?",
                "snippet": "?",
                "to_addresses": ["someone_else@gapps.yrdsb.ca"],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["email_count"] == 1
    assert result["attribution_counts"]["unattributed"] == 1
    assert result["attribution_counts"]["school_email"] == 0


@pytest.mark.asyncio
async def test_unified_digest_counts_parent_direct(db_session):
    """#4329 — an email sent to the parent's gmail (no school-looking
    recipient) should bin under ``parent_direct``, not ``unattributed``."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _int, _prof = _make_parent_with_integrations(
        db_session,
        "unified_pd@test.com",
        ["solo@gapps.yrdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(db, integration, since=None):
        return {
            "emails": [{
                "source_id": "pd1",
                "sender_email": "newsletter@anywhere.com",
                "subject": "Weekly newsletter",
                "snippet": "...",
                "to_addresses": ["parent@gmail.com"],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["email_count"] == 1
    assert result["attribution_counts"]["parent_direct"] == 1
    assert result["attribution_counts"]["unattributed"] == 0
    assert result["attribution_counts"]["school_email"] == 0


@pytest.mark.asyncio
async def test_unified_digest_dedup_prevents_second_run_same_day(db_session):
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import DigestDeliveryLog

    parent, int_ids, _ = _make_parent_with_integrations(
        db_session,
        "unified_dedup@test.com",
        ["dedup@ocdsb.ca"],
    )
    # Seed a delivered log for today under the integration id.
    log = DigestDeliveryLog(
        parent_id=parent.id,
        integration_id=int_ids[0],
        email_count=1,
        digest_content="prior",
        status="delivered",
        channels_used="in_app,email",
    )
    db_session.add(log)
    db_session.commit()

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": [], "synced_at": None}),
    ) as mock_fetch:
        result = await send_unified_digest_for_parent(
            db_session, parent.id, since=datetime.now(timezone.utc)
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "already_delivered"
    # #4449 — early-return paths emit ``channel_status=None``.
    assert result["channel_status"] is None
    # fetch should NOT have been invoked (dedup short-circuits).
    mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# #4449 — unified worker must return ``channel_status`` so the manual
# "Send Now" UI keeps showing per-channel delivery indicators when V2
# dispatches. Mirrors the legacy ``send_digest_for_integration`` contract:
# True = sent, False = attempted+failed, None = not requested.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_digest_returns_channel_status_for_all_three_channels(
    db_session,
):
    """Parent with delivery_channels='in_app,email,whatsapp' → returned
    ``channel_status`` includes all three keys keyed to the per-channel
    outcome.
    """
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _ = _make_parent_with_whatsapp_integration(
        db_session, "channel_status_all3@test.com"
    )

    sectioned_payload = {
        "urgent": ["Yearbook due TODAY"],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=_fake_fetch_one_email),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": False}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned_payload),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template",
        new=MagicMock(return_value=True),
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid", "HXv1sid"
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid_v2", ""
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    # Status is "partial" because email failed but in_app + whatsapp ok.
    assert result["status"] == "partial"
    # All three channel keys present, mirroring legacy semantics.
    assert result["channel_status"] == {
        "in_app": True,
        "email": False,
        "whatsapp": True,
    }


# ---------------------------------------------------------------------------
# #4052 — single DigestDeliveryLog per parent + last_synced_at hygiene
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_digest_writes_one_log_and_stamps_forwarding(db_session):
    """Two integrations + one email via real-shape dict → exactly one
    DigestDeliveryLog keyed to integrations[0]; forwarding_seen_at stamped
    on the matched school-email row (#4046 + #4052)."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import (
        DigestDeliveryLog,
        ParentChildSchoolEmail,
    )

    parent, int_ids, prof_ids = _make_parent_with_integrations(
        db_session,
        "one_log_per_parent@test.com",
        ["kid_a@ocdsb.ca", "kid_b@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    # Only integrations[0]'s fetch returns a match; integrations[1] empty.
    async def fake_fetch(db, integration, since=None):
        if integration.id == int_ids[0]:
            return {
                "emails": [{
                    "source_id": "msg-1",
                    "sender_name": "Teacher",
                    "sender_email": "teacher@school.ca",
                    "subject": "Test",
                    "snippet": "body",
                    "to_addresses": ["kid_a@ocdsb.ca"],
                    "delivered_to_addresses": [],
                    "received_at": since,
                }],
                "synced_at": datetime.now(timezone.utc),
            }
        return {"emails": [], "synced_at": datetime.now(timezone.utc)}

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "delivered"
    assert result["email_count"] == 1

    # Exactly ONE log row, keyed to integrations[0].
    logs = (
        db_session.query(DigestDeliveryLog)
        .filter(DigestDeliveryLog.parent_id == parent.id)
        .all()
    )
    assert len(logs) == 1
    assert logs[0].integration_id == int_ids[0]

    # forwarding_seen_at stamped on the matching school-email row.
    stamped = (
        db_session.query(ParentChildSchoolEmail)
        .filter(ParentChildSchoolEmail.email_address == "kid_a@ocdsb.ca")
        .first()
    )
    assert stamped is not None
    assert stamped.forwarding_seen_at is not None


@pytest.mark.asyncio
async def test_unified_digest_skip_path_updates_last_synced_at(db_session):
    """When fetch_child_emails returns empty, the worker skips delivery but
    must still advance last_synced_at on all integrations so the next run
    doesn't re-query the same historical window (#4052)."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import (
        DigestDeliveryLog,
        ParentGmailIntegration,
    )

    parent, int_ids, _ = _make_parent_with_integrations(
        db_session,
        "skip_updates_synced@test.com",
        ["sa@ocdsb.ca", "sb@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value={"emails": [], "synced_at": None}),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(),
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "no_new_emails"

    # All integrations had last_synced_at bumped (was None before the run).
    integs = (
        db_session.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.id.in_(int_ids))
        .all()
    )
    assert len(integs) == len(int_ids)
    for integ in integs:
        assert integ.last_synced_at is not None

    # No DigestDeliveryLog written on the skip path.
    logs = (
        db_session.query(DigestDeliveryLog)
        .filter(DigestDeliveryLog.parent_id == parent.id)
        .all()
    )
    assert len(logs) == 0


# ---------------------------------------------------------------------------
# #4058 — unified path: crash between fetch and delivery-log commit must NOT
# advance last_synced_at for any of the parent's integrations, so a retry
# re-fetches the same window.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_crash_between_fetch_and_log_preserves_last_synced_at(
    db_session,
):
    """Before this fix, fetch_child_emails committed last_synced_at eagerly,
    so if the worker died after fetch but before the delivery-log commit,
    retries saw advanced stamps and produced an empty digest — the unified
    path amplified this across ALL of a parent's integrations.

    The fix moves the stamp into the worker's final commit. This test
    verifies: crash → stamps stay at pre-run values → retry with identical
    ``since`` argument reprocesses the same email window.
    """
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import ParentGmailIntegration

    parent, int_ids, _ = _make_parent_with_integrations(
        db_session,
        "unified_crash_retry@test.com",
        ["kidx@ocdsb.ca", "kidy@ocdsb.ca"],
    )
    # Capture baseline (None on fresh rows).
    pre_stamps = {
        integ.id: integ.last_synced_at
        for integ in db_session.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.id.in_(int_ids))
        .all()
    }

    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)
    captured_since: list = []

    async def capturing_fetch(db, integration, since=None):
        captured_since.append(since)
        return {
            "emails": [{
                "source_id": f"m-{integration.id}",
                "sender_name": "T",
                "sender_email": "t@school.ca",
                "subject": "S",
                "snippet": "b",
                "to_addresses": [integration.child_school_email],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    # First run: the delivery step raises mid-flight. The unified worker
    # propagates uncaught exceptions (the outer loop's rollback handler in
    # process_unified_parent_email_digests catches them), so here we let
    # pytest.raises capture it — the important assertion is that no
    # last_synced_at stamp has been advanced.
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=capturing_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(side_effect=RuntimeError("notification crashed")),
    ):
        with pytest.raises(RuntimeError, match="notification crashed"):
            await send_unified_digest_for_parent(
                db_session, parent.id, skip_dedup=True, since=since
            )

    db_session.rollback()
    integs = (
        db_session.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.id.in_(int_ids))
        .all()
    )
    # Crash → no stamp advanced.
    for integ in integs:
        assert integ.last_synced_at == pre_stamps[integ.id]

    # Retry with identical ``since`` — success this time. Must see the SAME
    # ``since`` arg reach fetch_child_emails.
    first_since = captured_since[0]
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=capturing_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ):
        retry_result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert retry_result["status"] == "delivered"
    # Both integrations were fetched on the retry with the same ``since``.
    retry_sinces = captured_since[len(int_ids):]
    assert len(retry_sinces) == len(int_ids)
    for s in retry_sinces:
        assert s == first_since

    # Success path MUST have advanced all stamps.
    integs = (
        db_session.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.id.in_(int_ids))
        .all()
    )
    for integ in integs:
        assert integ.last_synced_at is not None


@pytest.mark.asyncio
async def test_unified_partial_fetch_failure_only_stamps_succeeded_integrations(
    db_session,
):
    """If the fetch errored for one integration but succeeded for another,
    only the succeeded one's ``last_synced_at`` should advance. Advancing
    the failed integration's stamp silently drops its unread window on
    the next run (mini-#4058 regression caught in pass-2 /pr-review).
    """
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import ParentGmailIntegration

    parent, int_ids, _ = _make_parent_with_integrations(
        db_session,
        "unified_partial_fetch_fail@test.com",
        ["ok@ocdsb.ca", "fail@ocdsb.ca"],
    )
    ok_id, fail_id = int_ids[0], int_ids[1]

    pre_stamps = {
        integ.id: integ.last_synced_at
        for integ in db_session.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.id.in_(int_ids))
        .all()
    }

    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def partial_fail_fetch(db, integration, since=None):
        # OK integration returns a message; failing integration raises.
        if integration.id == fail_id:
            raise RuntimeError("gmail transient error")
        return {
            "emails": [{
                "source_id": f"m-{integration.id}",
                "sender_name": "T",
                "sender_email": "t@school.ca",
                "subject": "S",
                "snippet": "b",
                "to_addresses": [integration.child_school_email],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=partial_fail_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    # Digest should still deliver (the OK integration produced content).
    assert result["status"] == "delivered"

    integs = {
        i.id: i
        for i in db_session.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.id.in_(int_ids))
        .all()
    }

    # OK integration: stamp advanced past pre-run value.
    assert integs[ok_id].last_synced_at is not None
    assert integs[ok_id].last_synced_at != pre_stamps[ok_id]

    # FAILED integration: stamp UNCHANGED — retry must cover its unread window.
    assert integs[fail_id].last_synced_at == pre_stamps[fail_id]


# ---------------------------------------------------------------------------
# #4103 — unified path: WhatsApp delivery with V2-then-V1-then-freeform
# fallback. Replaces the legacy per-kid path entirely so multi-kid parents
# get exactly ONE WhatsApp message instead of N (each previously naming the
# wrong child in subject + greeting).
# ---------------------------------------------------------------------------


def _make_parent_with_whatsapp_integration(db_session, email):
    """Build parent + 1 verified-WhatsApp integration. Returns (parent, integration_id)."""
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email=email,
        full_name="Unified WA Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.commit()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address=f"{email}.gmail@gmail.com",
        google_id=f"google_{email}",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="kid@ocdsb.ca",
        child_first_name="Kid",
        whatsapp_phone="+15555550100",
        whatsapp_verified=True,
    )
    db_session.add(integration)
    db_session.commit()
    db_session.add(
        ParentDigestSettings(
            integration_id=integration.id,
            delivery_channels="in_app,email,whatsapp",
        )
    )
    db_session.commit()

    profile = ParentChildProfile(parent_id=parent.id, first_name="Kid")
    db_session.add(profile)
    db_session.commit()
    db_session.add(
        ParentChildSchoolEmail(
            child_profile_id=profile.id,
            email_address="kid@ocdsb.ca",
        )
    )
    db_session.commit()

    return parent, integration.id


async def _fake_fetch_one_email(db, integration, since=None):
    return {
        "emails": [{
            "source_id": f"wa-{integration.id}",
            "sender_name": "Teacher",
            "sender_email": "t@school.ca",
            "subject": "Yearbook due TODAY",
            "snippet": "Submit the cover by EOD",
            "to_addresses": [integration.child_school_email],
            "delivered_to_addresses": [],
            "received_at": since,
        }],
        "synced_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_unified_digest_sends_v1_whatsapp_when_v2_sid_unset(db_session):
    """V2 SID empty + V1 SID set → V1 single-variable template called once
    per parent with sanitized flattened content. (Today's prod state — V2
    awaiting Meta approval per #3987.)"""
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _ = _make_parent_with_whatsapp_integration(
        db_session, "unified_wa_v1@test.com"
    )

    sectioned_payload = {
        "urgent": ["Yearbook due TODAY"],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_v1 = MagicMock(return_value=True)
    mock_v2 = MagicMock(return_value=True)
    mock_freeform = MagicMock(return_value=True)

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=_fake_fetch_one_email),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned_payload),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_v1
    ), patch.object(
        job, "_send_sectioned_whatsapp_v2", new=mock_v2
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message", new=mock_freeform
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid", "HXv1sid"
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid_v2", ""
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    assert result["status"] == "delivered"
    # V1 path used.
    mock_v1.assert_called_once()
    call_args = mock_v1.call_args
    assert call_args[0][0] == "+15555550100"
    assert call_args[0][1] == "HXv1sid"
    variables = call_args[0][2]
    expected_first_name = parent.full_name.split()[0]
    assert variables["1"] == expected_first_name
    assert "Yearbook" in variables["2"]
    # V2 + freeform NOT used.
    mock_v2.assert_not_called()
    mock_freeform.assert_not_called()


@pytest.mark.asyncio
async def test_unified_digest_sends_v2_whatsapp_when_v2_sid_set(db_session):
    """V2 SID set → sectioned 4-variable V2 template called once per parent.
    V1 + freeform paths are NOT used."""
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _ = _make_parent_with_whatsapp_integration(
        db_session, "unified_wa_v2@test.com"
    )

    sectioned_payload = {
        "urgent": ["Yearbook due TODAY"],
        "announcements": ["School concert Friday"],
        "action_items": ["Sign permission form"],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_v1 = MagicMock(return_value=True)
    mock_v2 = MagicMock(return_value=True)
    mock_freeform = MagicMock(return_value=True)

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=_fake_fetch_one_email),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned_payload),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_v1
    ), patch.object(
        job, "_send_sectioned_whatsapp_v2", new=mock_v2
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message", new=mock_freeform
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid", "HXv1sid"
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid_v2", "HXv2sid"
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    assert result["status"] == "delivered"
    # V2 path used.
    mock_v2.assert_called_once()
    v2_call_args = mock_v2.call_args[0]
    assert v2_call_args[0] == "+15555550100"
    assert v2_call_args[1] == "HXv2sid"
    assert v2_call_args[2] == parent.full_name.split()[0]
    assert v2_call_args[3] == sectioned_payload
    # V1 + freeform NOT used.
    mock_v1.assert_not_called()
    mock_freeform.assert_not_called()


@pytest.mark.asyncio
async def test_unified_digest_falls_back_to_freeform_when_no_sid(db_session):
    """No V1 + no V2 SID → freeform send_whatsapp_message body fallback."""
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _ = _make_parent_with_whatsapp_integration(
        db_session, "unified_wa_freeform@test.com"
    )

    sectioned_payload = {
        "urgent": ["Yearbook due TODAY"],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_freeform = MagicMock(return_value=True)
    mock_v1 = MagicMock(return_value=True)

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=_fake_fetch_one_email),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=sectioned_payload),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message", new=mock_freeform
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_v1
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid", ""
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid_v2", ""
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    assert result["status"] == "delivered"
    mock_freeform.assert_called_once()
    sent_body = mock_freeform.call_args[0][1]
    assert "Yearbook" in sent_body
    assert "https://www.classbridge.ca/email-digest" in sent_body
    mock_v1.assert_not_called()


@pytest.mark.asyncio
async def test_unified_digest_skips_whatsapp_when_phone_unverified(db_session):
    """WhatsApp selected but no integration has a verified phone → skipped
    (whatsapp_ok=None), NOT counted as a failure (#3887)."""
    from app.core.security import get_password_hash
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.user import User, UserRole

    parent = User(
        email="unified_wa_unverified@test.com",
        full_name="Unverified Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(parent)
    db_session.commit()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="x@gmail.com",
        google_id="g",
        access_token="a",
        refresh_token="r",
        child_school_email="kid@ocdsb.ca",
        child_first_name="Kid",
        whatsapp_phone=None,
        whatsapp_verified=False,
    )
    db_session.add(integration)
    db_session.commit()
    db_session.add(
        ParentDigestSettings(
            integration_id=integration.id,
            delivery_channels="in_app,email,whatsapp",
        )
    )
    db_session.commit()
    profile = ParentChildProfile(parent_id=parent.id, first_name="Kid")
    db_session.add(profile)
    db_session.commit()
    db_session.add(
        ParentChildSchoolEmail(
            child_profile_id=profile.id, email_address="kid@ocdsb.ca"
        )
    )
    db_session.commit()

    mock_v1 = MagicMock()
    mock_v2 = MagicMock()
    mock_freeform = MagicMock()

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=_fake_fetch_one_email),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_v1
    ), patch.object(
        job, "_send_sectioned_whatsapp_v2", new=mock_v2
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message", new=mock_freeform
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    # No WhatsApp helper called.
    mock_v1.assert_not_called()
    mock_v2.assert_not_called()
    mock_freeform.assert_not_called()
    # Overall status still "delivered" — the in_app + email channels succeeded
    # and WhatsApp's None outcome is excluded from overall (#3887 semantics).
    assert result["status"] == "delivered"


# ---------------------------------------------------------------------------
# #4106 / #4109 — empty-digest WA short-circuit + single-kid subject parity.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_digest_empty_sectioned_wa_short_circuit_v1(db_session):
    """#4106 — when notify_on_empty=true and ZERO emails come through, the
    sectioned digest is all-empty; flattening yields ``""`` which Twilio's V1
    template may reject. The worker must substitute the fixed message
    ``"No new school emails today."`` for V1 variable ``"2"`` BEFORE branching
    to the V2/V1/freeform render."""
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import ParentDigestSettings

    parent, integration_id = _make_parent_with_whatsapp_integration(
        db_session, "unified_wa_empty@test.com"
    )
    # Flip notify_on_empty=true so the worker proceeds with no emails.
    setting = (
        db_session.query(ParentDigestSettings)
        .filter(ParentDigestSettings.integration_id == integration_id)
        .first()
    )
    setting.notify_on_empty = True
    db_session.commit()

    empty_sectioned = {
        "urgent": [],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_v1 = MagicMock(return_value=True)
    mock_v2 = MagicMock(return_value=True)
    mock_freeform = MagicMock(return_value=True)

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(
            return_value={"emails": [], "synced_at": datetime.now(timezone.utc)}
        ),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(return_value=empty_sectioned),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_v1
    ), patch.object(
        job, "_send_sectioned_whatsapp_v2", new=mock_v2
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message", new=mock_freeform
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid", "HXv1sid"
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid_v2", ""
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    assert result["status"] == "delivered"
    # V1 path used with the fixed empty-digest message in variable "2".
    mock_v1.assert_called_once()
    variables = mock_v1.call_args[0][2]
    assert variables["2"] == "No new school emails today."
    # V2 + freeform NOT used.
    mock_v2.assert_not_called()
    mock_freeform.assert_not_called()


@pytest.mark.asyncio
async def test_unified_digest_single_kid_subject_personalized(db_session):
    """#4109 — when the parent has exactly one kid, the digest title becomes
    ``"Email Digest for {KidName}"`` instead of the generic
    ``"Email Digest for your kids"``."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _int_ids, _prof_ids = _make_parent_with_integrations(
        db_session,
        "unified_subject_one_kid@test.com",
        ["solo_kid@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(db, integration, since=None):
        return {
            "emails": [{
                "source_id": "msg-1",
                "sender_name": "Teacher",
                "sender_email": "teacher@school.ca",
                "subject": "Hello",
                "snippet": "body",
                "to_addresses": ["solo_kid@ocdsb.ca"],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    mock_notify = MagicMock(return_value={"in_app": True, "email": True})
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=mock_notify,
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "delivered"
    mock_notify.assert_called_once()
    # First kid in _make_parent_with_integrations is "Kid0".
    assert mock_notify.call_args.kwargs["title"] == "Email Digest for Kid0"


@pytest.mark.asyncio
async def test_unified_digest_multi_kid_subject_keeps_plural(db_session):
    """#4109 regression — two distinct kids must keep the plural
    ``"your kids"`` phrasing (no specific kid name leaked into the subject)."""
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _int_ids, _prof_ids = _make_parent_with_integrations(
        db_session,
        "unified_subject_multi_kid@test.com",
        ["kid_alpha@ocdsb.ca", "kid_beta@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(db, integration, since=None):
        return {
            "emails": [{
                "source_id": f"msg-{integration.id}",
                "sender_name": "Teacher",
                "sender_email": "teacher@school.ca",
                "subject": "Hello",
                "snippet": "body",
                "to_addresses": [integration.child_school_email],
                "delivered_to_addresses": [],
                "received_at": since,
            }],
            "synced_at": datetime.now(timezone.utc),
        }

    mock_notify = MagicMock(return_value={"in_app": True, "email": True})
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=fake_fetch),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=mock_notify,
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True, since=since
        )

    assert result["status"] == "delivered"
    title = mock_notify.call_args.kwargs["title"]
    assert "kids" in title.lower()
    assert "Kid0" not in title
    assert "Kid1" not in title


@pytest.mark.asyncio
async def test_unified_digest_whatsapp_ai_failure_partial_not_full_failure(db_session):
    """#4107 — when generate_sectioned_digest raises (Anthropic outage etc.),
    in_app + email still deliver and overall status is 'partial', not 'failed'.
    The whatsapp_delivery_status is 'failed' on the persisted log."""
    from app.jobs import parent_email_digest_job as job
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent
    from app.models.parent_gmail_integration import DigestDeliveryLog

    parent, _ = _make_parent_with_whatsapp_integration(
        db_session, "unified_wa_aifail@test.com"
    )

    mock_v1 = MagicMock()
    mock_v2 = MagicMock()
    mock_freeform = MagicMock()

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(side_effect=_fake_fetch_one_email),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"in_app": True, "email": True}),
    ), patch(
        "app.services.parent_digest_ai_service.generate_sectioned_digest",
        new=AsyncMock(side_effect=RuntimeError("anthropic timeout")),
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_v1
    ), patch.object(
        job, "_send_sectioned_whatsapp_v2", new=mock_v2
    ), patch(
        "app.services.whatsapp_service.send_whatsapp_message", new=mock_freeform
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid", "HXv1sid"
    ), patch.object(
        job.app_settings, "twilio_whatsapp_digest_content_sid_v2", ""
    ):
        result = await send_unified_digest_for_parent(
            db_session, parent.id, skip_dedup=True,
            since=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

    # in_app + email succeeded but WhatsApp's AI step raised → partial.
    assert result["status"] == "partial"

    # No WhatsApp helper called (the exception was raised before any send).
    mock_v1.assert_not_called()
    mock_v2.assert_not_called()
    mock_freeform.assert_not_called()

    # Log persists the failed WhatsApp status alongside the successful email.
    log = (
        db_session.query(DigestDeliveryLog)
        .filter(DigestDeliveryLog.parent_id == parent.id)
        .first()
    )
    assert log is not None
    assert log.whatsapp_delivery_status == "failed"
    assert log.email_delivery_status == "sent"


# ---------------------------------------------------------------------------
# #4502 — V2 sectioned WhatsApp variable sanitisation
#
# Twilio's Content API rejects \n in template variables (HTTP 400 "Content
# Variables parameter is invalid"). #3941 fixed this for V1; these tests
# guard the V2 send-boundary sanitisation so a regression cannot silently
# reintroduce the failure mode.
# ---------------------------------------------------------------------------


def test_send_sectioned_whatsapp_v2_strips_newlines_from_variables():
    """Mutation-test guard: every variable passed to Twilio must be \\n-free.

    If the V2 sanitisation is reverted, ``urgent_block`` (and the other two
    section blocks) will contain ``\\n`` bullet separators emitted by
    ``_sectioned_section_block``, and this test will fail.
    """
    from app.jobs.parent_email_digest_job import _send_sectioned_whatsapp_v2

    sectioned = {
        "urgent": ["item one", "item two", "item three"],
        "announcements": ["news alpha", "news beta"],
        "action_items": ["sign form", "pay fee", "rsvp"],
        "overflow": {"urgent": 2, "announcements": 1, "action_items": 0},
    }

    mock_send = MagicMock(return_value=True)
    with patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_send
    ):
        result = _send_sectioned_whatsapp_v2(
            "+15555550100", "HXv2sid", "Pat Parent", sectioned
        )

    assert result is True
    mock_send.assert_called_once()
    # Variables dict is the third positional arg.
    variables = mock_send.call_args[0][2]
    assert set(variables.keys()) == {"1", "2", "3", "4"}
    for key, value in variables.items():
        assert "\n" not in value, f"variable {key!r} contains \\n: {value!r}"
        assert "\r" not in value, f"variable {key!r} contains \\r: {value!r}"
        assert "\t" not in value, f"variable {key!r} contains \\t: {value!r}"
    # Real content survives the flattening.
    assert "item one" in variables["2"]
    assert "item two" in variables["2"]
    assert "And 2 more" in variables["2"]
    assert "news alpha" in variables["3"]
    assert "And 1 more" in variables["3"]
    assert "rsvp" in variables["4"]


def test_send_sectioned_whatsapp_v2_caps_each_variable_at_1024_chars():
    """Per-variable 1024-char Twilio cap: long blocks truncate with ``...``."""
    from app.jobs.parent_email_digest_job import _send_sectioned_whatsapp_v2

    long_item = "x" * 2000  # forces overflow past Twilio's per-variable cap
    sectioned = {
        "urgent": [long_item],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_send = MagicMock(return_value=True)
    with patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_send
    ):
        _send_sectioned_whatsapp_v2(
            "+15555550100", "HXv2sid", "Pat", sectioned
        )

    variables = mock_send.call_args[0][2]
    urgent_var = variables["2"]
    assert len(urgent_var) <= 1024
    assert urgent_var.endswith("...")


def test_send_sectioned_whatsapp_v2_empty_sections_render_as_none():
    """Empty section round-trips to literal ``(none)`` (V2 template requires
    non-empty variables)."""
    from app.jobs.parent_email_digest_job import _send_sectioned_whatsapp_v2

    sectioned = {
        "urgent": [],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_send = MagicMock(return_value=True)
    with patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_send
    ):
        _send_sectioned_whatsapp_v2(
            "+15555550100", "HXv2sid", "Pat", sectioned
        )

    variables = mock_send.call_args[0][2]
    assert variables["2"] == "(none)"
    assert variables["3"] == "(none)"
    assert variables["4"] == "(none)"


def test_send_sectioned_whatsapp_v2_strips_control_chars():
    """ASCII control chars (0x00-0x1f) get stripped from section variables."""
    from app.jobs.parent_email_digest_job import _send_sectioned_whatsapp_v2

    # Inject a NUL, BEL, vertical tab, and form feed inside a bullet.
    dirty_item = "alpha\x00beta\x07gamma\x0bdelta\x0cend"
    sectioned = {
        "urgent": [dirty_item],
        "announcements": [],
        "action_items": [],
        "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
    }

    mock_send = MagicMock(return_value=True)
    with patch(
        "app.services.whatsapp_service.send_whatsapp_template", new=mock_send
    ):
        _send_sectioned_whatsapp_v2(
            "+15555550100", "HXv2sid", "Pat", sectioned
        )

    variables = mock_send.call_args[0][2]
    urgent_var = variables["2"]
    # No control chars survive.
    for ch in urgent_var:
        assert ord(ch) >= 0x20, f"control char {ch!r} leaked through"
    # Real content survives.
    assert "alpha" in urgent_var
    assert "beta" in urgent_var
    assert "gamma" in urgent_var
    assert "delta" in urgent_var
    assert "end" in urgent_var
