"""Tests for CB-CMCP-001 M3α prequel (#4575) — persist M1 generation
results to ``study_guides`` on completion.

Covers
------
- Sync route INSERT: PARENT requestor → ``state=SELF_STUDY``.
- Sync route INSERT: TEACHER + ``course_id`` → ``state=PENDING_REVIEW``.
- Sync route INSERT: TEACHER without ``course_id`` → ``state=SELF_STUDY``.
- All M0/M1 columns populated (se_codes, voice_module_hash, ceg_version-
  ish, requested_persona, board_id best-effort).
- ``GenerationPreview.id`` matches the inserted row.
- Stream route INSERT on ``done`` event with parent-companion stash in
  ``parent_summary``.
- ``GET /api/cmcp/artifacts/{id}/parent-companion``:
  - 200 for parent-persona artifact (creator + linked parent).
  - 404 for unknown id.
  - 404 for unrelated parent (visibility deny collapses to 404).
  - 422 for non-parent-persona artifact.

All Claude/OpenAI calls are mocked.
"""
from __future__ import annotations

import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch
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


# ── User fixtures ──────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcppersist_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPPersist {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


@pytest.fixture()
def student_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


# ── CEG seed ───────────────────────────────────────────────────────────


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
    """Seed a Grade-7 CEG slice with two SEs (mirrors test_cmcp_generate_route)."""
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    suffix = uuid4().hex[:6].upper()
    subject_code = f"P{suffix}"
    strand_code = "B"
    version_slug = f"test-persist-{uuid4().hex[:6]}"

    subject = CEGSubject(code=subject_code, name="Mathematics")
    db_session.add(subject)
    db_session.flush()

    strand = CEGStrand(
        subject_id=subject.id, code=strand_code, name="Number Sense"
    )
    db_session.add(strand)
    db_session.flush()

    version = CurriculumVersion(
        subject_id=subject.id,
        grade=7,
        version=version_slug,
        change_severity=None,
        notes="test seed",
    )
    db_session.add(version)
    db_session.flush()

    oe = CEGExpectation(
        ministry_code="B2",
        cb_code=f"CB-G7-{subject_code}-B2",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_OVERALL,
        description="Demonstrate understanding of fractions, decimals, percents.",
        curriculum_version_id=version.id,
    )
    db_session.add(oe)
    db_session.flush()

    se1 = CEGExpectation(
        ministry_code="B2.1",
        cb_code=f"CB-G7-{subject_code}-B2-SE1",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        parent_oe_id=oe.id,
        description="Add and subtract fractions with unlike denominators.",
        curriculum_version_id=version.id,
    )
    se2 = CEGExpectation(
        ministry_code="B2.2",
        cb_code=f"CB-G7-{subject_code}-B2-SE2",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        parent_oe_id=oe.id,
        description="Multiply and divide decimal numbers to thousandths.",
        curriculum_version_id=version.id,
    )
    db_session.add_all([se1, se2])
    db_session.commit()

    expectation_ids = [oe.id, se1.id, se2.id]
    yield {
        "subject_code": subject_code,
        "strand_code": strand_code,
        "subject": subject,
        "strand": strand,
        "version": version,
    }

    from app.models.curriculum import CEGExpectation as _E

    db_session.query(_E).filter(_E.id.in_(expectation_ids)).delete(
        synchronize_session=False
    )
    db_session.query(CurriculumVersion).filter(
        CurriculumVersion.id == version.id
    ).delete(synchronize_session=False)
    db_session.query(CEGStrand).filter(
        CEGStrand.id == strand.id
    ).delete(synchronize_session=False)
    db_session.query(CEGSubject).filter(
        CEGSubject.id == subject.id
    ).delete(synchronize_session=False)
    db_session.commit()


def _payload(seeded, **overrides):
    body = {
        "grade": 7,
        "subject_code": seeded["subject_code"],
        "strand_code": seeded["strand_code"],
        "content_type": "QUIZ",
        "difficulty": "GRADE_LEVEL",
    }
    body.update(overrides)
    return body


# ─────────────────────────────────────────────────────────────────────
# Sync route persistence
# ─────────────────────────────────────────────────────────────────────


