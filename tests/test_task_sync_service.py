"""Tests for CB-TASKSYNC-001 I3 — TaskSyncService core upsert + lifecycle (#3915).

Covers the 17 required scenarios from the issue:
1.  test_upsert_new_assignment_creates_tasks_per_enrolled_student
2.  test_upsert_idempotent_same_assignment_twice
3.  test_upsert_skips_assignment_with_null_due_date
4.  test_upsert_updates_due_date_on_change
5.  test_upsert_skips_update_when_user_edited_task
6.  test_upsert_skips_task_marked_user_deleted
7.  test_upsert_preserves_user_completion_on_update
8.  test_handle_assignment_deleted_soft_cancels
9.  test_handle_assignment_submitted_marks_complete
10. test_digest_item_low_confidence_dropped
11. test_digest_item_tentative_confidence
12. test_digest_item_high_confidence_active
13. test_digest_item_same_ref_second_run_idempotent
14. test_digest_item_upgraded_to_assignment
15. test_source_ref_normalizes_titles
16. test_source_ref_uses_integration_timezone
17. test_multi_child_assignment_creates_one_task_per_child

Note: All SQLAlchemy/ORM imports happen inside functions/fixtures to avoid
interaction with the conftest `app` fixture, which reloads ``app.models``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest


# Sentinel for "use the default due date" — lets tests explicitly pass None
# to mean "null due date".
_DEFAULT_DUE = datetime(2026, 5, 10, 15, 0, tzinfo=timezone.utc)
_UNSET = object()


# ──────────────────────────────────────────────────────────────────────────
# Fixtures — each test DB is session-scoped, so we generate unique emails.
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tasksync_env(db_session):
    """Build: teacher (real user), course, two students (child1, child2), parent."""
    from app.core.security import get_password_hash
    from app.models.course import Course, student_courses
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher
    from app.models.user import User, UserRole

    suffix = f"_ts3_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    hashed = get_password_hash("Password123!")

    teacher_user = User(
        email=f"ts3_teacher{suffix}@example.com",
        full_name="TaskSync Teacher",
        role=UserRole.TEACHER,
        hashed_password=hashed,
    )
    parent_user = User(
        email=f"ts3_parent{suffix}@example.com",
        full_name="TaskSync Parent",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    child_user1 = User(
        email=f"ts3_child1{suffix}@example.com",
        full_name="TaskSync Child 1",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    child_user2 = User(
        email=f"ts3_child2{suffix}@example.com",
        full_name="TaskSync Child 2",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add_all([teacher_user, parent_user, child_user1, child_user2])
    db_session.commit()

    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.commit()

    student1 = Student(user_id=child_user1.id, grade_level=8)
    student2 = Student(user_id=child_user2.id, grade_level=8)
    db_session.add_all([student1, student2])
    db_session.commit()

    db_session.execute(
        parent_students.insert().values(parent_id=parent_user.id, student_id=student1.id)
    )
    db_session.execute(
        parent_students.insert().values(parent_id=parent_user.id, student_id=student2.id)
    )
    db_session.commit()

    course = Course(
        name=f"TS3 Math{suffix}",
        teacher_id=teacher.id,
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.execute(
        student_courses.insert().values(student_id=student1.id, course_id=course.id)
    )
    db_session.execute(
        student_courses.insert().values(student_id=student2.id, course_id=course.id)
    )
    db_session.commit()

    return {
        "teacher_user": teacher_user,
        "teacher": teacher,
        "parent_user": parent_user,
        "child_user1": child_user1,
        "child_user2": child_user2,
        "student1": student1,
        "student2": student2,
        "course": course,
    }


def _make_assignment(
    db_session,
    course_id: int,
    *,
    title: str = "Chapter 5 quiz",
    description: str = "Cover sections 5.1 - 5.3",
    due_date=_UNSET,
):
    from app.models.assignment import Assignment

    effective_due = _DEFAULT_DUE if due_date is _UNSET else due_date
    a = Assignment(
        title=title,
        description=description,
        course_id=course_id,
        due_date=effective_due,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def _digest_item(title: str, due: datetime, confidence: float, msg_id: str = "<m1>"):
    from app.services.parent_digest_ai_service import DigestTaskItem

    return DigestTaskItem(
        title=title,
        due_date=due,
        course_name=None,
        confidence=confidence,
        source_excerpt="",
        gmail_message_id=msg_id,
    )


# ──────────────────────────────────────────────────────────────────────────
# 1. Assignment-source upserts
# ──────────────────────────────────────────────────────────────────────────

def _naive(dt):
    """SQLite strips tzinfo from DateTime columns; compare naively."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def test_upsert_new_assignment_creates_tasks_per_enrolled_student(db_session, tasksync_env):
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)

    tasks = upsert_task_from_assignment(db_session, assignment)

    assert len(tasks) == 2
    assignee_ids = {t.assigned_to_user_id for t in tasks}
    assert assignee_ids == {env["child_user1"].id, env["child_user2"].id}
    for t in tasks:
        assert t.source == "assignment"
        assert t.source_ref == str(assignment.id)
        assert t.source_status == "active"
        assert t.created_by_user_id == env["teacher_user"].id
        assert t.course_id == env["course"].id
        assert t.title == assignment.title
        assert _naive(t.due_date) == _naive(assignment.due_date)


