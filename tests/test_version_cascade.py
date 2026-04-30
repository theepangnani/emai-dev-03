"""Tests for CB-CMCP-001 M3-G 3G-2 — artifact cascade trigger (#4662).

Per locked decision D9=B: when stripe 3G-1's classifier marks an SE
pair as ``scope_substantive``, every APPROVED ``study_guides`` row
whose ``se_codes`` JSON array contains that SE's ``cb_code`` is
transitioned APPROVED → PENDING_REVIEW and a
``cmcp.artifact.cascade_flagged`` audit row is written per artifact.

Wording-only pairs are counted but never trigger a transition.

These tests exercise the in-memory state transition + the audit-log
contract end-to-end against the live SQLite test DB. No real
notification API calls are made — stripe 3G-3 owns notification.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from conftest import PASSWORD


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def parent_user(db_session):
    """Create a PARENT user for owning study_guides under test."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"cascade_parent_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Cascade Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_study_guide(
    db_session,
    *,
    user_id: int,
    se_codes: list[str] | None,
    state: str,
    title_suffix: str = "",
):
    """Insert a StudyGuide row with the supplied state + se_codes."""
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=user_id,
        title=f"Cascade Test {title_suffix or uuid4().hex[:6]}",
        content="# placeholder content",
        guide_type="study_guide",
        version=1,
        relationship_type="version",
        state=state,
        se_codes=se_codes,
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


def _audit_rows_for(db_session, action: str, resource_id: int):
    """Fetch all audit_logs rows matching action + resource_id."""
    from app.models.audit_log import AuditLog

    return (
        db_session.query(AuditLog)
        .filter(AuditLog.action == action)
        .filter(AuditLog.resource_id == resource_id)
        .order_by(AuditLog.id.asc())
        .all()
    )


# SE-pair builders mirror 3G-1's dict shape (the MCP get_expectations
# payload). cb_code change → substantive; identical SE → wording_only.


def _se(*, cb_code: str = "CB-G7-MATH-B2-SE3", text: str | None = None,
        parent_oe_id: int | None = 42) -> dict:
    return {
        "expectation_text": text or "describe the water cycle and its key processes",
        "cb_code": cb_code,
        "parent_oe_id": parent_oe_id,
    }


def _substantive_pair(
    *,
    cb_code: str = "CB-G7-MATH-B2-SE3",
    from_version: str = "2020-rev1",
    to_version: str = "2024",
) -> dict:
    """Build an SE pair that classifies as scope_substantive (cb_code unchanged
    on the SE rows themselves but parent_oe_id changes — substantive per 3G-1).
    """
    old_se = _se(cb_code=cb_code, parent_oe_id=42)
    new_se = _se(cb_code=cb_code, parent_oe_id=99)  # parent_oe change → substantive
    return {
        "old_se": old_se,
        "new_se": new_se,
        "from_version": from_version,
        "to_version": to_version,
    }


def _wording_only_pair(
    *,
    cb_code: str = "CB-G7-MATH-B2-SE7",
    from_version: str = "2020-rev1",
    to_version: str = "2024",
) -> dict:
    """Build an SE pair that classifies as wording_only (identical SEs)."""
    old_se = _se(cb_code=cb_code)
    new_se = _se(cb_code=cb_code)
    return {
        "old_se": old_se,
        "new_se": new_se,
        "from_version": from_version,
        "to_version": to_version,
    }


# ─────────────────────────────────────────────────────────────────────
# Core behavior — substantive cascade
# ─────────────────────────────────────────────────────────────────────


def test_substantive_se_change_flags_approved_artifact_to_pending_review(
    db_session, parent_user
):
    """APPROVED study_guide referencing the substantive SE → PENDING_REVIEW."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-CASCADE-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code, "CB-OTHER-XYZ"],
        state=ArtifactState.APPROVED,
    )

    result = apply_version_cascade(
        [_substantive_pair(cb_code=cb_code)],
        db_session,
    )
    db_session.commit()
    db_session.refresh(sg)

    assert sg.state == ArtifactState.PENDING_REVIEW
    assert sg.id in result.flagged_artifact_ids
    assert result.substantive_se_codes == [cb_code]
    assert result.wording_only_se_count == 0


def test_substantive_change_skips_artifact_without_matching_se(
    db_session, parent_user
):
    """APPROVED study_guide whose se_codes does NOT include the substantive
    SE is left unchanged."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    target_cb_code = f"CB-CASCADE-TARGET-{uuid4().hex[:6]}"
    other_cb_code = f"CB-CASCADE-OTHER-{uuid4().hex[:6]}"

    untouched = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[other_cb_code],
        state=ArtifactState.APPROVED,
    )

    result = apply_version_cascade(
        [_substantive_pair(cb_code=target_cb_code)],
        db_session,
    )
    db_session.commit()
    db_session.refresh(untouched)

    assert untouched.state == ArtifactState.APPROVED
    assert untouched.id not in result.flagged_artifact_ids


