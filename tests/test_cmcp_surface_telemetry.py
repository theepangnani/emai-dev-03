"""Tests for CB-CMCP-001 M3α 3C-5 — Surface integration telemetry helpers
(#4581).

Covers
------
- ``log_dispatched`` / ``log_rendered`` / ``log_ctr`` emit a single
  structured INFO log line with the documented ``extra=`` payload.
- Negative ``latency_ms_from_approve`` is clamped to 0.
- ``GET /api/cmcp/surfaces/{surface}/click``:
  * 422 for unknown surface.
  * 404 for unknown ``artifact_id``.
  * 404 for cross-visibility (unrelated parent → no existence leak).
  * 302 redirect + CTR log emitted on success.

All Claude/OpenAI calls are mocked (none required for this stripe — the
helpers are pure-logic and the click endpoint never hits AI).
"""
from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixture ──────────────────────────────────────────────────────


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


# ── User fixtures ─────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"cmcpsurface_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPSurface {role.value}",
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
def other_parent(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


# ── Artifact seed helper ──────────────────────────────────────────────


def _seed_artifact(db_session, user_id: int):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    artifact = StudyGuide(
        user_id=user_id,
        title="Test surface-telemetry artifact",
        content="Some content.",
        guide_type="study_guide",
        state=ArtifactState.SELF_STUDY,
        requested_persona="parent",
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


# ─────────────────────────────────────────────────────────────────────
# Helper unit tests — log shape
# ─────────────────────────────────────────────────────────────────────


def _capture_event(caplog, event_name: str):
    """Return the single LogRecord matching ``extra['event'] == event_name``.

    Asserts exactly one match so a future regression that double-emits
    the same event surfaces here rather than as a silent telemetry skew
    downstream.
    """
    matches = [
        rec
        for rec in caplog.records
        if getattr(rec, "event", None) == event_name
    ]
    assert len(matches) == 1, (
        f"Expected exactly 1 log line with event={event_name!r}, "
        f"got {len(matches)}"
    )
    return matches[0]


def test_log_dispatched_emits_structured_line(caplog):
    from app.services.cmcp.surface_telemetry import (
        SURFACE_BRIDGE,
        log_dispatched,
    )

    caplog.set_level(logging.INFO, logger="app.services.cmcp.surface_telemetry")
    log_dispatched(
        artifact_id=42, surface=SURFACE_BRIDGE, latency_ms_from_approve=1234
    )

    rec = _capture_event(caplog, "cmcp.surface.dispatched")
    assert rec.levelno == logging.INFO
    assert rec.artifact_id == 42
    assert rec.surface == "bridge"
    assert rec.latency_ms_from_approve == 1234
    assert isinstance(rec.dispatched_at, str) and rec.dispatched_at  # ISO ts


def test_log_dispatched_clamps_negative_latency(caplog):
    from app.services.cmcp.surface_telemetry import (
        SURFACE_DCI,
        log_dispatched,
    )

    caplog.set_level(logging.INFO, logger="app.services.cmcp.surface_telemetry")
    log_dispatched(
        artifact_id=7, surface=SURFACE_DCI, latency_ms_from_approve=-50
    )

    rec = _capture_event(caplog, "cmcp.surface.dispatched")
    assert rec.latency_ms_from_approve == 0


def test_log_rendered_emits_structured_line(caplog):
    from app.services.cmcp.surface_telemetry import (
        SURFACE_DIGEST,
        log_rendered,
    )

    caplog.set_level(logging.INFO, logger="app.services.cmcp.surface_telemetry")
    log_rendered(artifact_id=99, surface=SURFACE_DIGEST, user_id=12)

    rec = _capture_event(caplog, "cmcp.surface.rendered")
    assert rec.artifact_id == 99
    assert rec.surface == "digest"
    assert rec.user_id == 12
    assert isinstance(rec.rendered_at, str) and rec.rendered_at


def test_log_ctr_emits_structured_line(caplog):
    from app.services.cmcp.surface_telemetry import SURFACE_DCI, log_ctr

    caplog.set_level(logging.INFO, logger="app.services.cmcp.surface_telemetry")
    log_ctr(artifact_id=77, surface=SURFACE_DCI, user_id=21)

    rec = _capture_event(caplog, "cmcp.surface.ctr")
    assert rec.artifact_id == 77
    assert rec.surface == "dci"
    assert rec.user_id == 21
    assert isinstance(rec.clicked_at, str) and rec.clicked_at


def test_surfaces_constant_contains_three_known_paths():
    from app.services.cmcp.surface_telemetry import (
        SURFACE_BRIDGE,
        SURFACE_DCI,
        SURFACE_DIGEST,
        SURFACES,
    )

    assert SURFACES == frozenset(
        {SURFACE_BRIDGE, SURFACE_DCI, SURFACE_DIGEST}
    )
    assert {"bridge", "dci", "digest"} == set(SURFACES)


# ─────────────────────────────────────────────────────────────────────
# Click-redirect endpoint tests
# ─────────────────────────────────────────────────────────────────────


def test_click_redirect_unknown_surface_422(
    client, parent_user, cmcp_flag_on
):
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/cmcp/surfaces/notasurface/click?artifact_id=1",
        headers=headers,
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert "notasurface" in resp.json()["detail"]


def test_click_redirect_unknown_artifact_404(
    client, parent_user, cmcp_flag_on
):
    headers = _auth(client, parent_user.email)
    resp = client.get(
        "/api/cmcp/surfaces/bridge/click?artifact_id=9999999",
        headers=headers,
        follow_redirects=False,
    )
    assert resp.status_code == 404


def test_click_redirect_denies_cross_visibility(
    client, db_session, parent_user, other_parent, cmcp_flag_on
):
    """Unrelated parent → 404 (no existence leak)."""
    artifact = _seed_artifact(db_session, other_parent.id)
    try:
        headers = _auth(client, parent_user.email)
        resp = client.get(
            f"/api/cmcp/surfaces/bridge/click?artifact_id={artifact.id}",
            headers=headers,
            follow_redirects=False,
        )
        assert resp.status_code == 404
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_click_redirect_success_emits_ctr_and_302(
    client, db_session, parent_user, cmcp_flag_on, caplog
):
    """Creator sees 302 to canonical artifact view + CTR log emitted."""
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        caplog.set_level(
            logging.INFO, logger="app.services.cmcp.surface_telemetry"
        )
        headers = _auth(client, parent_user.email)
        resp = client.get(
            f"/api/cmcp/surfaces/dci/click?artifact_id={artifact.id}",
            headers=headers,
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == f"/parent/companion/{artifact.id}"

        rec = _capture_event(caplog, "cmcp.surface.ctr")
        assert rec.artifact_id == artifact.id
        assert rec.surface == "dci"
        assert rec.user_id == parent_user.id
    finally:
        from app.models.study_guide import StudyGuide

        db_session.query(StudyGuide).filter(
            StudyGuide.id == artifact.id
        ).delete(synchronize_session=False)
        db_session.commit()


def test_click_redirect_unauthenticated_401(client, cmcp_flag_on):
    resp = client.get(
        "/api/cmcp/surfaces/bridge/click?artifact_id=1",
        follow_redirects=False,
    )
    assert resp.status_code == 401
