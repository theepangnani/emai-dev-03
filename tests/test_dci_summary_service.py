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
    # query(...).filter(...).delete(...) chain — the AiSummary delete is the
    # idempotent guard we count. (The starter pre-purge only fires when
    # existing_ids is non-empty; we cover both legs in this test.)
    chain = fake_db.query.return_value.filter.return_value
    chain.delete.return_value = 0  # nothing existed yet on 1st run
    chain.all.return_value = []    # no existing AiSummary rows on 1st run

    with patch.dict("sys.modules", {"app.models.dci": fake_models}):
        # 1st run — empty DB
        await generate_summary(
            kid_id=7, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
            db=fake_db,
        )
        first_delete_calls = chain.delete.call_count

        # 2nd run — pretend the 1st run wrote a row that we now must replace.
        chain.delete.return_value = 1
        chain.all.return_value = [(42,)]  # existing AiSummary id tuple
        await generate_summary(
            kid_id=7, summary_date="2026-04-25",
            classification_events=_events_single_subject(),
            db=fake_db,
        )
        second_delete_calls = chain.delete.call_count

    # 1st run: exactly one DELETE (the AiSummary delete; starter pre-purge
    # is skipped because existing_ids is empty).
    # 2nd run: two DELETEs (starter pre-purge + AiSummary delete).
    assert first_delete_calls == 1, (
        f"1st run should issue 1 DELETE (AiSummary only), got {first_delete_calls}"
    )
    assert second_delete_calls == first_delete_calls + 2, (
        "2nd run should issue 2 more DELETEs (starter pre-purge + AiSummary)"
    )

    # Sharper assertion: verify the 2nd run actually queried
    # ConversationStarter (the starter pre-purge) — without this, the
    # delete-count check above could pass even if the code accidentally
    # ran two AiSummary deletes. Compare query() positional args by
    # identity against the fake model classes.
    queried_args = [
        call.args[0] for call in fake_db.query.call_args_list if call.args
    ]
    # ConversationStarter is the bare class (used in `db.query(ConversationStarter)`),
    # whereas AiSummary is queried both as the class (DELETE) and as
    # `AiSummary.id` (the existing-id lookup, which is an attribute access on
    # the MagicMock — a *different* identity). So the only call where
    # the positional arg IS `fake_models.ConversationStarter` is the
    # starter pre-purge, which only fires on run 2.
    assert fake_models.ConversationStarter in queried_args, (
        "2nd run must purge ConversationStarter rows before AiSummary; "
        "no db.query(ConversationStarter) call was recorded."
    )


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
    # Empty DB — no prior rows, audit fires either way.
    chain = fake_db.query.return_value.filter.return_value
    chain.delete.return_value = 0
    chain.all.return_value = []

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


# ---------------------------------------------------------------------------
# #4204 — cost thresholds resolved from Settings at call time
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_cost_thresholds_read_from_settings(mock_get_client, caplog):
    """Lowering `settings.dci_cost_alert_usd` triggers ALERT at lower cost."""
    from app.services import dci_summary_service
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    # ~$0.0011 cost — well under the 0.05 default but above a 0.0005
    # override, which lets us verify the override actually wires through.
    mock_client.messages.create.return_value = _make_message(
        _good_payload(), input_tok=100, output_tok=50,
    )
    mock_get_client.return_value = mock_client

    with patch.object(dci_summary_service.settings, "dci_cost_alert_usd", 0.0005), \
         patch.object(dci_summary_service.settings, "dci_cost_target_usd", 0.0001):
        with caplog.at_level(logging.WARNING, logger="app.services.dci_summary_service"):
            await generate_summary(
                kid_id=1, summary_date="2026-04-25",
                classification_events=_events_single_subject(),
            )

    alert_logs = [r for r in caplog.records if "ALERT" in r.getMessage()]
    assert alert_logs, (
        "Lowering dci_cost_alert_usd via settings should trigger ALERT log "
        "even at sub-cent cost."
    )


# ---------------------------------------------------------------------------
# #4205 — audit row carries BOTH prompt_hash and prompt_template_hash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.log_action")
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_audit_records_dual_prompt_hashes(mock_get_client, mock_log_action):
    """Audit details must include both prompt_hash and prompt_template_hash."""
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    fake_db = MagicMock()
    chain = fake_db.query.return_value.filter.return_value
    chain.delete.return_value = 0
    chain.all.return_value = []

    await generate_summary(
        kid_id=3, summary_date="2026-04-25",
        classification_events=_events_single_subject(),
        db=fake_db,
    )

    details = mock_log_action.call_args.kwargs["details"]
    assert "prompt_hash" in details
    assert "prompt_template_hash" in details
    assert details["prompt_hash"] != details["prompt_template_hash"], (
        "Envelope hash and template hash should differ — envelope includes "
        "today's user content blocks."
    )
    # Both must be 64-char SHA-256 hex strings.
    assert len(details["prompt_hash"]) == 64
    assert len(details["prompt_template_hash"]) == 64


