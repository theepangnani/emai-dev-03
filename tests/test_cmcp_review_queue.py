"""Tests for CB-CMCP-001 M3-A 3A-1 (#4576) — Teacher Review Queue backend.

Covers
------
- ``GET  /api/cmcp/review/queue``       — TEACHER own classes only; ADMIN
  sees everything; non-TEACHER non-ADMIN 403; PENDING_REVIEW filter.
- ``GET  /api/cmcp/review/{id}``        — full artifact + metadata; 404 for
  cross-class teacher (no existence leak).
- ``PATCH /api/cmcp/review/{id}``       — content updated, edit_history grows.
- ``POST /api/cmcp/review/{id}/approve``    — state PENDING_REVIEW → APPROVED;
  reviewer + reviewed_at stamped.
- ``POST /api/cmcp/review/{id}/reject``     — state → REJECTED; reason
  required (Pydantic 422 on missing); rejection_reason persisted.
- ``POST /api/cmcp/review/{id}/regenerate`` — content replaced, state
  stays PENDING_REVIEW, same id; AI/CEG layer mocked through
  ``generate_cmcp_preview_sync`` patch.

All Claude/OpenAI calls are mocked.
"""
from __future__ import annotations

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

    email = f"cmcprev_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPRev {role.value}",
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
def other_teacher_user(db_session):
    from app.models.teacher import Teacher
    from app.models.user import UserRole

    user = _make_user(db_session, UserRole.TEACHER)
    teacher = Teacher(user_id=user.id, full_name=user.full_name)
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return user


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN)


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


