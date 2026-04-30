"""Tests for CB-CMCP-001 M3-D 3D-2 (#4659) — XP eligibility for completed
assigned artifacts.

Covers
------
- STUDENT completes assigned QUIZ artifact → +10 XP awarded.
- STUDENT completes assigned STUDY_GUIDE → +5 XP awarded.
- STUDENT completes assigned WORKSHEET → +8 XP awarded.
- STUDENT completes assigned SAMPLE_TEST → +20 XP awarded.
- STUDENT completes assigned ASSIGNMENT → +15 XP awarded.
- STUDENT completes a SELF_STUDY artifact (no Task with
  ``source='cmcp_artifact'``) → 0 XP (gate-fail on task_source).
- Already-claimed XP for the same (artifact, student) pair → 0 XP
  (lifetime-dedup idempotency).
- Artifact in non-APPROVED state → 0 XP (defence-in-depth).
- PARENT_COMPANION artifact → 0 XP (parent-facing, not a student task).
- Unknown ``guide_type`` → 0 XP (fail-safe).
- Missing artifact → 0 XP, no exception.
- ``xp_enabled = False`` global flag → 0 XP.
- Task PATCH endpoint integration: a STUDENT toggling a CMCP-sourced
  Task to completed invokes the XP hook exactly once.

All XP service calls are exercised against the real test DB but the
module-level XP hook is patched in the integration test so we can
assert call count + arguments (mock contract from #4659).
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── User + course + artifact + enrollment helpers ────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcpxp_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPXp {role.value}",
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


@pytest.fixture()
def student_user(db_session):
    from app.models.student import Student
    from app.models.user import UserRole

    user = _make_user(db_session, UserRole.STUDENT)
    student = Student(user_id=user.id, grade_level=5)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return user


def _make_course(db_session, teacher_user):
    from app.models.course import Course

    course = Course(
        name=f"CMCP XP Course {uuid4().hex[:6]}",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


def _enroll_student(db_session, student_user, course):
    from app.models.course import student_courses
    from app.models.student import Student

    student = (
        db_session.query(Student).filter(Student.user_id == student_user.id).first()
    )
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
    guide_type: str = "quiz",
    title: str | None = None,
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title or f"XP test artifact {uuid4().hex[:6]}",
        content="Body content for the artifact.",
        guide_type=guide_type,
        state=state,
        requested_persona="student" if course_id else "parent",
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


def _seed_cmcp_task(
    db_session,
    *,
    creator_id: int,
    assignee_id: int,
    artifact_id: int | None,
    course_id: int | None,
    source: str = "cmcp_artifact",
):
    """Create a Task row mirroring 3D-1's fan-out output."""
    from app.models.task import Task

    task = Task(
        created_by_user_id=creator_id,
        assigned_to_user_id=assignee_id,
        title=f"CMCP XP task {uuid4().hex[:6]}",
        description="task body",
        course_id=course_id,
        study_guide_id=artifact_id,
        source=source,
        source_ref=str(artifact_id) if artifact_id is not None else None,
        source_status="active",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def _xp_total(db_session, student_user_id: int) -> int:
    """Return the XpSummary total_xp for the student (0 if no row)."""
    from app.models.xp import XpSummary

    summary = (
        db_session.query(XpSummary)
        .filter(XpSummary.student_id == student_user_id)
        .first()
    )
    return int(summary.total_xp or 0) if summary else 0


# ── Unit tests on the dispatcher ─────────────────────────────────────


def test_award_xp_for_completed_quiz_grants_10_xp(
    db_session, teacher_user, student_user
):
    """STUDENT completes assigned QUIZ → +10 XP."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    assert awarded == 10
    assert _xp_total(db_session, student_user.id) == 10


@pytest.mark.parametrize(
    "guide_type,expected_xp",
    [
        ("study_guide", 5),
        ("quiz", 10),
        ("worksheet", 8),
        ("sample_test", 20),
        ("assignment", 15),
    ],
)
def test_award_xp_table_per_content_type(
    db_session, teacher_user, student_user, guide_type, expected_xp
):
    """Per-content-type XP table: study_guide=5, quiz=10, worksheet=8,
    sample_test=20, assignment=15.
    """
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type=guide_type,
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    assert awarded == expected_xp


def test_self_study_artifact_awards_zero_xp(
    db_session, teacher_user, student_user
):
    """SELF_STUDY artifact (no Task with source='cmcp_artifact') → 0 XP.

    The eligibility gate is the ``task_source`` argument: a
    parent/student-self-initiated artifact has no Task created by 3D-1
    fan-out. Even if the caller mis-supplies ``task_source=None``
    (legacy / non-CMCP Task), the guard returns 0.
    """
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=None,
        state=ArtifactState.SELF_STUDY,
        guide_type="quiz",
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source=None,
        db=db_session,
    )

    assert awarded == 0
    assert _xp_total(db_session, student_user.id) == 0


def test_already_claimed_xp_is_idempotent(
    db_session, teacher_user, student_user
):
    """Already-claimed XP for same (artifact, student) → 0 XP on second call."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )

    first = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )
    second = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    assert first == 10
    assert second == 0, "Same artifact + student must not double-award"
    # Total stays at the first award's value.
    assert _xp_total(db_session, student_user.id) == 10


