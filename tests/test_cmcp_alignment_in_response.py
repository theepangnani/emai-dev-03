"""Tests for CB-CMCP-001 M1-D 1D-3 (#4494) — alignment_score + flag_for_review
in the streaming completion event.

The 1E-1 streaming route (shipped) re-runs the 1D-2 ValidationPipeline over the
accumulated streamed content after the AI helper emits its terminal ``done``
envelope. The composed ``alignment_score`` + ``flag_for_review`` are stamped
onto the SSE ``event: complete`` payload so the frontend (1E-3, deferred) can
surface the soft "needs review" signal alongside the artifact.

Mocking strategy
----------------
- ``app.api.routes.cmcp_generate_stream.generate_content_stream`` is patched
  with a fake async generator that yields a deterministic chunk sequence — no
  real Claude streaming call.
- ``app.api.routes.cmcp_generate_stream.ValidationPipeline`` is patched with a
  stub class whose ``validate`` coroutine returns a hand-crafted
  ``ValidationPipelineResult`` — no real second-pass Claude validator call.

The test scenarios:

1. **Happy path** — high coverage → ``alignment_score`` near 1.0,
   ``flag_for_review=False``, validator received the accumulated content +
   expected SE codes + resolved grade/subject.
2. **Low-coverage flagging** — second pass below the review threshold →
   ``alignment_score`` reflects it and ``flag_for_review=True``.
3. **Validator failure is non-fatal** — pipeline raises mid-validation → the
   completion frame still ships with ``alignment_score=None`` +
   ``flag_for_review=False`` (and the artifact chunks were still streamed).
4. **Empty content skips the validator** — a stream with no chunks must not
   call into the validator (``alignment_score`` defaults to ``None``).
5. **Schema** — every completion frame still carries the existing curriculum
   fields (mutation-test guard against a regression that overwrote
   ``base_completion_payload``).
"""
from __future__ import annotations

import json as _json
from typing import AsyncIterator
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.services.cmcp.alignment_validator import ValidationResult
from app.services.cmcp.validation_pipeline import ValidationPipelineResult
from conftest import PASSWORD, _auth


# ── Flag fixtures (mirror test_cmcp_generate_stream.py) ─────────────────


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

    email = f"cmcpalign_{role.value.lower()}_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name=f"CMCPAlign {role.value}",
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


# ── CEG seed (uuid-suffixed subject so it doesn't clash with sibling tests) ──


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
    version_slug = f"test-align-{uuid4().hex[:6]}"

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


# ── Helpers ────────────────────────────────────────────────────────────


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


def _patch_stream(fake):
    return patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    )


def _make_pipeline_result(
    *,
    alignment_score: float,
    flag_for_review: bool,
    both_passed: bool = True,
    second_pass_rate: float | None = None,
) -> ValidationPipelineResult:
    """Build a ValidationPipelineResult shaped like the real composition."""
    if second_pass_rate is None:
        second_pass_rate = alignment_score
    return ValidationPipelineResult(
        both_passed=both_passed,
        alignment_score=alignment_score,
        first_pass_coverage_rate=alignment_score,
        second_pass_result=ValidationResult(
            passed=both_passed,
            coverage_rate=second_pass_rate,
            matched_se_codes=[],
            uncovered_se_codes=[],
            flag_for_review=flag_for_review,
            second_pass_concepts=[],
            error=None,
        ),
        flag_for_review=flag_for_review,
        matched_se_codes_union=[],
        uncovered_se_codes_intersection=[],
    )