def _make_course_owned_by(db_session, user) -> int:
    from app.models.course import Course

    course = Course(
        name=f"CMCP Review Course {uuid4().hex[:6]}",
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


# ── GET /queue ─────────────────────────────────────────────────────────


def test_queue_lists_pending_review_for_teachers_own_courses(
    client, db_session, teacher_user, other_teacher_user, cmcp_flag_on
):
    """TEACHER sees PENDING_REVIEW rows on their own courses; not others'."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    own_course = _make_course_owned_by(db_session, teacher_user)
    other_course = _make_course_owned_by(db_session, other_teacher_user)

    own = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=own_course,
        state=ArtifactState.PENDING_REVIEW,
        title="Own pending",
    )
    foreign = _seed_artifact(
        db_session,
        user_id=other_teacher_user.id,
        course_id=other_course,
        state=ArtifactState.PENDING_REVIEW,
        title="Foreign pending",
    )
    # Approved row on own course should NOT appear (queue filters PENDING_REVIEW).
    approved = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=own_course,
        state=ArtifactState.APPROVED,
        title="Own approved",
    )

    try:
        headers = _auth(client, teacher_user.email)
        resp = client.get("/api/cmcp/review/queue", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {item["id"] for item in body["items"]}
        assert own.id in ids
        assert foreign.id not in ids
        assert approved.id not in ids
        # All returned items must be PENDING_REVIEW.
        assert all(it["state"] == "PENDING_REVIEW" for it in body["items"])
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id.in_([own.id, foreign.id, approved.id])
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(
            Course.id.in_([own_course, other_course])
        ).delete(synchronize_session=False)
        db_session.commit()


def test_queue_admin_sees_everything(
    client, db_session, teacher_user, admin_user, cmcp_flag_on
):
    """ADMIN role sees PENDING_REVIEW rows from any teacher's classes."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, admin_user.email)
        resp = client.get("/api/cmcp/review/queue", headers=headers)
        assert resp.status_code == 200, resp.text
        ids = {item["id"] for item in resp.json()["items"]}
        assert art.id in ids
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_queue_non_teacher_non_admin_403(
    client, parent_user, cmcp_flag_on
):
    """Non-TEACHER, non-ADMIN callers (e.g. PARENT) get 403."""
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/cmcp/review/queue", headers=headers)
    assert resp.status_code == 403


def test_queue_paginates(
    client, db_session, teacher_user, cmcp_flag_on
):
    """page+limit pagination works; total reflects pre-paginated count."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    arts = [
        _seed_artifact(
            db_session,
            user_id=teacher_user.id,
            course_id=course,
            state=ArtifactState.PENDING_REVIEW,
            title=f"page-art-{i}",
        )
        for i in range(5)
    ]
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.get(
            "/api/cmcp/review/queue?page=1&limit=2", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["limit"] == 2
        assert len(body["items"]) <= 2
        # total includes ALL pending items the teacher sees, not just this page.
        assert body["total"] >= 5
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id.in_([a.id for a in arts])
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


# ── GET /{id} ──────────────────────────────────────────────────────────


def test_get_artifact_returns_full_content_and_metadata(
    client, db_session, teacher_user, cmcp_flag_on
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
        content="Body of the artifact.",
        se_codes=["B2.1", "B2.2"],
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.get(f"/api/cmcp/review/{art.id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == art.id
        assert body["content"] == "Body of the artifact."
        assert body["state"] == "PENDING_REVIEW"
        assert body["se_codes"] == ["B2.1", "B2.2"]
        assert body["course_id"] == course
        assert body["edit_history"] == []
        assert body["reviewed_by_user_id"] is None
        assert body["reviewed_at"] is None
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_get_artifact_cross_class_denied_404(
    client, db_session, teacher_user, other_teacher_user, cmcp_flag_on
):
    """TEACHER cannot fetch another teacher's PENDING_REVIEW artifact (404)."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    other_course = _make_course_owned_by(db_session, other_teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=other_teacher_user.id,
        course_id=other_course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.get(f"/api/cmcp/review/{art.id}", headers=headers)
        assert resp.status_code == 404
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == other_course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_get_artifact_unknown_id_404(
    client, teacher_user, cmcp_flag_on
):
    headers = _auth(client, teacher_user.email)
    resp = client.get("/api/cmcp/review/9999999", headers=headers)
    assert resp.status_code == 404


# ── PATCH /{id} ────────────────────────────────────────────────────────


def test_patch_persists_content_and_grows_edit_history(
    client, db_session, teacher_user, cmcp_flag_on
):
    """PATCH updates content and appends a single entry to edit_history."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
        content="Original content.",
    )
    try:
        headers = _auth(client, teacher_user.email)
        # First edit.
        resp = client.patch(
            f"/api/cmcp/review/{art.id}",
            json={"content": "Edited content v1."},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["content"] == "Edited content v1."
        assert len(body["edit_history"]) == 1
        assert body["edit_history"][0]["editor_id"] == teacher_user.id
        assert body["edit_history"][0]["before_snippet"] == "Original content."
        assert body["edit_history"][0]["after_snippet"] == "Edited content v1."

        # Second edit — history grows.
        resp = client.patch(
            f"/api/cmcp/review/{art.id}",
            json={"content": "Edited content v2."},
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["edit_history"]) == 2

        # DB-level sanity check.
        db_session.expire_all()
        row = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == art.id)
            .first()
        )
        assert row.content == "Edited content v2."
        assert isinstance(row.edit_history, list)
        assert len(row.edit_history) == 2
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_patch_terminal_state_409(
    client, db_session, teacher_user, cmcp_flag_on
):
    """PATCH on APPROVED / APPROVED_VERIFIED / ARCHIVED → 409.

    Mutation-test guard: if the state-gate were removed, the PATCH would
    silently succeed and the body would be replaced — this test would
    catch that by asserting 409 (not 200).
    """
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
        content="Published body — must not mutate.",
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.patch(
            f"/api/cmcp/review/{art.id}",
            json={"content": "Sneaky edit attempt."},
            headers=headers,
        )
        assert resp.status_code == 409, resp.text
        # Verify the body was NOT mutated (mutation-test guard).
        db_session.expire_all()
        row = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == art.id)
            .first()
        )
        assert row.content == "Published body — must not mutate."
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_patch_cross_class_denied_404(
    client, db_session, teacher_user, other_teacher_user, cmcp_flag_on
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    other_course = _make_course_owned_by(db_session, other_teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=other_teacher_user.id,
        course_id=other_course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.patch(
            f"/api/cmcp/review/{art.id}",
            json={"content": "Cross-class edit"},
            headers=headers,
        )
        assert resp.status_code == 404
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == other_course).delete(
            synchronize_session=False
        )
        db_session.commit()


# ── POST /{id}/approve ─────────────────────────────────────────────────


def test_approve_transitions_state_and_records_reviewer(
    client, db_session, teacher_user, cmcp_flag_on
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.post(
            f"/api/cmcp/review/{art.id}/approve", headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == ArtifactState.APPROVED
        assert body["reviewed_by_user_id"] == teacher_user.id
        assert body["reviewed_at"] is not None

        # Persisted in DB.
        db_session.expire_all()
        row = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == art.id)
            .first()
        )
        assert row.state == ArtifactState.APPROVED
        assert row.reviewed_by_user_id == teacher_user.id
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_approve_wrong_state_409(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Approving a non-PENDING_REVIEW row 409s.

    Uses ``APPROVED`` as the wrong-state stand-in: ``SELF_STUDY`` would
    404 here (3B-3 / #4585 denies SELF_STUDY at the review-queue
    visibility check, before the state check fires), so we use a state
    that is visible-but-not-mutable to exercise the 409 path.
    """
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.post(
            f"/api/cmcp/review/{art.id}/approve", headers=headers
        )
        assert resp.status_code == 409
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


# ── POST /{id}/reject ──────────────────────────────────────────────────


def test_reject_requires_reason(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Missing or empty ``reason`` 422s before reaching the handler."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, teacher_user.email)
        # No body at all.
        resp = client.post(
            f"/api/cmcp/review/{art.id}/reject", headers=headers
        )
        assert resp.status_code == 422
        # Empty reason.
        resp = client.post(
            f"/api/cmcp/review/{art.id}/reject",
            json={"reason": ""},
            headers=headers,
        )
        assert resp.status_code == 422
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_reject_records_reason_and_reviewer(
    client, db_session, teacher_user, cmcp_flag_on
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.post(
            f"/api/cmcp/review/{art.id}/reject",
            json={"reason": "Off-topic for the strand."},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == ArtifactState.REJECTED
        assert body["reviewed_by_user_id"] == teacher_user.id
        assert body["rejection_reason"] == "Off-topic for the strand."

        db_session.expire_all()
        row = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == art.id)
            .first()
        )
        assert row.state == ArtifactState.REJECTED
        assert row.rejection_reason == "Off-topic for the strand."
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


# ── POST /{id}/regenerate ──────────────────────────────────────────────


def test_regenerate_replaces_content_keeps_id_and_pending_state(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Regenerate calls the service layer + replaces content; same id; state stays PENDING_REVIEW."""
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

    fake_preview = GenerationPreview(
        id=None,
        prompt="Regenerated prompt content.",
        se_codes_targeted=["B2.1", "B2.2"],
        voice_module_id="voice-module-1",
        voice_module_hash="b" * 64,
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
            data = resp.json()
            # Same id.
            assert data["id"] == art.id
            # Content replaced.
            assert data["content"] == "Regenerated prompt content."
            # State stays PENDING_REVIEW.
            assert data["state"] == ArtifactState.PENDING_REVIEW
            # Voice module hash + SE codes were copied.
            assert data["voice_module_hash"] == "b" * 64
            assert data["se_codes"] == ["B2.1", "B2.2"]
            # Reviewer fields cleared.
            assert data["reviewed_by_user_id"] is None
            assert data["reviewed_at"] is None
            assert data["rejection_reason"] is None

        # DB-level sanity.
        db_session.expire_all()
        row = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == art.id)
            .first()
        )
        assert row is not None
        assert row.content == "Regenerated prompt content."
        assert row.state == ArtifactState.PENDING_REVIEW
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_regenerate_stamps_edit_history(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Regenerate appends an entry to edit_history (audit trail)."""
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
            data = resp.json()
            # Audit entry present.
            assert len(data["edit_history"]) == 1
            entry = data["edit_history"][0]
            assert entry["editor_id"] == teacher_user.id
            assert entry["before_snippet"] == "Original prompt."
            assert entry["after_snippet"] == "Regenerated prompt content."
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_regenerate_terminal_state_409(
    client, db_session, teacher_user, cmcp_flag_on
):
    """Regenerate on APPROVED → 409 (cannot mutate published artifact)."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _make_course_owned_by(db_session, teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=teacher_user.id,
        course_id=course,
        state=ArtifactState.APPROVED,
    )
    try:
        headers = _auth(client, teacher_user.email)
        body = {
            "request": {
                "grade": 7,
                "subject_code": "MATH",
                "strand_code": "B",
                "content_type": "QUIZ",
                "difficulty": "GRADE_LEVEL",
            }
        }
        resp = client.post(
            f"/api/cmcp/review/{art.id}/regenerate",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 409
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_regenerate_deletes_freshly_inserted_row(
    client, db_session, teacher_user, cmcp_flag_on
):
    """``generate_cmcp_preview_sync`` inserts a new row — regenerate must clean it up."""
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
        id=fresh_id,  # the fresh row's id — regenerate should delete it
        prompt="Regenerated prompt content.",
        se_codes_targeted=["B2.1"],
        voice_module_id="voice-module-1",
        voice_module_hash="c" * 64,
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
            assert resp.status_code == 200

        db_session.expire_all()
        # Original art still there.
        assert (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == art.id)
            .first()
            is not None
        )
        # Stale fresh row was deleted.
        assert (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == fresh_id)
            .first()
            is None
        )
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id.in_([art.id, fresh_id])
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_regenerate_cross_class_denied_404(
    client, db_session, teacher_user, other_teacher_user, cmcp_flag_on
):
    """Cross-class regenerate is denied with 404 (no existence leak)."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    other_course = _make_course_owned_by(db_session, other_teacher_user)
    art = _seed_artifact(
        db_session,
        user_id=other_teacher_user.id,
        course_id=other_course,
        state=ArtifactState.PENDING_REVIEW,
    )
    try:
        headers = _auth(client, teacher_user.email)
        body = {
            "request": {
                "grade": 7,
                "subject_code": "MATH",
                "strand_code": "B",
                "content_type": "QUIZ",
                "difficulty": "GRADE_LEVEL",
            }
        }
        resp = client.post(
            f"/api/cmcp/review/{art.id}/regenerate",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 404
    finally:
        from app.models.course import Course

        db_session.query(StudyGuide).filter(
            StudyGuide.id == art.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == other_course).delete(
            synchronize_session=False
        )
        db_session.commit()
