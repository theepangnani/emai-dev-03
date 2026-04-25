"""Unit tests for `dci_summary_service` (CB-DCI-001 M0-6).

Covers:
  * 3 fixture inputs (single-subject, multi-subject, no-voice) → non-empty
    bullets + non-empty conversation starter
  * cost-cap alert log fires above $0.05
  * idempotent re-run (same kid+date) issues a fresh DELETE before INSERT
  * model-override env flag swaps the model with no code branching
  * prompt-cache wiring (cache_control on system, tool, and 7-day context)
  * audit log records model_version, prompt_hash, input_hashes
"""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_message(payload: dict[str, Any], input_tok: int = 200, output_tok: int = 120):
    """Build a mock anthropic Message with one tool_use block."""
    msg = MagicMock()
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_daily_summary"
    block.input = payload
    msg.content = [block]
    usage = MagicMock()
    usage.input_tokens = input_tok
    usage.output_tokens = output_tok
    msg.usage = usage
    return msg


def _good_payload() -> dict[str, Any]:
    """A well-formed structured summary the model would emit."""
    return {
        "subjects": [
            {"name": "Math", "bullet": "Worked on long division word problems."},
            {"name": "Science", "bullet": "Started the plant-growth experiment journal."},
        ],
        "deadlines": [
            {"date": "2026-04-30", "label": "Permission slip due", "source": "photo"},
        ],
        "conversation_starter": {
            "text": "Did the long-division word problems feel easier than yesterday's set or trickier?",
            "tone": "curious",
        },
    }


def _events_single_subject() -> list[dict]:
    return [
        {
            "artifact_type": "photo",
            "subject": "Math",
            "topic": "long division",
            "strand_code": "B2.4",
            "deadline_iso": "2026-04-30",
            "confidence": 0.92,
            "corrected_by_kid": False,
            "excerpt": "Three pages of long-division practice problems.",
        }
    ]


def _events_multi_subject() -> list[dict]:
    return [
        {
            "artifact_type": "photo",
            "subject": "Math",
            "topic": "long division",
            "deadline_iso": "2026-04-30",
            "confidence": 0.91,
            "excerpt": "Three pages of long-division practice problems.",
        },
        {
            "artifact_type": "voice",
            "subject": "Science",
            "topic": "plant growth",
            "confidence": 0.85,
            "sentiment": 0.6,
            "excerpt": "Today we started watching the seeds we planted last week.",
        },
        {
            "artifact_type": "text",
            "subject": "Reading",
            "topic": "chapter 5",
            "confidence": 0.7,
            "excerpt": "We read chapter 5 of Charlotte's Web.",
        },
    ]


def _events_no_voice() -> list[dict]:
    return [
        {
            "artifact_type": "photo",
            "subject": "Math",
            "topic": "fractions",
            "confidence": 0.88,
            "excerpt": "Worksheet on equivalent fractions.",
        },
        {
            "artifact_type": "text",
            "subject": "Social Studies",
            "topic": "Confederation",
            "confidence": 0.74,
            "excerpt": "Notes on the 1867 Confederation map.",
        },
    ]


# ---------------------------------------------------------------------------
# 3 fixture inputs → non-empty bullets + non-empty starter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "events,fixture_name",
    [
        (_events_single_subject(), "single_subject"),
        (_events_multi_subject(), "multi_subject"),
        (_events_no_voice(), "no_voice"),
    ],
)
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_generate_summary_returns_non_empty(
    mock_get_client, events, fixture_name,
):
    """Each fixture returns ≥ 1 subject bullet and a non-empty starter."""
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    result = await generate_summary(
        kid_id=1,
        summary_date="2026-04-25",
        classification_events=events,
        prior_7day_context=None,
        kid_name="Haashini",
    )

    assert result["subjects"], f"{fixture_name}: expected non-empty subjects"
    assert all(s["name"] and s["bullet"] for s in result["subjects"])
    starter = result["conversation_starter"]
    assert starter["text"], f"{fixture_name}: starter text empty"
    assert starter["tone"], f"{fixture_name}: starter tone empty"
    assert len(starter["text"].split()) <= 25, (
        f"{fixture_name}: starter exceeds 25-word cap: {starter['text']!r}"
    )


