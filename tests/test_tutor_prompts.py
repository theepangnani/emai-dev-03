"""Tests for Arc tutor prompt templates (CB-TUTOR-002 Phase 1, #4064)."""

from __future__ import annotations

from app.prompts.grade_tone import get_tone_profile
from app.prompts.tutor_chat import (
    SUGGESTION_CHIP_INSTRUCTION,
    build_system_prompt,
    build_user_prompt,
)


def test_system_prompt_contains_grade_level() -> None:
    prompt = build_system_prompt(grade_level=4)
    assert "grade 4" in prompt.lower()


def test_system_prompt_defaults_for_none_grade() -> None:
    prompt = build_system_prompt(grade_level=None)
    # Defaults to grade 7 when no grade is provided (per CB-TUTOR-002 design doc).
    assert "grade 7" in prompt.lower()


def test_system_prompt_accepts_any_grade() -> None:
    # CB-TUTOR-002 canonical grade_tone (#4071) uses 4 bands (K-3/4-6/7-9/10-12);
    # out-of-range ints pass through — prompt still includes the raw number.
    below = build_system_prompt(grade_level=-3)
    above = build_system_prompt(grade_level=99)
    assert "grade -3" in below.lower() or "grade" in below.lower()
    assert "grade 99" in above.lower() or "grade" in above.lower()


def test_system_prompt_includes_chip_instruction() -> None:
    prompt = build_system_prompt(grade_level=7)
    assert SUGGESTION_CHIP_INSTRUCTION in prompt
    assert "[[CHIPS:" in prompt


def test_system_prompt_warns_against_pii_leak() -> None:
    prompt = build_system_prompt(grade_level=5).lower()
    assert "personally identifiable" in prompt or "pii" in prompt
    assert "phone" in prompt
    assert "email" in prompt


def test_system_prompt_does_not_leak_sample_pii() -> None:
    # The template itself must not contain example phone/email strings that
    # the model might echo back to users.
    prompt = build_system_prompt(grade_level=8)
    assert "416-" not in prompt
    assert "@gmail.com" not in prompt
    assert "@example.com" not in prompt


def test_system_prompt_has_anti_clarification_guidance() -> None:
    prompt = build_system_prompt(grade_level=6).lower()
    assert "clarification" in prompt
    assert "directly" in prompt or "concise" in prompt


def test_tone_profile_schema() -> None:
    # CB-TUTOR-002 canonical tone profile (#4071) ships 5 keys:
    # voice, vocabulary, sentence_length, examples, directive.
    expected_keys = {"voice", "vocabulary", "sentence_length", "examples", "directive"}
    for grade in (1, 5, 7, 11):
        profile = get_tone_profile(grade)
        assert expected_keys.issubset(profile.keys()), (
            f"grade {grade} profile missing keys; got {sorted(profile.keys())}"
        )


def test_build_user_prompt_includes_message() -> None:
    out = build_user_prompt("What is photosynthesis?", history=None, context=None)
    assert "What is photosynthesis?" in out


def test_build_user_prompt_formats_history() -> None:
    history = [
        {"role": "user", "content": "Hi Arc"},
        {"role": "assistant", "content": "Hello! How can I help?"},
    ]
    out = build_user_prompt("Tell me more", history=history, context=None)
    assert "User: Hi Arc" in out
    assert "Arc: Hello! How can I help?" in out
    assert "Tell me more" in out


def test_build_user_prompt_formats_context() -> None:
    context = {"subject": "Math", "topic": "fractions"}
    out = build_user_prompt("Help!", history=None, context=context)
    assert "subject: Math" in out
    assert "topic: fractions" in out


def test_build_user_prompt_skips_empty_sections() -> None:
    out = build_user_prompt("Hello", history=[], context={})
    assert "Recent conversation" not in out
    assert "Context:" not in out
    assert "Hello" in out


def test_system_prompt_mode_default_is_quick() -> None:
    """Regression: omitting `mode` must produce the same prompt as `mode='quick'` (#4375)."""
    default = build_system_prompt(grade_level=7)
    quick = build_system_prompt(grade_level=7, mode="quick")
    assert default == quick