def test_upsert_idempotent_same_assignment_twice(db_session, tasksync_env):
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)

    first = upsert_task_from_assignment(db_session, assignment)
    second = upsert_task_from_assignment(db_session, assignment)

    assert len(first) == 2
    assert len(second) == 2
    assert sorted(t.id for t in first) == sorted(t.id for t in second)
    total = (
        db_session.query(Task)
        .filter(Task.source == "assignment", Task.source_ref == str(assignment.id))
        .count()
    )
    assert total == 2


def test_upsert_skips_assignment_with_null_due_date(db_session, tasksync_env):
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id, due_date=None)

    tasks = upsert_task_from_assignment(db_session, assignment)

    assert tasks == []
    count = (
        db_session.query(Task)
        .filter(Task.source == "assignment", Task.source_ref == str(assignment.id))
        .count()
    )
    assert count == 0


def test_upsert_updates_due_date_on_change(db_session, tasksync_env):
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    original_due = datetime(2026, 5, 10, 15, 0, tzinfo=timezone.utc)
    assignment = _make_assignment(db_session, env["course"].id, due_date=original_due)

    upsert_task_from_assignment(db_session, assignment)
    new_due = datetime(2026, 5, 15, 15, 0, tzinfo=timezone.utc)
    assignment.due_date = new_due
    db_session.commit()

    tasks = upsert_task_from_assignment(db_session, assignment)

    assert len(tasks) == 2
    for t in tasks:
        assert _naive(t.due_date) == _naive(new_due)


def test_upsert_server_side_refresh_does_not_false_trigger_user_edit(db_session, tasksync_env):
    """Regression: the user-edit heuristic must not flag server-side re-runs
    (after the 60s grace window) as user edits. source_created_at is refreshed
    on every server write so that updated_at compared against it stays within
    the grace window for the *next* run."""
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)

    # First run — creates the tasks.
    tasks = upsert_task_from_assignment(db_session, assignment)
    target = tasks[0]
    target_id = target.id

    # Simulate "server-side run >60s later": forcibly age updated_at AND
    # bump source_created_at as the service would have done on a prior run.
    # Then push a new assignment title and re-run.
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    target.updated_at = past
    # Simulate the service's "refresh source_created_at on each server write":
    # this must have happened last run, so the baseline has moved forward.
    target.source_created_at = past
    db_session.commit()

    assignment.title = "New server-pushed title"
    db_session.commit()
    upsert_task_from_assignment(db_session, assignment)

    reloaded = db_session.query(Task).filter(Task.id == target_id).first()
    # The server-side update must have gone through (not misread as user-edit).
    assert reloaded.title == "New server-pushed title"


