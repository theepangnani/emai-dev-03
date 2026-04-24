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
    mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_unified_digest_counts_unattributed(db_session):
    from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

    parent, _int, _prof = _make_parent_with_integrations(
        db_session,
        "unified_unattrib@test.com",
        ["only@ocdsb.ca"],
    )
    since = datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(db, integration, since=None):
        # No recipient match, no monitored sender registered for this
        # parent -> unattributed.
        return {
            "emails": [{
                "source_id": "mx",
                "sender_email": "mystery@nowhere.ca",
                "subject": "?",
                "snippet": "?",
                "to_addresses": ["someone_else@ocdsb.ca"],
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
    # fetch should NOT have been invoked (dedup short-circuits).
    mock_fetch.assert_not_called()


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
