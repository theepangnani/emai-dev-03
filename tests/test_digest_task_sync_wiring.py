"""Tests for CB-TASKSYNC-001 I6 — email-digest → task sync wiring (#3918).

Covers:
- `send_digest_for_integration(..., create_tasks=True)` calls the AI extractor
  and upserts Tasks when `task_sync_enabled` is ON.
- HTTP "Send digest now" endpoint does NOT create tasks without the opt-in
  query param.
- HTTP "Send digest now" endpoint DOES create tasks with `?create_tasks=true`
  when the feature flag is ON.
- The override respects the feature flag: flag OFF + `?create_tasks=true`
  → still 0 tasks.
- The override emits the `task_sync.test_override` warning.
- In-app notification is fired on every auto-create (new Task only,
  not on idempotent re-runs of an existing Task).
- In-app notification is fired on `email_digest → assignment` upgrade.

Note: these tests mock the Anthropic client (via `extract_digest_items`) and
the Gmail fetcher; the goal is to exercise the wiring between the job / HTTP
endpoint and `task_sync_service`, not the AI or Gmail integrations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import _auth


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _set_task_sync_flag(db_session, enabled: bool) -> None:
    """Ensure the `task_sync_enabled` feature flag exists and matches `enabled`."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "task_sync_enabled")
        .first()
    )
    assert flag is not None
    flag.enabled = enabled
    db_session.commit()


def _set_unified_v2_flag(db_session, enabled: bool) -> None:
    """Force `parent.unified_digest_v2` to a known state for tests that need
    to pin the dispatch to a specific path (#4434).

    Default in production is ON; tests that exercise the legacy per-integration
    path's task-sync pilot (#3929) must opt out of V2 since the unified worker
    does not accept ``create_tasks`` and never invokes ``extract_digest_items``.
    """
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "parent.unified_digest_v2")
        .first()
    )
    assert flag is not None
    flag.enabled = enabled
    db_session.commit()


def _digest_item(title: str, due: datetime, confidence: float = 0.9, msg_id: str = "<m1>"):
    from app.services.parent_digest_ai_service import DigestTaskItem

    return DigestTaskItem(
        title=title,
        due_date=due,
        course_name=None,
        confidence=confidence,
        source_excerpt="",
        gmail_message_id=msg_id,
    )


