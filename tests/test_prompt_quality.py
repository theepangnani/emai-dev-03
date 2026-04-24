"""Regression test for answer-first prompt policy (issue #4070).

These tests guard against regressions where AI prompts would ask the user
for grade/subject/context BEFORE answering. The refactor in #4070 flipped
ASGF + ILE prompts to "answer-first": infer + default instead of asking.
"""
import pytest

from app.services import asgf_service, ile_question_service


# Phrases that indicate a "please give me context first" prompt posture.
# A prompt that CONTAINS any of these is regressing toward the old behaviour.
FORBIDDEN_PHRASES = [
    "please provide your grade",
    "please provide the grade",
    "please tell me your grade",
    "i need more context",
    "i need more information",
    "can you tell me your",
    "can you provide",
    "could you tell me",
    "could you provide",
    "what grade are you",
    "what is your grade",
    "please clarify",
    "please specify",
    "please ask the user",
]


# Every prompt string that was audited + refactored under #4070.
REFACTORED_ASGF_PROMPTS = {
    "_SYSTEM_PROMPT": asgf_service._SYSTEM_PROMPT,
    "_ALTERNATIVES_SYSTEM_PROMPT": asgf_service._ALTERNATIVES_SYSTEM_PROMPT,
    "_PLAN_SYSTEM_PROMPT": asgf_service._PLAN_SYSTEM_PROMPT,
}

REFACTORED_ILE_PROMPTS = {
    "_MCQ_SYSTEM": ile_question_service._MCQ_SYSTEM,
    "_FILL_BLANK_SYSTEM": ile_question_service._FILL_BLANK_SYSTEM,
    "_HINT_SYSTEM": ile_question_service._HINT_SYSTEM,
    "_EXPLANATION_SYSTEM": ile_question_service._EXPLANATION_SYSTEM,
}

ALL_REFACTORED_PROMPTS = {**REFACTORED_ASGF_PROMPTS, **REFACTORED_ILE_PROMPTS}


@pytest.mark.parametrize(
    ("name", "prompt"),
    list(ALL_REFACTORED_PROMPTS.items()),
)
def test_prompt_does_not_ask_user_for_context(name, prompt):
    """Refactored prompts must not instruct the model to ask the user for context."""
    lowered = prompt.lower()
    hits = [phrase for phrase in FORBIDDEN_PHRASES if phrase in lowered]
    assert not hits, (
        f"Prompt {name} regressed to context-first posture — "
        f"contains forbidden phrase(s): {hits}"
    )


@pytest.mark.parametrize(
    ("name", "prompt"),
    list(ALL_REFACTORED_PROMPTS.items()),
)
def test_prompt_has_answer_first_posture(name, prompt):
    """Each refactored prompt explicitly adopts the answer-first posture."""
    lowered = prompt.lower()
    signals = ("answer-first", "never refuse", "never ask", "default", "infer")
    assert any(sig in lowered for sig in signals), (
        f"Prompt {name} is missing answer-first signal — "
        f"expected one of {signals}"
    )