def test_upsert_skips_update_when_user_edited_task(db_session, tasksync_env):
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)

    tasks = upsert_task_from_assignment(db_session, assignment)
    target = tasks[0]
    target_id = target.id

    # Simulate a real user edit well after created_at + source_created_at.
    edited_title = "My personalised task title"
    target.title = edited_title
    target.updated_at = datetime.now(timezone.utc) + timedelta(days=1)
    db_session.commit()

    # Teacher pushes a title change; must NOT overwrite the edited row.
    assignment.title = "Teacher-updated title"
    db_session.commit()

    upsert_task_from_assignment(db_session, assignment)
    reloaded = db_session.query(Task).filter(Task.id == target_id).first()

    assert reloaded.title == edited_title
    # Non-edited sibling still updated.
    other = [t for t in tasks if t.id != target_id][0]
    db_session.refresh(other)
    assert other.title == "Teacher-updated title"


def test_upsert_skips_task_marked_user_deleted(db_session, tasksync_env):
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)

    tasks = upsert_task_from_assignment(db_session, assignment)
    target = tasks[0]
    target_id = target.id
    original_title = target.title

    target.source_status = "user_deleted"
    target.archived_at = datetime.now(timezone.utc)
    db_session.commit()

    # Re-run with a changed title — the user_deleted row must not resurrect.
    assignment.title = "Totally different title"
    db_session.commit()
    upsert_task_from_assignment(db_session, assignment)

    reloaded = db_session.query(Task).filter(Task.id == target_id).first()
    assert reloaded.source_status == "user_deleted"
    assert reloaded.title == original_title


def test_upsert_preserves_user_completion_on_update(db_session, tasksync_env):
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)

    tasks = upsert_task_from_assignment(db_session, assignment)
    target = tasks[0]
    completed_ts = datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc)
    target.is_completed = True
    target.completed_at = completed_ts
    db_session.commit()

    assignment.due_date = datetime(2026, 5, 20, 15, 0, tzinfo=timezone.utc)
    db_session.commit()
    upsert_task_from_assignment(db_session, assignment)

    db_session.refresh(target)
    assert target.is_completed is True
    assert _naive(target.completed_at) == _naive(completed_ts)


def test_handle_assignment_deleted_soft_cancels(db_session, tasksync_env):
    from app.services.task_sync_service import (
        handle_assignment_deleted,
        upsert_task_from_assignment,
    )

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)
    tasks = upsert_task_from_assignment(db_session, assignment)
    assert len(tasks) == 2

    count = handle_assignment_deleted(db_session, assignment.id)

    assert count == 2
    for t in tasks:
        db_session.refresh(t)
        assert t.source_status == "source_deleted"
        assert t.archived_at is not None


def test_handle_assignment_submitted_marks_complete(db_session, tasksync_env):
    from app.services.task_sync_service import (
        handle_assignment_submitted,
        upsert_task_from_assignment,
    )

    env = tasksync_env
    assignment = _make_assignment(db_session, env["course"].id)
    upsert_task_from_assignment(db_session, assignment)

    submitted_at = datetime(2026, 5, 9, 11, 30, tzinfo=timezone.utc)
    task = handle_assignment_submitted(
        db_session, assignment.id, env["child_user1"].id, submitted_at
    )

    assert task is not None
    assert task.is_completed is True
    assert _naive(task.completed_at) == _naive(submitted_at)
    assert task.source_status == "source_submitted"


# ──────────────────────────────────────────────────────────────────────────
# 2. Email-digest upserts
# ──────────────────────────────────────────────────────────────────────────

