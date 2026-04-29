"""Unit tests for the 5-section extension of ParentCompanionService.

CB-CMCP-001 M1-F 1F-2 (#4474). Companion to `test_cmcp_parent_companion.py`
(1F-1 baseline) — these tests exercise the new `generate_5_section()` method
and the `ParentCompanionContent` Pydantic model only. The original `generate()`
contract is covered in the 1F-1 file and MUST remain green here.

Hard rules:
- Claude API is mocked — no real API calls.
- Answer-key lint is an explicit, auditable assertion.
- The original `generate()` method must still exist (backwards compat).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.cmcp.parent_companion_service import (
    ANSWER_KEY_MARKERS,
    MAX_TALKING_POINTS,
    MIN_TALKING_POINTS,
    PARENT_COMPANION_5_SECTION_SYSTEM_PROMPT,
    BridgeDeepLinkPayload,
    ParentCompanionContent,
    ParentCompanionService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_payload(talking_points_count: int = 3) -> dict:
    """Return a clean, lint-safe model payload with the requested TP count."""
    talking_points = [
        f"Ask {n}-th open-ended question about cell division." for n in range(1, talking_points_count + 1)
    ]
    return {
        "se_explanation": (
            "Your child is learning how living cells reproduce and pass on traits. "
            "This week focuses on comparing two ways cells divide."
        ),
        "talking_points": talking_points,
        "coaching_prompts": [
            "Can you describe in your own words what mitosis does?",
            "What surprised you about meiosis today?",
        ],
        "how_to_help_without_giving_answer": (
            "Stay curious and ask follow-up questions instead of solving it for them. "
            "If they get stuck, prompt them to re-read the diagram and try again."
        ),
    }


def _ai_returns(payload: dict) -> str:
    """Serialize a payload as the AI's raw JSON response."""
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Backwards compat — original generate() must still exist (HARD RULE).
# ---------------------------------------------------------------------------


def test_original_generate_method_still_exists():
    """Hard rule: 1F-2 MUST NOT remove the original `generate()` method."""
    assert hasattr(ParentCompanionService, "generate")
    # And must be a coroutine function (async).
    import inspect

    assert inspect.iscoroutinefunction(ParentCompanionService.generate)


def test_generate_5_section_method_exists_and_is_async():
    assert hasattr(ParentCompanionService, "generate_5_section")
    import inspect

    assert inspect.iscoroutinefunction(ParentCompanionService.generate_5_section)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_5_section_returns_content_with_all_fields():
    payload = _valid_payload(talking_points_count=3)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (_ai_returns(payload), "end_turn")

        result = await ParentCompanionService.generate_5_section(
            study_guide_content="# Cell Division\n\nMitosis vs meiosis...",
            student_name="Haashini",
            subject="Grade 8 Science",
            target_se_codes=["B2.3"],
            target_se_descriptions=["Compare the processes of mitosis and meiosis."],
            talking_points_count=3,
            child_id=42,
            deep_link_target="bridge:/kids/42/week",
            week_summary="Week of Apr 27",
        )

        assert isinstance(result, ParentCompanionContent)
        # All five sections populated.
        assert result.se_explanation
        assert len(result.talking_points) == 3
        assert len(result.coaching_prompts) >= 1
        assert result.how_to_help_without_giving_answer
        assert isinstance(result.bridge_deep_link_payload, BridgeDeepLinkPayload)
        assert result.bridge_deep_link_payload.child_id == 42
        assert result.bridge_deep_link_payload.week_summary == "Week of Apr 27"
        assert result.bridge_deep_link_payload.deep_link_target == "bridge:/kids/42/week"

        # System prompt routed correctly.
        call_kwargs = mock_gen.await_args.kwargs
        assert call_kwargs["system_prompt"] == PARENT_COMPANION_5_SECTION_SYSTEM_PROMPT
        # Student name + subject + descriptions appear in the user prompt.
        prompt = call_kwargs["prompt"]
        assert "Haashini" in prompt
        assert "Grade 8 Science" in prompt
        assert "mitosis and meiosis" in prompt


@pytest.mark.asyncio
async def test_generate_5_section_falls_back_to_generic_when_optional_fields_missing():
    payload = _valid_payload(talking_points_count=3)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (_ai_returns(payload), "end_turn")

        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Some study guide content."
        )

        assert isinstance(result, ParentCompanionContent)
        prompt = mock_gen.await_args.kwargs["prompt"]
        assert "your child" in prompt
        assert "their course material" in prompt
        # No SE descriptions/codes were provided.
        assert "Internal curriculum targets" not in prompt
        assert "This week's learning targets" not in prompt