def test_substantive_change_skips_non_approved_states(db_session, parent_user):
    """DRAFT / IN_REVIEW / ARCHIVED rows are not transitioned even if their
    se_codes match the substantive SE — only APPROVED rows reflag."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-CASCADE-{uuid4().hex[:6]}"
    states_to_skip = [
        ArtifactState.DRAFT,
        ArtifactState.IN_REVIEW,
        ArtifactState.PENDING_REVIEW,
        ArtifactState.REJECTED,
        ArtifactState.SELF_STUDY,
        ArtifactState.ARCHIVED,
        ArtifactState.APPROVED_VERIFIED,
    ]
    rows = [
        _make_study_guide(
            db_session,
            user_id=parent_user.id,
            se_codes=[cb_code],
            state=state,
            title_suffix=f"skip-{state}",
        )
        for state in states_to_skip
    ]

    result = apply_version_cascade(
        [_substantive_pair(cb_code=cb_code)],
        db_session,
    )
    db_session.commit()

    for row, original_state in zip(rows, states_to_skip):
        db_session.refresh(row)
        assert row.state == original_state, (
            f"row originally {original_state} should not be transitioned; "
            f"got {row.state}"
        )
        assert row.id not in result.flagged_artifact_ids


# ─────────────────────────────────────────────────────────────────────
# Core behavior — wording-only no-op
# ─────────────────────────────────────────────────────────────────────


def test_wording_only_se_change_does_not_transition_approved_artifact(
    db_session, parent_user
):
    """wording_only SE pair → APPROVED artifact stays APPROVED, no audit."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import (
        CASCADE_AUDIT_ACTION,
        apply_version_cascade,
    )

    cb_code = f"CB-WORDING-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    result = apply_version_cascade(
        [_wording_only_pair(cb_code=cb_code)],
        db_session,
    )
    db_session.commit()
    db_session.refresh(sg)

    assert sg.state == ArtifactState.APPROVED
    assert result.flagged_artifact_ids == []
    assert result.substantive_se_codes == []
    assert result.wording_only_se_count == 1
    assert _audit_rows_for(db_session, CASCADE_AUDIT_ACTION, sg.id) == []


# ─────────────────────────────────────────────────────────────────────
# Audit log contract
# ─────────────────────────────────────────────────────────────────────


def test_audit_log_captures_cascade_event(db_session, parent_user):
    """Each cascaded artifact gets one cmcp.artifact.cascade_flagged audit row
    carrying se_code + from_version + to_version + severity in details."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import (
        CASCADE_AUDIT_ACTION,
        apply_version_cascade,
    )
    from app.services.cmcp.version_diff_classifier import (
        SEVERITY_SCOPE_SUBSTANTIVE,
    )

    cb_code = f"CB-AUDIT-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    apply_version_cascade(
        [
            _substantive_pair(
                cb_code=cb_code,
                from_version="2020-rev1",
                to_version="2024",
            )
        ],
        db_session,
    )
    db_session.commit()

    rows = _audit_rows_for(db_session, CASCADE_AUDIT_ACTION, sg.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.resource_type == "study_guide"
    assert row.user_id is None  # system-driven cascade
    payload = json.loads(row.details)
    assert payload["se_code"] == cb_code
    assert payload["from_version"] == "2020-rev1"
    assert payload["to_version"] == "2024"
    assert payload["severity"] == SEVERITY_SCOPE_SUBSTANTIVE


def test_audit_log_one_row_per_flagged_artifact(db_session, parent_user):
    """Two APPROVED artifacts referencing the same SE both flagged + each
    gets its own audit row."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import (
        CASCADE_AUDIT_ACTION,
        apply_version_cascade,
    )

    cb_code = f"CB-MULTI-{uuid4().hex[:6]}"
    sg_a = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
        title_suffix="multi-a",
    )
    sg_b = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code, "CB-EXTRA"],
        state=ArtifactState.APPROVED,
        title_suffix="multi-b",
    )

    result = apply_version_cascade(
        [_substantive_pair(cb_code=cb_code)],
        db_session,
    )
    db_session.commit()
    db_session.refresh(sg_a)
    db_session.refresh(sg_b)

    assert sg_a.state == ArtifactState.PENDING_REVIEW
    assert sg_b.state == ArtifactState.PENDING_REVIEW
    assert sorted(result.flagged_artifact_ids) == sorted([sg_a.id, sg_b.id])
    assert len(_audit_rows_for(db_session, CASCADE_AUDIT_ACTION, sg_a.id)) == 1
    assert len(_audit_rows_for(db_session, CASCADE_AUDIT_ACTION, sg_b.id)) == 1


# ─────────────────────────────────────────────────────────────────────
# Idempotency + edge cases
# ─────────────────────────────────────────────────────────────────────


