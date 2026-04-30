"""Tests for CB-CMCP-001 M3β 3E-4 — LTI 1.3 link-out stub (#4655).

Covers
------
- Valid signed token → 302 redirect to ``/parent/companion/{id}``.
- Invalid signature → 401.
- Expired token → 401.
- Unknown artifact → 404.
- Wrong-type token (e.g. an access token) → 401.
- ``artifact_id`` query mismatch with token claim → 401.
- Kid has no visibility on the artifact → 404 (no existence leak).

The endpoint is auth-free (JWT signature is the authorization proof),
so no ``Authorization`` header is sent on these requests — the
launching browser arrives at the URL directly from the LMS.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import jwt

from app.core.config import settings
from app.api.routes.lti_link import LTI_LAUNCH_TOKEN_TYPE
from conftest import PASSWORD


# ── Helpers ───────────────────────────────────────────────────────────


def _make_user(db_session, role):
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"lti_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"LTI {role.value}",
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


def _seed_artifact(db_session, user_id: int):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState

    artifact = StudyGuide(
        user_id=user_id,
        title="LTI test artifact",
        content="LTI launch test content.",
        guide_type="study_guide",
        state=ArtifactState.SELF_STUDY,
        requested_persona="parent",
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)
    return artifact


def _cleanup_artifact(db_session, artifact_id: int):
    from app.models.study_guide import StudyGuide

    db_session.query(StudyGuide).filter(
        StudyGuide.id == artifact_id
    ).delete(synchronize_session=False)
    db_session.commit()


def _sign_token(
    *,
    artifact_id: int,
    kid_id: int,
    expires_in_minutes: int = 30,
    token_type: str = LTI_LAUNCH_TOKEN_TYPE,
    secret: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Sign an LTI launch token. Knobs let tests forge each failure mode."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_in_minutes
    )
    payload = {
        "artifact_id": artifact_id,
        "kid_id": kid_id,
        "exp": expire,
        "type": token_type,
    }
    return jwt.encode(
        payload,
        secret if secret is not None else settings.secret_key,
        algorithm=algorithm if algorithm is not None else settings.algorithm,
    )


# ─────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────


def test_valid_token_returns_302_redirect(client, db_session, parent_user):
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        token = _sign_token(
            artifact_id=artifact.id, kid_id=parent_user.id
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={token}",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert (
            resp.headers["location"]
            == f"/parent/companion/{artifact.id}"
        )
    finally:
        _cleanup_artifact(db_session, artifact.id)


# ─────────────────────────────────────────────────────────────────────
# 401 paths
# ─────────────────────────────────────────────────────────────────────


def test_invalid_signature_returns_401(
    client, db_session, parent_user
):
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        # Sign with a different secret → signature won't verify against
        # the configured one.
        bad_token = _sign_token(
            artifact_id=artifact.id,
            kid_id=parent_user.id,
            secret="not-the-real-secret-key",
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={bad_token}",
            follow_redirects=False,
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid LTI token"
    finally:
        _cleanup_artifact(db_session, artifact.id)


def test_expired_token_returns_401(client, db_session, parent_user):
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        expired = _sign_token(
            artifact_id=artifact.id,
            kid_id=parent_user.id,
            expires_in_minutes=-1,  # already expired
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={expired}",
            follow_redirects=False,
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid LTI token"
    finally:
        _cleanup_artifact(db_session, artifact.id)


def test_wrong_token_type_returns_401(
    client, db_session, parent_user
):
    """A standard access-token JWT replayed against /lti/launch → 401."""
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        wrong_type = _sign_token(
            artifact_id=artifact.id,
            kid_id=parent_user.id,
            token_type="access",  # not lti_launch
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={wrong_type}",
            follow_redirects=False,
        )
        assert resp.status_code == 401
    finally:
        _cleanup_artifact(db_session, artifact.id)


def test_query_artifact_id_mismatch_returns_401(
    client, db_session, parent_user
):
    """Token issued for artifact A cannot be replayed against artifact B."""
    artifact_a = _seed_artifact(db_session, parent_user.id)
    artifact_b = _seed_artifact(db_session, parent_user.id)
    try:
        token = _sign_token(
            artifact_id=artifact_a.id, kid_id=parent_user.id
        )
        # Replay against artifact_b's URL
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact_b.id}&signed_token={token}",
            follow_redirects=False,
        )
        assert resp.status_code == 401
    finally:
        _cleanup_artifact(db_session, artifact_a.id)
        _cleanup_artifact(db_session, artifact_b.id)


def test_garbage_token_returns_401(client, db_session, parent_user):
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token=not.a.jwt",
            follow_redirects=False,
        )
        assert resp.status_code == 401
    finally:
        _cleanup_artifact(db_session, artifact.id)


# ─────────────────────────────────────────────────────────────────────
# 404 paths
# ─────────────────────────────────────────────────────────────────────


def test_unknown_artifact_returns_404(client, db_session, parent_user):
    """Token references a study_guides.id that doesn't exist."""
    bogus_id = 99_999_999
    token = _sign_token(artifact_id=bogus_id, kid_id=parent_user.id)
    resp = client.get(
        f"/api/lti/launch?artifact_id={bogus_id}&signed_token={token}",
        follow_redirects=False,
    )
    assert resp.status_code == 404


def test_unknown_kid_returns_404(client, db_session, parent_user):
    """``kid_id`` claim references a User row that doesn't exist."""
    artifact = _seed_artifact(db_session, parent_user.id)
    try:
        token = _sign_token(
            artifact_id=artifact.id, kid_id=99_999_999
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={token}",
            follow_redirects=False,
        )
        assert resp.status_code == 404
    finally:
        _cleanup_artifact(db_session, artifact.id)


def test_no_visibility_returns_404(
    client, db_session, parent_user, other_parent
):
    """Kid in token has no visibility on the artifact → collapsed 404."""
    # Artifact owned by other_parent; kid_id in token is an unrelated parent
    # who is not linked to other_parent. M3α visibility helper denies.
    artifact = _seed_artifact(db_session, other_parent.id)
    try:
        token = _sign_token(
            artifact_id=artifact.id, kid_id=parent_user.id
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={token}",
            follow_redirects=False,
        )
        assert resp.status_code == 404
    finally:
        _cleanup_artifact(db_session, artifact.id)


# ─────────────────────────────────────────────────────────────────────
# Query-param shape
# ─────────────────────────────────────────────────────────────────────


def test_missing_signed_token_returns_422(client):
    """FastAPI required-param validation kicks in before the handler."""
    resp = client.get(
        "/api/lti/launch?artifact_id=1", follow_redirects=False
    )
    assert resp.status_code == 422


def test_missing_artifact_id_returns_422(client):
    resp = client.get(
        "/api/lti/launch?signed_token=foo", follow_redirects=False
    )
    assert resp.status_code == 422
