"""Unit tests for the 3I-2 composition (#4664) of M1-D validators with the
3I-1 embedding-similarity validator.

The pipeline's existing M1-D first-pass (declared coverage) and the second-pass
``AlignmentValidator`` are stubbed; the third-pass embedding validator is
patched at the ``app.services.cmcp.validation_pipeline.validate_embedding_alignment``
seam so no DB row lookups or OpenAI calls happen.

Scenarios (per #4664 task spec):
1. First-pass pass + second-pass pass → flag_for_review=False
2. First-pass pass + second-pass fail → flag_for_review=True
3. First-pass fail (skip second-pass) → flag_for_review=True with first-pass reason

Plus structural coverage:
4. embedding_scores / embedding_threshold / failed_embedding_ses populated on success
5. embedding_threshold forwarded when caller overrides
6. Backwards compat — without ``db`` the new fields stay None / empty and
   legacy ``flag_for_review`` (score-based) semantics hold.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cmcp.alignment_validator import ValidationResult
from app.services.cmcp.validation_pipeline import (
    ValidationPipeline,
    ValidationPipelineResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _second_pass(
    *,
    passed: bool,
    coverage_rate: float,
    matched: list[str],
    uncovered: list[str],
    flag: bool | None = None,
    error: str | None = None,
) -> ValidationResult:
    return ValidationResult(
        passed=passed,
        coverage_rate=coverage_rate,
        matched_se_codes=matched,
        uncovered_se_codes=uncovered,
        flag_for_review=flag if flag is not None else (coverage_rate < 0.95),
        second_pass_concepts=[],
        error=error,
    )


class _StubAlignmentValidator:
    """Duck-typed stand-in for ``AlignmentValidator``; returns a fixed result."""

    def __init__(self, result: ValidationResult):
        self._result = result
        self.calls: list[dict] = []

    async def validate(
        self,
        generated_content: str,
        expected_se_codes: list[str],
        grade: int,
        subject_code: str,
    ) -> ValidationResult:
        self.calls.append({
            "generated_content": generated_content,
            "expected_se_codes": list(expected_se_codes),
            "grade": grade,
            "subject_code": subject_code,
        })
        return self._result


def _emb_result(
    *,
    passed: bool,
    scores: dict[str, float],
    threshold: float = 0.65,
    failed_ses: list[str] | None = None,
    error: str | None = None,
) -> dict:
    """Build an ``EmbeddingAlignmentResult``-shaped dict for the mock."""
    if failed_ses is None:
        failed_ses = [c for c, s in scores.items() if s < threshold]
    return {
        "passed": passed,
        "scores": dict(scores),
        "threshold": threshold,
        "failed_ses": list(failed_ses),
        "error": error,
    }


def _patch_embedding(coro_or_value):
    """Patch the ``validate_embedding_alignment`` import inside the pipeline.

    Note we patch the symbol at its USE site
    (``app.services.cmcp.validation_pipeline.validate_embedding_alignment``)
    rather than at its definition site, because ``validation_pipeline``
    imports the function with ``from … import …`` — patching the source
    module would not rebind the imported reference.
    """
    if isinstance(coro_or_value, dict):
        return patch(
            "app.services.cmcp.validation_pipeline.validate_embedding_alignment",
            new_callable=AsyncMock,
            return_value=coro_or_value,
        )
    return patch(
        "app.services.cmcp.validation_pipeline.validate_embedding_alignment",
        new=coro_or_value,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — first-pass pass + second-pass pass → flag_for_review=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_both_pass_flag_false():
    """M1-D both_passed AND embedding passed → flag_for_review=False."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4"]
    stub = _StubAlignmentValidator(_second_pass(
        passed=True,
        coverage_rate=1.0,
        matched=list(expected),
        uncovered=[],
    ))
    pipeline = ValidationPipeline(validator=stub)

    sentinel_db = object()  # the embedding mock ignores it
    emb = _emb_result(
        passed=True,
        scores={"MTH1W-B2.3": 0.91, "MTH1W-B2.4": 0.88},
    )

    with _patch_embedding(emb) as mock_emb:
        result = await pipeline.validate(
            generated_content="A guide on quadratics.",
            model_self_report_se_codes=expected,
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
            db=sentinel_db,
        )

    assert isinstance(result, ValidationPipelineResult)
    assert result.both_passed is True
    assert result.flag_for_review is False
    # Embedding mock was called exactly once with the right wiring.
    mock_emb.assert_awaited_once()
    call = mock_emb.await_args
    assert call.kwargs["content"] == "A guide on quadratics."
    assert call.kwargs["se_codes"] == expected
    assert call.kwargs["db"] is sentinel_db
    assert call.kwargs["threshold"] == pytest.approx(0.65)
    # Embedding fields populated.
    assert result.embedding_scores == {"MTH1W-B2.3": 0.91, "MTH1W-B2.4": 0.88}
    assert result.embedding_threshold == pytest.approx(0.65)
    assert result.failed_embedding_ses == []


