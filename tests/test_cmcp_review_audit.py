"""Tests for CB-CMCP-001 M3α follow-up #4631 — Bill 194 audit-log on the
review-queue state transitions.

Covers
------
- ``PATCH /api/cmcp/review/{id}``           writes ``cmcp.review.edited``
  with previous_state, new_state, edit_history_appended.
- ``POST /api/cmcp/review/{id}/approve``    writes ``cmcp.review.approved``
  with previous_state=PENDING_REVIEW, new_state=APPROVED.
- ``POST /api/cmcp/review/{id}/reject``     writes ``cmcp.review.rejected``
  with previous_state=PENDING_REVIEW, new_state=REJECTED, rejection_reason.
- ``POST /api/cmcp/review/{id}/regenerate`` writes ``cmcp.review.regenerated``
  with previous_state, new_state=PENDING_REVIEW, phantom_artifact_id.
- 409 paths (terminal-state guards) write NO audit row — confirms the audit
  call sits AFTER the state mutation, never on the rejection branch.

All Claude / OpenAI calls are mocked via ``generate_cmcp_preview_sync`` patch.
"""
from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixture ───────────────────────────────────────────────────────


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


# ── User + course fixtures ─────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcprevaud_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPRevAud {role.value}",
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


def _make_course_owned_by(db_session, user) -> int:
    from app.models.course import Course

    course = Course(
        name=f"CMCP Audit Course {uuid4().hex[:6]}",
        created_by_user_id=user.id,
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
    content: str = "Original prompt body.",
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=f"Audit artifact {uuid4().hex[:6]}",
        content=content,
        guide_type="quiz",
        state=state,
        requested_persona="teacher",
        se_codes=["B2.1"],
        voice_module_hash="a" * 64,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


def _audit_rows_for(db_session, *, artifact_id: int, action: str):
    from app.models.audit_log import AuditLog

    return (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == action,
            AuditLog.resource_id == artifact_id,
            AuditLog.resource_type == "study_guide",
        )
        .all()
    )


# ── PATCH ──────────────────────────────────────────────────────────────


def test_patch_writes_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Successful PATCH writes a ``cmcp.review.edited`` audit row."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.patch(
        f"/api/cmcp/review/{art.id}",
        json={"content": "New edited body."},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.edited"
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == teacher_user.id
    details = json.loads(row.details)
    assert details["previous_state"] == ArtifactState.PENDING_REVIEW
    # PATCH does not change state — but the audit row still records both
    # for cross-verb symmetry / compliance reporting.
    assert details["new_state"] == ArtifactState.PENDING_REVIEW
    assert details["edit_history_appended"] is True
    assert details["history_len"] == 1


def test_patch_terminal_state_writes_no_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """409 PATCH on APPROVED writes no ``cmcp.review.edited`` audit row.

    Confirms the audit-log call sits AFTER the 409 guard — a denied edit
    must not leave an "edited" trail in the audit table.
    """
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.patch(
        f"/api/cmcp/review/{art.id}",
        json={"content": "New edited body."},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text

    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.edited"
    )
    assert rows == []


# ── APPROVE ────────────────────────────────────────────────────────────


def test_approve_writes_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Successful approve writes a ``cmcp.review.approved`` audit row."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.post(
        f"/api/cmcp/review/{art.id}/approve", headers=headers
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.approved"
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == teacher_user.id
    details = json.loads(row.details)
    assert details["previous_state"] == ArtifactState.PENDING_REVIEW
    assert details["new_state"] == ArtifactState.APPROVED


def test_approve_wrong_state_writes_no_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """409 approve on REJECTED writes no audit row."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.REJECTED,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.post(
        f"/api/cmcp/review/{art.id}/approve", headers=headers
    )
    assert resp.status_code == 409, resp.text

    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.approved"
    )
    assert rows == []


# ── REJECT ─────────────────────────────────────────────────────────────


def test_reject_writes_audit_row_with_reason(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Successful reject writes a ``cmcp.review.rejected`` audit row that
    carries the rejection reason."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.post(
        f"/api/cmcp/review/{art.id}/reject",
        json={"reason": "Off-curriculum — strand mismatch."},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.rejected"
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == teacher_user.id
    details = json.loads(row.details)
    assert details["previous_state"] == ArtifactState.PENDING_REVIEW
    assert details["new_state"] == ArtifactState.REJECTED
    assert details["rejection_reason"] == "Off-curriculum — strand mismatch."


def test_reject_wrong_state_writes_no_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """409 reject on APPROVED writes no audit row."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    headers = _auth(client, teacher_user.email)
    resp = client.post(
        f"/api/cmcp/review/{art.id}/reject",
        json={"reason": "Already shipped."},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text

    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.rejected"
    )
    assert rows == []


# ── REGENERATE ─────────────────────────────────────────────────────────


