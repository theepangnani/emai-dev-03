"""
Second-pass Alignment Validator for CB-CMCP-001 (#4462, M1-D 1D-1).

Resolves the circular self-report problem in DD §3.4: the model that generated
the study guide cannot also be the sole judge of which Specific Expectation (SE)
codes the guide actually covers. This validator runs an INDEPENDENT second pass
that maps the generated content to Ontario curriculum codes, then computes
coverage against the expected SE codes.

Ported from `class-bridge-phase-2/app/services/curriculum_mapping.py`
(CurriculumMappingService) with the following adaptations for dev-03:

- Renamed: CurriculumMappingService → AlignmentValidator
- Method renamed: annotate() → validate()
- Adds coverage computation against `expected_se_codes`
- Returns a structured `ValidationResult` Pydantic model
- Uses `app.services.ai_service.generate_content` (NOT direct anthropic SDK)

Composition with the model's self-report (`se_codes_covered`) is deferred to
M1-D 1D-2; this stripe only ships the validator.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Coverage thresholds (per #4462 acceptance criteria).
PASS_THRESHOLD = 0.80
REVIEW_THRESHOLD = 0.95

# Maximum characters of generated content to send to the validator. Mirrors
# the phase-2 source which used a 3000-char excerpt to stay within prompt
# budget while remaining representative of the guide's content.
MAX_CONTENT_CHARS = 3000

CURRICULUM_SYSTEM_PROMPT = """You are an Ontario curriculum specialist for a K-12 education platform called ClassBridge.
You map educational content to Ontario curriculum expectation codes.

You are familiar with:
- Ontario elementary curriculum (Grades 1-8)
- Ontario secondary curriculum (Grades 9-12, OSSD)
- Course codes like MTH1W, SNC1W, ENG1D, etc.
- Strand and expectation numbering (e.g., B2.3 means Strand B, Overall Expectation 2, Specific Expectation 3)

When you cannot find an exact curriculum code match, provide your best approximation with the strand and general expectation area. Always include the course code prefix.

Respond with ONLY a JSON array (no markdown fences, no explanation). Each item must have: concept, curriculum_code, strand."""


class ValidationResult(BaseModel):
    """Structured outcome of the second-pass alignment validation.

    Fields:
        passed: True iff coverage_rate >= PASS_THRESHOLD (0.80).
        coverage_rate: Fraction in [0.0, 1.0] of expected SE codes that the
            independent second-pass mapped from the generated content.
        matched_se_codes: Subset of expected_se_codes the validator
            confirmed in the generated content.
        uncovered_se_codes: Subset of expected_se_codes NOT confirmed.
        flag_for_review: True iff coverage_rate < REVIEW_THRESHOLD (0.95).
            Soft signal — not a failure, but a hint to surface for review.
        second_pass_concepts: Raw concept→code list returned by the
            validator (Claude). Empty list on parsing/Claude failures.
        error: Optional human-readable failure reason. None on success.
    """

    passed: bool
    coverage_rate: float = Field(ge=0.0, le=1.0)
    matched_se_codes: list[str]
    uncovered_se_codes: list[str]
    flag_for_review: bool
    second_pass_concepts: list[dict]
    error: str | None = None


def _normalize_code(code: str) -> str:
    """Normalize an SE code for case-insensitive, whitespace-tolerant matching.

    Ontario codes are conventionally uppercase (e.g., "MTH1W-B2.3") but model
    output and inbound lists may differ in casing or stray whitespace; we
    normalize to uppercase + stripped to avoid spurious mismatches.
    """
    return code.strip().upper()


def _parse_concepts(raw_text: str) -> list[dict]:
    """Parse the validator's JSON-array reply into validated concept dicts.

    Strips optional ```...``` markdown fences before parsing.

    Returns:
        List of dicts with keys: concept, curriculum_code, strand.

    Raises:
        json.JSONDecodeError: if the response is not valid JSON.
        ValueError: if the JSON is not a list.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        # Strip leading fence (and optional language tag) + trailing fence.
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("validator response was not a JSON array")

    validated: list[dict] = []
    for item in parsed:
        if isinstance(item, dict) and "concept" in item and "curriculum_code" in item:
            validated.append({
                "concept": str(item["concept"]),
                "curriculum_code": str(item["curriculum_code"]),
                "strand": str(item.get("strand", "")),
            })

    # Surface prompt-conformance drift: if the model returned items missing
    # the required fields, log so we can detect quality regressions over
    # time (e.g., a model update breaking schema adherence).
    dropped = len(parsed) - len(validated)
    if dropped > 0:
        logger.warning(
            "AlignmentValidator: dropped %d malformed second-pass item(s) "
            "(kept %d/%d)",
            dropped, len(validated), len(parsed),
        )
    return validated