def test_digest_item_low_confidence_dropped(db_session, tasksync_env):
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_digest_item

    env = tasksync_env
    item = _digest_item(
        "Permission slip due Friday",
        datetime(2026, 5, 1, 12, 0, tzinfo=ZoneInfo("America/Toronto")),
        confidence=0.4,
    )
    result = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )
    assert result is None
    # No email_digest Task should exist for this specific parent/child pair.
    count = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child_user1"].id)
        .count()
    )
    assert count == 0


def test_digest_item_tentative_confidence(db_session, tasksync_env):
    from app.services.task_sync_service import upsert_task_from_digest_item

    env = tasksync_env
    item = _digest_item(
        "Pizza Day order form",
        datetime(2026, 5, 1, 12, 0, tzinfo=ZoneInfo("America/Toronto")),
        confidence=0.7,
    )
    task = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )
    assert task is not None
    assert task.source_status == "tentative"
    assert task.source_confidence == pytest.approx(0.7)
    assert task.assigned_to_user_id == env["child_user1"].id


def test_digest_item_high_confidence_active(db_session, tasksync_env):
    from app.services.task_sync_service import upsert_task_from_digest_item

    env = tasksync_env
    item = _digest_item(
        "Field trip permission slip",
        datetime(2026, 5, 3, 12, 0, tzinfo=ZoneInfo("America/Toronto")),
        confidence=0.9,
    )
    task = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )
    assert task is not None
    assert task.source_status == "active"
    assert task.source_confidence == pytest.approx(0.9)
    assert task.source_message_id == "<m1>"


def test_digest_item_same_ref_second_run_idempotent(db_session, tasksync_env):
    from app.models.task import Task
    from app.services.task_sync_service import upsert_task_from_digest_item

    env = tasksync_env
    item = _digest_item(
        "Book report due",
        datetime(2026, 5, 12, 12, 0, tzinfo=ZoneInfo("America/Toronto")),
        confidence=0.85,
    )

    first = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )
    second = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )

    assert first is not None and second is not None
    assert first.id == second.id
    total = (
        db_session.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == env["child_user1"].id)
        .count()
    )
    assert total == 1


def test_digest_item_upgraded_to_assignment(db_session, tasksync_env):
    from app.services.task_sync_service import (
        upsert_task_from_assignment,
        upsert_task_from_digest_item,
    )

    env = tasksync_env
    due = datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("America/Toronto"))
    item = _digest_item("Math project report", due, confidence=0.9)
    digest_task = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )
    assert digest_task is not None

    # Teacher later posts the matching assignment (same normalized title,
    # due ± 1 day). Child1's digest task should be upgraded; child2 gets a
    # fresh assignment-source Task.
    assignment = _make_assignment(
        db_session,
        env["course"].id,
        title="Math project report",
        description="See Google Classroom",
        due_date=due + timedelta(hours=6),
    )
    tasks = upsert_task_from_assignment(db_session, assignment)

    by_assignee = {t.assigned_to_user_id: t for t in tasks}
    upgraded = by_assignee[env["child_user1"].id]
    assert upgraded.id == digest_task.id
    assert upgraded.source == "assignment"
    assert upgraded.source_ref == str(assignment.id)
    assert upgraded.source_status == "upgraded"

    fresh = by_assignee[env["child_user2"].id]
    assert fresh.id != digest_task.id
    assert fresh.source_status == "active"


# ──────────────────────────────────────────────────────────────────────────
# 3. source_ref + timezone
# ──────────────────────────────────────────────────────────────────────────