@pytest.fixture
def digest_env(db_session):
    """Build a parent + child + Gmail integration + digest settings."""
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )
    from app.models.student import Student, parent_students
    from app.models.user import User, UserRole

    suffix = f"_dj_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    hashed = get_password_hash("Password123!")

    parent = User(
        email=f"dj_parent{suffix}@example.com",
        full_name="Digest Job Parent",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    child = User(
        email=f"dj_child{suffix}@example.com",
        full_name="Digest Job Child",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add_all([parent, child])
    db_session.commit()

    student = Student(user_id=child.id, grade_level=8)
    db_session.add(student)
    db_session.commit()

    db_session.execute(
        parent_students.insert().values(parent_id=parent.id, student_id=student.id)
    )
    db_session.commit()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address=f"parent_gmail{suffix}@gmail.com",
        google_id=f"google_id{suffix}",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email=child.email,
        child_first_name="Alex",
    )
    db_session.add(integration)
    db_session.commit()

    settings = ParentDigestSettings(
        integration_id=integration.id,
        timezone="America/Toronto",
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(integration)
    integration.digest_settings = settings

    return {
        "parent": parent,
        "child": child,
        "student": student,
        "integration": integration,
        "settings": settings,
    }


def _fetched_emails():
    # #4058 — fetch_child_emails now returns {"emails": [...], "synced_at": dt}
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)
    return {
        "emails": [
            {
                "source_id": "<msg-1@school.ca>",
                "sender_name": "Ms. Smith",
                "sender_email": "smith@school.ca",
                "subject": "Permission slip due",
                "body": "Please sign the permission slip by May 10.",
                "snippet": "Permission slip",
                "received_at": received_at,
            },
            {
                "source_id": "<msg-2@school.ca>",
                "sender_name": "Mr. Jones",
                "sender_email": "jones@school.ca",
                "subject": "Math quiz",
                "body": "Math quiz scheduled for May 12.",
                "snippet": "Math quiz",
                "received_at": received_at,
            },
        ],
        "synced_at": datetime.now(timezone.utc),
    }


# ──────────────────────────────────────────────────────────────────────────
# 1. Scheduled-job path: create_tasks defaults True → extracts + upserts.
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_email_digest_job_creates_tasks(db_session, digest_env):
    """Flag ON + 2 AI items → 2 tasks created with source='email_digest'."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.task import Task

    _set_task_sync_flag(db_session, True)
    env = digest_env

    items = [
        _digest_item(
            "Permission slip",
            datetime(2026, 5, 10, tzinfo=timezone.utc),
            confidence=0.9,
            msg_id="<msg-1@school.ca>",
        ),
        _digest_item(
            "Math quiz",
            datetime(2026, 5, 12, tzinfo=timezone.utc),
            confidence=0.9,
            msg_id="<msg-2@school.ca>",
        ),
    ]

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(return_value=items),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        result = await send_digest_for_integration(
            db_session,
            env["integration"],
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    assert result["status"] in ("delivered", "partial", "skipped")
    tasks = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child"].id)
        .all()
    )
    assert len(tasks) == 2
    titles = {t.title for t in tasks}
    assert titles == {"Permission slip", "Math quiz"}


@pytest.mark.asyncio
async def test_job_skips_task_creation_when_flag_off(db_session, digest_env):
    """Flag OFF → scheduled job default (create_tasks=True) must still create 0 tasks."""
    from app.jobs.parent_email_digest_job import send_digest_for_integration
    from app.models.task import Task

    _set_task_sync_flag(db_session, False)
    env = digest_env

    items = [
        _digest_item("Permission slip", datetime(2026, 5, 10, tzinfo=timezone.utc)),
    ]

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(return_value=items),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        await send_digest_for_integration(
            db_session,
            env["integration"],
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    count = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child"].id)
        .count()
    )
    assert count == 0


# ──────────────────────────────────────────────────────────────────────────
# 2. HTTP "Send digest now" — default (no query param) must NOT create tasks.
# ──────────────────────────────────────────────────────────────────────────

def test_send_digest_now_without_param_does_NOT_create_tasks(
    client, db_session, digest_env
):
    """Default production behaviour: no `?create_tasks=true` → 0 tasks created."""
    from app.models.task import Task

    _set_task_sync_flag(db_session, True)
    # #4434 — pin to legacy path so this test keeps exercising the #3929
    # task-sync pilot wiring (which does not exist on the V2 worker).
    _set_unified_v2_flag(db_session, False)
    env = digest_env

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(
            return_value=[
                _digest_item("Permission slip", datetime(2026, 5, 10, tzinfo=timezone.utc))
            ]
        ),
    ) as mock_extract, patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        resp = client.post(
            f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    # Extractor MUST NOT be called — gated out before the AI call.
    mock_extract.assert_not_called()
    count = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child"].id)
        .count()
    )
    assert count == 0


# ──────────────────────────────────────────────────────────────────────────
# 3. HTTP "Send digest now" — with `?create_tasks=true` + flag ON → creates.
# ──────────────────────────────────────────────────────────────────────────

def test_send_digest_now_with_create_tasks_true_creates_tasks(
    client, db_session, digest_env
):
    from app.models.task import Task

    _set_task_sync_flag(db_session, True)
    # #4434 — task-sync pilot only fires on the legacy worker; V2 ignores
    # the create_tasks query param.
    _set_unified_v2_flag(db_session, False)
    env = digest_env

    items = [
        _digest_item("Permission slip", datetime(2026, 5, 10, tzinfo=timezone.utc)),
    ]

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(return_value=items),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        resp = client.post(
            f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest?create_tasks=true",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    tasks = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child"].id)
        .all()
    )
    assert len(tasks) == 1
    assert tasks[0].title == "Permission slip"


# ──────────────────────────────────────────────────────────────────────────
# 4. Override MUST respect feature flag — flag OFF + ?create_tasks=true → 0.
# ──────────────────────────────────────────────────────────────────────────

def test_send_digest_now_override_respects_feature_flag(
    client, db_session, digest_env
):
    from app.models.task import Task

    _set_task_sync_flag(db_session, False)
    # #4434 — pin to legacy path. This test asserts the legacy pilot
    # honors task_sync_enabled=False; V2 never creates tasks regardless.
    _set_unified_v2_flag(db_session, False)
    env = digest_env

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(
            return_value=[
                _digest_item("Permission slip", datetime(2026, 5, 10, tzinfo=timezone.utc))
            ]
        ),
    ) as mock_extract, patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        resp = client.post(
            f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest?create_tasks=true",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    mock_extract.assert_not_called()
    count = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child"].id)
        .count()
    )
    assert count == 0


# ──────────────────────────────────────────────────────────────────────────
# 5. Override emits the `task_sync.test_override` warning.
# ──────────────────────────────────────────────────────────────────────────

def test_send_digest_now_override_logs_warning(
    client, db_session, digest_env, caplog
):
    import logging

    _set_task_sync_flag(db_session, True)
    # #4434 — log assertion is path-agnostic (the override warning fires
    # before dispatch), but pin legacy here for parity with the other
    # pilot-pathway tests in this section.
    _set_unified_v2_flag(db_session, False)
    env = digest_env

    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None}),
    ):
        with caplog.at_level(logging.WARNING, logger="app.api.routes.parent_email_digest"):
            resp = client.post(
                f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest?create_tasks=true",
                headers=_auth(client, env["parent"].email),
            )

    assert resp.status_code == 200, resp.text
    assert any(
        "task_sync.test_override" in rec.getMessage() for rec in caplog.records
    ), [r.getMessage() for r in caplog.records]


# ──────────────────────────────────────────────────────────────────────────
# 6. In-app notification fires once per newly auto-created Task.
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notification_sent_on_auto_create(db_session, digest_env):
    from app.jobs.parent_email_digest_job import send_digest_for_integration

    _set_task_sync_flag(db_session, True)
    env = digest_env

    items = [
        _digest_item("Permission slip", datetime(2026, 5, 10, tzinfo=timezone.utc)),
        _digest_item("Math quiz", datetime(2026, 5, 12, tzinfo=timezone.utc)),
    ]

    notify_mock = MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None})
    with patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        new=AsyncMock(return_value=_fetched_emails()),
    ), patch(
        "app.services.parent_digest_ai_service.generate_parent_digest",
        new=AsyncMock(return_value="<p>digest</p>"),
    ), patch(
        "app.services.parent_digest_ai_service.extract_digest_items",
        new=AsyncMock(return_value=items),
    ), patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=notify_mock,
    ):
        await send_digest_for_integration(
            db_session,
            env["integration"],
            skip_dedup=True,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )

    # Expect exactly 2 auto-create task notifications (one per NEW Task).
    # The parent digest itself also calls send_multi_channel_notification
    # with a different body — filter by the task-notification content.
    from app.models.notification import NotificationType

    task_calls = [
        c for c in notify_mock.call_args_list
        if "added to your tasks from teacher email" in (c.kwargs.get("content") or "")
    ]
    assert len(task_calls) == 2, f"expected 2 task notifications, got {len(task_calls)} of {len(notify_mock.call_args_list)}"
    for c in task_calls:
        assert c.kwargs.get("channels") == ["app_notification"]
        # #3947 — auto-create must be tagged TASK_CREATED, not TASK_DUE.
        assert c.kwargs.get("notification_type") == NotificationType.TASK_CREATED


# ──────────────────────────────────────────────────────────────────────────
# 7. Notification fires on email_digest → assignment upgrade.
# ──────────────────────────────────────────────────────────────────────────

def test_notification_sent_on_upgrade(db_session, digest_env):
    """Pre-existing email_digest Task + matching Assignment → upgrade + notify."""
    from app.models.assignment import Assignment
    from app.models.course import Course, student_courses
    from app.models.task import Task
    from app.models.teacher import Teacher
    from app.services.task_sync_service import (
        _digest_source_ref,
        upsert_task_from_assignment,
    )
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    env = digest_env
    due = datetime(2026, 5, 10, 15, 0, tzinfo=timezone.utc)

    # Seed a teacher + course the child is enrolled in.
    suffix = f"_up_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    teacher_user = User(
        email=f"up_teacher{suffix}@example.com",
        full_name="Upgrade Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(teacher_user)
    db_session.commit()
    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.commit()
    course = Course(
        name=f"Upgrade Course{suffix}",
        teacher_id=teacher.id,
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.execute(
        student_courses.insert().values(
            student_id=env["student"].id, course_id=course.id
        )
    )
    db_session.commit()

    # Seed a pre-existing email_digest Task for the child with a fuzzy-matching title.
    digest_title = "Chapter 5 Quiz"
    source_ref = _digest_source_ref(digest_title, due, "America/Toronto")
    pre_task = Task(
        created_by_user_id=env["parent"].id,
        assigned_to_user_id=env["child"].id,
        title=digest_title,
        due_date=due,
        source="email_digest",
        source_ref=source_ref,
        source_confidence=0.9,
        source_status="active",
        source_message_id="<m1>",
        source_created_at=datetime.now(timezone.utc),
    )
    db_session.add(pre_task)
    db_session.commit()

    # Now add a matching Assignment — upgrade should fire.
    assignment = Assignment(
        title="chapter 5 quiz",  # different case — normalize matches
        description="covering sections 5.1-5.3",
        course_id=course.id,
        due_date=due,
    )
    db_session.add(assignment)
    db_session.commit()

    notify_mock = MagicMock(return_value={"notification": None, "in_app": True, "email": None, "classbridge_message": None})
    with patch(
        "app.services.notification_service.send_multi_channel_notification",
        new=notify_mock,
    ):
        tasks = upsert_task_from_assignment(db_session, assignment)

    # The pre-existing email_digest Task was upgraded → source='assignment'.
    upgraded = [t for t in tasks if t.id == pre_task.id]
    assert upgraded, f"pre-existing task {pre_task.id} not in upsert result: {[t.id for t in tasks]}"
    db_session.refresh(upgraded[0])
    assert upgraded[0].source == "assignment"
    assert upgraded[0].source_ref == str(assignment.id)

    # And a notification fired mentioning the upgrade.
    from app.models.notification import NotificationType

    upgrade_calls = [
        c for c in notify_mock.call_args_list
        if "linked to a class assignment" in (c.kwargs.get("content") or "")
    ]
    assert len(upgrade_calls) == 1, f"expected 1 upgrade notification, got {len(upgrade_calls)}"
    assert upgrade_calls[0].kwargs.get("channels") == ["app_notification"]
    # #3947 — upgrade must be tagged TASK_UPGRADED, not TASK_DUE.
    assert upgrade_calls[0].kwargs.get("notification_type") == NotificationType.TASK_UPGRADED


# ──────────────────────────────────────────────────────────────────────────
# 8. #4434 — manual "Send Now" endpoint dispatches on the V2 flag.
# ──────────────────────────────────────────────────────────────────────────

def test_send_digest_now_dispatches_to_unified_when_v2_flag_on(
    client, db_session, digest_env
):
    """V2 flag ON → endpoint calls send_unified_digest_for_parent, NOT legacy."""
    _set_unified_v2_flag(db_session, True)
    env = digest_env

    unified_mock = AsyncMock(
        return_value={
            "status": "delivered",
            "email_count": 2,
            "attribution_counts": {"school_email": 2},
            "channel_status": {"in_app": True, "email": True},
            "message": "Unified digest delivered with 2 emails",
        }
    )
    legacy_mock = AsyncMock(
        return_value={"status": "delivered", "email_count": 0, "message": "legacy"}
    )

    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ), patch(
        "app.jobs.parent_email_digest_job.send_digest_for_integration",
        new=legacy_mock,
    ):
        resp = client.post(
            f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    unified_mock.assert_awaited_once()
    legacy_mock.assert_not_awaited()
    # The unified-shape attribution_counts field must round-trip through
    # SendDigestResponse (#4434 widened the schema).
    body = resp.json()
    assert body["status"] == "delivered"
    assert body["email_count"] == 2
    assert body["attribution_counts"] == {"school_email": 2}
    # #4449 — channel_status must also round-trip so the manual "Send Now"
    # UI keeps showing per-channel delivery indicators when V2 dispatches.
    assert body["channel_status"] == {"in_app": True, "email": True}


def test_send_digest_now_dispatches_to_legacy_when_v2_flag_off(
    client, db_session, digest_env
):
    """V2 flag OFF → endpoint calls send_digest_for_integration, NOT unified.

    Note: this is a parallel correctness check, not the regression guard for
    #4434. The flag-ON test above is the actual regression guard — it would
    fail if the dispatch fix were reverted. This flag-OFF test passes either
    way (legacy is what the buggy code called too).
    """
    _set_unified_v2_flag(db_session, False)
    env = digest_env

    unified_mock = AsyncMock(
        return_value={"status": "delivered", "email_count": 0, "message": "unified"}
    )
    legacy_mock = AsyncMock(
        return_value={
            "status": "delivered",
            "email_count": 1,
            "message": "Email digest delivered with 1 emails",
            "channel_status": {"in_app": True, "email": None, "whatsapp": None},
            "reason": None,
        }
    )

    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ), patch(
        "app.jobs.parent_email_digest_job.send_digest_for_integration",
        new=legacy_mock,
    ):
        resp = client.post(
            f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    legacy_mock.assert_awaited_once()
    unified_mock.assert_not_awaited()


def test_send_digest_now_v2_branch_warns_and_ignores_create_tasks(
    client, db_session, digest_env, caplog
):
    """V2 flag ON + ?create_tasks=true → unified path is called; create_tasks
    is NOT forwarded (V2 worker doesn't accept it) and a warning is logged."""
    import logging

    _set_unified_v2_flag(db_session, True)
    env = digest_env

    unified_mock = AsyncMock(
        return_value={
            "status": "delivered",
            "email_count": 0,
            "attribution_counts": {},
            "message": "unified",
        }
    )
    legacy_mock = AsyncMock(
        return_value={"status": "delivered", "email_count": 0, "message": "legacy"}
    )

    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ), patch(
        "app.jobs.parent_email_digest_job.send_digest_for_integration",
        new=legacy_mock,
    ):
        with caplog.at_level(logging.WARNING, logger="app.api.routes.parent_email_digest"):
            resp = client.post(
                f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest?create_tasks=true",
                headers=_auth(client, env["parent"].email),
            )

    assert resp.status_code == 200, resp.text
    unified_mock.assert_awaited_once()
    # Symmetric guard with the other dispatch tests — V2 must not double-dispatch.
    legacy_mock.assert_not_awaited()
    # call signature check — V2 worker is called with parent_id, NOT integration,
    # and create_tasks is NOT in its kwargs.
    call_kwargs = unified_mock.await_args.kwargs
    assert "create_tasks" not in call_kwargs
    assert call_kwargs.get("skip_dedup") is True
    # The V2-specific ignore warning must fire; the legacy `task_sync.test_override`
    # warning must NOT (it's now scoped to the legacy branch only — #4450).
    msgs = [rec.getMessage() for rec in caplog.records]
    assert any("ignoring create_tasks=true on unified V2 path" in m for m in msgs), msgs
    assert not any("task_sync.test_override" in m for m in msgs), msgs


# ──────────────────────────────────────────────────────────────────────────
# 9. #4450 — pre-dispatch validation must scope to the chosen path.
# ──────────────────────────────────────────────────────────────────────────

def test_send_digest_now_v2_dispatches_when_url_integration_inactive(
    client, db_session, digest_env
):
    """#4450 — V2 treats integration_id as triggering identity, not scope.
    An inactive URL integration must NOT 400 the request when other
    integrations are active."""
    _set_unified_v2_flag(db_session, True)
    env = digest_env
    # Mark the URL integration inactive — V2 should still dispatch.
    env["integration"].is_active = False
    db_session.commit()

    unified_mock = AsyncMock(return_value={
        "status": "delivered", "email_count": 1,
        "attribution_counts": {}, "message": "ok",
    })
    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ):
        resp = client.post(
            f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest",
            headers=_auth(client, env["parent"].email),
        )
    assert resp.status_code == 200, resp.text
    unified_mock.assert_awaited_once()


