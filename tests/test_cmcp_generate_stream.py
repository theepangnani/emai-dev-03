"""Tests for the CB-CMCP-001 M1-E 1E-1 streaming route (#4481).

Four required scenarios per the issue body:

1. POST stream for STUDY_GUIDE → returns text/event-stream + chunks +
   completion event.
2. POST stream for QUIZ → 400 with the redirect message.
3. ``cmcp.enabled`` flag OFF → 403.
4. Unauthenticated request → 401.

Plus mutation-test guards that fall out cheaply:
- All three short-form types (QUIZ / WORKSHEET / PARENT_COMPANION) take
  the 400 redirect path — a regression that switched the gate to a
  hardcoded ``content_type == "QUIZ"`` would let WORKSHEET +
  PARENT_COMPANION through.
- All three long-form types (STUDY_GUIDE / SAMPLE_TEST / ASSIGNMENT)
  successfully reach the stream path — an inverted gate would 400 on
  these.
- Persona auto-derivation still applies in the streaming path (the
  completion event carries the resolved persona).
- A mock Claude error mid-stream surfaces as ``event: error`` with the
  helper-supplied message rather than a 500.
- Unknown subject / strand codes → 422 (not 500, not silent).

Mocking strategy
----------------
``app.services.ai_service.generate_content_stream`` is patched with a
fake async generator that yields the same ``{"event": ..., "data":
...}`` envelope the real helper does. Tests never make real
Claude/OpenAI calls.
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Flag fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def cmcp_flag_off(db_session):
    """Force ``cmcp.enabled`` OFF for the test."""
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

    email = f"cmcpstream_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPStream {role.value}",
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
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


# ── CEG seed ───────────────────────────────────────────────────────────


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
    """Seed a Grade-7 ``MATH-XXXX`` slice with one OE + two SEs.

    Mirrors ``test_cmcp_generate_route.py``'s seed but with its own
    uuid-suffixed subject code so the two test files don't clash on the
    session-scoped DB.
    """
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
    version_slug = f"test-stream-{uuid4().hex[:6]}"

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
        "subject": subject,
        "strand": strand,
        "version": version,
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
    """Build a baseline streaming-route body — defaults to STUDY_GUIDE."""
    body = {
        "grade": 7,
        "subject_code": seeded["subject_code"],
        "strand_code": seeded["strand_code"],
        "content_type": "STUDY_GUIDE",
        "difficulty": "GRADE_LEVEL",
    }
    body.update(overrides)
    return body


# ── Mock helpers ───────────────────────────────────────────────────────


def _make_fake_stream(
    chunks: list[str], terminal_event: dict | None = None
):
    """Build a fake ``generate_content_stream`` that emits known frames.

    Returns an async generator factory matching the helper's signature
    (``prompt, system_prompt, max_tokens, temperature``). The factory
    yields a chunk envelope per chunk in ``chunks`` then the
    ``terminal_event`` (defaults to a clean ``done`` frame).
    """
    if terminal_event is None:
        terminal_event = {
            "event": "done",
            "data": {"is_truncated": False, "full_content": "".join(chunks)},
        }

    async def fake(*_args, **_kwargs) -> AsyncIterator[dict]:
        for c in chunks:
            yield {"event": "chunk", "data": c}
        yield terminal_event

    return fake


def _patch_stream(fake):
    """Patch the route's reference to ``generate_content_stream``."""
    return patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    )


def _parse_sse(text: str) -> list[dict]:
    """Parse an SSE response body into a list of ``{event, data}`` dicts.

    Default event type is ``"message"`` (per the SSE spec) when no
    ``event:`` line is present. Useful for asserting both the stream
    frames and the explicit completion / error events.
    """
    frames: list[dict] = []
    for raw in text.split("\n\n"):
        block = raw.strip("\n")
        if not block:
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip())
        frames.append({"event": event, "data": "\n".join(data_lines)})
    return frames


# ─────────────────────────────────────────────────────────────────────
# Scenario 1 — STUDY_GUIDE happy path streams chunks + completion
# ─────────────────────────────────────────────────────────────────────


def test_stream_study_guide_returns_event_stream_with_chunks_and_complete(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Long-form STUDY_GUIDE flows through Claude streaming + emits a
    final ``event: complete`` frame carrying the curriculum metadata.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="STUDY_GUIDE")

    fake = _make_fake_stream(["Hello ", "world", "!"])
    with _patch_stream(fake):
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse(resp.text)
    # Three chunk frames + one complete frame.
    chunk_frames = [f for f in frames if f["event"] == "message"]
    complete_frames = [f for f in frames if f["event"] == "complete"]

    assert [f["data"] for f in chunk_frames] == ["Hello ", "world", "!"]
    assert len(complete_frames) == 1

    import json as _json
    completion = _json.loads(complete_frames[0]["data"])
    assert completion["se_codes_targeted"] == ["B2.1", "B2.2"]
    assert completion["voice_module_id"] is None
    assert completion["persona"] == "parent"  # parent_user → parent
    assert completion["content_type"] == "STUDY_GUIDE"


