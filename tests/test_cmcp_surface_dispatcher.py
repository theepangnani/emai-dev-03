"""Tests for CB-CMCP-001 M3α 3C-1 (#4586) — Surface dispatcher.

Covers
------
- ``dispatch_artifact_to_surfaces`` fans out to all three surfaces
  successfully → returns ``{bridge: ok, dci: ok, digest: ok}`` and
  emits 3 ``cmcp.surface.dispatched`` log lines via 3C-5's helper.
- One surface failing is isolated: the other two still emit ``"ok"``
  and the failed one is marked ``"failed"`` in the returned dict.
- Retry logic: an emitter that fails on its first call but succeeds on
  the second is recorded as ``"ok"`` (recovery path).
- Approve endpoint integration: ``POST /api/cmcp/review/{id}/approve``
  invokes the dispatcher exactly once after the state transition.
- Missing artifact / non-renderable state path: dispatcher returns
  all-``"failed"`` without raising.
- Re-dispatch idempotency: calling the dispatcher twice for the same
  artifact updates the existing audit row (unique constraint upsert).

All Claude/OpenAI calls are mocked (none required for this stripe).
"""
from __future__ import annotations

import logging
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


# ── User + course + artifact helpers ──────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcpdisp_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPDisp {role.value}",
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
        name=f"CMCP Disp Course {uuid4().hex[:6]}",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course.id


def _seed_artifact(
    db_session,
    *,
    user_id: int,
    course_id: int | None,
    state: str,
    title: str | None = None,
    content: str = "Some prompt body.",
    requested_persona: str = "teacher",
    se_codes: list[str] | None = None,
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title or f"Disp test {uuid4().hex[:6]}",
        content=content,
        guide_type="quiz",
        state=state,
        requested_persona=requested_persona,
        se_codes=se_codes or ["B2.1"],
        voice_module_hash="b" * 64,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ── Dispatcher unit tests ─────────────────────────────────────────────


def test_dispatch_all_surfaces_ok(db_session, teacher_user, caplog):
    """All three surfaces succeed → 3 ok + 3 ``cmcp.surface.dispatched`` logs."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    caplog.clear()
    with caplog.at_level(
        logging.INFO, logger="app.services.cmcp.surface_telemetry"
    ):
        outcomes = dispatch_artifact_to_surfaces(art.id, db_session)

    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    dispatched_records = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "cmcp.surface.dispatched"
    ]
    assert len(dispatched_records) == 3
    surfaces = sorted(r.surface for r in dispatched_records)
    assert surfaces == ["bridge", "dci", "digest"]
    for r in dispatched_records:
        assert r.artifact_id == art.id
        assert r.latency_ms_from_approve >= 0


def test_dispatch_one_surface_failure_isolated(
    db_session, teacher_user, caplog
):
    """One emitter raises → other two still ok; failed surface marked failed."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp import surface_dispatcher
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    def _failing_dci(**kwargs):
        raise RuntimeError("dci offline")

    with patch.dict(
        surface_dispatcher._SURFACE_EMITTERS,
        {"dci": _failing_dci},
        clear=False,
    ):
        with caplog.at_level(
            logging.INFO, logger="app.services.cmcp.surface_telemetry"
        ):
            outcomes = dispatch_artifact_to_surfaces(art.id, db_session)

    assert outcomes == {"bridge": "ok", "dci": "failed", "digest": "ok"}

    # Telemetry only fires on success — only 2 dispatched records.
    dispatched_records = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "cmcp.surface.dispatched"
    ]
    surfaces = sorted(r.surface for r in dispatched_records)
    assert surfaces == ["bridge", "digest"]


