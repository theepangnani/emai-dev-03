"""Tests for CB-CMCP-001 M3α 3B-1 (#4577) — D3=C self-study state
plumbing + class-distribution authority + audit log.

Wave 0 (#4596) shipped the SELF_STUDY / PENDING_REVIEW resolution in
``persist_cmcp_artifact._resolve_state``. This stripe layers two
new behaviors on top:

1. **Authority guard** in ``cmcp_generate.py``:
   - PARENT or STUDENT with ``course_id`` set → 403.
   - TEACHER with ``course_id`` they don't own → 403.
   - TEACHER with ``course_id`` they own → 200 + PENDING_REVIEW.
   - PARENT / STUDENT / TEACHER with no ``course_id`` → 200 +
     SELF_STUDY (Wave 0 path, re-asserted here as a regression
     guard against future state-resolver edits).

2. **Audit log** entry on every successful artifact INSERT
   (``action='cmcp.artifact.created'``). The audit row carries the
   resolved state, persona, content_type, course_id, and the
   actor's role so Bill 194 reviewers can trace every CMCP write.

All Claude/OpenAI calls are NOT made — the sync route never calls
the LLM in M1, so these tests just exercise the validate → resolve
→ persist → audit pipeline.
"""
from __future__ import annotations

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

    email = f"cmcpstate_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPState {role.value}",
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


@pytest.fixture()
def other_teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


# ── CEG seed ───────────────────────────────────────────────────────────


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
    """Seed a Grade-7 CEG slice with two SEs."""
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    suffix = uuid4().hex[:6].upper()
    subject_code = f"S{suffix}"
    strand_code = "B"
    version_slug = f"test-state-{uuid4().hex[:6]}"

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


def _seed_course(db_session, owner_user_id):
    from app.models.course import Course

    course = Course(
        name=f"CMCP State Test Course {uuid4().hex[:6]}",
        created_by_user_id=owner_user_id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


# ─────────────────────────────────────────────────────────────────────
# State machine — happy paths (re-assert Wave 0 behavior under 3B-1
# audit + authority wiring)
# ─────────────────────────────────────────────────────────────────────


def test_parent_self_init_state_self_study(
    client, db_session, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """PARENT requestor (no course_id) → state=SELF_STUDY."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    artifact_id = resp.json()["id"]
    artifact = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.id == artifact_id)
        .first()
    )
    assert artifact is not None
    assert artifact.state == ArtifactState.SELF_STUDY
    assert artifact.user_id == parent_user.id


def test_student_self_init_state_self_study(
    client, db_session, student_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """STUDENT requestor (no course_id) → state=SELF_STUDY."""
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    headers = _auth(client, student_user.email)
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    artifact_id = resp.json()["id"]
    artifact = (
        db_session.query(StudyGuide)
        .filter(StudyGuide.id == artifact_id)
        .first()
    )
    assert artifact is not None
    assert artifact.state == ArtifactState.SELF_STUDY


def test_teacher_with_owned_course_state_pending_review(
    client, db_session, teacher_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """TEACHER + owned course_id → state=PENDING_REVIEW."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    course = _seed_course(db_session, teacher_user.id)
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_cmcp_curriculum, course_id=course.id),
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        artifact_id = resp.json()["id"]
        artifact = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.id == artifact_id)
            .first()
        )
        assert artifact is not None
        assert artifact.state == ArtifactState.PENDING_REVIEW
        assert artifact.course_id == course.id
    finally:
        db_session.query(StudyGuide).filter(
            StudyGuide.user_id == teacher_user.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ─────────────────────────────────────────────────────────────────────
# Authority guard — denies (403)
# ─────────────────────────────────────────────────────────────────────


def test_parent_with_course_id_denied_403(
    client,
    db_session,
    parent_user,
    teacher_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """PARENT + course_id (any owner) → 403; no row inserted."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide

    course = _seed_course(db_session, teacher_user.id)
    try:
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_cmcp_curriculum, course_id=course.id),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        # No artifact row should have been written.
        rows = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.user_id == parent_user.id)
            .all()
        )
        assert rows == []
    finally:
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_student_with_course_id_denied_403(
    client,
    db_session,
    student_user,
    teacher_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """STUDENT + course_id (any owner) → 403; no row inserted."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide

    course = _seed_course(db_session, teacher_user.id)
    try:
        headers = _auth(client, student_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_cmcp_curriculum, course_id=course.id),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        rows = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.user_id == student_user.id)
            .all()
        )
        assert rows == []
    finally:
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_teacher_with_other_teachers_course_denied_403(
    client,
    db_session,
    teacher_user,
    other_teacher_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """TEACHER + course owned by another teacher → 403; no row inserted."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide

    # Course is created by ``other_teacher_user`` — ``teacher_user``
    # does NOT own it.
    course = _seed_course(db_session, other_teacher_user.id)
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_cmcp_curriculum, course_id=course.id),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        rows = (
            db_session.query(StudyGuide)
            .filter(StudyGuide.user_id == teacher_user.id)
            .all()
        )
        assert rows == []
    finally:
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ─────────────────────────────────────────────────────────────────────
# Audit log — one entry per successful INSERT
# ─────────────────────────────────────────────────────────────────────


def test_audit_log_written_on_parent_self_init(
    client, db_session, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Successful PARENT self-init writes a ``cmcp.artifact.created``
    audit row carrying the resolved state + content_type + course_id.

    Filtering on ``user_id`` (not ``resource_id``) because the test DB
    is session-scoped — SQLite can reuse a deleted row's PK so a stale
    audit row from a prior test's deleted artifact would otherwise
    collide with this artifact's resource_id. ``parent_user`` is built
    with a uuid-suffixed email per test, so its user_id is unique to
    this test run.
    """
    import json

    from app.models.audit_log import AuditLog

    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/cmcp/generate",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    artifact_id = resp.json()["id"]

    audit_rows = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "cmcp.artifact.created",
            AuditLog.user_id == parent_user.id,
        )
        .all()
    )
    assert len(audit_rows) == 1
    row = audit_rows[0]
    assert row.resource_id == artifact_id
    assert row.resource_type == "study_guide"
    details = json.loads(row.details)
    assert details["state"] == "SELF_STUDY"
    assert details["persona"] == "parent"
    assert details["content_type"] == "QUIZ"
    assert details["course_id"] is None
    assert details["role"] == "parent"


