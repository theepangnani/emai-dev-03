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
    # Defaults to grade 6 when no grade is provided.
    assert "grade 6" in prompt.lower()


def test_system_prompt_clamps_out_of_range_grade() -> None:
    below = build_system_prompt(grade_level=-3)
    above = build_system_prompt(grade_level=99)
    assert "grade 0" in below.lower()
    assert "grade 12" in above.lower()


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


def test_tone_profile_bands() -> None:
    assert get_tone_profile(1)["band"] == "primary"
    assert get_tone_profile(5)["band"] == "junior"
    assert get_tone_profile(7)["band"] == "intermediate"
    assert get_tone_profile(11)["band"] == "senior"


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