def test_source_ref_normalizes_titles():
    from app.services.task_sync_service import _digest_source_ref, _normalize_title

    due = datetime(2026, 5, 1, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
    ref1 = _digest_source_ref("  Permission   Slip\tDue  ", due, "America/Toronto")
    ref2 = _digest_source_ref("permission slip due", due, "America/Toronto")
    ref3 = _digest_source_ref("PERMISSION SLIP DUE", due, "America/Toronto")
    assert ref1 == ref2 == ref3

    ref_other = _digest_source_ref("Different event", due, "America/Toronto")
    assert ref_other != ref1

    assert _normalize_title("  HELLO  WORLD  ") == "hello world"


def test_source_ref_uses_integration_timezone():
    from app.services.task_sync_service import _digest_source_ref

    toronto = ZoneInfo("America/Toronto")
    # 23:30 on May 5 in Toronto is already next-day UTC.
    local_dt = datetime(2026, 5, 5, 23, 30, tzinfo=toronto)

    ref_tz = _digest_source_ref("Permission slip", local_dt, "America/Toronto")
    ref_utc = _digest_source_ref("Permission slip", local_dt, "UTC")
    assert ref_tz != ref_utc

    # Two different local times on the same local day collide.
    earlier_same_day = datetime(2026, 5, 5, 9, 0, tzinfo=toronto)
    ref_earlier = _digest_source_ref("Permission slip", earlier_same_day, "America/Toronto")
    assert ref_tz == ref_earlier


# ──────────────────────────────────────────────────────────────────────────
# 3a. Batch orchestrator — eager loading + summary classification
# ──────────────────────────────────────────────────────────────────────────

def test_sync_upcoming_eager_loads_course_and_teacher(db_session, tasksync_env):
    """#3948 regression: the orchestrator query must eager-load
    ``Assignment.course`` and ``course.teacher`` so the per-assignment call
    to ``_assignment_creator_user_id`` does not fire lazy SELECTs.
    """
    from sqlalchemy import event

    from app.models.assignment import Assignment
    from app.services import task_sync_service
    from app.services.task_sync_service import sync_all_upcoming_assignments

    env = tasksync_env
    now = datetime.now(timezone.utc)
    # Create several in-window assignments.
    for i in range(3):
        _make_assignment(
            db_session,
            env["course"].id,
            title=f"Eager quiz {i}",
            due_date=now + timedelta(days=i + 1),
        )

    # Seed the initial run so the next pass hits the update path only.
    sync_all_upcoming_assignments(db_session)

    # Count SELECTs issued against the ``assignments`` or ``courses`` or
    # ``teachers`` tables during ``_assignment_creator_user_id`` access. If
    # eager-loading is in place, the creator-id helper must not trigger any.
    creator_access_queries: list[str] = []
    inside_creator_call = {"flag": False}

    engine = db_session.get_bind()

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if inside_creator_call["flag"]:
            stmt = statement or ""
            low = stmt.lower()
            if (
                "from assignments" in low
                or "from courses" in low
                or "from teachers" in low
            ):
                creator_access_queries.append(stmt)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    original_helper = task_sync_service._assignment_creator_user_id

    def traced_helper(assignment):
        inside_creator_call["flag"] = True
        try:
            return original_helper(assignment)
        finally:
            inside_creator_call["flag"] = False

    try:
        task_sync_service._assignment_creator_user_id = traced_helper
        summary = sync_all_upcoming_assignments(db_session)
    finally:
        task_sync_service._assignment_creator_user_id = original_helper
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert summary["scanned"] >= 3
    # Zero lazy SELECTs against assignment/course/teacher during the
    # per-assignment creator-id access.
    assert creator_access_queries == [], (
        f"expected no lazy loads during _assignment_creator_user_id, "
        f"got {len(creator_access_queries)}: {creator_access_queries[:3]}"
    )


def test_sync_summary_distinguishes_upgraded_from_created(db_session, tasksync_env):
    """#3950 regression: a digest Task upgraded to an Assignment during the
    orchestrator run must be counted as ``upgraded``, not ``created``.
    """
    from app.models.task import Task
    from app.services.task_sync_service import (
        sync_all_upcoming_assignments,
        upsert_task_from_digest_item,
    )

    env = tasksync_env
    # Only one child gets a pre-existing digest Task.
    due = datetime.now(timezone.utc) + timedelta(days=3)
    item = _digest_item("Upgrade target task uniq 3950", due, confidence=0.9)
    digest_task = upsert_task_from_digest_item(
        db_session, env["parent_user"], env["child_user1"].id, item
    )
    assert digest_task is not None
    digest_task_id = digest_task.id

    # Take a pre-run summary snapshot so we can isolate our delta from any
    # state left behind by earlier tests in this session-scoped DB.
    before = sync_all_upcoming_assignments(db_session)

    # Teacher posts the matching assignment (normalized-title equal, due ±1d).
    _make_assignment(
        db_session,
        env["course"].id,
        title="Upgrade target task uniq 3950",
        description="See classroom",
        due_date=due + timedelta(hours=4),
    )

    after = sync_all_upcoming_assignments(db_session)

    # Our one new assignment produces exactly: 1 upgrade (child1) + 1 create
    # (child2). Everything else pre-existed and should be steady-state updates.
    assert after["upgraded"] - before["upgraded"] == 1, (before, after)
    assert after["created"] - before["created"] == 1, (before, after)
    # The summary dict must carry the ``upgraded`` key.
    assert "upgraded" in after

    # Direct verification: the specific digest Task row was upgraded.
    upgraded = db_session.query(Task).filter(Task.id == digest_task_id).first()
    assert upgraded is not None
    assert upgraded.source == "assignment"
    assert upgraded.source_status == "upgraded"


def test_sync_summary_created_when_no_prior_task(db_session, tasksync_env):
    """Baseline: with no pre-existing digest Task, every enrolled student
    gets a freshly-created assignment-source Task — zero ``upgraded``
    *attributable to this assignment*.
    """
    from app.services.task_sync_service import sync_all_upcoming_assignments

    env = tasksync_env

    # Pre-run snapshot so we can compute a clean delta against session-scoped
    # DB state left by earlier tests.
    before = sync_all_upcoming_assignments(db_session)

    due = datetime.now(timezone.utc) + timedelta(days=2)
    _make_assignment(
        db_session,
        env["course"].id,
        title="Fresh assignment no digest 3950",
        due_date=due,
    )

    after = sync_all_upcoming_assignments(db_session)

    # 2 enrolled students → 2 fresh Tasks created by THIS assignment.
    assert after["created"] - before["created"] == 2, (before, after)
    # No digest Task matched this unique title — no new upgrades.
    assert after["upgraded"] - before["upgraded"] == 0, (before, after)


# ──────────────────────────────────────────────────────────────────────────
# 4. Multi-child sanity check
# ──────────────────────────────────────────────────────────────────────────

def test_multi_child_assignment_creates_one_task_per_child(db_session, tasksync_env):
    from app.core.security import get_password_hash
    from app.models.course import student_courses
    from app.models.student import Student
    from app.models.task import Task
    from app.models.user import User, UserRole
    from app.services.task_sync_service import upsert_task_from_assignment

    env = tasksync_env
    hashed = get_password_hash("Password123!")
    suffix = f"_m3_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    child_user3 = User(
        email=f"ts3_child3{suffix}@example.com",
        full_name="TaskSync Child 3",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add(child_user3)
    db_session.commit()
    student3 = Student(user_id=child_user3.id, grade_level=8)
    db_session.add(student3)
    db_session.commit()
    db_session.execute(
        student_courses.insert().values(student_id=student3.id, course_id=env["course"].id)
    )
    db_session.commit()

    assignment = _make_assignment(db_session, env["course"].id)
    tasks = upsert_task_from_assignment(db_session, assignment)

    assert len(tasks) == 3
    assignees = {t.assigned_to_user_id for t in tasks}
    assert assignees == {
        env["child_user1"].id,
        env["child_user2"].id,
        child_user3.id,
    }
    for uid in assignees:
        count = (
            db_session.query(Task)
            .filter(Task.source == "assignment")
            .filter(Task.source_ref == str(assignment.id))
            .filter(Task.assigned_to_user_id == uid)
            .count()
        )
        assert count == 1