def test_non_approved_state_awards_zero_xp(
    db_session, teacher_user, student_user
):
    """Artifact state != APPROVED → 0 XP (defence-in-depth)."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.PENDING_REVIEW,
        guide_type="quiz",
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    assert awarded == 0


def test_parent_companion_awards_zero_xp(
    db_session, teacher_user, student_user
):
    """PARENT_COMPANION content type → 0 XP (parent-facing, not student task)."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="parent_companion",
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    assert awarded == 0


def test_unknown_guide_type_awards_zero_xp(
    db_session, teacher_user, student_user
):
    """Unknown ``guide_type`` (e.g. legacy 'flashcards') → 0 XP."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="flashcards",
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    assert awarded == 0


def test_non_cmcp_task_source_awards_zero_xp(
    db_session, teacher_user, student_user
):
    """``task_source='assignment'`` (LMS) → 0 XP — not a 3D-1 emitted Task."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="assignment",
        db=db_session,
    )

    assert awarded == 0


def test_missing_artifact_returns_zero_no_exception(db_session, student_user):
    """Non-existent artifact id → 0 XP, no raised exception."""
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    awarded = award_xp_for_completed_artifact(
        artifact_id=999_999,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )
    assert awarded == 0


def test_xp_disabled_flag_returns_zero(
    db_session, teacher_user, student_user
):
    """``settings.xp_enabled = False`` → 0 XP, no ledger row written."""
    from app.core.config import settings
    from app.models.xp import XpLedger
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )

    original = settings.xp_enabled
    try:
        settings.xp_enabled = False
        awarded = award_xp_for_completed_artifact(
            artifact_id=artifact.id,
            student_user_id=student_user.id,
            task_source="cmcp_artifact",
            db=db_session,
        )
    finally:
        settings.xp_enabled = original

    assert awarded == 0
    rows = (
        db_session.query(XpLedger)
        .filter(XpLedger.student_id == student_user.id)
        .filter(XpLedger.context_id == f"cmcp_artifact_{artifact.id}")
        .all()
    )
    assert rows == []


def test_xp_ledger_row_shape(db_session, teacher_user, student_user):
    """Ledger row shape: action_type=cmcp_artifact_completed, context_id keyed
    on artifact id, reason references content_type.
    """
    from app.models.xp import XpLedger
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        XP_ACTION_CMCP_ARTIFACT_COMPLETED,
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="sample_test",
    )

    award_xp_for_completed_artifact(
        artifact_id=artifact.id,
        student_user_id=student_user.id,
        task_source="cmcp_artifact",
        db=db_session,
    )

    row = (
        db_session.query(XpLedger)
        .filter(XpLedger.student_id == student_user.id)
        .filter(XpLedger.context_id == f"cmcp_artifact_{artifact.id}")
        .one()
    )
    assert row.action_type == XP_ACTION_CMCP_ARTIFACT_COMPLETED
    assert row.xp_awarded == 20
    assert row.context_id == f"cmcp_artifact_{artifact.id}"
    assert "sample_test" in (row.reason or "")
    assert str(artifact.id) in (row.reason or "")


