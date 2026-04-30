"""Tests for CB-CMCP-001 M3-D 3D-1 (#4652) — Tasks emit on approve.

Covers
------
- ``emit_tasks_for_approved_artifact``: APPROVED + course_id + N enrolled
  students → N Task rows (one per student) with the expected
  ``source='cmcp_artifact'`` / ``source_ref=<artifact_id>`` /
  ``assigned_to_user_id=<student>`` shape.
- APPROVED + no course_id (SELF_STUDY-derived) → 0 Tasks emitted.
- PENDING_REVIEW state → 0 Tasks emitted (defence-in-depth).
- Course with zero enrolled students → 0 Tasks emitted.
- Re-running the dispatcher for the same artifact is idempotent —
  no duplicate Tasks; existing rows updated in place.
- Sticky ``user_deleted``: a Task previously deleted by the student
  is NOT resurrected on re-approve.
- Approve endpoint integration: ``POST /api/cmcp/review/{id}/approve``
  invokes the task dispatcher exactly once after the state transition,
  and approve still returns 200 even when the task dispatcher raises.

All Claude/OpenAI/CB-TASKSYNC external calls are mocked (none required
for this stripe — the dispatcher only writes ``tasks`` rows directly).
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixture ──────────────────────────────────────────────────────


@pytest.fixture()
def cmcp_flag_on(db_session):
    """Force ``cmcp.enabled`` ON for the test, OFF after."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "cmcp.enabled")
        .first()
    )
    assert flag is not None, "cmcp.enabled flag must be seeded"
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


# ── User + course + artifact + enrollment helpers ────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcptask_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPTask {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher_user(db_session):
    from app.models.teacher import Teacher
    from app.models.user import UserRole

    user = _make_user(db_session, UserRole.TEACHER)
    teacher = Teacher(user_id=user.id, full_name=user.full_name)
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return user


def _make_course(db_session, teacher_user):
    from app.models.course import Course

    course = Course(
        name=f"CMCP Task Course {uuid4().hex[:6]}",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


def _make_student(db_session, *, grade_level: int = 5):
    """Create a student User + Student record. Returns (user, student)."""
    from app.models.student import Student
    from app.models.user import UserRole

    user = _make_user(db_session, UserRole.STUDENT)
    student = Student(user_id=user.id, grade_level=grade_level)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return user, student


def _enroll_student(db_session, student, course):
    from app.models.course import student_courses

    db_session.execute(
        student_courses.insert().values(
            student_id=student.id, course_id=course.id
        )
    )
    db_session.commit()


def _seed_artifact(
    db_session,
    *,
    user_id: int,
    course_id: int | None,
    state: str,
    title: str | None = None,
    content: str = "Some prompt body for the task.",
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title or f"Tasks emit test {uuid4().hex[:6]}",
        content=content,
        guide_type="quiz",
        state=state,
        requested_persona="teacher",
        se_codes=["B2.1"],
        voice_module_hash="b" * 64,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ── Dispatcher unit tests ─────────────────────────────────────────────


def test_emit_tasks_one_per_enrolled_student(db_session, teacher_user):
    """APPROVED + course_id + 3 enrolled students → 3 Task rows (one each)."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    student_users = []
    for _ in range(3):
        s_user, s_rec = _make_student(db_session)
        _enroll_student(db_session, s_rec, course)
        student_users.append(s_user)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    emitted = emit_tasks_for_approved_artifact(artifact.id, db_session)
    assert emitted == 3

    rows = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .all()
    )
    assert len(rows) == 3
    assignees = sorted(r.assigned_to_user_id for r in rows)
    assert assignees == sorted(u.id for u in student_users)
    for r in rows:
        assert r.title == artifact.title
        assert r.course_id == course.id
        assert r.study_guide_id == artifact.id
        assert r.source_status == "active"
        assert r.is_completed is False or r.is_completed is None


def test_emit_tasks_skipped_when_no_course_id(db_session, teacher_user):
    """APPROVED + no course_id (SELF_STUDY-derived) → 0 Tasks emitted."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=None,
        state=ArtifactState.APPROVED,
    )

    emitted = emit_tasks_for_approved_artifact(artifact.id, db_session)
    assert emitted == 0

    rows = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .all()
    )
    assert rows == []


