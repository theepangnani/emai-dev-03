"""Tests for CB-CMCP-001 M3-C 3C-4 (#4587) — Bridge "What [child] is learning" card.

Covers ``GET /api/bridge/cards/cmcp/{kid_id}``:

- PARENT linked to kid sees their kid's APPROVED + SELF_STUDY artifacts.
- Cross-family PARENT call → 404 (no existence oracle).
- Unknown kid id → 404.
- ``limit`` query param honoured.
- ``parent_companion_available`` correctly computed (parent persona +
  non-empty ``parent_summary``).
- Non-PARENT/non-ADMIN role → 403.
- Flag-off → 403.

All AI/Claude/OpenAI calls are mocked / not invoked.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ───────────────────────────────────────────────────────────────────────────
# Flag fixture
# ───────────────────────────────────────────────────────────────────────────


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


# ───────────────────────────────────────────────────────────────────────────
# User / link / artifact factories
# ───────────────────────────────────────────────────────────────────────────


def _make_user(db_session, role, *, prefix: str | None = None):
    from app.core.security import get_password_hash
    from app.models.user import User

    base = prefix or f"bridgecmcp_{role.value.lower()}"
    user = User(
        email=f"{base}_{uuid4().hex[:8]}@test.com",
        full_name=f"BridgeCMCP {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_kid(db_session, *, grade=8):
    """Create a Student row + backing User (kid)."""
    from app.models.student import Student
    from app.models.user import UserRole

    kid_user = _make_user(db_session, UserRole.STUDENT, prefix="bridgecmcp_kid")
    student = Student(
        user_id=kid_user.id,
        grade_level=grade,
        school_name="Bridge CMCP Card Test School",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return kid_user, student


def _link_parent_kid(db_session, parent_user, student):
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=student.id,
        )
    )
    db_session.commit()


def _make_course(db_session, *, subject="Math", teacher_id=None):
    from app.models.course import Course

    course = Course(
        name=f"Bridge CMCP Course {uuid4().hex[:6]}",
        subject=subject,
        teacher_id=teacher_id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


def _seed_artifact(
    db_session,
    *,
    user_id,
    state,
    title="Bridge CMCP Test Artifact",
    guide_type="study_guide",
    course_id=None,
    requested_persona="student",
    parent_summary=None,
    se_codes=None,
    archived_at=None,
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title,
        content="# Body",
        guide_type=guide_type,
        state=state,
        requested_persona=requested_persona,
        parent_summary=parent_summary,
        se_codes=se_codes or ["MATH.B2.1"],
        archived_at=archived_at,
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ───────────────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────────────


def test_parent_lists_own_kids_approved_and_self_study(
    client, db_session, cmcp_flag_on
):
    """PARENT sees their linked kid's APPROVED + SELF_STUDY rows, newest first."""
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState

    parent = _make_user(db_session, UserRole.PARENT, prefix="bridgecmcp_p_own")
    kid_user, kid = _make_kid(db_session)
    _link_parent_kid(db_session, parent, kid)
    course = _make_course(db_session, subject="Science")

    # Two rows visible: APPROVED + SELF_STUDY.
    approved = _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        course_id=course.id,
        title="Cell Division",
    )
    self_study = _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.SELF_STUDY,
        title="Photosynthesis",
        course_id=None,
        se_codes=["SCI.B3.4"],
    )

    # Excluded: DRAFT, PENDING_REVIEW, ARCHIVED.
    _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.DRAFT,
        title="Draft (excluded)",
    )
    _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.PENDING_REVIEW,
        title="Pending (excluded)",
    )
    # ARCHIVED state is invalid here; an APPROVED row with archived_at
    # set is what the model treats as soft-deleted.
    from datetime import datetime, timezone

    _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        title="Soft-deleted (excluded)",
        archived_at=datetime.now(timezone.utc),
    )

    headers = _auth(client, parent.email)
    resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = [item["artifact_id"] for item in body["items"]]
    # Newest-first ordering: self_study was seeded after approved.
    assert ids == [self_study.id, approved.id]
    # APPROVED row carries course-derived subject; SELF_STUDY falls
    # back to SE-prefix.
    by_id = {item["artifact_id"]: item for item in body["items"]}
    assert by_id[approved.id]["subject"] == "Science"
    assert by_id[self_study.id]["subject"] == "SCI"
    assert by_id[approved.id]["state"] == ArtifactState.APPROVED
    assert by_id[approved.id]["topic"] == "Cell Division"
    assert by_id[approved.id]["content_type"] == "study_guide"


def test_cross_family_parent_denied_404(client, db_session, cmcp_flag_on):
    """Unrelated PARENT → 404 (no existence oracle)."""
    from app.models.user import UserRole

    other_parent = _make_user(
        db_session, UserRole.PARENT, prefix="bridgecmcp_p_other"
    )
    kid_user, kid = _make_kid(db_session)
    # Note: NO parent_students link from other_parent → kid.

    from app.services.cmcp.artifact_state import ArtifactState

    _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        title="Hidden",
    )

    headers = _auth(client, other_parent.email)
    resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
    assert resp.status_code == 404, resp.text


def test_unknown_kid_404(client, db_session, cmcp_flag_on):
    """Unknown ``kid_id`` → 404."""
    from app.models.user import UserRole

    parent = _make_user(db_session, UserRole.PARENT, prefix="bridgecmcp_p_404")
    headers = _auth(client, parent.email)

    resp = client.get("/api/bridge/cards/cmcp/9999999", headers=headers)
    assert resp.status_code == 404, resp.text


