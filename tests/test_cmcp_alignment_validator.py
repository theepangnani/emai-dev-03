"""Unit tests for app/services/cmcp/alignment_validator.py — CB-CMCP-001 M1-D 1D-1 (#4462).

All Claude calls are mocked via `app.services.ai_service.generate_content` —
no real API calls are made.

Covers the 5 acceptance scenarios from #4462:
1. Validator returns passed=True when generated content covers all expected SEs
2. Validator returns passed=False + flag_for_review=True when coverage < 80%
3. coverage_rate computed correctly (overlap / expected)
4. uncovered_se_codes correctly identified
5. Mock Claude returning malformed JSON → graceful failure (passed=False, raw error captured)
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services.cmcp.alignment_validator import (
    PASS_THRESHOLD,
    REVIEW_THRESHOLD,
    AlignmentValidator,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claude_response(concepts: list[dict]) -> tuple[str, str]:
    """Build a (content, stop_reason) tuple matching `generate_content`'s shape."""
    return json.dumps(concepts), "end_turn"


def _patch_generate_content(side_effect):
    """Patch `app.services.ai_service.generate_content` with the given side effect.

    Use as: ``with _patch_generate_content(...) as mock: ...``
    """
    return patch(
        "app.services.ai_service.generate_content",
        side_effect=side_effect,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — Full coverage → passed=True, flag=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_coverage_passes():
    """When the second pass maps every expected SE, validation should pass."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "Quadratic equations", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
            {"concept": "Solving by factoring", "curriculum_code": "MTH1W-B2.4", "strand": "Number"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="A study guide about quadratics and factoring.",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert isinstance(result, ValidationResult)
    assert result.passed is True
    assert result.coverage_rate == 1.0
    assert sorted(result.matched_se_codes) == sorted(expected)
    assert result.uncovered_se_codes == []
    assert result.flag_for_review is False  # 1.0 >= REVIEW_THRESHOLD (0.95)
    assert len(result.second_pass_concepts) == 2
    assert result.error is None


# ---------------------------------------------------------------------------
# Scenario 2 — Low coverage → passed=False, flag_for_review=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_coverage_fails_and_flags_for_review():
    """Coverage below the 0.80 pass threshold should fail AND set the review flag."""
    # 1 of 5 expected SEs covered → coverage 0.20 < 0.80
    expected = ["MTH1W-B2.3", "MTH1W-B2.4", "MTH1W-B2.5", "MTH1W-B2.6", "MTH1W-B2.7"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "Quadratic equations", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
            {"concept": "Unrelated trig", "curriculum_code": "MTH1W-D1.1", "strand": "Trig"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="Mostly off-topic content.",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.passed is False
    assert result.coverage_rate == pytest.approx(0.20)
    assert result.coverage_rate < PASS_THRESHOLD
    assert result.flag_for_review is True  # 0.20 < REVIEW_THRESHOLD
    assert result.matched_se_codes == ["MTH1W-B2.3"]
    assert sorted(result.uncovered_se_codes) == sorted(
        ["MTH1W-B2.4", "MTH1W-B2.5", "MTH1W-B2.6", "MTH1W-B2.7"]
    )
    assert result.error is None


# ---------------------------------------------------------------------------
# Scenario 3 — coverage_rate computed correctly (overlap / expected)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_coverage_rate_computation_partial():
    """3 of 4 expected SEs covered → coverage_rate == 0.75."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4", "MTH1W-B2.5", "MTH1W-B2.6"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "C1", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
            {"concept": "C2", "curriculum_code": "MTH1W-B2.4", "strand": "Number"},
            {"concept": "C3", "curriculum_code": "MTH1W-B2.5", "strand": "Number"},
            # B2.6 NOT mapped + an extra unrelated concept (should not affect coverage)
            {"concept": "Bonus", "curriculum_code": "MTH1W-D1.1", "strand": "Trig"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="x" * 100,
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.coverage_rate == pytest.approx(0.75)
    # 0.75 < PASS_THRESHOLD (0.80) → not passing
    assert result.passed is False
    # 0.75 < REVIEW_THRESHOLD (0.95) → flagged for review
    assert result.flag_for_review is True


@pytest.mark.asyncio
async def test_coverage_rate_passes_at_80_percent():
    """4 of 5 expected SEs covered → coverage_rate == 0.80, passes (>= threshold)."""
    expected = ["A1", "A2", "A3", "A4", "A5"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "C1", "curriculum_code": "A1", "strand": "S"},
            {"concept": "C2", "curriculum_code": "A2", "strand": "S"},
            {"concept": "C3", "curriculum_code": "A3", "strand": "S"},
            {"concept": "C4", "curriculum_code": "A4", "strand": "S"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=5,
            subject_code="MATH",
        )

    assert result.coverage_rate == pytest.approx(0.80)
    assert result.passed is True  # 0.80 >= PASS_THRESHOLD
    assert result.flag_for_review is True  # 0.80 < REVIEW_THRESHOLD (0.95)


# ---------------------------------------------------------------------------
# Scenario 4 — uncovered_se_codes correctly identified
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uncovered_se_codes_identified():
    """Codes the second pass did not map should appear in uncovered_se_codes."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4", "MTH1W-B2.5"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "C1", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.matched_se_codes == ["MTH1W-B2.3"]
    assert sorted(result.uncovered_se_codes) == ["MTH1W-B2.4", "MTH1W-B2.5"]


@pytest.mark.asyncio
async def test_case_insensitive_matching():
    """SE codes match case-insensitively (model output may differ in casing)."""
    expected = ["mth1w-b2.3", "MTH1W-B2.4"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "C1", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
            {"concept": "C2", "curriculum_code": "mth1w-b2.4", "strand": "Number"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.coverage_rate == 1.0
    assert result.uncovered_se_codes == []


# ---------------------------------------------------------------------------
# Scenario 5 — Malformed JSON → graceful failure with raw error captured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_json_graceful_failure():
    """Non-JSON Claude reply must NOT raise; result is a non-passing failure."""
    expected = ["MTH1W-B2.3", "MTH1W-B2.4"]

    async def fake(*_args, **_kwargs):
        return ("This is not JSON at all — the model ignored instructions.", "end_turn")

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.passed is False
    assert result.coverage_rate == 0.0
    assert result.matched_se_codes == []
    assert sorted(result.uncovered_se_codes) == sorted(expected)
    assert result.flag_for_review is True
    assert result.second_pass_concepts == []
    assert result.error is not None
    assert "parse_error" in result.error


@pytest.mark.asyncio
async def test_non_array_json_graceful_failure():
    """JSON that's not an array (e.g., a dict) is also a parse_error."""
    async def fake(*_args, **_kwargs):
        return _claude_response_dict_shaped()

    expected = ["A1"]
    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.passed is False
    assert result.error is not None
    assert "parse_error" in result.error


def _claude_response_dict_shaped() -> tuple[str, str]:
    return ('{"concept": "x", "curriculum_code": "A1"}', "end_turn")


# ---------------------------------------------------------------------------
# Robustness — markdown fences, Claude API errors, empty input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strips_markdown_fences():
    """Validator should strip ```json ... ``` fences before parsing."""
    expected = ["MTH1W-B2.3"]
    fenced = (
        "```json\n"
        '[{"concept": "Quadratics", "curriculum_code": "MTH1W-B2.3", "strand": "Number"}]\n'
        "```"
    )

    async def fake(*_args, **_kwargs):
        return (fenced, "end_turn")

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.passed is True
    assert result.coverage_rate == 1.0
    assert result.error is None


@pytest.mark.asyncio
async def test_claude_exception_graceful_failure():
    """If Claude raises, validator must NOT propagate; returns a failure result."""
    expected = ["MTH1W-B2.3"]

    async def fake(*_args, **_kwargs):
        raise RuntimeError("simulated Claude outage")

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.passed is False
    assert result.coverage_rate == 0.0
    assert result.uncovered_se_codes == expected
    assert result.flag_for_review is True
    assert result.error is not None
    assert "claude_error" in result.error


@pytest.mark.asyncio
async def test_empty_generated_content_short_circuits():
    """Empty/whitespace content fails immediately without calling Claude."""
    expected = ["A1", "A2"]
    call_count = {"n": 0}

    async def fake(*_args, **_kwargs):
        call_count["n"] += 1
        return _claude_response([])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="   \n  ",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert call_count["n"] == 0  # No Claude call
    assert result.passed is False
    assert result.coverage_rate == 0.0
    assert result.uncovered_se_codes == expected
    assert result.error == "empty generated_content"


@pytest.mark.asyncio
async def test_empty_expected_se_codes_rejected():
    """Empty expected_se_codes is a caller contract bug — must surface, not pass."""
    call_count = {"n": 0}

    async def fake(*_args, **_kwargs):
        call_count["n"] += 1
        return _claude_response([])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="some real content here",
            expected_se_codes=[],
            grade=9,
            subject_code="MTH1W",
        )

    # No Claude call — short-circuit BEFORE the empty-content check.
    assert call_count["n"] == 0
    assert result.passed is False
    assert result.coverage_rate == 0.0
    assert result.matched_se_codes == []
    assert result.uncovered_se_codes == []
    assert result.flag_for_review is True
    assert result.error == "no expected_se_codes provided"


@pytest.mark.asyncio
async def test_whitespace_tolerant_matching():
    """SE codes match with stray whitespace stripped (model output may include it)."""
    expected = ["  MTH1W-B2.3  ", "MTH1W-B2.4"]

    async def fake(*_args, **_kwargs):
        return _claude_response([
            {"concept": "C1", "curriculum_code": "MTH1W-B2.3", "strand": "Number"},
            {"concept": "C2", "curriculum_code": "  mth1w-b2.4 ", "strand": "Number"},
        ])

    with _patch_generate_content(fake):
        result = await AlignmentValidator.validate(
            generated_content="content",
            expected_se_codes=expected,
            grade=9,
            subject_code="MTH1W",
        )

    assert result.coverage_rate == 1.0
    assert result.uncovered_se_codes == []


@pytest.mark.asyncio
async def test_thresholds_match_spec():
    """Sanity check: thresholds in source must match #4462 spec (0.80 / 0.95)."""
    assert PASS_THRESHOLD == 0.80
    assert REVIEW_THRESHOLD == 0.95
