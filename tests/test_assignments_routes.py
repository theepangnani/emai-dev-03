"""Tests for CB-TASKSYNC-001 I7 — immediate hooks in assignments.py (#3919).

Covers:
1. test_submit_assignment_auto_completes_linked_task
2. test_submit_assignment_when_no_task_exists
3. test_delete_assignment_soft_cancels_linked_task
4. test_delete_assignment_hook_fails_gracefully
5. test_feature_flag_off_skips_submit_hook
6. test_feature_flag_off_skips_delete_hook

Notes
-----
- Each test uses unique emails/course names to avoid collisions with the
  session-scoped DB.
- The `task_sync_enabled` feature flag is toggled per-test and reset in
  teardown — do NOT leave it on, other tests rely on the default-off state.
- ORM imports happen inside functions to stay consistent with conftest's
  `app` fixture (which reloads `app.models`).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from conftest import PASSWORD, _auth


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _set_task_sync_flag(db_session, enabled: bool) -> None:
    """Force the `task_sync_enabled` flag to the requested state for this test."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "task_sync_enabled")
        .first()
    )
    assert flag is not None, "task_sync_enabled must be seeded"
    flag.enabled = bool(enabled)
    db_session.commit()


@pytest.fixture()
def hooks_env(db_session):
    """Teacher + student (enrolled in a course) + assignment with a linked Task.

    Unique suffix per-call keeps tests isolated in the session-scoped DB.
    """
    from app.core.security import get_password_hash
    from app.models.assignment import Assignment
    from app.models.course import Course, student_courses
    from app.models.student import Student
    from app.models.task import Task
    from app.models.teacher import Teacher
    from app.models.user import User, UserRole

    suffix = f"_i7_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    hashed = get_password_hash(PASSWORD)

    teacher_user = User(
        email=f"i7_teacher{suffix}@test.com",
        full_name="I7 Teacher",
        role=UserRole.TEACHER,
        hashed_password=hashed,
    )
    student_user = User(
        email=f"i7_student{suffix}@test.com",
        full_name="I7 Student",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add_all([teacher_user, student_user])
    db_session.commit()

    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.commit()

    student = Student(user_id=student_user.id, grade_level=8)
    db_session.add(student)
    db_session.commit()

    course = Course(
        name=f"I7 Course{suffix}",
        teacher_id=teacher.id,
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()

    db_session.execute(
        student_courses.insert().values(student_id=student.id, course_id=course.id)
    )
    db_session.commit()

    assignment = Assignment(
        title=f"Hook Test Assignment{suffix}",
        description="Original description",
        course_id=course.id,
        due_date=datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc),
    )
    db_session.add(assignment)
    db_session.commit()

    # Create a linked Task (as if the scheduled job had already run).
    task = Task(
        created_by_user_id=teacher_user.id,
        assigned_to_user_id=student_user.id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        course_id=course.id,
        student_id=student.id,
        source="assignment",
        source_ref=str(assignment.id),
        source_status="active",
        source_created_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    yield {
        "teacher_user": teacher_user,
        "teacher": teacher,
        "student_user": student_user,
        "student": student,
        "course": course,
        "assignment": assignment,
        "task": task,
    }

    # Teardown — reset flag to OFF so sibling tests see the default state.
    _set_task_sync_flag(db_session, False)


# ──────────────────────────────────────────────────────────────────────────
# 1. submit_assignment hook
# ──────────────────────────────────────────────────────────────────────────

def test_submit_assignment_auto_completes_linked_task(client, db_session, hooks_env):
    from app.models.task import Task

    _set_task_sync_flag(db_session, True)
    env = hooks_env

    headers = _auth(client, env["student_user"].email)
    resp = client.post(
        f"/api/assignments/{env['assignment'].id}/submit",
        data={"notes": "Done!"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Re-fetch the linked Task — must now be completed.
    db_session.expire_all()
    task = db_session.query(Task).filter(Task.id == env["task"].id).first()
    assert task is not None
    assert task.is_completed is True
    assert task.completed_at is not None
    assert task.source_status == "source_submitted"


def test_submit_assignment_when_no_task_exists(client, db_session, hooks_env):
    """Hook is a no-op (not an error) when no Task was previously created."""
    from app.models.task import Task

    _set_task_sync_flag(db_session, True)
    env = hooks_env

    # Simulate "scheduled job never ran" by deleting the pre-created Task.
    db_session.query(Task).filter(Task.id == env["task"].id).delete()
    db_session.commit()
    assert (
        db_session.query(Task)
        .filter(Task.source == "assignment", Task.source_ref == str(env["assignment"].id))
        .count()
        == 0
    )

    headers = _auth(client, env["student_user"].email)
    resp = client.post(
        f"/api/assignments/{env['assignment'].id}/submit",
        data={"notes": "First submit"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Hook should NOT create a Task — scheduled job owns creation.
    count = (
        db_session.query(Task)
        .filter(Task.source == "assignment", Task.source_ref == str(env["assignment"].id))
        .count()
    )
    assert count == 0


def test_feature_flag_off_skips_submit_hook(client, db_session, hooks_env):
    from app.models.task import Task

    _set_task_sync_flag(db_session, False)
    env = hooks_env

    headers = _auth(client, env["student_user"].email)
    resp = client.post(
        f"/api/assignments/{env['assignment'].id}/submit",
        data={"notes": "Submit with flag off"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    task = db_session.query(Task).filter(Task.id == env["task"].id).first()
    assert task is not None
    # Flag was off — Task must be untouched.
    assert task.is_completed is False
    assert task.completed_at is None
    assert task.source_status == "active"


# ──────────────────────────────────────────────────────────────────────────
# 2. delete_assignment hook
# ──────────────────────────────────────────────────────────────────────────

def test_delete_assignment_soft_cancels_linked_task(client, db_session, hooks_env):
    from app.models.task import Task

    _set_task_sync_flag(db_session, True)
    env = hooks_env
    task_id = env["task"].id
    assignment_id = env["assignment"].id

    headers = _auth(client, env["teacher_user"].email)
    resp = client.delete(
        f"/api/assignments/{assignment_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Task must still exist (soft-cancel, NOT hard-delete).
    db_session.expire_all()
    task = db_session.query(Task).filter(Task.id == task_id).first()
    assert task is not None, "Task must NOT be hard-deleted"
    assert task.archived_at is not None
    assert task.source_status == "source_deleted"


def test_delete_assignment_hook_fails_gracefully(
    client, db_session, hooks_env, monkeypatch
):
    """Hook exception must NOT fail the primary DELETE."""
    from app.models.assignment import Assignment

    _set_task_sync_flag(db_session, True)
    env = hooks_env
    # Snapshot ids before expiry — the ORM row is about to be deleted.
    assignment_id = env["assignment"].id

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated sync failure")

    # Patch the name actually imported into the route module.
    monkeypatch.setattr(
        "app.api.routes.assignments.handle_assignment_deleted", _raise
    )

    headers = _auth(client, env["teacher_user"].email)
    resp = client.delete(
        f"/api/assignments/{assignment_id}",
        headers=headers,
    )
    # Primary action still succeeds.
    assert resp.status_code == 200, resp.text

    # Assignment is gone.
    db_session.expire_all()
    remaining = (
        db_session.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .first()
    )
    assert remaining is None


def test_feature_flag_off_skips_delete_hook(client, db_session, hooks_env):
    from app.models.assignment import Assignment
    from app.models.task import Task

    _set_task_sync_flag(db_session, False)
    env = hooks_env
    task_id = env["task"].id
    assignment_id = env["assignment"].id

    headers = _auth(client, env["teacher_user"].email)
    resp = client.delete(
        f"/api/assignments/{assignment_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Assignment gone.
    db_session.expire_all()
    remaining = (
        db_session.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .first()
    )
    assert remaining is None

    # Task untouched — flag was off.
    task = db_session.query(Task).filter(Task.id == task_id).first()
    assert task is not None
    assert task.archived_at is None
    assert task.source_status == "active"