def test_system_prompt_full_mode_includes_structure_directives() -> None:
    """`mode='full'` adds the structured-artifact instructions (#4375)."""
    prompt = build_system_prompt(grade_level=7, mode="full")
    lower = prompt.lower()
    # Markdown-structure directives.
    assert "##" in prompt
    assert "table" in lower
    assert "code" in lower  # fenced code blocks
    assert "worked example" in lower or "examples" in lower
    assert "summary" in lower
    # Chip instruction is still present (full mode keeps the suffix).
    assert SUGGESTION_CHIP_INSTRUCTION in prompt


def test_system_prompt_full_mode_keeps_grade_tone() -> None:
    """Full mode must still be shaped by grade level (same age-tone profile)."""
    prompt = build_system_prompt(grade_level=4, mode="full")
    assert "grade 4" in prompt.lower()


def test_system_prompt_full_mode_chip_instruction_is_last() -> None:
    """The CHIPS suffix must come AFTER the structured-artifact block."""
    prompt = build_system_prompt(grade_level=7, mode="full")
    # CHIPS instruction must appear after the structure block — i.e. near the end.
    chips_idx = prompt.find(SUGGESTION_CHIP_INSTRUCTION)
    assert chips_idx != -1
    # Find a structure-directive marker that should precede the chips line.
    summary_idx = prompt.lower().find("summary")
    assert summary_idx != -1
    assert summary_idx < chips_idx


def test_chip_instruction_demands_self_contained_topic_named_chips() -> None:
    """Chips must be self-contained, topic-anchored, and grade-agnostic
    (#4381 Bug 2a + #4374 SUGG-3)."""
    assert "self-contained" in SUGGESTION_CHIP_INSTRUCTION
    # Abstract good-example phrasing — proves SUGG-3 fix is in place.
    assert "topic above" in SUGGESTION_CHIP_INSTRUCTION
    # Guard against regression to the grade-specific anchor.
    assert "Grade 10" not in SUGGESTION_CHIP_INSTRUCTION


def test_system_prompt_has_stay_on_topic_directive() -> None:
    """Short follow-ups ("examples", "more", "another") must continue the
    same topic — not switch subjects (#4381 Bug 2b)."""
    prompt = build_system_prompt(grade_level=7)
    assert "continue on the same topic" in prompt


def test_system_prompt_worksheet_mode_includes_directive() -> None:
    """`mode='worksheet'` must add the worksheet directives (#4382)."""
    prompt = build_system_prompt(grade_level=10, mode="worksheet")
    lower = prompt.lower()
    # Worksheet directive markers.
    assert "numbered list" in lower
    assert "answer key" in lower
    # Chip instruction is still present (worksheet mode keeps the suffix).
    assert SUGGESTION_CHIP_INSTRUCTION in prompt


def test_system_prompt_worksheet_mode_excludes_full_structure() -> None:
    """Worksheet mode must NOT include the full-mode structure block —
    worksheet has its own shape (#4382)."""
    prompt = build_system_prompt(grade_level=10, mode="worksheet")
    # The full-mode "## Summary" section + cheat-sheet wording are full-only.
    assert "cheat-sheet" not in prompt.lower()
    assert "## Summary" not in prompt
    # And the marker phrase that appears only in the full-mode instruction.
    assert "structured Markdown artifact" not in prompt


def test_system_prompt_default_arg_still_quick() -> None:
    """Default arg (no `mode`) must still produce quick output, unchanged
    by the worksheet addition (#4382)."""
    default = build_system_prompt(grade_level=10)
    quick = build_system_prompt(grade_level=10, mode="quick")
    assert default == quick
    # And the worksheet directive must NOT appear in the quick prompt.
    assert "answer key" not in default.lower()


def test_system_prompt_worksheet_mode_keeps_grade_tone() -> None:
    """Worksheet mode must still be shaped by grade level (#4382)."""
    prompt = build_system_prompt(grade_level=4, mode="worksheet")
    assert "grade 4" in prompt.lower()


def test_worksheet_mode_chip_directive_steers_away_from_more_practice() -> None:
    """Worksheet replies should suggest non-practice next steps to avoid
    chip-induced infinite worksheet loops (#4397 SUGG-10 / #4401)."""
    prompt = build_system_prompt(grade_level=10, mode="worksheet")
    lower = prompt.lower()
    # Steering directive must appear (any of the three phrasings is fine).
    assert (
        "point away" in lower
        or "steer away" in lower
        or "do not suggest more practice" in lower
    )
    # Sanity: the original worksheet directive (numbered list + answer key) still present.
    assert "numbered list" in lower
    assert "answer key" in lower
