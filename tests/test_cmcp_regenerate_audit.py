"""Tests for CB-CMCP-001 M3α IMP (#4634) — regenerate audit-log integrity.

When the regenerate endpoint runs, ``generate_cmcp_preview_sync`` calls
``persist_cmcp_artifact`` which:
1. INSERTs a fresh ``study_guides`` row,
2. Writes a ``cmcp.artifact.created`` audit row,
3. Commits both.

The regenerate cleanup then deletes the freshly-inserted "phantom" row.
Without a compensating audit entry the ``cmcp.artifact.created`` row is
left pointing at a deleted ``resource_id`` — a Bill 194 audit-trail
integrity break.

The fix writes a compensating ``cmcp.artifact.deleted_during_regenerate``
audit entry after the phantom delete, with ``details.replaces_artifact_id``
set to the original (preserved) artifact id. These tests assert:

- Both audit rows are written on the regenerate path.
- The compensating row's ``resource_id`` matches the phantom id.
- The compensating row's ``details.replaces_artifact_id`` matches the
  original artifact id.
"""
from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixtures ──────────────────────────────────────────────────────


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

    email = f"cmcpregenaud_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPRegenAud {role.value}",
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
        name=f"CMCP Regen Audit Course {uuid4().hex[:6]}",
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
    title: str | None = None,
    content: str = "Some prompt body.",
    requested_persona: str = "teacher",
    se_codes: list[str] | None = None,
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title or f"Test artifact {uuid4().hex[:6]}",
        content=content,
        guide_type="quiz",
        state=state,
        requested_persona=requested_persona,
        se_codes=se_codes or ["B2.1", "B2.2"],
        voice_module_hash="a" * 64,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ── Tests ──────────────────────────────────────────────────────────────


def test_regenerate_writes_compensating_audit_row_for_phantom(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Regenerate path writes BOTH audit rows.

    1. ``cmcp.artifact.created`` for the phantom row (emitted by
       ``persist_cmcp_artifact`` inside ``generate_cmcp_preview_sync``).
    2. ``cmcp.artifact.deleted_during_regenerate`` for the cleanup of
       the phantom (emitted by the regenerate route after the delete).

    The compensating row's ``resource_id`` must match the phantom id,
    and ``details.replaces_artifact_id`` must match the original
    artifact's id (so a Bill 194 reviewer can trace the phantom back
    to the regenerate operation).
    """
    from app.models.audit_log import AuditLog
    from app.models.study_guide import StudyGuide
    from app.schemas.cmcp import GenerationPreview
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
        content="Original prompt.",
    )

    # Simulate the underlying sync route having inserted a fresh row.
    fresh = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
        title="Stale fresh insert",
        content="Fresh content.",
    )
    fresh_id = fresh.id  # capture before the route deletes the row

    fake_preview = GenerationPreview(
        id=fresh_id,
        prompt="Regenerated prompt content.",
        se_codes_targeted=["B2.1"],
        voice_module_id="voice-module-1",
        voice_module_hash="c" * 64,
        persona="teacher",
    )

    # Patch ``persist_cmcp_artifact`` inside generate_cmcp_preview_sync to
    # emit the same ``cmcp.artifact.created`` audit row that production
    # does — without it, the test couldn't observe the "phantom audit
    # row" condition we're guarding against. We do this by writing the
    # row directly via the audit service to mirror the real call site.
    def _emit_phantom_audit_row():
        from app.services.audit_service import log_action

        log_action(
            db_session,
            user_id=teacher_user.id,
            action="cmcp.artifact.created",
            resource_type="study_guide",
            resource_id=fresh_id,
            details={
                "state": "PENDING_REVIEW",
                "persona": "teacher",
                "content_type": "QUIZ",
                "course_id": course,
                "role": "teacher",
            },
        )
        db_session.commit()

    _emit_phantom_audit_row()

    try:
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

        # Phantom row was deleted.
        assert (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == fresh_id)
            .first()
            is None
        )

        # Phantom-creation audit row exists (emitted before the
        # request, simulating ``persist_cmcp_artifact``'s commit).
        created_rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "cmcp.artifact.created",
                AuditLog.resource_id == fresh_id,
                AuditLog.user_id == teacher_user.id,
            )
            .all()
        )
        assert len(created_rows) == 1, (
            "expected the phantom-creation audit row to persist; without "
            "it we wouldn't have an audit-integrity issue to compensate"
        )

        # Compensating row exists, points at the phantom, and carries
        # ``replaces_artifact_id`` for the surviving original.
        compensating_rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action
                == "cmcp.artifact.deleted_during_regenerate",
                AuditLog.user_id == teacher_user.id,
            )
            .all()
        )
        assert len(compensating_rows) == 1, (
            "regenerate must write exactly one compensating audit row "
            "for the phantom delete"
        )
        comp = compensating_rows[0]
        assert comp.resource_id == fresh_id
        assert comp.resource_type == "study_guide"
        details = json.loads(comp.details)
        assert details["replaces_artifact_id"] == art.id
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id.in_([art.id, fresh_id])
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_regenerate_no_phantom_no_compensating_audit_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """If no phantom row was inserted (preview.id is None or matches the
    target), the compensating audit row must NOT be written — the
    compensation is for the phantom delete, nothing else.

    Regression guard: a future refactor that always emits the
    compensating row would corrupt the audit trail with phantom-delete
    entries that don't correspond to real deletes.
    """
    from app.models.audit_log import AuditLog
    from app.models.study_guide import StudyGuide
    from app.schemas.cmcp import GenerationPreview
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
        content="Original prompt.",
    )

    # No fresh insert — preview.id is None.
    fake_preview = GenerationPreview(
        id=None,
        prompt="Regenerated prompt content.",
        se_codes_targeted=["B2.1"],
        voice_module_id="voice-module-1",
        voice_module_hash="d" * 64,
        persona="teacher",
    )

    try:
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

        compensating_rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action
                == "cmcp.artifact.deleted_during_regenerate",
                AuditLog.user_id == teacher_user.id,
            )
            .all()
        )
        assert len(compensating_rows) == 0, (
            "no phantom row was deleted — no compensating audit row "
            "should exist"
        )
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()
