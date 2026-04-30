"""Integration tests for CB-CMCP-001 M3β fu (#4696) — verify the production
streaming route now wires ``db`` through to ``ValidationPipeline.validate``
so the 3I-2 embedding-similarity third pass actually runs.

3I-2's whole point was wiring the embedding validator into M1-D's pipeline.
The validator implementation + backwards-compat were correct, but the only
production caller (``_run_alignment_pipeline`` in ``cmcp_generate_stream.py``)
did not pass ``db``, so the embedding pass never ran in real generation
requests. This module asserts that:

1. The route opens a session and forwards it to the pipeline.
2. The pipeline's embedding pass runs (a stubbed ``AlignmentValidator`` and
   ``validate_embedding_alignment`` are both invoked).
3. The completion event surfaces ``embedding_scores != None`` and
   ``embedding_threshold != None``.

Mocking strategy mirrors ``test_cmcp_alignment_in_response.py``:

- ``app.api.routes.cmcp_generate_stream.generate_content_stream`` is patched
  with a fake async generator yielding deterministic chunks — no real Claude
  streaming call.
- ``app.services.cmcp.validation_pipeline.AlignmentValidator`` is replaced
  with a stub whose ``validate`` returns a canned passing result — no real
  second-pass Claude call.
- ``app.services.cmcp.validation_pipeline.validate_embedding_alignment`` is
  patched with an ``AsyncMock`` returning a canned ``passed=True`` dict — no
  real OpenAI embedding call.

This is a true integration test: it runs the real ``ValidationPipeline``
composition logic end-to-end (M1-D first pass + stubbed second pass +
stubbed third pass) inside the real streaming route. The only mocked
boundaries are the external API calls.
"""
from __future__ import annotations

import json as _json
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.cmcp.alignment_validator import ValidationResult
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

    email = f"cmcpvpi_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPVPI {role.value}",
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


# ── CEG seed (uuid-suffixed subject so it doesn't clash with siblings) ──


@pytest.fixture()
def seeded_cmcp_curriculum(db_session):
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
    version_slug = f"test-vpi-{uuid4().hex[:6]}"

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
    }

    db_session.query(CEGExpectation).filter(
        CEGExpectation.id.in_(expectation_ids)
    ).delete(synchronize_session=False)
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


# ── Helpers ───────────────────────────────────────────────────────────


def _payload(seeded, **overrides):
    body = {
        "grade": 7,
        "subject_code": seeded["subject_code"],
        "strand_code": seeded["strand_code"],
        "content_type": "STUDY_GUIDE",
        "difficulty": "GRADE_LEVEL",
    }
    body.update(overrides)
    return body


def _make_fake_stream(chunks: list[str]):
    """Async generator factory yielding the chunk sequence + a clean done."""
    async def fake(*_args, **_kwargs) -> AsyncIterator[dict]:
        for c in chunks:
            yield {"event": "chunk", "data": c}
        yield {
            "event": "done",
            "data": {"is_truncated": False, "full_content": "".join(chunks)},
        }

    return fake


def _parse_sse(text: str) -> list[dict]:
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


def _completion_dict(resp_text: str) -> dict:
    frames = _parse_sse(resp_text)
    completion_frames = [f for f in frames if f["event"] == "complete"]
    assert len(completion_frames) == 1, (
        f"expected exactly one completion frame, got {completion_frames!r}"
    )
    return _json.loads(completion_frames[0]["data"])


class _StubAlignmentValidator:
    """Stub for ``AlignmentValidator`` — returns a canned passing second pass.

    The pipeline calls ``validator.validate(...)`` with kwargs. We record the
    invocation so tests can assert it ran.
    """

    calls: list[dict] = []

    def __init__(self, *_args, **_kwargs):
        pass

    async def validate(
        self,
        generated_content: str,
        expected_se_codes: list[str],
        grade: int,
        subject_code: str,
    ) -> ValidationResult:
        _StubAlignmentValidator.calls.append({
            "generated_content": generated_content,
            "expected_se_codes": list(expected_se_codes),
            "grade": grade,
            "subject_code": subject_code,
        })
        return ValidationResult(
            passed=True,
            coverage_rate=1.0,
            matched_se_codes=list(expected_se_codes),
            uncovered_se_codes=[],
            flag_for_review=False,
            second_pass_concepts=[],
            error=None,
        )


@pytest.fixture(autouse=True)
def _reset_stub_alignment_validator():
    _StubAlignmentValidator.calls = []
    yield
    _StubAlignmentValidator.calls = []


# ─────────────────────────────────────────────────────────────────────
# The integration test the issue acceptance criteria asks for.
# ─────────────────────────────────────────────────────────────────────


