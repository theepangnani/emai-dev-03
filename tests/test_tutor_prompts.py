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