def test_sync_persist_parent_requestor_self_study(
    client, db_session, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """PARENT requestor → row inserted with state=SELF_STUDY."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    artifact_id = data["id"]
    assert isinstance(artifact_id, int)

    artifact = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.id == artifact_id)
        .first()
    )
    assert artifact is not None
    assert artifact.user_id == parent_user.id
    assert artifact.state == ArtifactState.SELF_STUDY
    assert artifact.requested_persona == "parent"
    # All M0/M1 columns populated.
    assert artifact.se_codes == ["B2.1", "B2.2"]
    assert artifact.voice_module_hash is not None
    assert len(artifact.voice_module_hash) == 64
    assert artifact.guide_type == "quiz"
    # Course-context was None — envelope summary may still capture
    # fallback metadata, but the row should commit cleanly either way.


def test_sync_persist_teacher_with_course_pending_review(
    client, db_session, teacher_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """TEACHER + course_id → row inserted with state=PENDING_REVIEW."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    # Seed a course owned by the teacher so the resolver doesn't 404
    # the envelope. ``Course`` requires a non-null ``name``.
    course = Course(
        name=f"CMCP Persist Test Course {uuid4().hex[:6]}",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    try:
        headers = _auth(client, teacher_user.email)
        body = _payload(seeded_cmcp_curriculum, course_id=course.id)
        resp = client.post("/api/cmcp/generate", json=body, headers=headers)
        assert resp.status_code == 200, resp.text

        data = resp.json()
        artifact_id = data["id"]
        assert isinstance(artifact_id, int)

        artifact = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == artifact_id)
            .first()
        )
        assert artifact is not None
        assert artifact.state == ArtifactState.PENDING_REVIEW
        assert artifact.requested_persona == "teacher"
        assert artifact.course_id == course.id
        assert artifact.user_id == teacher_user.id
    finally:
        db_session.query(StudyGuide).filter(
            StudyGuide.user_id == teacher_user.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_sync_persist_teacher_without_course_self_study(
    client, db_session, teacher_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """TEACHER WITHOUT course_id → falls into SELF_STUDY (D3=C tail)."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    headers = _auth(client, teacher_user.email)
    body = _payload(seeded_cmcp_curriculum)  # no course_id
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text

    artifact_id = resp.json()["id"]
    artifact = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.id == artifact_id)
        .first()
    )
    assert artifact is not None
    assert artifact.state == ArtifactState.SELF_STUDY


def test_sync_persist_response_id_matches_row(
    client, db_session, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """``GenerationPreview.id`` is the actual ``study_guides.id`` of the row."""
    from app.models.study_guide import StudyGuide

    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)
    resp = client.post("/api/cmcp/generate", json=body, headers=headers)
    assert resp.status_code == 200

    artifact_id = resp.json()["id"]
    rows = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.user_id == parent_user.id)
        .all()
    )
    # Mutation-test guard: if id were faked, this assertion catches it.
    assert any(r.id == artifact_id for r in rows)


# ─────────────────────────────────────────────────────────────────────
# Stream route persistence
# ─────────────────────────────────────────────────────────────────────


def _make_fake_stream(chunks: list[str]):
    async def fake(*_args, **_kwargs) -> AsyncIterator[dict]:
        for c in chunks:
            yield {"event": "chunk", "data": c}
        yield {
            "event": "done",
            "data": {"is_truncated": False, "full_content": "".join(chunks)},
        }

    return fake


def test_stream_persist_inserts_row_on_done(
    client, db_session, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Stream route inserts a row on ``done`` event."""
    from app.models.study_guide import StudyGuide

    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="STUDY_GUIDE")

    fake = _make_fake_stream(["Hello ", "world", "!"])
    with patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    ):
        # Ensure parent-companion auto-emit is a no-op (parent persona,
        # so the auto-emit gate is closed anyway). Also patch the
        # validation pipeline to keep the test focused on persistence.
        with patch(
            "app.api.routes.cmcp_generate_stream._run_alignment_pipeline",
            new_callable=AsyncMock,
            return_value=(None, False, None, None),
        ):
            resp = client.post(
                "/api/cmcp/generate/stream", json=body, headers=headers
            )

    assert resp.status_code == 200
    # Find the persisted row.
    rows = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.user_id == parent_user.id)
        .all()
    )
    assert len(rows) >= 1
    artifact = rows[-1]
    assert artifact.content == "Hello world!"
    assert artifact.requested_persona == "parent"
    assert artifact.guide_type == "study_guide"


