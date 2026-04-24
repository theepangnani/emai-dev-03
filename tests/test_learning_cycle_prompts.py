"""Tests for the CB-TUTOR-002 short learning-cycle prompt builders.

These tests validate the prompt STRINGS only — no LLM calls.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.prompts.learning_cycle import (
    ARC_SYSTEM_VOICE,
    JSON_ONLY_SUFFIX,
    build_answer_reveal_prompt,
    build_chunk_questions_prompt,
    build_chunk_teach_prompt,
    build_retry_hint_prompt,
    build_topic_outline_prompt,
)


# --- Outline prompt -------------------------------------------------------


def test_outline_prompt_includes_topic_chunk_count_and_json_request():
    prompt = build_topic_outline_prompt(
        topic="Photosynthesis",
        subject="Science",
        grade=7,
        num_chunks=5,
    )
    assert "Photosynthesis" in prompt
    assert "5" in prompt
    assert "JSON" in prompt
    assert JSON_ONLY_SUFFIX in prompt
    assert ARC_SYSTEM_VOICE in prompt
    # Mentions the fields the caller will parse
    assert "chunk_idx" in prompt
    assert "title" in prompt
    assert "learning_objective" in prompt


def test_outline_prompt_defaults_to_grade_7_when_grade_none():
    prompt = build_topic_outline_prompt(
        topic="Fractions",
        subject="Math",
        grade=None,
    )
    assert "Grade 7" in prompt


def test_outline_prompt_respects_custom_chunk_count():
    prompt = build_topic_outline_prompt(
        topic="Newton's Laws",
        subject="Physics",
        grade=9,
        num_chunks=3,
    )
    assert "3" in prompt
    assert "Grade 9" in prompt


# --- Teach prompt ---------------------------------------------------------


def test_teach_prompt_references_prior_chunks():
    prior = ["What plants need", "Where photosynthesis happens"]
    prompt = build_chunk_teach_prompt(
        topic="Photosynthesis",
        subject="Science",
        grade=7,
        chunk_title="The role of chlorophyll",
        objective="Explain how chlorophyll absorbs light energy.",
        prior_chunks_titles=prior,
    )
    for title in prior:
        assert title in prompt
    assert "The role of chlorophyll" in prompt
    assert "150" in prompt  # word budget
    assert "markdown" in prompt.lower()
    assert ARC_SYSTEM_VOICE in prompt


def test_teach_prompt_handles_first_chunk_with_no_priors():
    prompt = build_chunk_teach_prompt(
        topic="Photosynthesis",
        subject="Science",
        grade=7,
        chunk_title="What plants need",
        objective="List the four inputs plants need.",
        prior_chunks_titles=[],
    )
    assert "first chunk" in prompt.lower()


# --- Questions prompt -----------------------------------------------------


def test_questions_prompt_enforces_three_format_mix():
    prompt = build_chunk_questions_prompt(
        topic="Photosynthesis",
        chunk_title="The role of chlorophyll",
        teach_content="Chlorophyll is the green pigment that absorbs light...",
        grade=7,
    )
    assert "mcq" in prompt
    assert "true_false" in prompt
    assert "fill_blank" in prompt
    assert "EXACTLY 3" in prompt
    assert "4 options" in prompt
    assert JSON_ONLY_SUFFIX in prompt
    assert "correct_answer" in prompt
    assert "explanation" in prompt


def test_questions_prompt_embeds_teach_content():
    teach = "UNIQUE_TEACH_STRING_XYZ chlorophyll absorbs red and blue light."
    prompt = build_chunk_questions_prompt(
        topic="Photosynthesis",
        chunk_title="Chlorophyll",
        teach_content=teach,
        grade=7,
    )
    assert teach in prompt


# --- Retry hint prompt ----------------------------------------------------


def test_retry_hint_prompt_does_not_contain_correct_answer_instruction():
    prompt = build_retry_hint_prompt(
        question="What pigment absorbs light in plants?",
        wrong_answer="water",
        attempt_number=1,
    )
    # The wrong answer is quoted back to the LLM (so it can coach off it)...
    assert "water" in prompt
    # ...but the prompt must NOT instruct the LLM to reveal the correct answer.
    lower = prompt.lower()
    assert "do not" in lower
    assert "reveal" in lower
    # Guardrails are present
    assert "not state" in lower or "not reveal" in lower
    assert "#1" in prompt  # attempt number surfaced


def test_retry_hint_prompt_coaches_without_answer_key():
    """The prompt itself should not include a `correct_answer` field —
    the LLM is only given the question and the student's wrong answer."""
    prompt = build_retry_hint_prompt(
        question="2 + 2 = ?",
        wrong_answer="5",
        attempt_number=2,
    )
    assert "correct_answer" not in prompt
    assert "Correct answer:" not in prompt


# --- Reveal prompt --------------------------------------------------------


def test_reveal_prompt_includes_user_attempts():
    attempts = ["water", "sunlight", "oxygen"]
    prompt = build_answer_reveal_prompt(
        question="What pigment absorbs light in plants?",
        correct_answer="chlorophyll",
        user_attempts=attempts,
    )
    for attempt in attempts:
        assert attempt in prompt
    assert "chlorophyll" in prompt
    assert "Attempt 1" in prompt
    assert "Attempt 2" in prompt
    assert "Attempt 3" in prompt


def test_reveal_prompt_handles_empty_attempts():
    prompt = build_answer_reveal_prompt(
        question="Q?",
        correct_answer="A",
        user_attempts=[],
    )
    assert "no recorded attempts" in prompt


# --- Mocking guard --------------------------------------------------------


def test_prompt_builders_do_not_call_openai():
    """Sanity: builders are pure strings. If anything ever tries to hit
    OpenAI from the builder module, this test will fail loudly."""
    with patch("openai.OpenAI") as mock_client:
        build_topic_outline_prompt("T", "S", 7)
        build_chunk_teach_prompt("T", "S", 7, "ct", "obj", [])
        build_chunk_questions_prompt("T", "ct", "teach", 7)
        build_retry_hint_prompt("q", "wrong", 1)
        build_answer_reveal_prompt("q", "a", ["x"])
        mock_client.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
