"""Tests for the ``cb_cmcp_artifact_summary`` digest block renderer
(CB-CMCP-001 M3α 3C-3, #4580).

Covers
------
- Renders for an APPROVED CMCP artifact within the parent's visibility
  (linked-child relationship).
- Renders for a SELF_STUDY artifact the parent created themselves
  (parent-self-generated path).
- Returns ``None`` for ARCHIVED / DRAFT / PENDING_REVIEW / IN_REVIEW /
  REJECTED / GENERATING / APPROVED_VERIFIED states (parent visibility
  is constrained to ``{APPROVED, SELF_STUDY}``).
- Returns ``None`` when an unrelated parent (cross-family) tries to
  render an artifact owned by another family's child.
- Returns ``None`` when the artifact id does not exist.
- Block payload includes the expected keys: artifact_id, subject,
  content_type, description, open_link, kid_name.
- ``description`` is a single line and capped (no full body leak).
- ``open_link`` points at the ``/parent/companion/<id>`` Bridge route.
- ``DIGEST_BLOCK_RENDERERS`` registry exposes the renderer keyed by
  ``cb_cmcp_artifact_summary``.

DB note
-------
Uses the real SQLite ``db_session`` fixture (mirrors
``test_cmcp_persistence.py``). Real SQL is cheap on the in-memory
SQLite test DB and avoids brittle mocks of the ORM relationships used
by the visibility helpers (linked-children + course enrollment).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.cmcp.artifact_state import ArtifactState
from app.services.digest_block_renderers import (
    BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY,
    DIGEST_BLOCK_RENDERERS,
    render_cb_cmcp_artifact_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(db_session, role, *, full_name=None):
    from app.core.security import get_password_hash
    from app.models.user import User

    suffix = uuid4().hex[:8]
    name = full_name or f"Digest CMCP {role.value} {suffix}"
    user = User(
        email=f"digest_cmcp_{role.value.lower()}_{suffix}@test.com",
        full_name=name,
        role=role,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_parent(db_session, *, full_name="Parent One"):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT, full_name=full_name)


def _make_kid(db_session, *, full_name="Maya Tester"):
    """Create a STUDENT user + Student row. Returns (user, student)."""
    from app.models.student import Student
    from app.models.user import UserRole

    kid_user = _make_user(db_session, UserRole.STUDENT, full_name=full_name)
    student = Student(user_id=kid_user.id)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return kid_user, student


def _link_parent_child(db_session, parent, student):
    from app.models.student import RelationshipType, parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent.id,
            student_id=student.id,
            relationship_type=RelationshipType.GUARDIAN,
        )
    )
    db_session.commit()


def _make_artifact(
    db_session,
    *,
    user_id,
    state=ArtifactState.APPROVED,
    title="Fractions practice quiz",
    content="Add and subtract fractions with unlike denominators. Show your work in two steps.",
    guide_type="quiz",
    course_id=None,
):
    from app.models.study_guide import StudyGuide

    artifact = StudyGuide(
        user_id=user_id,
        course_id=course_id,
        title=title,
        content=content,
        guide_type=guide_type,
        state=state,
        se_codes=["B2.1"],
        voice_module_hash="a" * 64,
        requested_persona="parent",
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_block_registry_exposes_renderer_under_block_type():
    """The dispatcher (3C-1, Wave 2) reads the registry directly. The
    block_type → callable mapping must be stable + contain the new
    renderer."""
    assert BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY == "cb_cmcp_artifact_summary"
    assert DIGEST_BLOCK_RENDERERS[
        BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY
    ] is render_cb_cmcp_artifact_summary


# ---------------------------------------------------------------------------
# Happy-path renders
# ---------------------------------------------------------------------------


def test_renders_for_approved_artifact_with_linked_child(db_session):
    """APPROVED artifact + parent linked to the artifact's owner → renders."""
    parent = _make_parent(db_session)
    kid_user, kid_student = _make_kid(db_session, full_name="Maya Lee")
    _link_parent_child(db_session, parent, kid_student)

    artifact = _make_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        title="Cell Division Study Guide",
        content="Mitosis and meiosis basics. Compare phases with a diagram.",
        guide_type="study_guide",
    )

    block = render_cb_cmcp_artifact_summary(
        artifact.id, parent.id, kid_user.id, db_session
    )

    assert block is not None
    assert block["block_type"] == BLOCK_TYPE_CB_CMCP_ARTIFACT_SUMMARY
    assert block["artifact_id"] == artifact.id
    assert block["subject"] == "Cell Division Study Guide"
    assert block["content_type"] == "study_guide"
    # Description is the first non-empty line of content.
    assert block["description"] == "Mitosis and meiosis basics. Compare phases with a diagram."
    # Open link wires to the ParentCompanionPage route (#4575).
    assert block["open_link"].endswith(f"/parent/companion/{artifact.id}")
    # First name only.
    assert block["kid_name"] == "Maya"