@pytest.mark.asyncio
@patch("app.services.dci_summary_service.log_action")
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_prompt_template_hash_stable_across_days(
    mock_get_client, mock_log_action,
):
    """prompt_template_hash must NOT change when only today's events change."""
    from app.services.dci_summary_service import generate_summary

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(_good_payload())
    mock_get_client.return_value = mock_client

    fake_db = MagicMock()
    chain = fake_db.query.return_value.filter.return_value
    chain.delete.return_value = 0
    chain.all.return_value = []

    # Day 1
    await generate_summary(
        kid_id=3, summary_date="2026-04-25",
        classification_events=_events_single_subject(),
        db=fake_db,
    )
    day1 = mock_log_action.call_args.kwargs["details"]

    # Day 2 — different events, different date.
    await generate_summary(
        kid_id=3, summary_date="2026-04-26",
        classification_events=_events_multi_subject(),
        db=fake_db,
    )
    day2 = mock_log_action.call_args.kwargs["details"]

    assert day1["prompt_template_hash"] == day2["prompt_template_hash"], (
        "prompt_template_hash must be stable across days — only system + "
        "tool schema feed it."
    )
    assert day1["prompt_hash"] != day2["prompt_hash"], (
        "prompt_hash MUST differ across days — user content block changes."
    )


# ---------------------------------------------------------------------------
# #4206 — long excerpt prompt-block carries truncation marker
# ---------------------------------------------------------------------------

def test_build_today_block_marks_truncated_excerpts():
    """Excerpts > 400 chars are suffixed with `… [truncated]`."""
    from app.services.dci_prompts import build_today_block

    long_excerpt = "abcdefghij" * 50  # 500 chars
    short_excerpt = "short note"
    events = [
        {"artifact_type": "photo", "subject": "Math", "excerpt": long_excerpt},
        {"artifact_type": "text", "subject": "Reading", "excerpt": short_excerpt},
    ]
    block = build_today_block(events, "2026-04-25")

    assert "… [truncated]" in block, (
        "Truncation marker missing — model would treat chopped excerpt as complete."
    )
    # The short excerpt should NOT be flagged as truncated.
    short_line = [ln for ln in block.splitlines() if "short note" in ln]
    assert short_line, "Short excerpt should appear verbatim."
    assert "[truncated]" not in short_line[0]


# ---------------------------------------------------------------------------
# #4207 — smart starter trim preserves question mark / clause boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_smart_starter_trim_reappends_question_mark(mock_get_client):
    """Overflow starter that ended with ? gets a ? back after trim."""
    from app.services.dci_summary_service import generate_summary

    payload = _good_payload()
    # 30-word interrogative — chopped at 25 words should still end with ?
    payload["conversation_starter"]["text"] = (
        "Did the long division word problems feel a little easier today "
        "compared with the practice set you tackled together yesterday "
        "after your snack and quick break?"
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(payload)
    mock_get_client.return_value = mock_client

    result = await generate_summary(
        kid_id=1, summary_date="2026-04-25",
        classification_events=_events_single_subject(),
    )
    text = result["conversation_starter"]["text"]
    assert text.endswith("?"), (
        f"Smart trim should preserve interrogative tone, got: {text!r}"
    )
    assert len(text.split()) <= 25


@pytest.mark.asyncio
@patch("app.services.dci_summary_service.get_anthropic_client")
async def test_smart_starter_trim_prefers_sentence_boundary(mock_get_client):
    """When a clean clause-end sits within the 25-word window, prefer it."""
    from app.services.dci_summary_service import generate_summary

    payload = _good_payload()
    # Sentence ends at word ~18 with "?"; 30 total words — trim should
    # prefer the in-window question mark.
    payload["conversation_starter"]["text"] = (
        "Which part of the long division practice felt like the biggest "
        "win for you today and why did it click? "
        "Also tell me more about the Confederation notes you made."
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_message(payload)
    mock_get_client.return_value = mock_client

    result = await generate_summary(
        kid_id=1, summary_date="2026-04-25",
        classification_events=_events_single_subject(),
    )
    text = result["conversation_starter"]["text"]
    assert text.endswith("?"), (
        f"Smart trim should land on the in-window `?`, got: {text!r}"
    )
    # The trailing "Also tell me more…" clause must be gone.
    assert "Confederation" not in text


# ---------------------------------------------------------------------------
# #4187 — subject taxonomy validator (shared with M0-4 PATCH endpoint)
# ---------------------------------------------------------------------------

def test_validate_subject_accepts_canonical_values():
    from app.services.dci_subject_taxonomy import (
        DCI_VALID_SUBJECTS,
        validate_subject,
    )

    for subj in DCI_VALID_SUBJECTS:
        assert validate_subject(subj) == subj


def test_validate_subject_rejects_freeform_and_case_variants():
    from app.services.dci_subject_taxonomy import validate_subject

    # Case-sensitive: "MATH" / "math" / "maths" are NOT canonical.
    assert validate_subject("MATH") is None
    assert validate_subject("math") is None
    assert validate_subject("maths") is None
    assert validate_subject("english class") is None
    assert validate_subject("Phys Ed") is None  # canonical is "Phys-Ed"
    # Empty / whitespace / None
    assert validate_subject("") is None
    assert validate_subject("   ") is None
    assert validate_subject(None) is None


def test_validate_subject_strips_surrounding_whitespace():
    from app.services.dci_subject_taxonomy import validate_subject

    assert validate_subject("  Math  ") == "Math"
    assert validate_subject("\tScience\n") == "Science"
