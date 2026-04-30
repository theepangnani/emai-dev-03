"""Tests for CB-CMCP-001 M3β 3E-4 — LTI 1.3 link-out stub (#4655).

Covers
------
- Valid signed token (kid is a STUDENT, owns the artifact) → 302
  redirect to ``/parent/companion/{id}``.
- Invalid signature → 401.
- Expired token → 401.
- Wrong-type token (e.g. an access token) → 401.
- ``artifact_id`` query mismatch with token claim → 401.
- Garbage non-JWT token → 401.
- Bool ``artifact_id`` claim (subclass of int) → 401.
- Unknown artifact → 404.
- Unknown kid → 404 (collapsed with unknown-artifact).
- Kid claim resolves to a non-STUDENT user (e.g. a PARENT) → 404
  (collapsed). The "kid_id" name promise is enforced.
- Kid (STUDENT) has no visibility on the artifact → 404 (no leak).

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


@pytest.fixture()
def student_user(db_session):
    """A STUDENT user — the "kid" the LTI launch represents."""
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def unrelated_student(db_session):
    """A STUDENT with no family link to ``parent_user``."""
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


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


def test_valid_token_returns_302_redirect(
    client, db_session, student_user
):
    """Happy path: STUDENT kid owns the artifact → 302 redirect."""
    artifact = _seed_artifact(db_session, student_user.id)
    try:
        token = _sign_token(
            artifact_id=artifact.id, kid_id=student_user.id
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
    client, db_session, student_user
):
    artifact = _seed_artifact(db_session, student_user.id)
    try:
        # Sign with a different secret → signature won't verify against
        # the configured one.
        bad_token = _sign_token(
            artifact_id=artifact.id,
            kid_id=student_user.id,
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


def test_expired_token_returns_401(client, db_session, student_user):
    artifact = _seed_artifact(db_session, student_user.id)
    try:
        expired = _sign_token(
            artifact_id=artifact.id,
            kid_id=student_user.id,
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
    client, db_session, student_user
):
    """A standard access-token JWT replayed against /lti/launch → 401."""
    artifact = _seed_artifact(db_session, student_user.id)
    try:
        wrong_type = _sign_token(
            artifact_id=artifact.id,
            kid_id=student_user.id,
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
    client, db_session, student_user
):
    """Token issued for artifact A cannot be replayed against artifact B."""
    artifact_a = _seed_artifact(db_session, student_user.id)
    artifact_b = _seed_artifact(db_session, student_user.id)
    try:
        token = _sign_token(
            artifact_id=artifact_a.id, kid_id=student_user.id
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


def test_garbage_token_returns_401(client, db_session, student_user):
    artifact = _seed_artifact(db_session, student_user.id)
    try:
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token=not.a.jwt",
            follow_redirects=False,
        )
        assert resp.status_code == 401
    finally:
        _cleanup_artifact(db_session, artifact.id)


def test_bool_artifact_id_claim_returns_401(
    client, db_session, student_user
):
    """``bool`` is a subclass of ``int`` in Python — must be rejected.

    Mutation-test guard: without the explicit ``isinstance(..., bool)``
    rejection in ``_decode_lti_token``, ``True`` would pass the int
    check and load row id=1 by silent coercion.
    """
    artifact = _seed_artifact(db_session, student_user.id)
    try:
        # Hand-roll a token with bool artifact_id (test helper takes int)
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        bad_payload = {
            "artifact_id": True,
            "kid_id": student_user.id,
            "exp": expire,
            "type": LTI_LAUNCH_TOKEN_TYPE,
        }
        bad_token = jwt.encode(
            bad_payload, settings.secret_key, algorithm=settings.algorithm
        )
        resp = client.get(
            f"/api/lti/launch?artifact_id={artifact.id}&signed_token={bad_token}",
            follow_redirects=False,
        )
        assert resp.status_code == 401
    finally:
        _cleanup_artifact(db_session, artifact.id)


# ─────────────────────────────────────────────────────────────────────
# 404 paths
# ─────────────────────────────────────────────────────────────────────


def test_unknown_artifact_returns_404(
    client, db_session, student_user
):
    """Token references a study_guides.id that doesn't exist."""
    bogus_id = 99_999_999
    token = _sign_token(artifact_id=bogus_id, kid_id=student_user.id)
    resp = client.get(
        f"/api/lti/launch?artifact_id={bogus_id}&signed_token={token}",
        follow_redirects=False,
    )
    assert resp.status_code == 404


def test_unknown_kid_returns_404(client, db_session, student_user):
    """``kid_id`` claim references a User row that doesn't exist."""
    artifact = _seed_artifact(db_session, student_user.id)
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


def test_non_student_kid_returns_404(
    client, db_session, parent_user, student_user
):
    """``kid_id`` resolving to a non-STUDENT (e.g. PARENT) → collapsed 404.

    Mutation-test guard: without the explicit STUDENT-role check, a
    board-issued token with ``kid_id`` pointing at a PARENT/ADMIN/etc.
    User would inherit that role's visibility bypass and grant launch
    access. The "kid_id" name promise — only students — is enforced
    here.
    """
    artifact = _seed_artifact(db_session, student_user.id)
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


def test_no_visibility_returns_404(
    client, db_session, unrelated_student, other_parent
):
    """STUDENT kid has no visibility on a different family's artifact → 404.

    Artifact owned by ``other_parent``; ``kid_id`` is a STUDENT with no
    parent_students link to ``other_parent``. The M3α visibility
    helper's family-pair check denies.
    """
    artifact = _seed_artifact(db_session, other_parent.id)
    try:
        token = _sign_token(
            artifact_id=artifact.id, kid_id=unrelated_student.id
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
