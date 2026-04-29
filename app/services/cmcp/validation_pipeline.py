"""
Validation Pipeline for CB-CMCP-001 (#4473, M1-D 1D-2).

Composes the model's first-pass self-report (`se_codes_covered`) with the
second-pass `AlignmentValidator` (1D-1, shipped) into a single gate. Per locked
decision D4=C in M1 + plan §7 M1-D, BOTH passes must clear their respective
gates for an artifact to be considered aligned. This breaks the circular
self-report failure mode where the same model that wrote the guide is also
the sole judge of which Specific Expectations (SE) it covered.

Composition (per #4473 spec):
- First pass: ``|model_self_report ∩ expected| / |expected|`` ≥ PASS_THRESHOLD
- Second pass: ``AlignmentValidator.validate(...).passed``  (≥ PASS_THRESHOLD)
- ``both_passed = first_pass_passed AND second_pass.passed``
- ``alignment_score = mean(first_pass_coverage_rate, second_pass.coverage_rate)``
- ``flag_for_review = alignment_score < REVIEW_THRESHOLD``

Out of scope (per #4473):
- Writing ``alignment_score`` to the artifact — 1D-3 (Wave 3).
- Embedding-similarity validator — M3-I per D4=B in M3.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.logging_config import get_logger
from app.services.cmcp.alignment_validator import (
    PASS_THRESHOLD,
    REVIEW_THRESHOLD,
    AlignmentValidator,
    ValidationResult,
)

logger = get_logger(__name__)


def _normalize_code(code: str) -> str:
    """Normalize an SE code for case-insensitive, whitespace-tolerant matching.

    Local copy of the same helper in `alignment_validator.py` — kept private
    here so the pipeline does not depend on a private symbol of the 1D-1
    module. Semantics MUST stay identical to `alignment_validator._normalize_code`
    so that union/intersection set operations against the second-pass result
    project onto the same canonical form.
    """
    return code.strip().upper()


class ValidationPipelineResult(BaseModel):
    """Composed outcome of first-pass + second-pass validation.

    Fields:
        both_passed: True iff first-pass coverage rate >= PASS_THRESHOLD AND
            second-pass ``ValidationResult.passed``.
        alignment_score: Mean of first-pass coverage rate and second-pass
            coverage rate. In [0.0, 1.0].
        first_pass_coverage_rate: Coverage of expected SEs by the model's
            self-reported ``se_codes_covered`` list.
        second_pass_result: Raw 1D-1 ``ValidationResult`` from the
            independent ``AlignmentValidator``.
        flag_for_review: True iff ``alignment_score < REVIEW_THRESHOLD``.
            Soft signal — composition can pass while still being flagged.
        matched_se_codes_union: Union of SE codes matched by either pass.
        uncovered_se_codes_intersection: SE codes missed by BOTH passes
            (i.e., neither the self-report nor the second pass covered them).
    """

    both_passed: bool
    alignment_score: float = Field(ge=0.0, le=1.0)
    first_pass_coverage_rate: float = Field(ge=0.0, le=1.0)
    second_pass_result: ValidationResult
    flag_for_review: bool
    matched_se_codes_union: list[str]
    uncovered_se_codes_intersection: list[str]


def _compute_first_pass(
    model_self_report_se_codes: list[str],
    expected_se_codes: list[str],
) -> tuple[list[str], float]:
    """Compute first-pass matched SE codes and coverage rate.

    Mirrors ``alignment_validator._compute_coverage`` semantics — case- and
    whitespace-insensitive matching against ``expected_se_codes``. The
    ``matched`` list is returned in the original casing of
    ``expected_se_codes`` so downstream consumers see the canonical SE code.

    Empty ``expected_se_codes`` yields a 0.0 coverage rate (the caller
    surfaces this as a failure — see ``ValidationPipeline.validate``).

    Note: per-pass uncovered lists are not surfaced; the pipeline only needs
    the BOTH-passes intersection of uncovered codes, which is computed
    directly from the union of matched codes downstream.
    """
    if not expected_se_codes:
        return [], 0.0

    self_reported_codes = {
        _normalize_code(c) for c in model_self_report_se_codes if c
    }
    matched = [
        code for code in expected_se_codes
        if _normalize_code(code) in self_reported_codes
    ]
    coverage_rate = len(matched) / len(expected_se_codes)
    return matched, coverage_rate


class ValidationPipeline:
    """Composes first-pass model self-report with second-pass AlignmentValidator.

    The pipeline runs the cheap first pass (set-overlap on ``se_codes_covered``)
    and the expensive second pass (independent Claude mapping) and reports a
    composed outcome. BOTH must pass their respective gates for
    ``both_passed=True``.

    The validator is injectable (default: a fresh ``AlignmentValidator``) so
    tests can swap in a stub without making real Claude calls.
    """

    def __init__(self, validator: AlignmentValidator | None = None):
        # AlignmentValidator's `validate` is a staticmethod, so calling it on
        # any instance is equivalent. We accept an instance (rather than the
        # class) so callers/tests can inject a stub instance with a custom
        # `validate` coroutine via duck-typing.
        self.validator: AlignmentValidator = validator or AlignmentValidator()

    async def validate(
        self,
        generated_content: str,
        model_self_report_se_codes: list[str],
        expected_se_codes: list[str],
        grade: int,
        subject_code: str,
    ) -> ValidationPipelineResult:
        """Run both passes and compose the result.

        Args:
            generated_content: The artifact text to validate.
            model_self_report_se_codes: SE codes the generating model claims
                to have covered (from the generation output's
                ``se_codes_covered`` field).
            expected_se_codes: SE codes the artifact was generated against.
            grade: Student grade (1-12) — passed through to second pass.
            subject_code: Subject/course code (e.g., "MTH1W") — passed
                through to second pass.

        Returns:
            ``ValidationPipelineResult`` capturing both passes plus the
            composed score / pass / flag. Never raises — second-pass errors
            are captured in ``second_pass_result.error``.
        """
        # Empty expected_se_codes is a caller-contract bug. Mirror the 1D-1
        # AlignmentValidator's fail-safe behaviour rather than silently
        # reporting full coverage of the empty set. The second pass itself
        # also surfaces this, but composing with an empty self-report would
        # otherwise yield NaN/division-by-zero on the first pass.
        if not expected_se_codes:
            second_pass = await self.validator.validate(
                generated_content=generated_content,
                expected_se_codes=expected_se_codes,
                grade=grade,
                subject_code=subject_code,
            )
            return ValidationPipelineResult(
                both_passed=False,
                alignment_score=0.0,
                first_pass_coverage_rate=0.0,
                second_pass_result=second_pass,
                flag_for_review=True,
                matched_se_codes_union=[],
                uncovered_se_codes_intersection=[],
            )

        first_matched, first_coverage_rate = _compute_first_pass(
            model_self_report_se_codes=model_self_report_se_codes or [],
            expected_se_codes=expected_se_codes,
        )
        first_pass_passed = first_coverage_rate >= PASS_THRESHOLD

        second_pass = await self.validator.validate(
            generated_content=generated_content,
            expected_se_codes=expected_se_codes,
            grade=grade,
            subject_code=subject_code,
        )

        both_passed = first_pass_passed and second_pass.passed
        alignment_score = (first_coverage_rate + second_pass.coverage_rate) / 2.0
        flag_for_review = alignment_score < REVIEW_THRESHOLD

        # Union/intersection over normalized codes; reproject onto the
        # canonical casing from `expected_se_codes` so downstream consumers
        # see SE codes in the form they were declared.
        first_matched_norm = {_normalize_code(c) for c in first_matched}
        second_matched_norm = {
            _normalize_code(c) for c in second_pass.matched_se_codes
        }
        union_norm = first_matched_norm | second_matched_norm

        matched_union: list[str] = []
        uncovered_intersection: list[str] = []
        for code in expected_se_codes:
            if _normalize_code(code) in union_norm:
                matched_union.append(code)
            else:
                uncovered_intersection.append(code)

        logger.info(
            "ValidationPipeline: grade=%s subject=%s expected=%d "
            "first_pass=%.2f second_pass=%.2f score=%.2f both_passed=%s flag=%s",
            grade, subject_code, len(expected_se_codes),
            first_coverage_rate, second_pass.coverage_rate,
            alignment_score, both_passed, flag_for_review,
        )

        return ValidationPipelineResult(
            both_passed=both_passed,
            alignment_score=alignment_score,
            first_pass_coverage_rate=first_coverage_rate,
            second_pass_result=second_pass,
            flag_for_review=flag_for_review,
            matched_se_codes_union=matched_union,
            uncovered_se_codes_intersection=uncovered_intersection,
        )