# ---------------------------------------------------------------------------
# talking_points_count param respect (FR-02.6 configurable count)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("requested,expected_in_prompt", [(3, 3), (5, 5), (4, 4)])
@pytest.mark.asyncio
async def test_generate_5_section_respects_talking_points_count(requested, expected_in_prompt):
    payload = _valid_payload(talking_points_count=expected_in_prompt)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (_ai_returns(payload), "end_turn")

        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content.",
            talking_points_count=requested,
        )

        assert isinstance(result, ParentCompanionContent)
        assert len(result.talking_points) == expected_in_prompt
        # The user prompt must encode the clamped count.
        prompt = mock_gen.await_args.kwargs["prompt"]
        assert f"EXACTLY {expected_in_prompt} talking_points" in prompt


@pytest.mark.asyncio
async def test_generate_5_section_clamps_talking_points_count_above_max():
    """Requested 10 → clamped to MAX_TALKING_POINTS (5)."""
    payload = _valid_payload(talking_points_count=MAX_TALKING_POINTS)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (_ai_returns(payload), "end_turn")

        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content.",
            talking_points_count=10,
        )

        assert result is not None
        prompt = mock_gen.await_args.kwargs["prompt"]
        assert f"EXACTLY {MAX_TALKING_POINTS} talking_points" in prompt


@pytest.mark.asyncio
async def test_generate_5_section_clamps_talking_points_count_below_min():
    """Requested 1 → clamped to MIN_TALKING_POINTS (3)."""
    payload = _valid_payload(talking_points_count=MIN_TALKING_POINTS)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (_ai_returns(payload), "end_turn")

        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content.",
            talking_points_count=1,
        )

        assert result is not None
        prompt = mock_gen.await_args.kwargs["prompt"]
        assert f"EXACTLY {MIN_TALKING_POINTS} talking_points" in prompt