def test_renders_for_self_study_artifact_parent_self_generated(db_session):
    """SELF_STUDY artifact created by the parent themselves → renders;
    ``kid_name`` is None when the artifact owner is the parent (not a kid)."""
    parent = _make_parent(db_session, full_name="Sam Parent")
    artifact = _make_artifact(
        db_session,
        user_id=parent.id,
        state=ArtifactState.SELF_STUDY,
        title="Mom's review pack",
    )
    block = render_cb_cmcp_artifact_summary(
        artifact.id, parent.id, None, db_session
    )

    assert block is not None
    assert block["artifact_id"] == artifact.id
    assert block["subject"] == "Mom's review pack"
    # Self-generated → no kid label.
    assert block["kid_name"] is None


# ---------------------------------------------------------------------------
# State filtering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skipped_state",
    [
        ArtifactState.ARCHIVED,
        ArtifactState.DRAFT,
        ArtifactState.PENDING_REVIEW,
        ArtifactState.IN_REVIEW,
        ArtifactState.REJECTED,
        ArtifactState.GENERATING,
        ArtifactState.APPROVED_VERIFIED,
    ],
)
def test_returns_none_for_states_outside_visible_set(db_session, skipped_state):
    """Only ``{APPROVED, SELF_STUDY}`` are surfaced in the parent digest."""
    parent = _make_parent(db_session)
    kid_user, kid_student = _make_kid(db_session)
    _link_parent_child(db_session, parent, kid_student)

    artifact = _make_artifact(
        db_session, user_id=kid_user.id, state=skipped_state
    )

    result = render_cb_cmcp_artifact_summary(
        artifact.id, parent.id, kid_user.id, db_session
    )
    assert result is None


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


def test_returns_none_for_cross_family_parent(db_session):
    """An unrelated parent (no link to the artifact's child + not the
    creator) gets None — no cross-family leak."""
    # Family A — owns the artifact.
    family_a_parent = _make_parent(db_session, full_name="Family A")
    kid_a_user, kid_a_student = _make_kid(db_session, full_name="Alex A")
    _link_parent_child(db_session, family_a_parent, kid_a_student)
    artifact = _make_artifact(
        db_session, user_id=kid_a_user.id, state=ArtifactState.APPROVED
    )

    # Family B — unrelated parent + child.
    family_b_parent = _make_parent(db_session, full_name="Family B")

    # Family-B parent has no link to kid_a_user → must not see the
    # artifact even though state is APPROVED.
    result = render_cb_cmcp_artifact_summary(
        artifact.id, family_b_parent.id, kid_a_user.id, db_session
    )
    assert result is None


def test_returns_none_for_unknown_artifact_id(db_session):
    """No row with id=N → None (not an exception)."""
    parent = _make_parent(db_session)
    result = render_cb_cmcp_artifact_summary(
        9_999_999, parent.id, None, db_session
    )
    assert result is None


# ---------------------------------------------------------------------------
# Description hardening
# ---------------------------------------------------------------------------


def test_description_caps_long_first_line(db_session):
    """A long single-line content body must be capped (no full-body leak)."""
    parent = _make_parent(db_session)
    kid_user, kid_student = _make_kid(db_session)
    _link_parent_child(db_session, parent, kid_student)

    long_line = "X" * 500  # well past the 140-char cap.
    artifact = _make_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        content=long_line,
    )
    block = render_cb_cmcp_artifact_summary(
        artifact.id, parent.id, kid_user.id, db_session
    )
    assert block is not None
    assert len(block["description"]) <= 140
    # Truncation marker.
    assert block["description"].endswith("…")


def test_description_falls_back_to_title_when_content_blank(db_session):
    """Empty/whitespace content body → description is the title."""
    parent = _make_parent(db_session)
    kid_user, kid_student = _make_kid(db_session)
    _link_parent_child(db_session, parent, kid_student)

    artifact = _make_artifact(
        db_session,
        user_id=kid_user.id,
        state=ArtifactState.APPROVED,
        title="Just the title",
        content="   \n   \n",
    )
    block = render_cb_cmcp_artifact_summary(
        artifact.id, parent.id, kid_user.id, db_session
    )
    assert block is not None
    assert block["description"] == "Just the title"