def test_streaming_route_runs_embedding_pass_and_surfaces_scores(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """End-to-end: the streaming route must thread a session into the pipeline
    so 3I-2's embedding validator actually runs in production.

    Asserts:
    - ``validate_embedding_alignment`` was awaited exactly once with a real
      Session (not None) and the route's expected SE codes.
    - The completion event carries ``embedding_scores != None`` and
      ``embedding_threshold != None`` (the explicit acceptance criterion).
    - ``flag_for_review=False`` because both M1-D + embedding passed.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    fake_embedding_result = {
        "passed": True,
        "scores": {"B2.1": 0.91, "B2.2": 0.88},
        "threshold": 0.65,
        "failed_ses": [],
        "error": None,
    }
    embedding_mock = AsyncMock(return_value=fake_embedding_result)

    fake_stream = _make_fake_stream(
        ["Fractions and decimals ", "are related."]
    )

    with patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake_stream,
    ), patch(
        "app.services.cmcp.validation_pipeline.AlignmentValidator",
        _StubAlignmentValidator,
    ), patch(
        "app.services.cmcp.validation_pipeline.validate_embedding_alignment",
        embedding_mock,
    ):
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text

    # Embedding validator was actually invoked — proves db was threaded
    # through. Pre-fix this assertion would fail (call count == 0).
    assert embedding_mock.await_count == 1, (
        "validate_embedding_alignment must run when streaming route "
        "supplies db to ValidationPipeline"
    )
    emb_call = embedding_mock.call_args
    # db kwarg must be a real SQLAlchemy session, not None.
    from sqlalchemy.orm import Session as _Session
    assert isinstance(emb_call.kwargs["db"], _Session), (
        f"expected SQLAlchemy Session for db, got {type(emb_call.kwargs['db'])!r}"
    )
    # Expected SE codes forwarded to the embedding validator.
    assert sorted(emb_call.kwargs["se_codes"]) == ["B2.1", "B2.2"]
    # Default threshold (0.65 per #4658 spec) flowed through.
    assert emb_call.kwargs["threshold"] == pytest.approx(0.65)

    # Second pass also ran (M1-D first/second composition).
    assert len(_StubAlignmentValidator.calls) == 1
    assert _StubAlignmentValidator.calls[0]["generated_content"] == (
        "Fractions and decimals are related."
    )

    # Acceptance criterion: completion event surfaces embedding fields.
    completion = _completion_dict(resp.text)
    assert completion["embedding_scores"] is not None
    assert completion["embedding_scores"] == {"B2.1": 0.91, "B2.2": 0.88}
    assert completion["embedding_threshold"] is not None
    assert completion["embedding_threshold"] == pytest.approx(0.65)
    # Both gates clear → no flag.
    assert completion["flag_for_review"] is False
    # Score = mean(1.0, 1.0) = 1.0 from the M1-D composition.
    assert completion["alignment_score"] == pytest.approx(1.0)


def test_streaming_route_skips_embedding_when_m1d_first_pass_fails(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Mutation-test guard: when M1-D's first pass fails, the embedding pass
    must be elided as a cost-saver. ``flag_for_review`` becomes True even
    though the embedding mock would have returned passed=True.

    This locks in 3I-2's "skip embedding if M1-D fails" cost-saver — without
    it, the route would spend an OpenAI round-trip on artifacts already
    flagged by the cheap M1-D composition.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    embedding_mock = AsyncMock(return_value={
        "passed": True,
        "scores": {"B2.1": 0.99, "B2.2": 0.99},
        "threshold": 0.65,
        "failed_ses": [],
        "error": None,
    })

    class _FailingSecondPass:
        """Second-pass coverage 0.20 → fails PASS_THRESHOLD."""

        def __init__(self, *_args, **_kwargs):
            pass

        async def validate(
            self,
            generated_content: str,
            expected_se_codes: list[str],
            grade: int,
            subject_code: str,
        ) -> ValidationResult:
            return ValidationResult(
                passed=False,
                coverage_rate=0.20,
                matched_se_codes=[],
                uncovered_se_codes=list(expected_se_codes),
                flag_for_review=True,
                second_pass_concepts=[],
                error=None,
            )

    fake_stream = _make_fake_stream(["Off-topic content."])

    with patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake_stream,
    ), patch(
        "app.services.cmcp.validation_pipeline.AlignmentValidator",
        _FailingSecondPass,
    ), patch(
        "app.services.cmcp.validation_pipeline.validate_embedding_alignment",
        embedding_mock,
    ):
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    # Embedding pass must NOT have run — M1-D failed first.
    assert embedding_mock.await_count == 0

    completion = _completion_dict(resp.text)
    # Threshold is still surfaced so consumers know an embedding pass was
    # attempted (db was supplied) — only ``embedding_scores`` is None
    # because the round-trip was elided.
    assert completion["embedding_scores"] is None
    assert completion["embedding_threshold"] == pytest.approx(0.65)
    assert completion["flag_for_review"] is True
