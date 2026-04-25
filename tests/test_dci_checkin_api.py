"""Tests for the DCI check-in API (CB-DCI-001 M0-4, #4139).

Covers
------
- 3 happy paths: photo only, voice only, text only (each returns 202 +
  job_id + classification chip + accepted_at)
- multi-artifact happy path: photo + voice + text together
- auth: missing token returns 401
- feature flag OFF returns 403 (and short-circuits before classifier)
- 422 invalid: no inputs / oversize photo / oversize text
- rate-limit: 11th request in a minute returns 429
- PATCH .../correct works as a best-effort no-op when M0-2 model is absent
- GET .../status returns the M0 stub payload

Cross-stripe stubs (M0-2 / M0-5 / M0-6) — see ``app/api/routes/dci.py``
docstring.
"""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"dci_parent_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="DCI Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"dci_student_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="DCI Kid",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def kid(db_session, student_user):
    from app.models.student import Student

    s = Student(user_id=student_user.id, grade_level=5)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture()
def linked_parent(db_session, parent_user, kid):
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(parent_id=parent_user.id, student_id=kid.id)
    )
    db_session.commit()
    return parent_user


@pytest.fixture()
def dci_flag_on(db_session):
    """Force the dci_v1_enabled feature flag ON for the test, OFF after."""
    from app.models.feature_flag import FeatureFlag

    existing = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "dci_v1_enabled")
        .first()
    )
    if existing is None:
        existing = FeatureFlag(
            key="dci_v1_enabled",
            name="DCI Daily Check-In",
            description="CB-DCI-001 V1 feature gate",
            enabled=True,
        )
        db_session.add(existing)
    else:
        existing.enabled = True
    db_session.commit()
    yield
    existing.enabled = False
    db_session.commit()


@pytest.fixture()
def mock_classifier():
    """Bypass the OpenAI network call with a deterministic classification."""
    from app.services.dci_classifier import ClassificationResult

    fake = ClassificationResult(
        subject="Math",
        topic="Fractions: adding unlike denominators",
        deadline_iso="2026-04-30",
        confidence=0.86,
    )
    with patch(
        "app.api.routes.dci.classify_artifact", AsyncMock(return_value=fake)
    ) as m:
        yield m


# ── Tiny binary fixtures ──────────────────────────────────────────────

_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
    b"\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _photo_part(name: str = "snap.png", payload: bytes | None = None):
    return ("photo", (name, io.BytesIO(payload or _PNG_1x1), "image/png"))


def _voice_part(name: str = "today.webm", payload: bytes = b"\x00" * 32):
    return ("voice", (name, io.BytesIO(payload), "audio/webm"))


# ── Happy paths ───────────────────────────────────────────────────────


