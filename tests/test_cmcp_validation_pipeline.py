"""Unit tests for app/services/cmcp/validation_pipeline.py — CB-CMCP-001 M1-D 1D-2 (#4473).

Composition tests: model self-report (first pass) + AlignmentValidator (second pass).
The second-pass `AlignmentValidator` is mocked via a stub class — no real Claude
calls are made.
"""

from __future__ import annotations

import pytest

from app.services.cmcp.alignment_validator import (
    PASS_THRESHOLD,
    REVIEW_THRESHOLD,
    ValidationResult,
)
from app.services.cmcp.validation_pipeline import (
    ValidationPipeline,
    ValidationPipelineResult,
)


# ---------------------------------------------------------------------------
# Helpers — stub AlignmentValidator (avoids any real Claude call)
# ---------------------------------------------------------------------------


def _make_second_pass_result(
    *,
    passed: bool,
    coverage_rate: float,
    matched_se_codes: list[str],
    uncovered_se_codes: list[str],
    flag_for_review: bool | None = None,
    error: str | None = None,
) -> ValidationResult:
    if flag_for_review is None:
        flag_for_review = coverage_rate < REVIEW_THRESHOLD
    return ValidationResult(
        passed=passed,
        coverage_rate=coverage_rate,
        matched_se_codes=matched_se_codes,
        uncovered_se_codes=uncovered_se_codes,
        flag_for_review=flag_for_review,
        second_pass_concepts=[],
        error=error,
    )


class _StubValidator:
    """Drop-in stand-in for ``AlignmentValidator`` that returns a fixed result.

    The pipeline only invokes ``validator.validate(...)`` so we don't need to
    subclass — duck-typing is enough. We still record the call kwargs so
    tests can assert the pipeline forwards them correctly.
    """

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


# ---------------------------------------------------------------------------
# Scenario 1 — Both passes succeed → both_passed=True, alignment_score >= 0.80
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_passes_succeed():
    """Full coverage on both passes → both_passed=True, score=1.0, no flag."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4"]
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=list(expected),
        uncovered_se_codes=[],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="A guide on quadratics and factoring.",
        model_self_report_se_codes=expected,
        expected_se_codes=expected,
        grade=9,
        subject_code="MTH1W",
    )

    assert isinstance(result, ValidationPipelineResult)
    assert result.both_passed is True
    assert result.alignment_score == pytest.approx(1.0)
    assert result.alignment_score >= 0.80  # acceptance criterion
    assert result.first_pass_coverage_rate == pytest.approx(1.0)
    assert result.second_pass_result.passed is True
    assert result.flag_for_review is False
    assert sorted(result.matched_se_codes_union) == sorted(expected)
    assert result.uncovered_se_codes_intersection == []


# ---------------------------------------------------------------------------
# Scenario 2 — First pass full coverage but second pass low → both_passed=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_pass_full_second_pass_low_fails():
    """Model claims everything but the independent second pass disagrees."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4", "MTH1W-B2.5", "MTH1W-B2.6", "MTH1W-B2.7"]
    # Second pass: 1/5 = 0.20 (well below PASS_THRESHOLD)
    stub = _StubValidator(_make_second_pass_result(
        passed=False,
        coverage_rate=0.20,
        matched_se_codes=["MTH1W-B2.3"],
        uncovered_se_codes=["MTH1W-B2.4", "MTH1W-B2.5", "MTH1W-B2.6", "MTH1W-B2.7"],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="Mostly off-topic content.",
        model_self_report_se_codes=expected,  # model claims full coverage
        expected_se_codes=expected,
        grade=9,
        subject_code="MTH1W",
    )

    # First pass: 5/5 = 1.0, passed. Second: 0.20, failed. Composition FAILS.
    assert result.first_pass_coverage_rate == pytest.approx(1.0)
    assert result.second_pass_result.passed is False
    assert result.both_passed is False
    # alignment_score = mean(1.0, 0.20) = 0.60
    assert result.alignment_score == pytest.approx(0.60)
    # 0.60 < 0.95 → flag for review
    assert result.flag_for_review is True
    # Union = first ∪ second = expected ∪ {B2.3} = expected
    assert sorted(result.matched_se_codes_union) == sorted(expected)
    # Intersection of uncovered: nothing — first pass covered everything
    assert result.uncovered_se_codes_intersection == []


# ---------------------------------------------------------------------------
# Scenario 3 — Empty expected_se_codes → graceful fail-safe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_expected_se_codes_fail_safe():
    """Empty expected list is a caller-contract bug — fail-safe per 1D-1 pattern."""
    # Stub returns 1D-1's empty-input fail-safe shape.
    stub = _StubValidator(_make_second_pass_result(
        passed=False,
        coverage_rate=0.0,
        matched_se_codes=[],
        uncovered_se_codes=[],
        flag_for_review=True,
        error="no expected_se_codes provided",
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="some content",
        model_self_report_se_codes=["MTH1W-B2.3"],
        expected_se_codes=[],
        grade=9,
        subject_code="MTH1W",
    )

    assert result.both_passed is False
    assert result.first_pass_coverage_rate == 0.0
    assert result.alignment_score == 0.0
    assert result.flag_for_review is True
    assert result.matched_se_codes_union == []
    assert result.uncovered_se_codes_intersection == []
    # Second-pass error surfaces through the composed result.
    assert result.second_pass_result.error == "no expected_se_codes provided"


# ---------------------------------------------------------------------------
# Scenario 4 — Forwarding kwargs to the second-pass validator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_forwards_kwargs_to_validator():
    """Pipeline must forward generated_content/expected/grade/subject to the validator."""
    expected = ["MTH1W-B2.3"]
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=expected,
        uncovered_se_codes=[],
    ))
    pipeline = ValidationPipeline(validator=stub)

    await pipeline.validate(
        generated_content="THE CONTENT",
        model_self_report_se_codes=expected,
        expected_se_codes=expected,
        grade=9,
        subject_code="MTH1W",
    )

    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["generated_content"] == "THE CONTENT"
    assert call["expected_se_codes"] == expected
    assert call["grade"] == 9
    assert call["subject_code"] == "MTH1W"


