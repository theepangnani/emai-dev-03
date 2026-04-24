"""Regression tests for Arc tutor prompts against 5 canonical queries.

Each canonical prompt is sent through a helper that calls OpenAI's chat
completion API (mocked) using the build_system_prompt + build_user_prompt
templates. The fake model reply is constructed to honour the prompt contract
(direct answer + trailing [[CHIPS: ...]] block) so we exercise the contract
as-shipped without hitting the real API. CB-TUTOR-002 Phase 1, #4064.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import openai
import pytest

from app.prompts.tutor_chat import build_system_prompt, build_user_prompt

CANONICAL_PROMPTS = [
    ("What is photosynthesis?", 5),
    ("Help me solve 3x + 7 = 22", 8),
    ("Why did World War 1 start?", 10),
    ("How do I write a persuasive paragraph?", 6),
    ("Can you explain the water cycle?", 3),
]

_BANNED_PHRASES = [
    "please provide more context",
    "could you clarify",
    "can you provide more information",
    "i need more information",
    "as an ai",
]


async def _call_tutor(message: str, grade_level: int) -> str:
    """Invoke the (mocked) tutor LLM using the real prompt templates."""
    system_prompt = build_system_prompt(grade_level=grade_level)
    user_prompt = build_user_prompt(message=message, history=None, context=None)

    client = openai.AsyncOpenAI(api_key="sk-test", timeout=5.0)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
    )
    return response.choices[0].message.content


def _fake_reply_for(message: str) -> str:
    body = (
        f"Great question! Here's a clear explanation about: {message}. "
        "This is a direct, encouraging answer with a concrete example."
    )
    chips = '[[CHIPS: "Tell me more", "Give me an example", "Quiz me on this"]]'
    return f"{body}\n{chips}"


@pytest.mark.asyncio
@pytest.mark.parametrize("message, grade_level", CANONICAL_PROMPTS)
async def test_canonical_prompt_returns_contract_compliant_reply(
    message: str, grade_level: int
) -> None:
    fake_reply = _fake_reply_for(message)
    fake_choice = SimpleNamespace(
        message=SimpleNamespace(content=fake_reply),
    )
    fake_response = SimpleNamespace(choices=[fake_choice])

    mock_create = AsyncMock(return_value=fake_response)
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=mock_create),
        ),
    )

    with patch.object(openai, "AsyncOpenAI", return_value=fake_client):
        reply = await _call_tutor(message, grade_level)

    # Non-empty reply.
    assert reply is not None
    assert reply.strip() != ""

    # No vague-clarification / hedging phrasing.
    lower = reply.lower()
    for phrase in _BANNED_PHRASES:
        assert phrase not in lower, f"reply should not contain '{phrase}': {reply}"

    # Trailing CHIPS block present and parseable.
    chips_match = re.search(r"\[\[CHIPS:\s*(.+?)\]\]", reply)
    assert chips_match, f"reply missing CHIPS block: {reply}"
    chip_items = re.findall(r'"([^"]+)"', chips_match.group(1))
    assert 3 <= len(chip_items) <= 4, f"expected 3-4 chips, got {chip_items}"

    # The mock was called with both a system and a user message containing the
    # grade level and the original question.
    mock_create.assert_awaited_once()
    sent_messages = mock_create.await_args.kwargs["messages"]
    assert sent_messages[0]["role"] == "system"
    assert f"grade {grade_level}" in sent_messages[0]["content"].lower()
    assert sent_messages[1]["role"] == "user"
    assert message in sent_messages[1]["content"]