def test_send_digest_now_legacy_400s_when_url_integration_inactive(
    client, db_session, digest_env
):
    """#4450 regression guard — legacy path keeps the per-integration
    is_active check (was the original behavior)."""
    _set_unified_v2_flag(db_session, False)
    env = digest_env
    env["integration"].is_active = False
    db_session.commit()
    resp = client.post(
        f"/api/parent/email-digest/integrations/{env['integration'].id}/send-digest",
        headers=_auth(client, env["parent"].email),
    )
    assert resp.status_code == 400
    assert "not active" in resp.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────────
# 10. #4483 (D2/D3) — parent-scoped manual "Send Now" endpoint.
#
# The new endpoint at POST /api/parent/email-digest/send-now (no
# integration_id) honors `parent.unified_digest_v2`:
#   * flag ON  → calls send_unified_digest_for_parent ONCE
#   * flag OFF → loops the parent's active integrations and calls
#                send_digest_for_integration per integration
# This is what the unified UI calls so multi-kid parents always get the
# multi-kid framing in subject + body.
# ──────────────────────────────────────────────────────────────────────────


def _add_second_integration(db_session, parent, *, suffix_extra: str):
    """Add a second active Gmail integration (+ digest settings) for ``parent``.

    Used by the parent-scoped tests below to assert behavior across multiple
    integrations under the legacy fallback path.
    """
    from app.models.parent_gmail_integration import (
        ParentDigestSettings,
        ParentGmailIntegration,
    )

    integ2 = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address=f"parent2{suffix_extra}@gmail.com",
        google_id=f"google_id2{suffix_extra}",
        access_token="enc_access2",
        refresh_token="enc_refresh2",
        child_school_email=f"child2{suffix_extra}@school.ca",
        child_first_name="Sam",
    )
    db_session.add(integ2)
    db_session.commit()
    settings2 = ParentDigestSettings(
        integration_id=integ2.id,
        timezone="America/Toronto",
    )
    db_session.add(settings2)
    db_session.commit()
    db_session.refresh(integ2)
    return integ2