# ---------------------------------------------------------------------------
# Scenario 2 — first-pass pass + second-pass fail → flag_for_review=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_first_pass_then_embedding_fail_flags():
    """M1-D both_passed BUT embedding fails → flag_for_review=True."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4"]
    stub = _StubAlignmentValidator(_second_pass(
        passed=True,
        coverage_rate=1.0,
        matched=list(expected),
        uncovered=[],
    ))
    pipeline = ValidationPipeline(validator=stub)

    emb = _emb_result(
        passed=False,
        scores={"MTH1W-B2.3": 0.71, "MTH1W-B2.4": 0.20},
        failed_ses=["MTH1W-B2.4"],
    )

    with _patch_embedding(emb) as mock_emb:
        result = await pipeline.validate(
            generated_content="Mostly off-topic content.",
            model_self_report_se_codes=expected,
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
            db=object(),
        )

    # M1-D layer still reports both_passed=True (declared + Claude OK).
    assert result.both_passed is True
    # 3I-2 escalates to flag_for_review=True because embedding failed.
    assert result.flag_for_review is True
    mock_emb.assert_awaited_once()
    assert result.embedding_scores == {"MTH1W-B2.3": 0.71, "MTH1W-B2.4": 0.20}
    assert result.failed_embedding_ses == ["MTH1W-B2.4"]
    assert result.embedding_threshold == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# Scenario 3 — first-pass fail → skip embedding, flag_for_review=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_first_pass_fail_skips_embedding():
    """When M1-D both_passed=False, embedding pass is skipped (cost saver)
    and flag_for_review=True with the M1-D failure preserved on
    ``second_pass_result``.
    """
    expected = ["A1", "A2", "A3", "A4", "A5"]
    # Second-pass (Claude) reports low coverage → 1D-1 fails.
    stub = _StubAlignmentValidator(_second_pass(
        passed=False,
        coverage_rate=0.20,
        matched=["A1"],
        uncovered=["A2", "A3", "A4", "A5"],
        error="parse_error: simulated low coverage",
    ))
    pipeline = ValidationPipeline(validator=stub)

    with _patch_embedding(_emb_result(
        passed=True,
        scores={c: 0.99 for c in expected},
    )) as mock_emb:
        result = await pipeline.validate(
            generated_content="content",
            model_self_report_se_codes=expected,  # first pass = 1.0
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
            db=object(),
        )

    # M1-D first-pass passed (5/5) but second-pass failed → both_passed False.
    assert result.first_pass_coverage_rate == pytest.approx(1.0)
    assert result.second_pass_result.passed is False
    assert result.both_passed is False

    # Embedding pass MUST NOT have been called (cost saver).
    mock_emb.assert_not_awaited()

    # Flag for review and the M1-D second-pass error is preserved.
    assert result.flag_for_review is True
    assert result.second_pass_result.error == (
        "parse_error: simulated low coverage"
    )

    # Embedding result fields surface their "did not run on success" shape.
    assert result.embedding_scores is None
    assert result.failed_embedding_ses == []
    # Threshold is still echoed because the caller asked for embedding.
    assert result.embedding_threshold == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# Scenario 4 — first-pass declared coverage failure → skip embedding too
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_declared_coverage_fail_skips_embedding():
    """If declared first-pass coverage is below threshold, embedding is
    still skipped (M1-D both_passed=False)."""
    expected = ["A1", "A2", "A3", "A4", "A5"]
    stub = _StubAlignmentValidator(_second_pass(
        passed=True,
        coverage_rate=1.0,
        matched=expected,
        uncovered=[],
    ))
    pipeline = ValidationPipeline(validator=stub)

    with _patch_embedding(_emb_result(
        passed=True,
        scores={c: 0.99 for c in expected},
    )) as mock_emb:
        result = await pipeline.validate(
            generated_content="content",
            # Declared first-pass coverage = 1/5 = 0.20 → fails 0.80 gate.
            model_self_report_se_codes=["A1"],
            expected_se_codes=expected,
            grade=5,
            subject_code="MATH",
            db=object(),
        )

    assert result.first_pass_coverage_rate == pytest.approx(0.20)
    assert result.both_passed is False
    mock_emb.assert_not_awaited()
    assert result.flag_for_review is True
    assert result.embedding_scores is None


# ---------------------------------------------------------------------------
# Scenario 5 — embedding_threshold override forwarded to validator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedding_threshold_override_forwarded():
    """Caller-supplied ``embedding_threshold`` reaches the embedding mock."""
    expected = ["A1"]
    stub = _StubAlignmentValidator(_second_pass(
        passed=True,
        coverage_rate=1.0,
        matched=expected,
        uncovered=[],
    ))
    pipeline = ValidationPipeline(validator=stub)

    with _patch_embedding(_emb_result(
        passed=True,
        scores={"A1": 0.80},
        threshold=0.75,
    )) as mock_emb:
        result = await pipeline.validate(
            generated_content="content",
            model_self_report_se_codes=expected,
            expected_se_codes=expected,
            grade=5,
            subject_code="MATH",
            db=object(),
            embedding_threshold=0.75,
        )

    mock_emb.assert_awaited_once()
    assert mock_emb.await_args.kwargs["threshold"] == pytest.approx(0.75)
    assert result.embedding_threshold == pytest.approx(0.75)
    assert result.flag_for_review is False


# ---------------------------------------------------------------------------
# Scenario 6 — backwards compat: no db → embedding skipped, legacy flag rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_db_preserves_legacy_flag_for_review():
    """When ``db`` is omitted, the embedding pass MUST NOT run and
    ``flag_for_review`` keeps the legacy score-based semantics.
    """
    expected = ["A1", "A2", "A3", "A4", "A5"]
    stub = _StubAlignmentValidator(_second_pass(
        passed=True,
        coverage_rate=0.95,  # at REVIEW_THRESHOLD boundary
        matched=["A1", "A2", "A3", "A4"],
        uncovered=["A5"],
    ))
    pipeline = ValidationPipeline(validator=stub)

    with _patch_embedding(_emb_result(
        passed=False,
        scores={c: 0.0 for c in expected},
    )) as mock_emb:
        result = await pipeline.validate(
            generated_content="content",
            model_self_report_se_codes=expected,
            expected_se_codes=expected,
            grade=5,
            subject_code="MATH",
            # no db → embedding should NOT run
        )

    mock_emb.assert_not_awaited()
    # alignment_score = mean(1.0, 0.95) = 0.975 → no flag.
    assert result.alignment_score == pytest.approx(0.975)
    assert result.flag_for_review is False
    # Backwards-compat fields default to None / empty.
    assert result.embedding_scores is None
    assert result.embedding_threshold is None
    assert result.failed_embedding_ses == []


# ---------------------------------------------------------------------------
# Scenario 7 — embedding error path (validator returns passed=False with error)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedding_pass_internal_error_flags_for_review():
    """3I-1 returns passed=False + populated error on internal failures
    (e.g., embedding API down). Pipeline must surface flag_for_review=True
    rather than re-raising.
    """
    expected = ["A1", "A2"]
    stub = _StubAlignmentValidator(_second_pass(
        passed=True,
        coverage_rate=1.0,
        matched=expected,
        uncovered=[],
    ))
    pipeline = ValidationPipeline(validator=stub)

    emb = _emb_result(
        passed=False,
        scores={"A1": 0.0, "A2": 0.0},
        failed_ses=expected,
        error="embedding_error: RuntimeError: api down",
    )
    with _patch_embedding(emb):
        result = await pipeline.validate(
            generated_content="content",
            model_self_report_se_codes=expected,
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
            db=object(),
        )

    assert result.both_passed is True  # M1-D layer is unaffected
    assert result.flag_for_review is True
    assert result.failed_embedding_ses == expected
    assert result.embedding_scores == {"A1": 0.0, "A2": 0.0}