class _StubPipeline:
    """Drop-in stub for ``ValidationPipeline``.

    The route instantiates ``ValidationPipeline()`` with no args and then
    awaits ``.validate(...)``. We patch the class symbol to this factory so
    every invocation returns the same canned result + records its kwargs for
    assertions.
    """

    calls: list[dict] = []
    next_result: ValidationPipelineResult | None = None
    raise_on_validate: bool = False

    def __init__(self, *_args, **_kwargs):
        pass

    async def validate(
        self,
        *,
        generated_content: str,
        model_self_report_se_codes: list[str],
        expected_se_codes: list[str],
        grade: int,
        subject_code: str,
        db=None,
        embedding_threshold: float | None = None,
    ) -> ValidationPipelineResult:
        _StubPipeline.calls.append({
            "generated_content": generated_content,
            "model_self_report_se_codes": list(model_self_report_se_codes),
            "expected_se_codes": list(expected_se_codes),
            "grade": grade,
            "subject_code": subject_code,
            "db": db,
            "embedding_threshold": embedding_threshold,
        })
        if _StubPipeline.raise_on_validate:
            raise RuntimeError("simulated validator failure")
        assert _StubPipeline.next_result is not None, (
            "_StubPipeline.next_result must be set before invocation"
        )
        return _StubPipeline.next_result


@pytest.fixture(autouse=True)
def _reset_stub_pipeline():
    """Reset ``_StubPipeline`` state between tests so cross-test leakage
    can't cause false passes (e.g., a stale ``next_result`` from another
    test silently satisfying a later assertion).
    """
    _StubPipeline.calls = []
    _StubPipeline.next_result = None
    _StubPipeline.raise_on_validate = False
    yield
    _StubPipeline.calls = []
    _StubPipeline.next_result = None
    _StubPipeline.raise_on_validate = False


def _patch_pipeline():
    return patch(
        "app.api.routes.cmcp_generate_stream.ValidationPipeline",
        _StubPipeline,
    )


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


# ─────────────────────────────────────────────────────────────────────
# Scenario 1 — happy path: high coverage → score near 1.0, no flag
# ─────────────────────────────────────────────────────────────────────