def _compute_coverage(
    expected_se_codes: list[str],
    second_pass_concepts: list[dict],
) -> tuple[list[str], list[str], float]:
    """Compute matched/uncovered SE codes and coverage rate.

    A code in `expected_se_codes` is considered matched iff at least one
    concept's `curriculum_code` (case-insensitively) equals it.
    Returns (matched, uncovered, coverage_rate).

    Empty `expected_se_codes` is rejected by the caller (`validate`) as a
    contract bug, but we keep a defensive 0.0 fallback here in case of
    future direct callers. A degenerate "no expectations declared" input
    must NOT silently report full coverage.
    """
    if not expected_se_codes:
        return [], [], 0.0

    mapped_codes = {
        _normalize_code(c["curriculum_code"])
        for c in second_pass_concepts
        if c.get("curriculum_code")
    }

    matched: list[str] = []
    uncovered: list[str] = []
    for code in expected_se_codes:
        if _normalize_code(code) in mapped_codes:
            matched.append(code)
        else:
            uncovered.append(code)

    coverage_rate = len(matched) / len(expected_se_codes)
    return matched, uncovered, coverage_rate


class AlignmentValidator:
    """Second-pass validator for SE-code coverage of generated content.

    This is the D4=C "second-pass" component of CB-CMCP-001 M1: it runs AFTER
    the model's own `se_codes_covered` self-report, providing an independent
    check that breaks the circular-self-report failure mode.
    """

    @staticmethod
    async def validate(
        generated_content: str,
        expected_se_codes: list[str],
        grade: int,
        subject_code: str,
    ) -> ValidationResult:
        """Validate that `generated_content` covers `expected_se_codes`.

        Args:
            generated_content: The study-guide / artifact text to validate.
            expected_se_codes: SE codes the artifact was generated against
                (e.g., ["MTH1W-B2.3", "MTH1W-B2.4"]).
            grade: Student grade level (1-12). Used as Claude context.
            subject_code: Subject/course code (e.g., "MTH1W"). Used as
                Claude context.

        Returns:
            ValidationResult capturing pass/coverage/raw concepts. On any
            failure (empty input, malformed JSON, Claude error) returns a
            non-passing result with `error` populated and an empty
            `second_pass_concepts` — never raises.
        """
        # Empty `expected_se_codes` is a caller-contract bug — every artifact
        # passing through this validator is generated against declared SEs.
        # Surface it as a non-passing flagged result rather than silently
        # approving an artifact with zero declared learning intent.
        if not expected_se_codes:
            return ValidationResult(
                passed=False,
                coverage_rate=0.0,
                matched_se_codes=[],
                uncovered_se_codes=[],
                flag_for_review=True,
                second_pass_concepts=[],
                error="no expected_se_codes provided",
            )

        # Empty content can never cover anything. Short-circuit before we
        # spend a Claude call. Treats every expected SE as uncovered.
        if not generated_content or not generated_content.strip():
            return ValidationResult(
                passed=False,
                coverage_rate=0.0,
                matched_se_codes=[],
                uncovered_se_codes=list(expected_se_codes),
                flag_for_review=True,
                second_pass_concepts=[],
                error="empty generated_content",
            )

        excerpt = generated_content[:MAX_CONTENT_CHARS]
        prompt = f"""Student context: Grade: {grade}, Course: {subject_code}

Generated content:
---
{excerpt}
---

Identify the 3-12 most important concepts in this content and map each to the most relevant Ontario curriculum expectation code for the given grade/course. Return a JSON array."""

        # Lazy import so unit tests can patch
        # `app.services.ai_service.generate_content` without an `anthropic`
        # client being constructed at import time. Mirrors the pattern used
        # in `cli/extract_ceg.py` (M0 0B-2).
        from app.services.ai_service import generate_content

        try:
            content, _ = await generate_content(
                prompt=prompt,
                system_prompt=CURRICULUM_SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.3,  # Lower temperature for precise mapping.
            )
        except Exception as e:  # noqa: BLE001 — fail-safe: never raise out
            logger.warning("AlignmentValidator: Claude call failed: %s", e)
            return ValidationResult(
                passed=False,
                coverage_rate=0.0,
                matched_se_codes=[],
                uncovered_se_codes=list(expected_se_codes),
                flag_for_review=True,
                second_pass_concepts=[],
                error=f"claude_error: {type(e).__name__}: {e}",
            )

        try:
            concepts = _parse_concepts(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "AlignmentValidator: failed to parse second-pass response: %s", e
            )
            return ValidationResult(
                passed=False,
                coverage_rate=0.0,
                matched_se_codes=[],
                uncovered_se_codes=list(expected_se_codes),
                flag_for_review=True,
                second_pass_concepts=[],
                error=f"parse_error: {e}",
            )

        matched, uncovered, coverage_rate = _compute_coverage(
            expected_se_codes, concepts
        )

        passed = coverage_rate >= PASS_THRESHOLD
        flag_for_review = coverage_rate < REVIEW_THRESHOLD

        logger.info(
            "AlignmentValidator: grade=%s subject=%s expected=%d matched=%d "
            "coverage=%.2f passed=%s flag=%s",
            grade, subject_code, len(expected_se_codes), len(matched),
            coverage_rate, passed, flag_for_review,
        )

        return ValidationResult(
            passed=passed,
            coverage_rate=coverage_rate,
            matched_se_codes=matched,
            uncovered_se_codes=uncovered,
            flag_for_review=flag_for_review,
            second_pass_concepts=concepts,
            error=None,
        )