def test_audit_log_written_on_teacher_class_distribute(
    client, db_session, teacher_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Successful TEACHER + owned-course write produces an audit row
    stamped with state=PENDING_REVIEW + course_id."""
    import json

    from app.models.audit_log import AuditLog
    from app.models.course import Course
    from app.models.study_guide import StudyGuide

    course = _seed_course(db_session, teacher_user.id)
    try:
        headers = _auth(client, teacher_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_cmcp_curriculum, course_id=course.id),
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        artifact_id = resp.json()["id"]

        audit_rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "cmcp.artifact.created",
                AuditLog.user_id == teacher_user.id,
            )
            .all()
        )
        assert len(audit_rows) == 1
        row = audit_rows[0]
        assert row.resource_id == artifact_id
        details = json.loads(row.details)
        assert details["state"] == "PENDING_REVIEW"
        assert details["persona"] == "teacher"
        assert details["course_id"] == course.id
        assert details["role"] == "teacher"
    finally:
        db_session.query(StudyGuide).filter(
            StudyGuide.user_id == teacher_user.id
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_audit_log_NOT_written_on_403_denial(
    client,
    db_session,
    parent_user,
    teacher_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
):
    """403 path short-circuits before persistence → no audit row.

    Regression guard: the audit-on-INSERT call must live INSIDE
    ``persist_cmcp_artifact``, not in the route, so denied requests
    leave no ``cmcp.artifact.created`` trail (which would otherwise
    confuse the Bill 194 reviewer).
    """
    from app.models.audit_log import AuditLog
    from app.models.course import Course

    course = _seed_course(db_session, teacher_user.id)
    audit_count_before = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "cmcp.artifact.created")
        .count()
    )
    try:
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/api/cmcp/generate",
            json=_payload(seeded_cmcp_curriculum, course_id=course.id),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        audit_count_after = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "cmcp.artifact.created")
            .count()
        )
        assert audit_count_before == audit_count_after
    finally:
        db_session.query(Course).filter(Course.id == course.id).delete(
            synchronize_session=False
        )
        db_session.commit()
