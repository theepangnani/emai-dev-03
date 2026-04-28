"""CB-CMCP-001 M0-B 0B-3a — Curriculum-admin review backend tests (#4428).

Covers
------
- Auth gates: 401 unauthed, 403 for non-CURRICULUM_ADMIN, 403 when
  ``cmcp.enabled`` flag is OFF (even for a CURRICULUM_ADMIN).
- Happy paths for all four endpoints:
    * ``GET    /api/ceg/admin/review/pending``
    * ``POST   /api/ceg/admin/review/{id}/accept``
    * ``POST   /api/ceg/admin/review/{id}/reject``
    * ``PATCH  /api/ceg/admin/review/{id}``
- 404 for unknown id on each mutating endpoint.
- Edit validation: invalid ``expectation_type`` is rejected, empty body is
  rejected with 400, valid partial updates only touch the fields sent.
- Audit-log entries are written for accept / reject / edit and skipped for
  no-op edits.

The tests seed a real ``CEGExpectation`` row (the model from stripe 0A-1
is in the integration branch we forked from) so they exercise the live
schema rather than a stub.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Feature flag helpers ───────────────────────────────────────────────


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


@pytest.fixture()
def cmcp_flag_off(db_session):
    """Ensure ``cmcp.enabled`` exists and is OFF (default)."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "cmcp.enabled")
        .first()
    )
    if flag is not None and flag.enabled is True:
        flag.enabled = False
        db_session.commit()
    return flag


# ── User fixtures ──────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcp_review_{role.name.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"Review {role.name}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def curriculum_admin(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.CURRICULUM_ADMIN)


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


# ── CEG seed helpers ───────────────────────────────────────────────────


@pytest.fixture()
def ceg_seed(db_session):
    """Insert subject + strand + version + 2 expectations (1 pending, 1 accepted).

    Returns a dict with ``pending``, ``accepted``, ``subject``, ``strand``,
    ``version`` so tests can reference rows directly.
    """
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
    )

    code_suffix = uuid4().hex[:6].upper()
    subject = CEGSubject(code=f"MATH_{code_suffix}", name="Math Test")
    db_session.add(subject)
    db_session.flush()

    strand = CEGStrand(subject_id=subject.id, code="B", name="Number Sense")
    version = CurriculumVersion(
        subject_id=subject.id,
        grade=7,
        version=f"2020-rev1-{code_suffix}",
        change_severity=None,
    )
    db_session.add_all([strand, version])
    db_session.flush()

    pending = CEGExpectation(
        ministry_code=f"B2.1-{code_suffix}",
        cb_code=f"CB-G7-MATH-B2-SE1-{code_suffix}",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        description="Pending: paraphrase me",
        curriculum_version_id=version.id,
        active=False,
        review_state="pending",
    )
    accepted = CEGExpectation(
        ministry_code=f"B2.2-{code_suffix}",
        cb_code=f"CB-G7-MATH-B2-OE1-{code_suffix}",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_OVERALL,
        description="Already accepted",
        curriculum_version_id=version.id,
        active=True,
        review_state="accepted",
    )
    db_session.add_all([pending, accepted])
    db_session.commit()
    db_session.refresh(pending)
    db_session.refresh(accepted)

    return {
        "subject": subject,
        "strand": strand,
        "version": version,
        "pending": pending,
        "accepted": accepted,
    }


def _audit_entries_for(db_session, expectation_id, action):
    from app.models.audit_log import AuditLog

    return (
        db_session.query(AuditLog)
        .filter(
            AuditLog.resource_type == "ceg_expectation",
            AuditLog.resource_id == expectation_id,
            AuditLog.action == action,
        )
        .all()
    )


# ── Auth (401) ─────────────────────────────────────────────────────────


def test_pending_without_auth_returns_401(client):
    resp = client.get("/api/ceg/admin/review/pending")
    assert resp.status_code == 401


def test_accept_without_auth_returns_401(client):
    resp = client.post("/api/ceg/admin/review/1/accept")
    assert resp.status_code == 401


def test_reject_without_auth_returns_401(client):
    resp = client.post("/api/ceg/admin/review/1/reject")
    assert resp.status_code == 401


def test_edit_without_auth_returns_401(client):
    resp = client.patch(
        "/api/ceg/admin/review/1", json={"description": "x"}
    )
    assert resp.status_code == 401


# ── RBAC (403 for non-CURRICULUM_ADMIN) ────────────────────────────────


def test_pending_non_admin_returns_403(client, parent_user, cmcp_flag_on):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/ceg/admin/review/pending", headers=headers)
    assert resp.status_code == 403