def test_checkin_photo_only_returns_202(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        files=[_photo_part()],
        data={"kid_id": str(kid.id)},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["job_id"].startswith(f"dci-{kid.id}-")
    assert body["classification"]["subject"] == "Math"
    assert body["classification"]["confidence"] == 0.86
    assert body["accepted_at"]
    mock_classifier.assert_awaited()


def test_checkin_voice_only_returns_202(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        files=[_voice_part()],
        data={"kid_id": str(kid.id)},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["classification"]["topic"].startswith("Fractions")


def test_checkin_text_only_returns_202(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        data={"kid_id": str(kid.id), "text": "Today we did fractions and got homework"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["classification"]["subject"] == "Math"


def test_checkin_multi_artifact_returns_202(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        files=[_photo_part(), _voice_part()],
        data={"kid_id": str(kid.id), "text": "Math handout + quick voice note"},
    )
    assert resp.status_code == 202, resp.text


def test_checkin_as_kid_user_does_not_need_kid_id(
    client, db_session, kid, student_user, dci_flag_on, mock_classifier
):
    headers = _auth(client, student_user.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        data={"text": "I learned fractions today"},
    )
    assert resp.status_code == 202, resp.text


# ── Auth ──────────────────────────────────────────────────────────────


def test_checkin_without_auth_returns_401(client):
    resp = client.post(
        "/api/dci/checkin",
        data={"text": "test"},
    )
    assert resp.status_code == 401


def test_checkin_parent_cannot_submit_for_unlinked_kid(
    client, db_session, parent_user, kid, dci_flag_on, mock_classifier
):
    """Parent NOT linked to this kid cannot submit."""
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        data={"kid_id": str(kid.id), "text": "should be 404"},
    )
    assert resp.status_code == 404


# ── Feature flag ──────────────────────────────────────────────────────


def test_checkin_flag_off_returns_403(
    client, db_session, kid, linked_parent, mock_classifier
):
    """When the dci_v1_enabled flag is missing/OFF, every route returns 403."""
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        data={"kid_id": str(kid.id), "text": "blocked"},
    )
    assert resp.status_code == 403
    # Classifier must NOT have been called when flag is OFF.
    mock_classifier.assert_not_called()


def test_checkin_flag_off_short_circuits_before_rate_limit(
    client, db_session, kid, linked_parent, mock_classifier, app
):
    """PR-review pass 1 [I1]: 403 must fire BEFORE the 10/min limiter
    decrements. Flag-OFF traffic should not be able to burn through the
    kid's rate-limit bucket. Mirrors `test_stream_flag_off_returns_403_before_rate_limit`
    in CB-TUTOR-002."""
    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        headers = _auth(client, linked_parent.email)
        # Far more than 10 — if the limiter ran first we'd see a 429
        # before this loop ended.
        for _ in range(15):
            resp = client.post(
                "/api/dci/checkin",
                headers=headers,
                data={"kid_id": str(kid.id), "text": "blocked"},
            )
            assert resp.status_code == 403
    finally:
        app.state.limiter.enabled = False
        app.state.limiter.reset()


# ── 422 / 413 invalid input ───────────────────────────────────────────


def test_checkin_no_inputs_returns_422(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        data={"kid_id": str(kid.id)},
    )
    assert resp.status_code == 422, resp.text
    assert "at least one" in resp.json()["detail"].lower()


def test_checkin_oversize_text_returns_422(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        data={"kid_id": str(kid.id), "text": "x" * 281},
    )
    assert resp.status_code == 422
    assert "280" in resp.json()["detail"]


def test_checkin_oversize_photo_returns_413(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    big = b"\x00" * (500 * 1024 + 1)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        files=[_photo_part(name="big.png", payload=big)],
        data={"kid_id": str(kid.id)},
    )
    assert resp.status_code == 413
    assert "500" in resp.json()["detail"]


def test_checkin_wrong_photo_content_type_returns_422(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier
):
    headers = _auth(client, linked_parent.email)
    resp = client.post(
        "/api/dci/checkin",
        headers=headers,
        files=[("photo", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))],
        data={"kid_id": str(kid.id)},
    )
    assert resp.status_code == 422
    assert "image/" in resp.json()["detail"]


# ── Rate-limit ────────────────────────────────────────────────────────


def test_checkin_rate_limit_exceeded_returns_429(
    client, db_session, kid, linked_parent, dci_flag_on, mock_classifier, app
):
    """11th request in the same minute should trip the 10/min limit."""
    headers = _auth(client, linked_parent.email)
    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        for _ in range(10):
            resp = client.post(
                "/api/dci/checkin",
                headers=headers,
                data={"kid_id": str(kid.id), "text": "ok"},
            )
            assert resp.status_code == 202, resp.text

        resp = client.post(
            "/api/dci/checkin",
            headers=headers,
            data={"kid_id": str(kid.id), "text": "too many"},
        )
        assert resp.status_code == 429
    finally:
        app.state.limiter.enabled = False
        app.state.limiter.reset()


# ── Status + correct ──────────────────────────────────────────────────


def test_status_returns_stub_state(
    client, db_session, kid, linked_parent, dci_flag_on
):
    headers = _auth(client, linked_parent.email)
    resp = client.get("/api/dci/checkin/123/status", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkin_id"] == 123
    assert body["state"] == "pending"
    assert body["voice_transcribed"] is False
    assert body["summary_ready"] is False


def test_status_flag_off_returns_403(client, db_session, kid, linked_parent):
    headers = _auth(client, linked_parent.email)
    resp = client.get("/api/dci/checkin/1/status", headers=headers)
    assert resp.status_code == 403


def test_correct_returns_corrected_false_when_model_missing(
    client, db_session, kid, linked_parent, dci_flag_on
):
    """Until M0-2 lands, PATCH /correct degrades to a no-op (200, corrected=false)."""
    headers = _auth(client, linked_parent.email)
    resp = client.patch(
        "/api/dci/checkin/999/correct",
        headers=headers,
        json={"subject": "Science"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkin_id"] == 999
    # Either corrected=False (M0-2 not yet shipped) OR 404 if M0-2 + missing row.
    # In this test the M0-2 model file is not on disk, so corrected=False is expected.
    assert body["corrected"] is False


def test_kid_checkin_resolves_linked_parent_not_self(
    db_session, kid, student_user, linked_parent
):
    """PR-review pass 1 [C1]: when a kid checks in, the row's parent_id
    must reference the LINKED parent, not the kid's own user_id."""
    from app.api.routes.dci import _resolve_parent_id_for_kid

    resolved = _resolve_parent_id_for_kid(db=db_session, kid_id=kid.id)
    assert resolved == linked_parent.id
    assert resolved != student_user.id


def test_kid_checkin_with_no_linked_parent_returns_none(db_session, kid):
    """A kid with no linked parent gets None — persistence is skipped
    rather than FK-violating once M0-2 lands."""
    from app.api.routes.dci import _resolve_parent_id_for_kid

    assert _resolve_parent_id_for_kid(db=db_session, kid_id=kid.id) is None


def test_correct_requires_at_least_one_field(
    client, db_session, kid, linked_parent, dci_flag_on
):
    headers = _auth(client, linked_parent.email)
    resp = client.patch(
        "/api/dci/checkin/1/correct",
        headers=headers,
        json={},
    )
    assert resp.status_code == 422