def test_regenerate_writes_audit_row_from_pending(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Regenerate writes a ``cmcp.review.regenerated`` audit row.

    ``previous_state`` carries the source state (PENDING_REVIEW here),
    ``new_state`` is always PENDING_REVIEW (regenerate contract).
    ``phantom_artifact_id`` is None when the preview helper inserts no
    fresh row (``preview.id is None``).
    """
    from app.schemas.cmcp import GenerationPreview
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    fake_preview = GenerationPreview(
        id=None,
        prompt="Regen body.",
        se_codes_targeted=["B2.1"],
        voice_module_id="voice-module-1",
        voice_module_hash="b" * 64,
        persona="teacher",
    )

    with patch(
        "app.api.routes.cmcp_review.generate_cmcp_preview_sync",
        return_value=fake_preview,
    ):
        headers = _auth(client, teacher_user.email)
        body = {
            "request": {
                "grade": 7,
                "subject_code": "MATH",
                "strand_code": "B",
                "content_type": "QUIZ",
                "difficulty": "GRADE_LEVEL",
                "course_id": course,
            }
        }
        resp = client.post(
            f"/api/cmcp/review/{art.id}/regenerate",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    db_session.expire_all()
    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.regenerated"
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == teacher_user.id
    details = json.loads(row.details)
    assert details["previous_state"] == ArtifactState.PENDING_REVIEW
    assert details["new_state"] == ArtifactState.PENDING_REVIEW
    # Preview returned id=None, so no phantom row was inserted.
    assert details["phantom_artifact_id"] is None


def test_regenerate_writes_audit_row_from_rejected(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Regenerate from REJECTED writes audit with previous_state=REJECTED.

    Regenerate is allowed from PENDING_REVIEW / REJECTED / DRAFT and
    always lands at PENDING_REVIEW; the audit must record both ends of
    that transition.
    """
    from app.schemas.cmcp import GenerationPreview
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.REJECTED,
    )

    fake_preview = GenerationPreview(
        id=None,
        prompt="Regen body.",
        se_codes_targeted=["B2.1"],
        voice_module_id="voice-module-1",
        voice_module_hash="c" * 64,
        persona="teacher",
    )

    with patch(
        "app.api.routes.cmcp_review.generate_cmcp_preview_sync",
        return_value=fake_preview,
    ):
        headers = _auth(client, teacher_user.email)
        body = {
            "request": {
                "grade": 7,
                "subject_code": "MATH",
                "strand_code": "B",
                "content_type": "QUIZ",
                "difficulty": "GRADE_LEVEL",
                "course_id": course,
            }
        }
        resp = client.post(
            f"/api/cmcp/review/{art.id}/regenerate",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    db_session.expire_all()
    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.regenerated"
    )
    assert len(rows) == 1
    details = json.loads(rows[0].details)
    assert details["previous_state"] == ArtifactState.REJECTED
    assert details["new_state"] == ArtifactState.PENDING_REVIEW


def test_regenerate_audit_carries_phantom_artifact_id(
    client, db_session, teacher_user, cmcp_flag_on
):
    """When the preview helper inserts a fresh row, ``phantom_artifact_id``
    on the audit row carries that id so compliance can cross-reference
    the matching ``cmcp.artifact.created`` audit entry.
    """
    from app.models.study_guide import StudyGuide
    from app.schemas.cmcp import GenerationPreview
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )

    # Simulate the freshly-inserted row that ``persist_cmcp_artifact``
    # creates inside ``generate_cmcp_preview_sync`` so the regenerate
    # cleanup path runs + the phantom id is captured on the audit row.
    fresh = StudyGuide(
        user_id=teacher_user.id,
        course_id=course,
        title="Phantom",
        content="Phantom body",
        guide_type="quiz",
        state=ArtifactState.PENDING_REVIEW,
        requested_persona="teacher",
        se_codes=["B2.1"],
        voice_module_hash="d" * 64,
    )
    db_session.add(fresh)
    db_session.commit()
    db_session.refresh(fresh)
    phantom_id = fresh.id

    fake_preview = GenerationPreview(
        id=phantom_id,
        prompt="Regen body.",
        se_codes_targeted=["B2.1"],
        voice_module_id="voice-module-1",
        voice_module_hash="e" * 64,
        persona="teacher",
    )

    with patch(
        "app.api.routes.cmcp_review.generate_cmcp_preview_sync",
        return_value=fake_preview,
    ):
        headers = _auth(client, teacher_user.email)
        body = {
            "request": {
                "grade": 7,
                "subject_code": "MATH",
                "strand_code": "B",
                "content_type": "QUIZ",
                "difficulty": "GRADE_LEVEL",
                "course_id": course,
            }
        }
        resp = client.post(
            f"/api/cmcp/review/{art.id}/regenerate",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    db_session.expire_all()
    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.regenerated"
    )
    assert len(rows) == 1
    details = json.loads(rows[0].details)
    assert details["phantom_artifact_id"] == phantom_id


def test_regenerate_terminal_state_writes_no_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """409 regenerate on APPROVED writes no audit row."""
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )

    headers = _auth(client, teacher_user.email)
    body = {
        "request": {
            "grade": 7,
            "subject_code": "MATH",
            "strand_code": "B",
            "content_type": "QUIZ",
            "difficulty": "GRADE_LEVEL",
            "course_id": course,
        }
    }
    resp = client.post(
        f"/api/cmcp/review/{art.id}/regenerate", json=body, headers=headers
    )
    assert resp.status_code == 409, resp.text

    rows = _audit_rows_for(
        db_session, artifact_id=art.id, action="cmcp.review.regenerated"
    )
    assert rows == []
