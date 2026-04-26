"""Tests for CB-TASKSYNC-001 I4 — scheduled task sync job (#3916).

Covers:
  * Full end-to-end: rolling-window filtering, per-student fan-out, null due skip.
  * Feature flag gating — job is a no-op when ``task_sync_enabled`` is OFF.
  * Error isolation — service exceptions are swallowed (do not bubble).
  * Scheduler registration at ``hour=6, minute=45`` UTC.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tasksync_env(db_session):
    """Build: teacher + 3 students enrolled in 1 course, parent linked to them."""
    from app.core.security import get_password_hash
    from app.models.course import Course, student_courses
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher
    from app.models.user import User, UserRole

    suffix = f"_ts4_{id(db_session)}_{datetime.now(timezone.utc).timestamp():.6f}"
    hashed = get_password_hash("Password123!")

    teacher_user = User(
        email=f"ts4_teacher{suffix}@example.com",
        full_name="TaskSync Job Teacher",
        role=UserRole.TEACHER,
        hashed_password=hashed,
    )
    parent_user = User(
        email=f"ts4_parent{suffix}@example.com",
        full_name="TaskSync Job Parent",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    child1 = User(
        email=f"ts4_child1{suffix}@example.com",
        full_name="Child One",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    child2 = User(
        email=f"ts4_child2{suffix}@example.com",
        full_name="Child Two",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    child3 = User(
        email=f"ts4_child3{suffix}@example.com",
        full_name="Child Three",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add_all([teacher_user, parent_user, child1, child2, child3])
    db_session.commit()

    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.commit()

    s1 = Student(user_id=child1.id, grade_level=8)
    s2 = Student(user_id=child2.id, grade_level=8)
    s3 = Student(user_id=child3.id, grade_level=8)
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    for s in (s1, s2, s3):
        db_session.execute(
            parent_students.insert().values(parent_id=parent_user.id, student_id=s.id)
        )
    db_session.commit()

    course = Course(
        name=f"TS4 Math{suffix}",
        teacher_id=teacher.id,
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    for s in (s1, s2, s3):
        db_session.execute(
            student_courses.insert().values(student_id=s.id, course_id=course.id)
        )
    db_session.commit()

    return {
        "teacher_user": teacher_user,
        "parent_user": parent_user,
        "child_users": [child1, child2, child3],
        "students": [s1, s2, s3],
        "course": course,
    }


def _set_flag(db_session, enabled: bool):
    """Upsert the ``task_sync_enabled`` feature flag to the given value."""
    from app.models.feature_flag import FeatureFlag

    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "task_sync_enabled")
        .first()
    )
    if flag is None:
        flag = FeatureFlag(
            key="task_sync_enabled",
            name="Task Sync",
            description="Auto-create Tasks from due-date signals.",
            enabled=enabled,
        )
        db_session.add(flag)
    else:
        flag.enabled = enabled
    db_session.commit()


def _make_assignment(db_session, course_id, title, due_date):
    from app.models.assignment import Assignment

    a = Assignment(
        title=title,
        description=f"{title} description",
        course_id=course_id,
        due_date=due_date,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


# ──────────────────────────────────────────────────────────────────────────
# 1. Full-job end-to-end
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_assignments_to_tasks_full_job(db_session, tasksync_env, monkeypatch):
    """With flag ON: 3 in-window assignments → 9 Tasks (3 students × 3 assignments).
    Out-of-window and NULL-due assignments yield 0 Tasks."""
    from app.jobs.task_sync_job import sync_assignments_to_tasks
    from app.models.task import Task

    _set_flag(db_session, True)
    # CI defense (#4254): the job's `is_feature_enabled("task_sync_enabled")`
    # opens its own SessionLocal() to read the DB-backed flag. Under
    # pytest-xdist `--dist loadfile` on CI the cross-session read of a
    # just-committed flag value has been observed to come back stale even
    # though local runs always see True, leading to `task_sync.skipped |
    # flag=off` and the job returning early. Patch the job's flag check to
    # eliminate the race — flag-OFF coverage stays in
    # `test_feature_flag_off_skips_job` below.
    monkeypatch.setattr(
        "app.jobs.task_sync_job.is_feature_enabled", lambda *_a, **_kw: True
    )

    env = tasksync_env
    now = datetime.now(timezone.utc)

    # 3 in-window assignments (within +30 days).
    in_window = [
        _make_assignment(db_session, env["course"].id, "Chapter 1 quiz", now + timedelta(days=1)),
        _make_assignment(db_session, env["course"].id, "Chapter 2 quiz", now + timedelta(days=7)),
        _make_assignment(db_session, env["course"].id, "Chapter 3 quiz", now + timedelta(days=21)),
    ]
    # 1 out-of-window (far future).
    out_of_window = _make_assignment(
        db_session, env["course"].id, "Far-future quiz", now + timedelta(days=90)
    )
    # 1 with NULL due — skipped by the rolling-window query.
    null_due = _make_assignment(db_session, env["course"].id, "No-due quiz", None)

    await sync_assignments_to_tasks()

    # In-window → one Task per (assignment, student) pair = 3 × 3 = 9.
    # Scope count by course_id because SQLite recycles auto-increment ids when
    # an Assignment is deleted earlier in the session-scoped test DB — a stale
    # ``Task(source='assignment', source_ref='N')`` from an unrelated test
    # can then alias onto this test's ``Assignment(id=N)`` and inflate the
    # count. Filtering on course_id removes the cross-test collision (#4059).
    course_id = env["course"].id
    for assignment in in_window:
        count = (
            db_session.query(Task)
            .filter(Task.source == "assignment", Task.source_ref == str(assignment.id))
            .filter(Task.course_id == course_id)
            .count()
        )
        assert count == 3, f"expected 3 Tasks for {assignment.title}, got {count}"

    # Out-of-window → 0 Tasks (scoped to this course for the same reason).
    oow_count = (
        db_session.query(Task)
        .filter(Task.source == "assignment", Task.source_ref == str(out_of_window.id))
        .filter(Task.course_id == course_id)
        .count()
    )
    assert oow_count == 0

    # NULL-due → 0 Tasks (scoped to this course for the same reason).
    null_count = (
        db_session.query(Task)
        .filter(Task.source == "assignment", Task.source_ref == str(null_due.id))
        .filter(Task.course_id == course_id)
        .count()
    )
    assert null_count == 0

    # Grand total for this course's in-window assignments = 9.
    total = (
        db_session.query(Task)
        .filter(Task.source == "assignment")
        .filter(Task.course_id == env["course"].id)
        .count()
    )
    assert total == 9


# ──────────────────────────────────────────────────────────────────────────
# 2. Feature-flag gating
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_flag_off_skips_job(db_session, tasksync_env, caplog):
    """With flag OFF: no Tasks are created and the skip line is logged."""
    from app.jobs.task_sync_job import sync_assignments_to_tasks
    from app.models.task import Task

    _set_flag(db_session, False)

    env = tasksync_env
    now = datetime.now(timezone.utc)
    _make_assignment(db_session, env["course"].id, "Quiz while flag off", now + timedelta(days=2))

    with caplog.at_level(logging.INFO, logger="app.jobs.task_sync_job"):
        await sync_assignments_to_tasks()

    # Scope by this test's course — other tests using the same session-scoped
    # DB may have left Tasks around.
    count = (
        db_session.query(Task)
        .filter(Task.source == "assignment")
        .filter(Task.course_id == env["course"].id)
        .count()
    )
    assert count == 0
    assert any("task_sync.skipped | flag=off" in rec.getMessage() for rec in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# 3. Exception isolation
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_handles_service_exception(
    db_session, tasksync_env, caplog, monkeypatch
):
    """If the service raises, the job swallows the exception and logs it."""
    from app.jobs import task_sync_job

    _set_flag(db_session, True)
    # CI defense (#4254): force flag-ON inside the job so the patched
    # `sync_all_upcoming_assignments` actually fires and the test can
    # observe the `task_sync.failed` log line.
    monkeypatch.setattr(
        "app.jobs.task_sync_job.is_feature_enabled", lambda *_a, **_kw: True
    )

    with patch.object(
        task_sync_job,
        "sync_all_upcoming_assignments",
        side_effect=RuntimeError("boom"),
    ):
        with caplog.at_level(logging.ERROR, logger="app.jobs.task_sync_job"):
            # Must NOT raise.
            await task_sync_job.sync_assignments_to_tasks()

    exc_rec = next(
        (
            rec
            for rec in caplog.records
            if "task_sync.failed | source=assignment" in rec.getMessage()
        ),
        None,
    )
    assert exc_rec is not None
    # Prove logger.exception was used (not just logger.error) — the traceback
    # is the load-bearing piece of the failure signal.
    assert exc_rec.exc_info is not None


# ──────────────────────────────────────────────────────────────────────────
# 4. Scheduler registration — verify cron at 06:45 UTC
# ──────────────────────────────────────────────────────────────────────────

def test_job_registered_at_0645_utc_in_main():
    """Regression guard: ``main.py`` startup wiring MUST register
    ``task_sync_assignments`` at ``CronTrigger(hour=6, minute=45)``.

    We can't run ``startup_event()`` here because it does heavy seeding +
    DB work, and the conftest ``app`` fixture deliberately clears
    ``on_startup`` handlers. Instead we contract-check the literal cron
    registration in ``main.py`` — if someone changes ``hour=7`` or renames
    the job id, this test fails immediately.
    """
    import re
    from pathlib import Path

    main_py = Path(__file__).resolve().parents[1] / "main.py"
    source = main_py.read_text(encoding="utf-8")

    # Contract: CronTrigger(hour=6, minute=45) block that schedules our job
    # must exist and assign id="task_sync_assignments".
    pattern = re.compile(
        r"scheduler\.add_job\(\s*"
        r"sync_assignments_to_tasks\s*,\s*"
        r"CronTrigger\(\s*hour\s*=\s*6\s*,\s*minute\s*=\s*45\s*\)\s*,\s*"
        r'id\s*=\s*"task_sync_assignments"',
        re.MULTILINE,
    )
    assert pattern.search(source), (
        "main.py must register sync_assignments_to_tasks at "
        "CronTrigger(hour=6, minute=45) with id='task_sync_assignments'"
    )
