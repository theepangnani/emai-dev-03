"""Unit tests for app/services/cmcp/parent_companion_service.py.

Per CB-CMCP-001 M1-F 1F-1 (#4463) acceptance criteria:
- Generate returns a non-empty summary for valid inputs (happy path)
- Returns None for empty study_guide_content
- System prompt content snapshot
- Claude API is mocked — no real API calls
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cmcp.parent_companion_service import (
    PARENT_COMPANION_SYSTEM_PROMPT,
    ParentCompanionService,
)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_summary_for_valid_input():
    """Happy path: returns the AI-produced summary string for valid inputs."""
    mock_response = (
        "Haashini is preparing for a Grade 8 science lab on cell division.\n"
        "Here are 3 ways you can support her tonight:\n"
        "1. Ask her to explain the difference between mitosis and meiosis\n"
        "2. Help her review the key vocabulary terms highlighted in yellow\n"
        "3. Quiz her on the practice questions at the end of the study guide"
    )

    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (mock_response, "end_turn")

        result = await ParentCompanionService.generate(
            study_guide_content="# Cell Division\n\nMitosis vs meiosis...",
            student_name="Haashini",
            subject="Grade 8 Science",
            document_type="lab_experiment",
            study_goal="lab_prep",
        )

        assert result == mock_response.strip()
        mock_gen.assert_awaited_once()
        call_kwargs = mock_gen.await_args.kwargs
        # Verify the system prompt is passed through unchanged
        assert call_kwargs["system_prompt"] == PARENT_COMPANION_SYSTEM_PROMPT
        # Verify the prompt body includes the student's name and subject context
        assert "Haashini" in call_kwargs["prompt"]
        assert "Grade 8 Science" in call_kwargs["prompt"]
        # Sanity-check max_tokens / temperature defaults (port behaviour)
        assert call_kwargs["max_tokens"] == 500
        assert call_kwargs["temperature"] == 0.7


@pytest.mark.asyncio
async def test_generate_uses_defaults_when_optional_fields_missing():
    """Without student_name / subject, the service falls back to generic phrasing."""
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = ("Some summary text", "end_turn")

        result = await ParentCompanionService.generate(
            study_guide_content="Some study guide content with topics."
        )

        assert result == "Some summary text"
        prompt = mock_gen.await_args.kwargs["prompt"]
        assert "your child" in prompt
        assert "their course material" in prompt


# ---------------------------------------------------------------------------
# Empty / whitespace-only content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_none_for_empty_content():
    """Returns None when study_guide_content is empty (no AI call made)."""
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        result = await ParentCompanionService.generate(study_guide_content="")
        assert result is None
        mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_generate_returns_none_for_whitespace_only_content():
    """Whitespace-only content is treated as empty."""
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        result = await ParentCompanionService.generate(study_guide_content="   \n\t  ")
        assert result is None
        mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# AI failure handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_none_on_ai_failure():
    """Returns None when the AI call raises (logged, not re-raised)."""
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.side_effect = RuntimeError("AI service down")

        result = await ParentCompanionService.generate(
            study_guide_content="Some content",
            student_name="Alex",
        )
        assert result is None


# ---------------------------------------------------------------------------
# System-prompt snapshot — guards against accidental drift in 1F-1.
# (1F-2 wave 2 will intentionally extend this prompt; updating the snapshot
# at that point is expected and explicit.)
# ---------------------------------------------------------------------------


def test_system_prompt_snapshot():
    """Snapshot test: PARENT_COMPANION_SYSTEM_PROMPT must match phase-2 source verbatim."""
    expected = """You are a friendly educational assistant on ClassBridge, a K-12 education platform.
You are writing a brief summary for a PARENT (not the student). Your goal is to help the parent understand what their child is studying and give them 3 specific, actionable ways to support their child's learning tonight.

Guidelines:
- Use warm, encouraging language
- Keep it short (150-200 words max)
- Always include exactly 3 numbered action items
- Use the child's name if provided
- Mention the subject/topic clearly
- Make action items specific and practical (not generic like "help them study")
- Do NOT include any markdown headers or complex formatting — use plain text with numbered lists"""

    assert PARENT_COMPANION_SYSTEM_PROMPT == expected