def test_cascade_is_idempotent_across_re_runs(db_session, parent_user):
    """Re-applying the same diff after an initial cascade is a no-op —
    the artifact is already PENDING_REVIEW and is excluded by the SQL
    filter on the second pass."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import (
        CASCADE_AUDIT_ACTION,
        apply_version_cascade,
    )

    cb_code = f"CB-IDEMPOTENT-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    pair = _substantive_pair(cb_code=cb_code)
    apply_version_cascade([pair], db_session)
    db_session.commit()
    db_session.refresh(sg)
    assert sg.state == ArtifactState.PENDING_REVIEW

    # Re-run identical diff — should be a no-op.
    result_2 = apply_version_cascade([pair], db_session)
    db_session.commit()
    db_session.refresh(sg)
    assert sg.state == ArtifactState.PENDING_REVIEW
    assert result_2.flagged_artifact_ids == []
    # But the SE is still classified as substantive — that's a property
    # of the diff, not the artifact corpus.
    assert result_2.substantive_se_codes == [cb_code]
    # Exactly one audit row from the original cascade.
    assert len(_audit_rows_for(db_session, CASCADE_AUDIT_ACTION, sg.id)) == 1


def test_empty_diff_returns_empty_result(db_session):
    """Empty version_diff → no work, empty CascadeResult."""
    from app.services.cmcp.version_cascade import apply_version_cascade

    result = apply_version_cascade([], db_session)
    assert result.flagged_artifact_ids == []
    assert result.substantive_se_codes == []
    assert result.wording_only_se_count == 0


def test_substantive_pair_with_no_cb_code_is_skipped(db_session, parent_user):
    """Substantive pair with cb_code=None on both sides → can't match
    against se_codes, skipped without raising. wording_only counter
    stays zero (the pair WAS substantive — just unmatched)."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=["CB-SOMETHING"],
        state=ArtifactState.APPROVED,
    )

    # parent_oe_id change drives substantive even with no cb_code on either side.
    pair = {
        "old_se": {
            "expectation_text": "describe the water cycle",
            "cb_code": None,
            "parent_oe_id": 1,
        },
        "new_se": {
            "expectation_text": "describe the water cycle",
            "cb_code": None,
            "parent_oe_id": 2,
        },
        "from_version": "2020-rev1",
        "to_version": "2024",
    }
    result = apply_version_cascade([pair], db_session)
    db_session.commit()
    db_session.refresh(sg)

    assert sg.state == ArtifactState.APPROVED
    assert result.flagged_artifact_ids == []
    # Pair classified substantive but had no recoverable cb_code —
    # it's NOT a wording_only pair.
    assert result.wording_only_se_count == 0
    assert result.substantive_se_codes == []


def test_artifact_with_null_se_codes_is_skipped(db_session, parent_user):
    """APPROVED study_guide with se_codes=NULL is excluded from cascade
    (cannot match — SQL filter is_not(None) catches this)."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-NULL-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=None,
        state=ArtifactState.APPROVED,
    )

    result = apply_version_cascade(
        [_substantive_pair(cb_code=cb_code)],
        db_session,
    )
    db_session.commit()
    db_session.refresh(sg)

    assert sg.state == ArtifactState.APPROVED
    assert result.flagged_artifact_ids == []


def test_mixed_diff_substantive_plus_wording_only(db_session, parent_user):
    """Diff with one substantive + one wording_only pair — only the
    substantive one transitions, both are counted in the result."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_substantive = f"CB-MIX-SUB-{uuid4().hex[:6]}"
    cb_wording = f"CB-MIX-WORD-{uuid4().hex[:6]}"
    sg_sub = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_substantive],
        state=ArtifactState.APPROVED,
        title_suffix="sub",
    )
    sg_word = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_wording],
        state=ArtifactState.APPROVED,
        title_suffix="word",
    )

    result = apply_version_cascade(
        [
            _substantive_pair(cb_code=cb_substantive),
            _wording_only_pair(cb_code=cb_wording),
        ],
        db_session,
    )
    db_session.commit()
    db_session.refresh(sg_sub)
    db_session.refresh(sg_word)

    assert sg_sub.state == ArtifactState.PENDING_REVIEW
    assert sg_word.state == ArtifactState.APPROVED
    assert result.flagged_artifact_ids == [sg_sub.id]
    assert result.substantive_se_codes == [cb_substantive]
    assert result.wording_only_se_count == 1


def test_classify_falls_back_to_old_se_cb_code_when_new_is_deleted(
    db_session, parent_user
):
    """If the SE was deleted in the new version (new_se=None), fall back
    to old_se.cb_code so historical artifacts pinned to that SE get
    reflagged. classify_se_change returns substantive when one side is
    None and the other has a populated cb_code (per 3G-1's edge case)."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-DELETED-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=parent_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    pair = {
        "old_se": _se(cb_code=cb_code),
        "new_se": None,  # SE removed in the new version
        "from_version": "2020-rev1",
        "to_version": "2024",
    }
    result = apply_version_cascade([pair], db_session)
    db_session.commit()
    db_session.refresh(sg)

    assert sg.state == ArtifactState.PENDING_REVIEW
    assert sg.id in result.flagged_artifact_ids
    assert result.substantive_se_codes == [cb_code]