# ── Tasks PATCH integration ──────────────────────────────────────────


def test_task_patch_complete_invokes_xp_hook_once(
    client, db_session, teacher_user, student_user
):
    """A STUDENT completing a CMCP-sourced Task fires the XP hook exactly once."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )
    task = _seed_cmcp_task(
        db_session,
        creator_id=teacher_user.id,
        assignee_id=student_user.id,
        artifact_id=artifact.id,
        course_id=course.id,
    )

    headers = _auth(client, student_user.email)
    with patch(
        "app.services.cmcp.xp_eligibility.award_xp_for_completed_artifact",
        return_value=10,
    ) as mock_award:
        resp = client.patch(
            f"/api/tasks/{task.id}",
            headers=headers,
            json={"is_completed": True},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_completed"] is True
    assert mock_award.call_count == 1
    _, kwargs = mock_award.call_args
    assert kwargs["artifact_id"] == artifact.id
    assert kwargs["student_user_id"] == student_user.id
    assert kwargs["task_source"] == "cmcp_artifact"


def test_task_patch_complete_skips_xp_for_non_cmcp_source(
    client, db_session, teacher_user, student_user
):
    """A non-CMCP Task (source='assignment') does NOT invoke the XP hook."""
    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    task = _seed_cmcp_task(
        db_session,
        creator_id=teacher_user.id,
        assignee_id=student_user.id,
        artifact_id=None,  # non-CMCP Task does not link to an artifact
        course_id=course.id,
        source="assignment",
    )

    headers = _auth(client, student_user.email)
    with patch(
        "app.services.cmcp.xp_eligibility.award_xp_for_completed_artifact",
    ) as mock_award:
        resp = client.patch(
            f"/api/tasks/{task.id}",
            headers=headers,
            json={"is_completed": True},
        )

    assert resp.status_code == 200, resp.text
    assert mock_award.call_count == 0


def test_task_patch_complete_xp_failure_does_not_break_endpoint(
    client, db_session, teacher_user, student_user
):
    """Best-effort: an XP hook exception must not break the Task PATCH."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )
    task = _seed_cmcp_task(
        db_session,
        creator_id=teacher_user.id,
        assignee_id=student_user.id,
        artifact_id=artifact.id,
        course_id=course.id,
    )

    headers = _auth(client, student_user.email)
    with patch(
        "app.services.cmcp.xp_eligibility.award_xp_for_completed_artifact",
        side_effect=RuntimeError("XP service exploded"),
    ):
        resp = client.patch(
            f"/api/tasks/{task.id}",
            headers=headers,
            json={"is_completed": True},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_completed"] is True


# ── Telemetry shape (#4703) ─────────────────────────────────────────


def test_award_xp_logs_structured_event_on_award(
    db_session, teacher_user, student_user, caplog
):
    """``cmcp.xp.awarded`` INFO log must include structured ``extra``
    fields so log-aggregation can pivot on it (#4703).
    """
    import logging

    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.xp_eligibility import (
        award_xp_for_completed_artifact,
    )

    course = _make_course(db_session, teacher_user)
    _enroll_student(db_session, student_user, course)
    artifact = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course.id,
        state=ArtifactState.APPROVED,
        guide_type="quiz",
    )

    with caplog.at_level(
        logging.INFO, logger="app.services.cmcp.xp_eligibility"
    ):
        awarded = award_xp_for_completed_artifact(
            artifact_id=artifact.id,
            student_user_id=student_user.id,
            task_source="cmcp_artifact",
            db=db_session,
        )

    assert awarded == 10
    awarded_records = [
        r
        for r in caplog.records
        if r.name == "app.services.cmcp.xp_eligibility"
        and getattr(r, "event", None) == "cmcp.xp.awarded"
    ]
    assert len(awarded_records) == 1
    rec = awarded_records[0]
    assert rec.artifact_id == artifact.id
    assert rec.student_user_id == student_user.id
    assert rec.content_type == "quiz"
    assert rec.xp_awarded == 10