def test_send_now_parent_scoped_unified_path(client, db_session, digest_env):
    """Flag ON + 2 integrations → unified worker called ONCE; legacy NOT called."""
    _set_unified_v2_flag(db_session, True)
    env = digest_env
    _add_second_integration(
        db_session, env["parent"], suffix_extra=f"_p1_{id(db_session)}"
    )

    unified_mock = AsyncMock(
        return_value={
            "status": "delivered",
            "email_count": 3,
            "attribution_counts": {"school_email": 3},
            "channel_status": {"in_app": True, "email": True},
            "message": "Unified digest delivered with 3 emails",
        }
    )
    legacy_mock = AsyncMock(
        return_value={"status": "delivered", "email_count": 0, "message": "legacy"}
    )

    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ), patch(
        "app.jobs.parent_email_digest_job.send_digest_for_integration",
        new=legacy_mock,
    ):
        resp = client.post(
            "/api/parent/email-digest/send-now",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    unified_mock.assert_awaited_once()
    legacy_mock.assert_not_awaited()
    body = resp.json()
    assert body["status"] == "delivered"
    assert body["email_count"] == 3
    assert body["attribution_counts"] == {"school_email": 3}
    assert body["channel_status"] == {"in_app": True, "email": True}
    # The unified worker is called with parent_id (not integration); skip_dedup
    # is forced True because this is an explicit manual trigger.
    call_kwargs = unified_mock.await_args.kwargs
    assert call_kwargs.get("skip_dedup") is True
    # Positional second arg = parent_id (db is positional 0).
    assert unified_mock.await_args.args[1] == env["parent"].id


def test_send_now_parent_scoped_legacy_path(client, db_session, digest_env):
    """Flag OFF + 2 integrations → legacy helper called twice, unified never."""
    _set_unified_v2_flag(db_session, False)
    env = digest_env
    _add_second_integration(
        db_session, env["parent"], suffix_extra=f"_p2_{id(db_session)}"
    )

    unified_mock = AsyncMock(
        return_value={"status": "delivered", "email_count": 0, "message": "unified"}
    )
    legacy_mock = AsyncMock(
        return_value={
            "status": "delivered",
            "email_count": 1,
            "message": "Email digest delivered",
            "channel_status": {"in_app": True, "email": None, "whatsapp": None},
        }
    )

    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ), patch(
        "app.jobs.parent_email_digest_job.send_digest_for_integration",
        new=legacy_mock,
    ):
        resp = client.post(
            "/api/parent/email-digest/send-now",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    unified_mock.assert_not_awaited()
    assert legacy_mock.await_count == 2
    body = resp.json()
    # Aggregated success across both integrations → "delivered".
    assert body["status"] == "delivered"
    assert body["email_count"] == 2  # 1 + 1
    # Sanity on legacy invocation contract: create_tasks=False is forced
    # because the parent-scoped trigger never opt-ins to the #3929 pilot.
    for call in legacy_mock.await_args_list:
        assert call.kwargs.get("create_tasks") is False
        assert call.kwargs.get("skip_dedup") is True


def test_send_now_parent_scoped_no_active_integrations_returns_skipped(
    client, db_session, digest_env
):
    """Flag OFF + 0 active integrations → SKIPPED with email_count=0."""
    _set_unified_v2_flag(db_session, False)
    env = digest_env
    # Deactivate the only integration on the parent.
    env["integration"].is_active = False
    db_session.commit()

    unified_mock = AsyncMock(return_value={"status": "delivered", "email_count": 0})
    legacy_mock = AsyncMock(return_value={"status": "delivered", "email_count": 0})

    with patch(
        "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
        new=unified_mock,
    ), patch(
        "app.jobs.parent_email_digest_job.send_digest_for_integration",
        new=legacy_mock,
    ):
        resp = client.post(
            "/api/parent/email-digest/send-now",
            headers=_auth(client, env["parent"].email),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "skipped"
    assert body["email_count"] == 0
    # Neither helper should fire when the parent has nothing to send.
    unified_mock.assert_not_awaited()
    legacy_mock.assert_not_awaited()


def test_send_now_parent_scoped_requires_parent_role(
    client, db_session, digest_env
):
    """Non-parent user (student) gets 403."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    suffix = f"_studcheck_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    student_user = User(
        email=f"student{suffix}@example.com",
        full_name="A Student",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(student_user)
    db_session.commit()

    resp = client.post(
        "/api/parent/email-digest/send-now",
        headers=_auth(client, student_user.email),
    )
    assert resp.status_code == 403


def test_send_now_parent_scoped_rate_limited_after_10(
    client, db_session, digest_env, app
):
    """11th call within a minute must trip the 10/min limiter."""
    _set_unified_v2_flag(db_session, True)
    env = digest_env

    unified_mock = AsyncMock(
        return_value={
            "status": "delivered",
            "email_count": 0,
            "attribution_counts": {},
            "channel_status": None,
            "message": "ok",
        }
    )

    headers = _auth(client, env["parent"].email)
    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        with patch(
            "app.jobs.parent_email_digest_job.send_unified_digest_for_parent",
            new=unified_mock,
        ):
            for _ in range(10):
                resp = client.post(
                    "/api/parent/email-digest/send-now", headers=headers
                )
                assert resp.status_code == 200, resp.text
            resp = client.post(
                "/api/parent/email-digest/send-now", headers=headers
            )
        assert resp.status_code == 429
    finally:
        app.state.limiter.enabled = False
        app.state.limiter.reset()