@pytest.mark.parametrize(
    "long_form_type", ["STUDY_GUIDE", "SAMPLE_TEST", "ASSIGNMENT"]
)
def test_stream_all_long_form_types_succeed(
    client,
    parent_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
    long_form_type,
):
    """All three long-form types reach the stream path. Mutation-test
    guard for an inverted ``_LONG_FORM_CONTENT_TYPES`` membership check.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type=long_form_type)

    fake = _make_fake_stream(["chunk-1"])
    with _patch_stream(fake):
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)
    assert any(f["event"] == "complete" for f in frames)


# ─────────────────────────────────────────────────────────────────────
# Scenario 2 — short-form content types → 400 with redirect message
# ─────────────────────────────────────────────────────────────────────


def test_stream_quiz_returns_400_with_redirect_message(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Short-form QUIZ is rejected with 400 + canonical redirect text."""
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="QUIZ")

    # No mock needed — the gate fires before the AI call.
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "/api/cmcp/generate" in detail
    assert "sync" in detail.lower()


@pytest.mark.parametrize(
    "short_form_type", ["QUIZ", "WORKSHEET", "PARENT_COMPANION"]
)
def test_stream_all_short_form_types_return_400(
    client,
    parent_user,
    cmcp_flag_on,
    seeded_cmcp_curriculum,
    short_form_type,
):
    """All three short-form types are rejected with 400. Mutation-test
    guard for a hardcoded ``content_type == "QUIZ"`` regression.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type=short_form_type)
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────
# Scenario 3 — flag OFF → 403
# ─────────────────────────────────────────────────────────────────────


def test_stream_flag_off_returns_403(
    client, parent_user, cmcp_flag_off, seeded_cmcp_curriculum
):
    headers = _auth(client, parent_user.email)
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=_payload(seeded_cmcp_curriculum),
        headers=headers,
    )
    assert resp.status_code == 403
    assert "CB-CMCP-001" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────
# Scenario 4 — unauthenticated → 401
# ─────────────────────────────────────────────────────────────────────


def test_stream_without_auth_returns_401(
    client, cmcp_flag_on, seeded_cmcp_curriculum
):
    """No Authorization header → 401 regardless of flag state."""
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=_payload(seeded_cmcp_curriculum),
    )
    assert resp.status_code == 401


def test_stream_without_auth_returns_401_even_when_flag_off(
    client, cmcp_flag_off, seeded_cmcp_curriculum
):
    """Auth check fires *before* the flag check — flag-state probing
    without a valid token must not be possible. Mutation-test guard for
    a regression that flipped the order in ``require_cmcp_enabled``.
    """
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=_payload(seeded_cmcp_curriculum),
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# Persona auto-derivation in the streaming path
# ─────────────────────────────────────────────────────────────────────


def test_stream_derives_persona_from_role(
    client, teacher_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Teacher role → completion event carries persona="teacher". The
    sync route already covers parent / student / teacher exhaustively;
    one role here is enough to confirm the streaming path delegates to
    the same ``_derive_persona`` helper.
    """
    headers = _auth(client, teacher_user.email)
    body = _payload(seeded_cmcp_curriculum)

    fake = _make_fake_stream(["x"])
    with _patch_stream(fake):
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)
    complete = next(f for f in frames if f["event"] == "complete")
    import json as _json
    completion = _json.loads(complete["data"])
    assert completion["persona"] == "teacher"


# ─────────────────────────────────────────────────────────────────────
# Mid-stream error from the AI helper → event: error frame
# ─────────────────────────────────────────────────────────────────────


def test_stream_ai_error_emits_error_frame(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """When ``generate_content_stream`` yields an ``error`` envelope the
    route surfaces it as a terminal ``event: error`` frame and stops.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    fake = _make_fake_stream(
        chunks=["partial..."],
        terminal_event={
            "event": "error",
            "data": "AI generation failed: APITimeoutError",
        },
    )
    with _patch_stream(fake):
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)
    error_frames = [f for f in frames if f["event"] == "error"]
    assert len(error_frames) == 1
    assert "APITimeoutError" in error_frames[0]["data"]
    # No completion frame on a failed stream.
    assert not any(f["event"] == "complete" for f in frames)


# ─────────────────────────────────────────────────────────────────────
# Resolution failures still 422 in the streaming path
# ─────────────────────────────────────────────────────────────────────


def test_stream_unknown_subject_code_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Unknown subject_code must surface as 422 *before* the SSE stream
    opens — easier to handle on the client than a stream that immediately
    closes with an error frame.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, subject_code="UNKNOWNXYZ")
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "UNKNOWNXYZ" in resp.json()["detail"]


def test_stream_no_curriculum_match_returns_422(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """The seed has G7 SEs only — request G2 to get an empty CEG match
    and surface ``NoCurriculumMatchError`` as 422 *before* opening the
    stream.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, grade=2)
    resp = client.post(
        "/api/cmcp/generate/stream",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "specific expectations" in resp.json()["detail"].lower()