def test_emit_tasks_skipped_when_state_not_approved(db_session, teacher_user):
    """PENDING_REVIEW state → 0 Tasks emitted (defence-in-depth)."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    s_user, s_rec = _make_student(db_session)
    _enroll_student(db_session, s_rec, course)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.PENDING_REVIEW,
    )

    emitted = emit_tasks_for_approved_artifact(artifact.id, db_session)
    assert emitted == 0

    rows = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .all()
    )
    assert rows == []


def test_emit_tasks_skipped_when_course_has_no_students(
    db_session, teacher_user
):
    """APPROVED + course_id but zero enrolled students → 0 Tasks emitted."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    emitted = emit_tasks_for_approved_artifact(artifact.id, db_session)
    assert emitted == 0
    # Scope to this artifact's source_ref so other tests' Tasks don't
    # confuse the count when ``db_session`` persists rows across tests.
    assert (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .count()
        == 0
    )


def test_emit_tasks_missing_artifact_returns_zero(db_session):
    """Non-existent artifact id → 0 Tasks emitted, no exception."""
    from app.services.cmcp.task_dispatcher import (
        emit_tasks_for_approved_artifact,
    )

    emitted = emit_tasks_for_approved_artifact(999_999, db_session)
    assert emitted == 0


def test_emit_tasks_idempotent_on_redispatch(db_session, teacher_user):
    """Re-running the dispatcher does NOT create duplicate Task rows."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    s_user, s_rec = _make_student(db_session)
    _enroll_student(db_session, s_rec, course)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    emit_tasks_for_approved_artifact(artifact.id, db_session)
    emit_tasks_for_approved_artifact(artifact.id, db_session)

    rows = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .all()
    )
    assert len(rows) == 1, (
        f"Expected 1 Task after two dispatch calls (idempotent upsert); "
        f"got {len(rows)}"
    )


def test_emit_tasks_sticky_user_deleted(db_session, teacher_user):
    """A Task the student deleted (source_status='user_deleted') is NOT resurrected."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    s_user, s_rec = _make_student(db_session)
    _enroll_student(db_session, s_rec, course)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    # First emit: creates the Task.
    emit_tasks_for_approved_artifact(artifact.id, db_session)
    task = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .first()
    )
    assert task is not None
    original_id = task.id

    # Student "deletes" the Task — sticky lifecycle marker.
    task.source_status = "user_deleted"
    db_session.commit()

    # Second emit: must NOT resurrect / overwrite the user_deleted row.
    emit_tasks_for_approved_artifact(artifact.id, db_session)

    rows = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .all()
    )
    assert len(rows) == 1
    assert rows[0].id == original_id
    assert rows[0].source_status == "user_deleted"


def test_emit_tasks_preserves_user_edited_title(db_session, teacher_user):
    """A user-renamed Task must NOT be overwritten on re-approve (CB-TASKSYNC §6.13.1)."""
    from datetime import datetime, timedelta, timezone

    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    s_user, s_rec = _make_student(db_session)
    _enroll_student(db_session, s_rec, course)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        title="Original artifact title",
        content="Original artifact content body.",
    )

    # First emit creates the Task.
    emit_tasks_for_approved_artifact(artifact.id, db_session)
    task = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .first()
    )
    assert task is not None

    # Simulate a student edit that occurred AFTER the auto-create grace
    # window (60s): bump updated_at well past created_at + grace AND
    # past source_created_at + grace, so ``_is_user_edited`` returns True.
    user_edit_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    task.title = "Student renamed this task"
    task.updated_at = user_edit_time
    db_session.commit()

    # Update the artifact and re-emit — student rename must survive.
    artifact.title = "Teacher renamed artifact"
    artifact.content = "Teacher updated artifact content."
    db_session.commit()
    emit_tasks_for_approved_artifact(artifact.id, db_session)

    db_session.refresh(task)
    assert task.title == "Student renamed this task", (
        "User-edited title was overwritten by re-approve — violates CB-TASKSYNC §6.13.1"
    )