def test_dispatch_retry_recovery(db_session, teacher_user, caplog):
    """Emitter fails first call, succeeds second → recorded as ok."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp import surface_dispatcher
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    call_state = {"calls": 0}

    def _flaky_bridge(**kwargs):
        call_state["calls"] += 1
        if call_state["calls"] < 2:
            raise RuntimeError("transient bridge failure")
        # Second call: succeed without persisting (the original
        # emitter persists; this stub just succeeds so retry path is
        # exercised in isolation).

    with patch.dict(
        surface_dispatcher._SURFACE_EMITTERS,
        {"bridge": _flaky_bridge},
        clear=False,
    ):
        with caplog.at_level(
            logging.INFO, logger="app.services.cmcp.surface_telemetry"
        ):
            outcomes = dispatch_artifact_to_surfaces(art.id, db_session)

    assert outcomes["bridge"] == "ok"
    assert call_state["calls"] >= 2  # at least one retry happened
    dispatched_records = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "cmcp.surface.dispatched"
    ]
    bridge_records = [r for r in dispatched_records if r.surface == "bridge"]
    assert len(bridge_records) == 1


def test_dispatch_success_after_retry_persists_correct_attempts(
    db_session, teacher_user
):
    """Success-after-retry honesty (#4633).

    When the per-surface emitter succeeds on attempt 2 (transient
    failure recovered), the ``cmcp_surface_dispatches`` row must show
    ``attempts=2``, ``status='ok'``, ``last_error=None``. Without the
    fix, the row writes ``attempts=1`` because the emitters hard-code
    that value and the dispatcher only re-recorded attempts on the
    failure branch — making flaky surfaces look healthy in ops.
    """
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp import surface_dispatcher
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    # Track per-surface call counts. The first call on each surface
    # raises (simulating a transient PG deadlock); the second call
    # falls through to the real emitter so the audit row + retry
    # tuple shape match production.
    real_emitters = dict(surface_dispatcher._SURFACE_EMITTERS)
    call_counts: dict[str, int] = {"bridge": 0, "dci": 0, "digest": 0}

    def make_flaky(surface_name: str):
        real = real_emitters[surface_name]

        def flaky(**kwargs):
            call_counts[surface_name] += 1
            if call_counts[surface_name] < 2:
                raise RuntimeError(f"transient {surface_name} failure")
            return real(**kwargs)

        return flaky

    flaky_emitters = {s: make_flaky(s) for s in ("bridge", "dci", "digest")}

    with patch.dict(
        surface_dispatcher._SURFACE_EMITTERS,
        flaky_emitters,
        clear=False,
    ):
        outcomes = dispatch_artifact_to_surfaces(art.id, db_session)

    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}
    # Every surface needed exactly 2 attempts.
    assert call_counts == {"bridge": 2, "dci": 2, "digest": 2}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    assert len(rows) == 3
    for row in rows:
        assert row.status == "ok", f"surface={row.surface}"
        assert row.attempts == 2, (
            f"surface={row.surface} attempts={row.attempts} "
            "(expected 2 — success-after-retry must record true count)"
        )
        assert row.last_error is None, f"surface={row.surface}"


def test_dispatch_first_attempt_success_records_attempts_one(
    db_session, teacher_user
):
    """First-attempt-success keeps the emitter's ``attempts=1`` write.

    Guards against an over-eager re-record that would write a second
    audit row (or overwrite the emitter's row needlessly) on the
    common happy path. The fix only re-records when ``attempts_used >
    1``.
    """
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    dispatch_artifact_to_surfaces(art.id, db_session)

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    assert len(rows) == 3
    for row in rows:
        assert row.status == "ok"
        assert row.attempts == 1


def test_dispatch_audit_failure_recovers_via_retry(db_session, teacher_user):
    """Audit-write returning None on first call → retried; recovers on 2nd."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp import surface_dispatcher

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    # Track which (artifact_id, surface) tuples have been seen so the
    # mock only flakes the FIRST emit per tuple — subsequent retries
    # for the same tuple succeed via the real implementation.
    real_record = surface_dispatcher._record_dispatch
    seen: set[tuple[int, str]] = set()

    def flaky_record(db, **kwargs):
        key = (kwargs.get("artifact_id"), kwargs.get("surface"))
        if key not in seen:
            seen.add(key)
            return None  # simulates audit-write failure
        return real_record(db, **kwargs)

    # Use ``patch.object`` for consistency with the rest of the file
    # (every other test in this module patches via ``unittest.mock``).
    with patch.object(
        surface_dispatcher, "_record_dispatch", side_effect=flaky_record
    ):
        outcomes = surface_dispatcher.dispatch_artifact_to_surfaces(
            art.id, db_session
        )
    # Every surface recovered via retry → "ok".
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}


def test_dispatch_missing_artifact_returns_all_failed(db_session):
    """No artifact row → dispatcher returns all-failed without raising."""
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    outcomes = dispatch_artifact_to_surfaces(999_999, db_session)
    assert outcomes == {"bridge": "failed", "dci": "failed", "digest": "failed"}


def test_dispatch_non_renderable_state_returns_all_failed(
    db_session, teacher_user
):
    """DRAFT artifact → dispatcher returns all-failed without raising."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.DRAFT,
    )
    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "failed", "dci": "failed", "digest": "failed"}


def test_dispatch_persists_audit_rows(db_session, teacher_user):
    """Each successful surface writes one cmcp_surface_dispatches row."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    dispatch_artifact_to_surfaces(art.id, db_session)

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    assert len(rows) == 3
    surfaces = sorted(r.surface for r in rows)
    assert surfaces == ["bridge", "dci", "digest"]
    assert all(r.status == "ok" for r in rows)


def test_dispatch_fans_out_to_all_linked_parents(db_session):
    """Co-parents (two linked parents) → one audit row per parent per surface."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.models.student import Student, parent_students
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    # Two parents + one student linked to both.
    parent_a = _make_user(db_session, UserRole.PARENT)
    parent_b = _make_user(db_session, UserRole.PARENT)
    student_user = _make_user(db_session, UserRole.STUDENT)
    student = Student(user_id=student_user.id, grade_level=5)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_a.id, student_id=student.id
        )
    )
    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_b.id, student_id=student.id
        )
    )
    db_session.commit()

    art = _seed_artifact(
        db_session,
        user_id=student_user.id,  # artifact owned by the student
        course_id=None,
        state=ArtifactState.APPROVED,
        requested_persona="parent",
    )
    outcomes = dispatch_artifact_to_surfaces(art.id, db_session)
    assert outcomes == {"bridge": "ok", "dci": "ok", "digest": "ok"}

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    # 2 parents × 3 surfaces = 6 audit rows.
    assert len(rows) == 6
    parent_ids_per_surface: dict[str, set[int]] = {}
    for row in rows:
        parent_ids_per_surface.setdefault(row.surface, set()).add(row.parent_id)
    for surface in ("bridge", "dci", "digest"):
        assert parent_ids_per_surface[surface] == {parent_a.id, parent_b.id}, (
            f"surface {surface} missing a co-parent: {parent_ids_per_surface[surface]}"
        )
    # Every row carries the kid_id.
    assert all(r.kid_id == student.id for r in rows)


def test_dispatch_idempotent_on_redispatch(db_session, teacher_user):
    """Re-dispatching the same artifact updates rows in place (no duplicates)."""
    from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.surface_dispatcher import (
        dispatch_artifact_to_surfaces,
    )

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    dispatch_artifact_to_surfaces(art.id, db_session)
    dispatch_artifact_to_surfaces(art.id, db_session)

    rows = (
        db_session.query(CMCPSurfaceDispatch)
        .filter(CMCPSurfaceDispatch.artifact_id == art.id)
        .all()
    )
    # Three surfaces × one (parent_id, kid_id) tuple = 3 rows even
    # after two dispatch calls.
    assert len(rows) == 3


# ── Approve endpoint integration ──────────────────────────────────────


def test_approve_endpoint_invokes_dispatcher_once(
    client, db_session, teacher_user, cmcp_flag_on
):
    """POST /approve fires the dispatcher exactly once after state transition."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    with patch(
        "app.services.cmcp.surface_dispatcher.dispatch_artifact_to_surfaces"
    ) as mock_dispatch:
        mock_dispatch.return_value = {
            "bridge": "ok",
            "dci": "ok",
            "digest": "ok",
        }
        resp = client.post(
            f"/api/cmcp/review/{art.id}/approve", headers=headers
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == ArtifactState.APPROVED
    # Dispatcher invoked exactly once with the approved artifact id.
    assert mock_dispatch.call_count == 1
    args, _kwargs = mock_dispatch.call_args
    assert args[0] == art.id


def test_approve_endpoint_succeeds_even_when_dispatcher_raises(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Approve still returns 200 if dispatcher raises (best-effort guarantee)."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    with patch(
        "app.services.cmcp.surface_dispatcher.dispatch_artifact_to_surfaces",
        side_effect=RuntimeError("dispatcher exploded"),
    ):
        resp = client.post(
            f"/api/cmcp/review/{art.id}/approve", headers=headers
        )

    # Approve still returns 200 — dispatcher failures are ops-only.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == ArtifactState.APPROVED