# ---------------------------------------------------------------------------
# Empty / whitespace input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_for_empty_content():
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        result = await ParentCompanionService.generate_5_section(study_guide_content="")
        assert result is None
        mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_for_whitespace_only_content():
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        result = await ParentCompanionService.generate_5_section(study_guide_content="  \n\t  ")
        assert result is None
        mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_on_ai_exception():
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.side_effect = RuntimeError("AI down")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_on_invalid_json():
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = ("This is not JSON at all.", "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_on_non_object_json():
    """The model returned a JSON list rather than the expected object."""
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(["not", "an", "object"]), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_on_schema_validation_failure():
    """Missing required fields → Pydantic rejects → service returns None."""
    bad_payload = {"se_explanation": "only one field"}
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(bad_payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_when_talking_points_below_min():
    """Pydantic min_length=3 → fewer items rejected."""
    payload = _valid_payload(talking_points_count=3)
    payload["talking_points"] = ["only one tp"]
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_returns_none_when_talking_points_above_max():
    """Pydantic max_length=5 → too many items rejected."""
    payload = _valid_payload(talking_points_count=5)
    payload["talking_points"] = [f"tp {i}" for i in range(6)]  # 6 > MAX_TALKING_POINTS
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


# ---------------------------------------------------------------------------
# JSON-fence tolerance — model sometimes wraps despite instruction.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_5_section_tolerates_markdown_json_fences():
    payload = _valid_payload(talking_points_count=3)
    fenced = f"```json\n{json.dumps(payload)}\n```"
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (fenced, "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert isinstance(result, ParentCompanionContent)


@pytest.mark.asyncio
async def test_generate_5_section_tolerates_bare_triple_backtick_fence():
    payload = _valid_payload(talking_points_count=3)
    fenced = f"```\n{json.dumps(payload)}\n```"
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (fenced, "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert isinstance(result, ParentCompanionContent)


# ---------------------------------------------------------------------------
# A2 ACCEPTANCE — answer-key lint (auditable). Output MUST NOT contain markers.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", list(ANSWER_KEY_MARKERS))
@pytest.mark.asyncio
async def test_generate_5_section_rejects_output_containing_answer_key_marker_in_se_explanation(
    marker,
):
    payload = _valid_payload(talking_points_count=3)
    # Embed marker (case-insensitive match).
    payload["se_explanation"] = (
        f"Your child is learning division. {marker.upper()} 12 divided by 3 is 4. "
        "This week we work on long division."
    )
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_rejects_marker_in_talking_points():
    payload = _valid_payload(talking_points_count=3)
    payload["talking_points"][0] = "The answer is 42 — quiz them on this."
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_rejects_marker_in_coaching_prompts():
    payload = _valid_payload(talking_points_count=3)
    payload["coaching_prompts"][0] = "Solution: write the steps in order."
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_rejects_marker_in_how_to_help_field():
    payload = _valid_payload(talking_points_count=3)
    payload["how_to_help_without_giving_answer"] = (
        "Here is the answer key — share it once they finish."
    )
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.parametrize(
    "evasion_phrase",
    [
        "answer :",  # extra space before colon
        "the  answer  is",  # collapsed multi-space variant
        "ANSWER:\t42",  # tab whitespace + uppercase
        "answer\nkey",  # newline between words
        "Solution:\t",  # solution with tab
    ],
)
@pytest.mark.asyncio
async def test_generate_5_section_lint_resists_whitespace_evasion(evasion_phrase):
    """A2 acceptance hardening: whitespace-padded markers must still be caught.

    The lint normalizes whitespace before substring matching, so adversarial
    or accidental variants like 'answer :' (extra space) or 'the  answer  is'
    (double space) trip it the same as the canonical marker.
    """
    payload = _valid_payload(talking_points_count=3)
    payload["se_explanation"] = (
        f"Your child is learning division. {evasion_phrase} 12 divided by 3 is 4. "
        "This week we work on long division."
    )
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is None


@pytest.mark.asyncio
async def test_generate_5_section_clean_output_passes_lint():
    """Sanity: a payload with NO markers is accepted and returned as-is."""
    payload = _valid_payload(talking_points_count=4)
    # Belt-and-suspenders: scrub every text field for any marker substring.
    text_fields = [
        payload["se_explanation"],
        payload["how_to_help_without_giving_answer"],
        *payload["talking_points"],
        *payload["coaching_prompts"],
    ]
    for field_text in text_fields:
        for marker in ANSWER_KEY_MARKERS:
            assert marker not in field_text.lower()

    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content.",
            talking_points_count=4,
        )
        assert isinstance(result, ParentCompanionContent)
        assert len(result.talking_points) == 4


# ---------------------------------------------------------------------------
# SE-target context wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_5_section_includes_se_descriptions_in_prompt_when_provided():
    payload = _valid_payload(talking_points_count=3)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        await ParentCompanionService.generate_5_section(
            study_guide_content="Content.",
            target_se_descriptions=["Describe how cells reproduce."],
        )
        prompt = mock_gen.await_args.kwargs["prompt"]
        assert "This week's learning targets" in prompt
        assert "Describe how cells reproduce." in prompt


@pytest.mark.asyncio
async def test_generate_5_section_falls_back_to_codes_when_descriptions_missing():
    payload = _valid_payload(talking_points_count=3)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        await ParentCompanionService.generate_5_section(
            study_guide_content="Content.",
            target_se_codes=["B2.3", "B2.4"],
        )
        prompt = mock_gen.await_args.kwargs["prompt"]
        # The instruction explicitly forbids leaking codes — the prompt
        # carries them internally with a "do not include" warning.
        assert "Internal curriculum targets" in prompt
        assert "B2.3" in prompt


# ---------------------------------------------------------------------------
# bridge_deep_link_payload defaults
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_5_section_deep_link_payload_defaults_to_none_fields():
    payload = _valid_payload(talking_points_count=3)
    with patch(
        "app.services.cmcp.parent_companion_service.generate_content",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (json.dumps(payload), "end_turn")
        result = await ParentCompanionService.generate_5_section(
            study_guide_content="Content."
        )
        assert result is not None
        assert isinstance(result.bridge_deep_link_payload, BridgeDeepLinkPayload)
        assert result.bridge_deep_link_payload.child_id is None
        assert result.bridge_deep_link_payload.week_summary is None
        assert result.bridge_deep_link_payload.deep_link_target is None


# ---------------------------------------------------------------------------
# System-prompt sanity (5-section) — does NOT replace 1F-1's snapshot.
# ---------------------------------------------------------------------------


def test_5_section_system_prompt_demands_pure_json():
    """The 5-section system prompt must instruct the model to output PURE JSON."""
    p = PARENT_COMPANION_5_SECTION_SYSTEM_PROMPT
    assert "JSON" in p
    # Must list all five model-generated fields by name.
    assert "se_explanation" in p
    assert "talking_points" in p
    assert "coaching_prompts" in p
    assert "how_to_help_without_giving_answer" in p


def test_5_section_system_prompt_forbids_answer_keys():
    """The system prompt itself must forbid answer-key content (defense in depth)."""
    p = PARENT_COMPANION_5_SECTION_SYSTEM_PROMPT.lower()
    # The prompt explicitly enumerates banned phrases.
    assert "answer key" in p or "answer keys" in p
    assert "answer:" in p
    assert "the answer is" in p