def test_accept_non_admin_returns_403(client, parent_user, cmcp_flag_on, ceg_seed):
    headers = _auth(client, parent_user.email)
    resp = client.post(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}/accept",
        headers=headers,
    )
    assert resp.status_code == 403


def test_reject_non_admin_returns_403(client, parent_user, cmcp_flag_on, ceg_seed):
    headers = _auth(client, parent_user.email)
    resp = client.post(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}/reject",
        headers=headers,
    )
    assert resp.status_code == 403


def test_edit_non_admin_returns_403(client, parent_user, cmcp_flag_on, ceg_seed):
    headers = _auth(client, parent_user.email)
    resp = client.patch(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}",
        headers=headers,
        json={"description": "x"},
    )
    assert resp.status_code == 403


# ── Feature-flag gating (403 when cmcp.enabled is OFF) ─────────────────


def test_pending_flag_off_returns_403(client, curriculum_admin, cmcp_flag_off):
    headers = _auth(client, curriculum_admin.email)
    resp = client.get("/api/ceg/admin/review/pending", headers=headers)
    assert resp.status_code == 403
    assert "CB-CMCP-001" in resp.json()["detail"]


def test_accept_flag_off_returns_403(
    client, curriculum_admin, cmcp_flag_off, ceg_seed
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.post(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}/accept",
        headers=headers,
    )
    assert resp.status_code == 403


def test_reject_flag_off_returns_403(
    client, curriculum_admin, cmcp_flag_off, ceg_seed
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.post(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}/reject",
        headers=headers,
    )
    assert resp.status_code == 403


def test_edit_flag_off_returns_403(
    client, curriculum_admin, cmcp_flag_off, ceg_seed
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.patch(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}",
        headers=headers,
        json={"description": "x"},
    )
    assert resp.status_code == 403


# ── Happy paths ────────────────────────────────────────────────────────