# ---------------------------------------------------------------------------
# Conversation-starter 25-word cap is enforced even if model overshoots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_starter_word_cap_truncates_overlong(mock_get_client):
    from app.services.dci_summary_service import generate_summary

    payload = _good_payload()
    payload["conversation_starter"]["text"] = " ".join(["word"] * 40)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(payload)
    mock_get_client.return_value = mock_client

    result = await generate_summary(
        kid_id=1,
        summary_date="2026-04-25",
        classification_events=_events_single_subject(),
        prior_7day_context=None,
    )
    assert len(result["conversation_starter"]["text"].split()) == 25


# ---------------------------------------------------------------------------
# Cost-cap alert: cost > $0.05 logs WARNING with "ALERT"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_cost_alert_logs_warning_above_threshold(mock_get_client, caplog):
    from app.services.dci_summary_service import generate_summary

    # Sonnet 4.6 pricing in ai_service: ($3/$15 per 1M tokens). To exceed
    # $0.05 we need roughly 5000 input + 1500 output tokens — pick something
    # comfortably above so the threshold triggers regardless of rounding.
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(
        _good_payload(), input_tok=10_000, output_tok=2_000,
    )
    mock_get_client.return_value = mock_client

    with caplog.at_level(logging.WARNING, logger="app.services.dci_summary_service"):
        await generate_summary(
            kid_id=1,
            summary_date="2026-04-25",
            classification_events=_events_multi_subject(),
        )

    alert_logs = [r for r in caplog.records if "ALERT" in r.getMessage()]
    assert alert_logs, "Expected cost ALERT log above $0.05 threshold"


@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_cost_under_target_no_alert(mock_get_client, caplog):
    """Sub-target cost (≤ $0.02) does NOT emit the alert log."""
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    # 100 in / 50 out on Sonnet ≈ $0.0011 — well under target.
    mock_client.messages.create.return_value = _make_message(
        _good_payload(), input_tok=100, output_tok=50,
    )
    mock_get_client.return_value = mock_client

    with caplog.at_level(logging.WARNING, logger="app.services.dci_summary_service"):
        await generate_summary(
            kid_id=1, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
        )

    assert not [r for r in caplog.records if "ALERT" in r.getMessage()]


# ---------------------------------------------------------------------------
# Idempotent re-run: same kid+date → DELETE-then-INSERT against the DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_idempotent_rerun_replaces_existing_row(mock_get_client):
    """Two runs for same (kid_id, date) → 2nd run issues a DELETE."""
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    # Mock the dci models module so _persist_summary can run end-to-end.
    fake_summary_row = MagicMock(id=42)
    fake_starter_row = MagicMock(id=99)

    fake_models = MagicMock()
    fake_models.AiSummary = MagicMock(return_value=fake_summary_row)
    fake_models.ConversationStarter = MagicMock(return_value=fake_starter_row)

    fake_db = MagicMock()
    # query(...).filter(...).delete(...) chain
    delete_chain = fake_db.query.return_value.filter.return_value
    delete_chain.delete.return_value = 0  # nothing existed yet

    with patch.dict("sys.modules", {"app.models.dci": fake_models}):
        # 1st run
        await generate_summary(
            kid_id=7, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
            db=fake_db,
        )
        first_delete_calls = delete_chain.delete.call_count

        # 2nd run — same kid+date
        delete_chain.delete.return_value = 1  # now there's an existing row to nuke
        await generate_summary(
            kid_id=7, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
            db=fake_db,
        )
        second_delete_calls = delete_chain.delete.call_count

    # Each run must issue exactly one DELETE (idempotent REPLACE pattern).
    assert second_delete_calls == first_delete_calls + 1