def test_happy_path_carries_alignment_score_and_flag_false(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Validator returns alignment_score=0.97 (above review threshold) →
    completion frame surfaces it verbatim with flag_for_review=False.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    _StubPipeline.next_result = _make_pipeline_result(
        alignment_score=0.97,
        flag_for_review=False,
    )

    fake = _make_fake_stream(["Fractions and decimals ", "are related."])
    with _patch_stream(fake), _patch_pipeline():
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    completion = _completion_dict(resp.text)
    assert completion["alignment_score"] == pytest.approx(0.97)
    assert completion["flag_for_review"] is False

    # Validator ran exactly once on the accumulated streamed content +
    # received the resolved grade/subject_code/SE list.
    assert len(_StubPipeline.calls) == 1
    call = _StubPipeline.calls[0]
    assert call["generated_content"] == "Fractions and decimals are related."
    assert call["expected_se_codes"] == ["B2.1", "B2.2"]
    assert call["model_self_report_se_codes"] == ["B2.1", "B2.2"]
    assert call["grade"] == 7
    assert call["subject_code"] == seeded_cmcp_curriculum["subject_code"]


# ─────────────────────────────────────────────────────────────────────
# Scenario 2 — low-coverage flagging
# ─────────────────────────────────────────────────────────────────────


def test_low_coverage_sets_flag_for_review_true(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Validator returns alignment_score=0.40 (below review threshold) →
    completion frame surfaces flag_for_review=True. Mutation-test guard:
    if the route hardcoded ``flag_for_review=False`` this would fail.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    _StubPipeline.next_result = _make_pipeline_result(
        alignment_score=0.40,
        flag_for_review=True,
        both_passed=False,
    )

    fake = _make_fake_stream(["Off-topic content about cats."])
    with _patch_stream(fake), _patch_pipeline():
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    completion = _completion_dict(resp.text)
    assert completion["alignment_score"] == pytest.approx(0.40)
    assert completion["flag_for_review"] is True


# ─────────────────────────────────────────────────────────────────────
# Scenario 3 — validator failure is non-fatal
# ─────────────────────────────────────────────────────────────────────


def test_validator_failure_yields_alignment_score_none(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """When ``ValidationPipeline.validate`` raises, the route must still
    emit a completion frame — alignment is a soft signal, not a generation
    gate. The artifact's chunks were already streamed; failing the entire
    request would lose them.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    _StubPipeline.raise_on_validate = True

    fake = _make_fake_stream(["Some content"])
    with _patch_stream(fake), _patch_pipeline():
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)
    # The chunks were streamed before the validator ran.
    chunk_frames = [f for f in frames if f["event"] == "message"]
    assert [f["data"] for f in chunk_frames] == ["Some content"]

    completion = _completion_dict(resp.text)
    assert completion["alignment_score"] is None
    assert completion["flag_for_review"] is False
    # Curriculum metadata still present — only the alignment fields
    # degraded.
    assert completion["se_codes_targeted"] == ["B2.1", "B2.2"]
    # 1F-3 parent_companion key still present (defaults to None for
    # parent persona).
    assert completion["parent_companion"] is None


# ─────────────────────────────────────────────────────────────────────
# Scenario 4 — empty content skips the validator
# ─────────────────────────────────────────────────────────────────────


def test_empty_content_skips_validator(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """A stream that yields only whitespace (or no chunks) must not call
    the validator — there's nothing to validate. ``alignment_score=None``
    on the completion frame conveys "validator skipped" rather than
    "score=0".
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    fake = _make_fake_stream(["   "])  # whitespace-only chunk
    with _patch_stream(fake), _patch_pipeline():
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    completion = _completion_dict(resp.text)
    assert completion["alignment_score"] is None
    assert completion["flag_for_review"] is False
    # Validator was never invoked.
    assert _StubPipeline.calls == []


# ─────────────────────────────────────────────────────────────────────
# Scenario 5 — completion frame carries every existing curriculum field
# ─────────────────────────────────────────────────────────────────────


def test_completion_frame_preserves_existing_curriculum_fields(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """Mutation-test guard: a regression that replaced the existing
    ``base_completion_payload`` with a 1D-3-only dict would drop
    ``voice_module_id`` / ``voice_module_hash`` / ``persona`` /
    ``content_type``. Assert all four still ship.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum, content_type="ASSIGNMENT")

    _StubPipeline.next_result = _make_pipeline_result(
        alignment_score=0.99,
        flag_for_review=False,
    )

    fake = _make_fake_stream(["x"])
    with _patch_stream(fake), _patch_pipeline():
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    completion = _completion_dict(resp.text)
    assert completion["se_codes_targeted"] == ["B2.1", "B2.2"]
    assert completion["voice_module_id"] == "parent_coach_v1"
    assert isinstance(completion["voice_module_hash"], str)
    assert len(completion["voice_module_hash"]) == 64
    assert completion["persona"] == "parent"
    assert completion["content_type"] == "ASSIGNMENT"
    # And the new 1D-3 fields are also there.
    assert completion["alignment_score"] == pytest.approx(0.99)
    assert completion["flag_for_review"] is False


# ─────────────────────────────────────────────────────────────────────
# Scenario 6 — error frames bypass the validator entirely
# ─────────────────────────────────────────────────────────────────────


def test_ai_error_does_not_invoke_validator(
    client, parent_user, cmcp_flag_on, seeded_cmcp_curriculum
):
    """A mid-stream AI error short-circuits with an ``event: error`` frame
    and never reaches the validator — there's no valid artifact to
    validate. Mutation-test guard against a regression that ran the
    validator on partial content.
    """
    headers = _auth(client, parent_user.email)
    body = _payload(seeded_cmcp_curriculum)

    async def fake(*_args, **_kwargs):
        yield {"event": "chunk", "data": "partial..."}
        yield {"event": "error", "data": "AI generation failed"}

    with patch(
        "app.api.routes.cmcp_generate_stream.generate_content_stream",
        side_effect=fake,
    ), _patch_pipeline():
        resp = client.post(
            "/api/cmcp/generate/stream",
            json=body,
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    frames = _parse_sse(resp.text)
    error_frames = [f for f in frames if f["event"] == "error"]
    assert len(error_frames) == 1
    # No completion frame on a failed stream.
    assert not any(f["event"] == "complete" for f in frames)
    # Validator was never invoked.
    assert _StubPipeline.calls == []