# ---------------------------------------------------------------------------
# Scenario 5 — alignment_score = mean of the two coverage rates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alignment_score_is_mean_of_two_rates():
    """alignment_score must be ((first + second) / 2)."""
    expected = ["A1", "A2", "A3", "A4"]
    # First pass: model claims 2/4 = 0.50
    self_report = ["A1", "A2"]
    # Second pass: claims 3/4 = 0.75
    stub = _StubValidator(_make_second_pass_result(
        passed=False,  # 0.75 < 0.80
        coverage_rate=0.75,
        matched_se_codes=["A1", "A2", "A3"],
        uncovered_se_codes=["A4"],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=self_report,
        expected_se_codes=expected,
        grade=5,
        subject_code="MATH",
    )

    assert result.first_pass_coverage_rate == pytest.approx(0.50)
    assert result.second_pass_result.coverage_rate == pytest.approx(0.75)
    # mean(0.50, 0.75) = 0.625
    assert result.alignment_score == pytest.approx(0.625)
    # First passed? 0.50 < 0.80 → no. Second passed? no. → both_passed=False
    assert result.both_passed is False
    assert result.flag_for_review is True


# ---------------------------------------------------------------------------
# Scenario 6 — First pass passes at exactly PASS_THRESHOLD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_pass_at_threshold_passes():
    """First-pass coverage of exactly 0.80 should pass (>= threshold)."""
    expected = ["A1", "A2", "A3", "A4", "A5"]
    self_report = ["A1", "A2", "A3", "A4"]  # 4/5 = 0.80
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=expected,
        uncovered_se_codes=[],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=self_report,
        expected_se_codes=expected,
        grade=5,
        subject_code="MATH",
    )

    assert result.first_pass_coverage_rate == pytest.approx(0.80)
    assert result.second_pass_result.passed is True
    assert result.both_passed is True  # 0.80 >= PASS_THRESHOLD AND second passes
    # mean(0.80, 1.0) = 0.90
    assert result.alignment_score == pytest.approx(0.90)
    # 0.90 < 0.95 → still flagged for review
    assert result.flag_for_review is True


# ---------------------------------------------------------------------------
# Scenario 7 — First pass below threshold but second pass passes → both_passed=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_pass_low_second_pass_high_fails():
    """If first pass is below threshold, both_passed=False even if second passes."""
    expected = ["A1", "A2", "A3", "A4", "A5"]
    self_report = ["A1"]  # 1/5 = 0.20
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=expected,
        uncovered_se_codes=[],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=self_report,
        expected_se_codes=expected,
        grade=5,
        subject_code="MATH",
    )

    assert result.first_pass_coverage_rate == pytest.approx(0.20)
    assert result.first_pass_coverage_rate < PASS_THRESHOLD
    assert result.second_pass_result.passed is True
    assert result.both_passed is False  # first failed → composition fails
    # mean(0.20, 1.0) = 0.60
    assert result.alignment_score == pytest.approx(0.60)
    assert result.flag_for_review is True


