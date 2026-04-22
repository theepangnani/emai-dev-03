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
    received_at = datetime.now(timezone.utc) - timedelta(hours=1)
    return [
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
    ]


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

    # Expect at least 2 auto-create notifications (one per new Task). The
    # parent digest itself also calls the same function once — assert >=3 and
    # that at least 2 carry the "added to your tasks from teacher email" body.
    task_calls = [
        c for c in notify_mock.call_args_list
        if "added to your tasks from teacher email" in (c.kwargs.get("content") or "")
    ]
    assert len(task_calls) == 2, f"expected 2 task notifications, got {len(task_calls)} of {len(notify_mock.call_args_list)}"
    for c in task_calls:
        assert c.kwargs.get("channels") == ["app_notification"]


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
    upgrade_calls = [
        c for c in notify_mock.call_args_list
        if "linked to a class assignment" in (c.kwargs.get("content") or "")
    ]
    assert len(upgrade_calls) == 1, f"expected 1 upgrade notification, got {len(upgrade_calls)}"
    assert upgrade_calls[0].kwargs.get("channels") == ["app_notification"]
