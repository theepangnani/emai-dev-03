"""Tests for CB-CMCP-001 0A-2 — extend study_guides per locked decision D2=B (#4413).

Verifies:
- Round-trip of all 8 new curriculum-aware columns when populated.
- Round-trip when the new columns are NULL (existing behavior unchanged).
- ``state`` defaults to 'DRAFT' on insert when not provided.
- Existing study_guide columns (title, content, guide_type, version) still
  round-trip alongside the new fields.

These columns are nullable / defaulted by design — the migration must be
backward compatible for non-CMCP code paths that do not yet populate them.
"""
from decimal import Decimal

import pytest


@pytest.fixture()
def cmcp_user(db_session):
    """Create a parent user for CMCP study_guide ownership."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == "cmcp_sg_user@test.com").first()
    if user:
        return user

    user = User(
        email="cmcp_sg_user@test.com",
        full_name="CMCP SG User",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_round_trip_all_new_columns_populated(db_session, cmcp_user):
    """Insert + reload a row with all 8 new columns populated."""
    from app.models.study_guide import StudyGuide

    se_codes = ["MATH.4.NS.1", "MATH.4.NS.2"]
    envelope = {"class_id": 42, "topic": "fractions", "kid_count": 24}

    guide = StudyGuide(
        user_id=cmcp_user.id,
        title="CMCP Aligned Guide",
        content="# Aligned content",
        guide_type="study_guide",
        version=1,
        # New CMCP columns
        se_codes=se_codes,
        alignment_score=Decimal("0.875"),
        ceg_version=3,
        state="APPROVED",
        board_id="TDSB",
        voice_module_hash="a" * 64,
        class_context_envelope_summary=envelope,
        requested_persona="parent",
    )
    db_session.add(guide)
    db_session.commit()
    guide_id = guide.id
    db_session.expire_all()

    reloaded = db_session.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    assert reloaded is not None
    assert reloaded.se_codes == se_codes
    # Decimal round-trip — alignment_score is NUMERIC(4,3); cast back to Decimal
    # for comparison and tolerate driver-specific Decimal/float scale variation.
    assert Decimal(str(reloaded.alignment_score)) == Decimal("0.875")
    assert reloaded.ceg_version == 3
    assert reloaded.state == "APPROVED"
    assert reloaded.board_id == "TDSB"
    assert reloaded.voice_module_hash == "a" * 64
    assert reloaded.class_context_envelope_summary == envelope
    assert reloaded.requested_persona == "parent"

    # Existing columns also still round-trip alongside the new ones.
    assert reloaded.title == "CMCP Aligned Guide"
    assert reloaded.guide_type == "study_guide"
    assert reloaded.version == 1


def test_round_trip_with_null_new_columns(db_session, cmcp_user):
    """Existing behavior unchanged — a row with NO new columns set still works.

    Regression guard: the CMCP-extension migration must not break legacy code
    paths that build StudyGuide rows from the pre-CMCP shape.
    """
    from app.models.study_guide import StudyGuide

    guide = StudyGuide(
        user_id=cmcp_user.id,
        title="Legacy Guide (no CMCP fields)",
        content="# Legacy content",
        guide_type="study_guide",
        version=1,
    )
    db_session.add(guide)
    db_session.commit()
    guide_id = guide.id
    db_session.expire_all()

    reloaded = db_session.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    assert reloaded is not None
    # Nullable new columns return None
    assert reloaded.se_codes is None
    assert reloaded.alignment_score is None
    assert reloaded.ceg_version is None
    assert reloaded.board_id is None
    assert reloaded.voice_module_hash is None
    assert reloaded.class_context_envelope_summary is None
    assert reloaded.requested_persona is None
    # Existing fields round-trip unchanged
    assert reloaded.title == "Legacy Guide (no CMCP fields)"
    assert reloaded.guide_type == "study_guide"


def test_state_defaults_to_draft_on_insert(db_session, cmcp_user):
    """state defaults to 'DRAFT' when not explicitly provided on insert."""
    from app.models.study_guide import StudyGuide

    guide = StudyGuide(
        user_id=cmcp_user.id,
        title="State Default Test",
        content="# whatever",
        guide_type="study_guide",
        version=1,
    )
    db_session.add(guide)
    db_session.commit()
    guide_id = guide.id
    db_session.expire_all()

    reloaded = db_session.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    assert reloaded is not None
    assert reloaded.state == "DRAFT"


def test_state_self_study_value_supported(db_session, cmcp_user):
    """SELF_STUDY state value (D3=C hybrid path) round-trips correctly.

    The locked decision D3=C adds a SELF_STUDY state to the artifact state
    machine. This is a string comparison — there is no Enum in the DB layer
    by design (memory rule on Enum/PG NAME storage).
    """
    from app.models.study_guide import StudyGuide

    guide = StudyGuide(
        user_id=cmcp_user.id,
        title="Self-Study Guide",
        content="# self-study content",
        guide_type="study_guide",
        version=1,
        state="SELF_STUDY",
    )
    db_session.add(guide)
    db_session.commit()
    guide_id = guide.id
    db_session.expire_all()

    reloaded = db_session.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    assert reloaded is not None
    assert reloaded.state == "SELF_STUDY"