# ---------------------------------------------------------------------------
# Scenario 8 — Union / intersection bookkeeping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_union_and_intersection_bookkeeping():
    """matched_union = first ∪ second; uncovered_intersection = missed by BOTH."""
    expected = ["A1", "A2", "A3", "A4"]
    # First pass matches A1, A2 → first uncovered = A3, A4
    self_report = ["A1", "A2"]
    # Second pass matches A2, A3 → second uncovered = A1, A4
    stub = _StubValidator(_make_second_pass_result(
        passed=False,
        coverage_rate=0.50,
        matched_se_codes=["A2", "A3"],
        uncovered_se_codes=["A1", "A4"],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=self_report,
        expected_se_codes=expected,
        grade=5,
        subject_code="MATH",
    )

    # Union of matched = {A1, A2} ∪ {A2, A3} = {A1, A2, A3}
    assert sorted(result.matched_se_codes_union) == ["A1", "A2", "A3"]
    # Intersection of uncovered = {A3, A4} ∩ {A1, A4} = {A4}
    assert result.uncovered_se_codes_intersection == ["A4"]


# ---------------------------------------------------------------------------
# Scenario 9 — Case- / whitespace-insensitive first-pass matching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_pass_case_and_whitespace_insensitive():
    """First-pass set-overlap mirrors 1D-1 normalization (case + whitespace)."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4"]
    self_report = ["  mth1w-b2.3 ", "MTH1W-B2.4"]  # mixed casing/whitespace
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=expected,
        uncovered_se_codes=[],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=self_report,
        expected_se_codes=expected,
        grade=9,
        subject_code="MTH1W",
    )

    assert result.first_pass_coverage_rate == pytest.approx(1.0)
    assert result.both_passed is True


# ---------------------------------------------------------------------------
# Scenario 10 — Empty self-report list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_self_report_first_pass_zero():
    """No self-reported codes → first-pass coverage = 0.0."""
    expected = ["A1", "A2"]
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=expected,
        uncovered_se_codes=[],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=[],
        expected_se_codes=expected,
        grade=9,
        subject_code="MTH1W",
    )

    assert result.first_pass_coverage_rate == 0.0
    assert result.both_passed is False
    # mean(0.0, 1.0) = 0.50
    assert result.alignment_score == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# Scenario 11 — Default validator construction
# ---------------------------------------------------------------------------


def test_default_validator_constructed():
    """When no validator is injected, an AlignmentValidator instance is used."""
    from app.services.cmcp.alignment_validator import AlignmentValidator

    pipeline = ValidationPipeline()
    assert isinstance(pipeline.validator, AlignmentValidator)


def test_injected_validator_used():
    """An injected validator replaces the default."""
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=1.0,
        matched_se_codes=["A1"],
        uncovered_se_codes=[],
    ))
    pipeline = ValidationPipeline(validator=stub)
    assert pipeline.validator is stub


# ---------------------------------------------------------------------------
# Scenario 12 — flag_for_review boundary at REVIEW_THRESHOLD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flag_for_review_boundary():
    """alignment_score >= 0.95 → no flag; < 0.95 → flag."""
    expected = ["A1", "A2", "A3", "A4", "A5"]
    self_report = expected  # 1.0
    # The pipeline recomputes flag_for_review from alignment_score and
    # ignores the second-pass flag — we don't override it here.
    stub = _StubValidator(_make_second_pass_result(
        passed=True,
        coverage_rate=0.95,  # just at threshold
        matched_se_codes=["A1", "A2", "A3", "A4"],
        uncovered_se_codes=["A5"],
    ))

    pipeline = ValidationPipeline(validator=stub)
    result = await pipeline.validate(
        generated_content="content",
        model_self_report_se_codes=self_report,
        expected_se_codes=expected,
        grade=5,
        subject_code="MATH",
    )

    # mean(1.0, 0.95) = 0.975 >= 0.95 → no flag
    assert result.alignment_score == pytest.approx(0.975)
    assert result.flag_for_review is False
    assert result.both_passed is True