def test_list_pending_returns_only_pending_rows(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.get("/api/ceg/admin/review/pending", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {row["id"] for row in body}
    assert ceg_seed["pending"].id in ids
    # The accepted row must NOT show up.
    assert ceg_seed["accepted"].id not in ids
    # Every returned row is in the pending state.
    assert all(row["review_state"] == "pending" for row in body)


def test_accept_marks_active_and_writes_audit(
    client, curriculum_admin, cmcp_flag_on, ceg_seed, db_session
):
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id

    resp = client.post(
        f"/api/ceg/admin/review/{eid}/accept", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == eid
    assert body["review_state"] == "accepted"
    assert body["active"] is True
    assert body["reviewed_by_user_id"] == curriculum_admin.id
    assert body["reviewed_at"] is not None

    # Audit log written exactly once.
    rows = _audit_entries_for(db_session, eid, "ceg_review_accept")
    assert len(rows) == 1
    audit = rows[0]
    assert audit.user_id == curriculum_admin.id


def test_reject_keeps_inactive_and_writes_audit(
    client, curriculum_admin, cmcp_flag_on, ceg_seed, db_session
):
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id

    resp = client.post(
        f"/api/ceg/admin/review/{eid}/reject",
        headers=headers,
        json={"review_notes": "Mis-extracted; SE belongs to a different strand"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["review_state"] == "rejected"
    assert body["active"] is False
    assert body["review_notes"] == (
        "Mis-extracted; SE belongs to a different strand"
    )

    rows = _audit_entries_for(db_session, eid, "ceg_review_reject")
    assert len(rows) == 1
    assert rows[0].user_id == curriculum_admin.id


def test_reject_with_no_body_works(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    """The reject body is optional — a bare POST should still flip state."""
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    resp = client.post(
        f"/api/ceg/admin/review/{eid}/reject", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["review_state"] == "rejected"


def test_edit_partial_update_persists_only_touched_fields(
    client, curriculum_admin, cmcp_flag_on, ceg_seed, db_session
):
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    original_ministry_code = ceg_seed["pending"].ministry_code

    resp = client.patch(
        f"/api/ceg/admin/review/{eid}",
        headers=headers,
        json={"description": "Paraphrased description"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["description"] == "Paraphrased description"
    # ministry_code must not change because it wasn't in the payload.
    assert body["ministry_code"] == original_ministry_code

    rows = _audit_entries_for(db_session, eid, "ceg_review_edit")
    assert len(rows) == 1


def test_edit_unknown_field_is_rejected_with_422(
    client, curriculum_admin, cmcp_flag_on, ceg_seed, db_session
):
    """Pydantic ``extra='forbid'`` rejects unknown fields — no silent drops.

    A reviewer who sends a typo'd field name (e.g., ``topic``, ``foo``)
    must get 422 so they know the change wasn't applied. Silent drops are
    the MFIPPA / curriculum-accuracy failure mode this product hardens
    against.
    """
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id

    resp = client.patch(
        f"/api/ceg/admin/review/{eid}",
        headers=headers,
        json={"topic": "fractions"},
    )
    assert resp.status_code == 422, resp.text

    # No audit row written when validation fails.
    rows = _audit_entries_for(db_session, eid, "ceg_review_edit")
    assert len(rows) == 0


def test_edit_parent_oe_self_reference_returns_400(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    """A row cannot be its own parent_oe (cycle prevention)."""
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    resp = client.patch(
        f"/api/ceg/admin/review/{eid}",
        headers=headers,
        json={"parent_oe_id": eid},
    )
    assert resp.status_code == 400
    assert "itself" in resp.json()["detail"]


def test_edit_parent_oe_unknown_id_returns_400(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    """parent_oe_id must reference an existing row."""
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    resp = client.patch(
        f"/api/ceg/admin/review/{eid}",
        headers=headers,
        json={"parent_oe_id": 999999},
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


def test_edit_parent_oe_must_be_overall_type(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    """parent_oe_id must point at an OE row (DD §2.1: SE → OE only)."""
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    # The 'pending' fixture row is itself a 'specific' (SE), so pointing
    # the accepted row's parent_oe at it should be rejected.
    accepted_id = ceg_seed["accepted"].id
    resp = client.patch(
        f"/api/ceg/admin/review/{accepted_id}",
        headers=headers,
        json={"parent_oe_id": eid},
    )
    assert resp.status_code == 400
    assert "overall" in resp.json()["detail"]


def test_edit_parent_oe_must_be_same_curriculum_version(
    client, curriculum_admin, cmcp_flag_on, ceg_seed, db_session
):
    """parent_oe_id must be in the same curriculum_version as the row."""
    from app.models.curriculum import (
        CEGExpectation,
        CurriculumVersion,
        EXPECTATION_TYPE_OVERALL,
    )

    # Spin up a second curriculum_version + an OE belonging to it.
    other_version = CurriculumVersion(
        subject_id=ceg_seed["subject"].id,
        grade=7,
        version=f"2020-rev2-{uuid4().hex[:6]}",
        change_severity=None,
    )
    db_session.add(other_version)
    db_session.flush()

    other_oe = CEGExpectation(
        ministry_code=f"X1.1-{uuid4().hex[:6]}",
        subject_id=ceg_seed["subject"].id,
        strand_id=ceg_seed["strand"].id,
        grade=7,
        expectation_type=EXPECTATION_TYPE_OVERALL,
        description="Cross-version OE",
        curriculum_version_id=other_version.id,
        active=True,
        review_state="accepted",
    )
    db_session.add(other_oe)
    db_session.commit()

    headers = _auth(client, curriculum_admin.email)
    resp = client.patch(
        f"/api/ceg/admin/review/{ceg_seed['pending'].id}",
        headers=headers,
        json={"parent_oe_id": other_oe.id},
    )
    assert resp.status_code == 400
    assert "curriculum_version" in resp.json()["detail"]


def test_edit_invalid_expectation_type_returns_422(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    resp = client.patch(
        f"/api/ceg/admin/review/{eid}",
        headers=headers,
        json={"expectation_type": "bogus"},
    )
    assert resp.status_code == 422


def test_edit_empty_body_returns_400(
    client, curriculum_admin, cmcp_flag_on, ceg_seed
):
    headers = _auth(client, curriculum_admin.email)
    eid = ceg_seed["pending"].id
    resp = client.patch(
        f"/api/ceg/admin/review/{eid}", headers=headers, json={}
    )
    assert resp.status_code == 400


# ── 404 ────────────────────────────────────────────────────────────────


def test_accept_unknown_id_returns_404(
    client, curriculum_admin, cmcp_flag_on
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.post(
        "/api/ceg/admin/review/999999/accept", headers=headers
    )
    assert resp.status_code == 404


def test_reject_unknown_id_returns_404(
    client, curriculum_admin, cmcp_flag_on
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.post(
        "/api/ceg/admin/review/999999/reject", headers=headers
    )
    assert resp.status_code == 404


def test_edit_unknown_id_returns_404(
    client, curriculum_admin, cmcp_flag_on
):
    headers = _auth(client, curriculum_admin.email)
    resp = client.patch(
        "/api/ceg/admin/review/999999",
        headers=headers,
        json={"description": "x"},
    )
    assert resp.status_code == 404