# ---------------------------------------------------------------------------
# Model-override env flag swaps the model — no branching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_model_override_env_flag_swaps_model(mock_get_client):
    from app.services import dci_summary_service
    from app.services.dci_summary_service import (
        DCI_SUMMARY_MODEL_DEFAULT,
        generate_summary,
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    # Default → Sonnet 4.6
    with patch.object(
        dci_summary_service.settings, "dci_summary_model_override", None,
    ):
        await generate_summary(
            kid_id=1, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
        )
        assert mock_client.messages.create.call_args.kwargs["model"] == DCI_SUMMARY_MODEL_DEFAULT

    # Override → Opus 4.7 (single env var, no code branching)
    mock_client.messages.create.reset_mock()
    with patch.object(
        dci_summary_service.settings, "dci_summary_model_override", "claude-opus-4-7",
    ):
        await generate_summary(
            kid_id=1, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
        )
        assert mock_client.messages.create.call_args.kwargs["model"] == "claude-opus-4-7"


# ---------------------------------------------------------------------------
# Prompt cache wiring: cache_control attached to system + tool + context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_prompt_cache_wiring(mock_get_client):
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    await generate_summary(
        kid_id=1, summary_date="2026-04-25",
        classification_events=_events_single_subject(),
        prior_7day_context=[
            {"summary_date": "2026-04-24",
             "subjects": [{"name": "Math", "bullet": "earlier work"}]},
        ],
    )

    kwargs = mock_client.messages.create.call_args.kwargs

    # System prompt cached
    assert isinstance(kwargs["system"], list)
    assert kwargs["system"][0].get("cache_control") == {"type": "ephemeral"}

    # Tool schema cached
    assert kwargs["tools"][0].get("cache_control") == {"type": "ephemeral"}

    # 7-day context block cached (second user content block)
    user_blocks = kwargs["messages"][0]["content"]
    assert isinstance(user_blocks, list)
    assert len(user_blocks) == 2
    assert user_blocks[1].get("cache_control") == {"type": "ephemeral"}
    assert "CONTEXT" in user_blocks[1]["text"]

    # Forced tool_choice for deterministic structured output
    assert kwargs["tool_choice"] == {"type": "tool", "name": "emit_daily_summary"}


# ---------------------------------------------------------------------------
# Audit row carries model_version, prompt_hash, input_hashes (NFR5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.log_action")
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_audit_records_provenance(mock_get_client, mock_log_action):
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.delete.return_value = 0

    await generate_summary(
        kid_id=3, summary_date="2026-04-25",
        classification_events=_events_single_subject(),
        db=fake_db,
    )

    assert mock_log_action.called, "Audit log_action must be called"
    details = mock_log_action.call_args.kwargs["details"]
    assert "model_version" in details
    assert "prompt_hash" in details
    assert "input_hashes" in details
    assert isinstance(details["input_hashes"], dict)
    # Each input dimension hashed independently
    assert {"classification_events", "prior_7day_context", "summary_date"} <= set(
        details["input_hashes"].keys()
    )
    assert mock_log_action.call_args.kwargs["action"] == "dci.summary.generated"
    assert mock_log_action.call_args.kwargs["resource_type"] == "ai_summary"


# ---------------------------------------------------------------------------
# Defensive: model returns no tool_use block → ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_missing_tool_use_block_raises(mock_get_client):
    from app.services.dci_summary_service import generate_summary

    msg = MagicMock()
    msg.content = []  # no tool_use
    msg.usage.input_tokens = 50
    msg.usage.output_tokens = 10

    mock_client = MagicMock()
    mock_client.messages.create.return_value = msg
    mock_get_client.return_value = mock_client

    with pytest.raises(ValueError, match="no tool_use block"):
        await generate_summary(
            kid_id=1, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
        )