def test_stream_persist_stores_parent_companion_in_parent_summary(
    client,
    db_session,
    student_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """Stream auto-emit on student persona stashes parent_companion JSON."""
    from app.models.study_guide import StudyGuide

    headers = _auth(client, student_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="STUDY_GUIDE")

    fake_companion = {
        "se_explanation": "First sentence. Second sentence.",
        "talking_points": [
            "Talking point one.",
            "Talking point two.",
            "Talking point three.",
        ],
        "coaching_prompts": [
            "Prompt one?",
            "Prompt two?",
        ],
        "how_to_help_without_giving_answer": (
            "Ask questions. Encourage process. Avoid revealing solutions."
        ),
        "bridge_deep_link_payload": {
            "child_id": None,
            "week_summary": None,
            "deep_link_target": None,
        },
    }

    fake = _make_fake_stream(["Hello ", "world", "!"])
    # Patch the async classmethod to return a ParentCompanionContent-shaped
    # mock with model_dump returning fake_companion.
    fake_obj = type("FakeCompanion", (), {"model_dump": lambda self: fake_companion})()
    with patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    ), patch(
        "app.api.routes.cmcp_generate_stream.ParentCompanionService.generate_5_section",
        new_callable=AsyncMock,
        return_value=fake_obj,
    ), patch(
        "app.api.routes.cmcp_generate_stream._run_alignment_pipeline",
        new_callable=AsyncMock,
        return_value=(None, False, None, None),
    ):
        resp = client.post(
            "/api/cmcp/generate/stream", json=body, headers=headers
        )

    assert resp.status_code == 200
    rows = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.user_id == student_user.id)
        .all()
    )
    assert len(rows) >= 1
    artifact = rows[-1]
    assert artifact.requested_persona == "student"
    assert artifact.parent_summary is not None
    parsed = json.loads(artifact.parent_summary)
    assert parsed["se_explanation"] == fake_companion["se_explanation"]
    assert parsed["talking_points"] == fake_companion["talking_points"]


# ─────────────────────────────────────────────────────────────────────
# GET /api/cmcp/artifacts/{id}/parent-companion
# ─────────────────────────────────────────────────────────────────────