def test_limit_query_honoured(client, db_session, cmcp_flag_on):
    """``limit`` caps the returned items."""
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState

    parent = _make_user(
        db_session, UserRole.PARENT, prefix="bridgecmcp_p_limit"
    )
    kid_user, kid = _make_kid(db_session)
    _link_parent_kid(db_session, parent, kid)

    for i in range(7):
        _seed_artifact(
            db_session,
            user_id=kid_user.id,
            state=ArtifactState.APPROVED,
            title=f"Topic #{i}",
        )

    headers = _auth(client, parent.email)
    resp = client.get(
        f"/api/bridge/cards/cmcp/{kid.id}?limit=3", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 3

    # Default limit is 5.
    resp_default = client.get(
        f"/api/bridge/cards/cmcp/{kid.id}", headers=headers
    )
    assert resp_default.status_code == 200, resp_default.text
    assert len(resp_default.json()["items"]) == 5


def test_parent_companion_available_flag(client, db_session, cmcp_flag_on):
    """``parent_companion_available`` is True only for parent-persona + non-empty parent_summary."""
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState

    parent = _make_user(db_session, UserRole.PARENT, prefix="bridgecmcp_p_pca")
    kid_user, kid = _make_kid(db_session)
    _link_parent_kid(db_session, parent, kid)

    # Parent-persona + summary → True.
    with_summary = _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        requested_persona="parent",
        parent_summary='{"se_explanation": "..."}',
        title="Has companion",
    )
    # Parent-persona + empty summary → False.
    without_summary = _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        requested_persona="parent",
        parent_summary=None,
        title="No companion",
    )
    # Student-persona + summary → False (persona mismatch).
    student_persona = _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        requested_persona="student",
        parent_summary='{"se_explanation": "..."}',
        title="Wrong persona",
    )

    headers = _auth(client, parent.email)
    resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    by_id = {item["artifact_id"]: item for item in resp.json()["items"]}
    assert by_id[with_summary.id]["parent_companion_available"] is True
    assert by_id[without_summary.id]["parent_companion_available"] is False
    assert by_id[student_persona.id]["parent_companion_available"] is False


def test_non_parent_non_admin_403(client, db_session, cmcp_flag_on):
    """STUDENT / TEACHER → 403 even with flag ON."""
    from app.models.teacher import Teacher
    from app.models.user import UserRole

    student = _make_user(db_session, UserRole.STUDENT, prefix="bridgecmcp_stud")
    teacher = _make_user(db_session, UserRole.TEACHER, prefix="bridgecmcp_tea")
    db_session.add(Teacher(user_id=teacher.id, full_name=teacher.full_name))
    db_session.commit()

    kid_user, kid = _make_kid(db_session)

    for u in (student, teacher):
        headers = _auth(client, u.email)
        resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
        assert resp.status_code == 403, (u.email, resp.status_code, resp.text)


def test_flag_off_returns_403(client, db_session):
    """When ``cmcp.enabled`` is OFF, the route 403s (caught by ``require_cmcp_enabled``)."""
    from app.models.user import UserRole

    parent = _make_user(
        db_session, UserRole.PARENT, prefix="bridgecmcp_p_flagoff"
    )
    kid_user, kid = _make_kid(db_session)
    _link_parent_kid(db_session, parent, kid)

    # Note: no ``cmcp_flag_on`` fixture — autouse fixture in conftest
    # resets the flag to OFF for every test.
    headers = _auth(client, parent.email)
    resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
    assert resp.status_code == 403, resp.text


def test_admin_can_list_any_kid(client, db_session, cmcp_flag_on):
    """ADMIN bypasses the parent-link check."""
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState

    admin = _make_user(db_session, UserRole.ADMIN, prefix="bridgecmcp_admin")
    kid_user, kid = _make_kid(db_session)
    # No parent link — admin should still see the kid's rows.

    a = _seed_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        title="Admin-visible",
    )

    headers = _auth(client, admin.email)
    resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = {item["artifact_id"] for item in resp.json()["items"]}
    assert a.id in ids


def test_parent_self_authored_self_study_visible_in_kid_card(
    client, db_session, cmcp_flag_on
):
    """SELF_STUDY parent-persona rows the parent generated for themselves
    surface on every linked-kid card.

    M3α-wide: per the module docstring, parent-persona artifacts don't
    carry a kid foreign key, so the M3α surface widens to "any
    parent-self-authored parent-persona SELF_STUDY row owned by the
    caller". This test pins that contract until M3β tightens it.
    """
    from app.models.user import UserRole
    from app.services.cmcp.artifact_state import ArtifactState

    parent = _make_user(db_session, UserRole.PARENT, prefix="bridgecmcp_p_self")
    kid_user, kid = _make_kid(db_session)
    _link_parent_kid(db_session, parent, kid)

    parent_owned = _seed_artifact(
        db_session,
        user_id=parent.id,
        state=ArtifactState.SELF_STUDY,
        requested_persona="parent",
        title="Parent self-study",
    )

    headers = _auth(client, parent.email)
    resp = client.get(f"/api/bridge/cards/cmcp/{kid.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = {item["artifact_id"] for item in resp.json()["items"]}
    assert parent_owned.id in ids