def test_emit_tasks_creator_is_artifact_owner_not_student(db_session, teacher_user):
    """Tasks must be attributed to the teacher (artifact owner), never to the student.

    Guards against the previous ``creator_id or student_user_id`` fallback
    that could self-attribute a Task to the student if ``artifact.user_id``
    was ever NULL.
    """
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import (
        TASK_SOURCE_CMCP_ARTIFACT,
        emit_tasks_for_approved_artifact,
    )

    course = _make_course(db_session, teacher_user)
    s_user, s_rec = _make_student(db_session)
    _enroll_student(db_session, s_rec, course)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    emitted = emit_tasks_for_approved_artifact(artifact.id, db_session)
    assert emitted == 1

    task = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .one()
    )
    assert task.created_by_user_id == teacher_user.id
    assert task.created_by_user_id != s_user.id, (
        "Task self-attributed to student — violates ops attribution invariant"
    )


# ── Approve endpoint integration ──────────────────────────────────────


def test_approve_endpoint_invokes_task_dispatcher_once(
    client, db_session, teacher_user, cmcp_flag_on
):
    """POST /approve fires the task dispatcher exactly once after state transition."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course(db_session, teacher_user)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    with patch(
        "app.services.cmcp.task_dispatcher.emit_tasks_for_approved_artifact"
    ) as mock_emit:
        mock_emit.return_value = 0
        resp = client.post(
            f"/api/cmcp/review/{artifact.id}/approve", headers=headers
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == ArtifactState.APPROVED
    # Task dispatcher invoked exactly once with the approved artifact id.
    assert mock_emit.call_count == 1
    args, _kwargs = mock_emit.call_args
    assert args[0] == artifact.id


def test_approve_endpoint_succeeds_even_when_task_dispatcher_raises(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Approve still returns 200 if the task dispatcher raises (best-effort)."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course(db_session, teacher_user)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    with patch(
        "app.services.cmcp.task_dispatcher.emit_tasks_for_approved_artifact",
        side_effect=RuntimeError("task dispatcher exploded"),
    ):
        resp = client.post(
            f"/api/cmcp/review/{artifact.id}/approve", headers=headers
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == ArtifactState.APPROVED


def test_approve_endpoint_emits_tasks_for_enrolled_students(
    client, db_session, teacher_user, cmcp_flag_on
):
    """End-to-end: approve endpoint creates Task rows for each enrolled student."""
    from app.models.task import Task
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import TASK_SOURCE_CMCP_ARTIFACT

    course = _make_course(db_session, teacher_user)
    student_users = []
    for _ in range(2):
        s_user, s_rec = _make_student(db_session)
        _enroll_student(db_session, s_rec, course)
        student_users.append(s_user)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.post(
        f"/api/cmcp/review/{artifact.id}/approve", headers=headers
    )
    assert resp.status_code == 200, resp.text

    rows = (
        db_session.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == str(artifact.id))
        .all()
    )
    assert len(rows) == 2
    assignees = sorted(r.assigned_to_user_id for r in rows)
    assert assignees == sorted(u.id for u in student_users)


# ── Telemetry shape (#4703) ─────────────────────────────────────────


def test_emit_tasks_logs_structured_event_on_dispatch(
    db_session, teacher_user, caplog
):
    """Per-artifact dispatch summary must include ``cmcp.tasks.dispatch_completed``
    in ``extra={"event": ...}`` so log-aggregation can pivot on it (#4703).
    """
    import logging

    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.task_dispatcher import emit_tasks_for_approved_artifact

    course = _make_course(db_session, teacher_user)
    s_user, s_rec = _make_student(db_session)
    _enroll_student(db_session, s_rec, course)

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
    )

    with caplog.at_level(
        logging.INFO, logger="app.services.cmcp.task_dispatcher"
    ):
        emit_tasks_for_approved_artifact(artifact.id, db_session)

    events = [
        getattr(r, "event", None)
        for r in caplog.records
        if r.name == "app.services.cmcp.task_dispatcher"
    ]
    assert "cmcp.tasks.emitted" in events
    assert "cmcp.tasks.dispatch_completed" in events