def _seed_parent_persona_artifact(
    db_session,
    user_id: int,
    *,
    parent_summary: str | None = None,
    course_id: int | None = None,
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title="Test parent-persona artifact",
        content="Some prompt text.",
        guide_type="study_guide",
        state=ArtifactState.SELF_STUDY,
        se_codes=["B2.1"],
        voice_module_hash="a" * 64,
        requested_persona="parent",
        parent_summary=parent_summary,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


def _seed_non_parent_artifact(db_session, user_id: int):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    artifact = StudyGuide(
        user_id=user_id,
        title="Student artifact",
        content="Student-facing content.",
        guide_type="study_guide",
        state=ArtifactState.SELF_STUDY,
        requested_persona="student",
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


def test_get_parent_companion_200_for_parent_persona_creator(
    client, db_session, parent_user, cmcp_flag_on
):
    """Creator of a parent-persona artifact gets 200 + the content."""
    fake_payload = {
        "se_explanation": "First. Second.",
        "talking_points": ["a", "b", "c"],
        "coaching_prompts": ["q1?", "q2?"],
        "how_to_help_without_giving_answer": "Ask, don't tell.",
        "bridge_deep_link_payload": {
            "child_id": None,
            "week_summary": None,
            "deep_link_target": None,
        },
    }
    artifact = _seed_parent_persona_artifact(
        db_session,
        parent_user.id,
        parent_summary=json.dumps(fake_payload),
    )
    try:
        headers = _auth(client, parent_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/parent-companion",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["artifact_id"] == artifact.id
        assert body["content"]["se_explanation"] == "First. Second."
        assert body["content"]["talking_points"] == ["a", "b", "c"]
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_get_parent_companion_200_returns_stub_when_summary_none(
    client, db_session, parent_user, cmcp_flag_on
):
    """Parent-persona artifact w/o stored JSON → returns minimal stub."""
    artifact = _seed_parent_persona_artifact(
        db_session, parent_user.id, parent_summary=None
    )
    try:
        headers = _auth(client, parent_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/parent-companion",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Stub should validate as ParentCompanionContent (>=3 talking points).
        assert len(body["content"]["talking_points"]) >= 3
        assert body["content"]["se_explanation"]
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_get_parent_companion_404_unknown_id(
    client, parent_user, cmcp_flag_on
):
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/cmcp/artifacts/9999999/parent-companion", headers=headers
    )
    assert resp.status_code == 404


def test_get_parent_companion_404_for_unrelated_parent(
    client, db_session, parent_user, cmcp_flag_on
):
    """Unrelated parent (not creator + not linked) → 404 (no existence leak)."""
    from app.models.user import UserRole

    # Owner of the artifact.
    owner = _make_user(db_session, UserRole.PARENT)
    artifact = _seed_parent_persona_artifact(db_session, owner.id)
    try:
        # Caller is the original ``parent_user`` — unrelated to ``owner``.
        headers = _auth(client, parent_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/parent-companion",
            headers=headers,
        )
        assert resp.status_code == 404
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_get_parent_companion_422_for_non_parent_persona(
    client, db_session, student_user, cmcp_flag_on
):
    """Caller has visibility but artifact's persona != 'parent' → 422."""
    artifact = _seed_non_parent_artifact(db_session, student_user.id)
    try:
        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/parent-companion",
            headers=headers,
        )
        assert resp.status_code == 422
        assert "parent-persona" in resp.json()["detail"].lower()
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


# ─────────────────────────────────────────────────────────────────────
# CB-CMCP-001 M3β follow-up #4694 — GET /api/cmcp/artifacts/{id}/student-view
# (Companion to the LTI launch redirect target.)
# ─────────────────────────────────────────────────────────────────────


def test_get_student_view_200_for_creator_student(
    client, db_session, student_user, cmcp_flag_on
):
    """STUDENT creator of a student-persona artifact → 200 + raw fields."""
    artifact = _seed_non_parent_artifact(db_session, student_user.id)
    try:
        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/student-view",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["artifact_id"] == artifact.id
        assert body["title"] == artifact.title
        assert body["content"] == artifact.content
        assert body["guide_type"] == artifact.guide_type
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_get_student_view_404_for_unknown_id(
    client, student_user, cmcp_flag_on
):
    """Unknown artifact id → 404 (matches parent-companion convention)."""
    headers = _auth(client, student_user.email)
    resp = client.get(
        "/api/cmcp/artifacts/99999999/student-view", headers=headers
    )
    assert resp.status_code == 404


def test_get_student_view_404_for_unrelated_caller(
    client, db_session, student_user, parent_user, cmcp_flag_on
):
    """Unrelated user (no visibility) → 404 (collapsed, no leak)."""
    # Artifact owned by ``student_user``; ``parent_user`` has no
    # parent_students link to ``student_user`` so the visibility check
    # denies. Collapses to 404 to match the parent-companion contract.
    artifact = _seed_non_parent_artifact(db_session, student_user.id)
    try:
        headers = _auth(client, parent_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/student-view",
            headers=headers,
        )
        assert resp.status_code == 404
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_get_student_view_403_when_flag_off(
    client, db_session, student_user
):
    """``cmcp.enabled`` OFF → 403 (kill switch).

    Deliberately does NOT use ``cmcp_flag_on`` so the flag stays in its
    default-OFF state; the route should 403 before hitting any other
    logic.
    """
    artifact = _seed_non_parent_artifact(db_session, student_user.id)
    try:
        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/cmcp/artifacts/{artifact.id}/student-view",
            headers=headers,
        )
        assert resp.status_code == 403
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()
