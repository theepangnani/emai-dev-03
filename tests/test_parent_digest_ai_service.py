"""Unit tests for parent_digest_ai_service.

Covers both:
- :func:`extract_digest_items` (#3917 / CB-TASKSYNC-001 I5) — tool-use extraction
- :func:`generate_sectioned_digest` (#3956) — sectioned 3×3 JSON path

The existing HTML-digest tests live in
``tests/test_parent_email_digest_services.py`` and MUST keep passing.
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest


def _make_tool_use_message(tool_input: dict | None, input_tokens: int = 100, output_tokens: int = 40):
    """Build a mock Anthropic Message with a single tool_use content block."""
    message = MagicMock()
    if tool_input is None:
        # No tool_use block at all
        message.content = []
    else:
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "extract_urgent_items"
        tool_block.input = tool_input
        message.content = [tool_block]
    message.usage.input_tokens = input_tokens
    message.usage.output_tokens = output_tokens
    return message


def _emails_fixture() -> list[dict]:
    return [
        {
            "source_id": "gmail-msg-1",
            "sender_name": "Ms. Johnson",
            "sender_email": "teacher@school.ca",
            "subject": "Permission slip due",
            "body": "Please sign by Friday May 2.",
        },
        {
            "source_id": "gmail-msg-2",
            "sender_name": "Principal Smith",
            "sender_email": "principal@school.ca",
            "subject": "Pizza day RSVP",
            "body": "RSVP by April 30.",
        },
    ]


class TestExtractDigestItems:
    """Covers :func:`extract_digest_items` happy and failure paths."""

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_returns_valid_items(self, mock_get_client):
        """Tool returns 2 items → 2 DigestTaskItem objects with source_id mapped."""
        from app.services.parent_digest_ai_service import extract_digest_items, DigestTaskItem

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message({
            "urgent_items": [
                {
                    "title": "Sign permission slip",
                    "due_date": "2026-05-02",
                    "course_or_context": "Grade 3",
                    "confidence": 0.95,
                    "source_email_excerpt": "Please sign by Friday May 2.",
                    "source_email_index": 1,
                },
                {
                    "title": "RSVP pizza day",
                    "due_date": "2026-04-30",
                    "course_or_context": None,
                    "confidence": 0.82,
                    "source_email_excerpt": "RSVP by April 30.",
                    "source_email_index": 2,
                },
            ]
        })
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture())

        assert len(result) == 2
        assert all(isinstance(r, DigestTaskItem) for r in result)
        assert result[0].title == "Sign permission slip"
        assert result[0].gmail_message_id == "gmail-msg-1"
        assert result[0].confidence == pytest.approx(0.95)
        assert result[0].course_name == "Grade 3"
        assert result[1].gmail_message_id == "gmail-msg-2"
        assert result[1].course_name is None

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_handles_empty_tool_call(self, mock_get_client):
        """Tool returns urgent_items=[] → function returns []."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message({"urgent_items": []})
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture())
        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_handles_missing_tool_block(self, mock_get_client):
        """Response with no tool_use block → returns []."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message(None)
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture())
        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.logger")
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_handles_api_error(self, mock_get_client, mock_logger):
        """API exception → returns [] and logs error (never raises)."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("anthropic 500")
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture())

        assert result == []
        # error path logs with "failed" in the message
        assert mock_logger.error.called
        args, _ = mock_logger.error.call_args
        assert "failed" in args[0].lower()

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_sets_cache_control(self, mock_get_client):
        """cache_control: ephemeral is set on BOTH the tool schema and system prompt."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message({"urgent_items": []})
        mock_get_client.return_value = mock_client

        await extract_digest_items(_emails_fixture())

        kwargs = mock_client.messages.create.call_args.kwargs

        # System prompt is passed as a list of text blocks with cache_control
        system = kwargs["system"]
        assert isinstance(system, list) and len(system) >= 1
        assert system[0].get("cache_control") == {"type": "ephemeral"}
        assert system[0].get("type") == "text"
        assert "ClassBridge" in system[0]["text"]

        # Tool schema has cache_control attached
        tools = kwargs["tools"]
        assert isinstance(tools, list) and len(tools) == 1
        assert tools[0]["name"] == "extract_urgent_items"
        assert tools[0].get("cache_control") == {"type": "ephemeral"}

        # Tool choice forces the extraction tool
        assert kwargs["tool_choice"] == {"type": "tool", "name": "extract_urgent_items"}

        # Deterministic extraction config locked in
        assert kwargs["max_tokens"] == 1024
        assert kwargs["temperature"] == 0.0
        assert kwargs["model"] == "claude-haiku-4-5-20251001"

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_parses_due_date_in_timezone(self, mock_get_client):
        """'2026-05-02' in America/Toronto → 2026-05-02 00:00 EDT == 2026-05-02 04:00 UTC."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message({
            "urgent_items": [{
                "title": "Sign slip",
                "due_date": "2026-05-02",
                "course_or_context": None,
                "confidence": 0.9,
                "source_email_excerpt": "due May 2",
                "source_email_index": 1,
            }]
        })
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture(), tz_name="America/Toronto")

        assert len(result) == 1
        due = result[0].due_date
        assert due.tzinfo is not None
        # Local midnight in Toronto
        assert due.year == 2026 and due.month == 5 and due.day == 2
        assert due.hour == 0 and due.minute == 0
        # In UTC that's 04:00 (EDT is UTC-4 on May 2, 2026)
        assert due.astimezone(timezone.utc) == datetime(2026, 5, 2, 4, 0, tzinfo=timezone.utc)
        # And the tz is actually America/Toronto (not just some fixed offset)
        assert due.tzinfo == ZoneInfo("America/Toronto")

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_empty_email_list_short_circuits(self, mock_get_client):
        """Empty email list returns [] without hitting the API."""
        from app.services.parent_digest_ai_service import extract_digest_items

        result = await extract_digest_items([])
        assert result == []
        mock_get_client.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.logger")
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_bad_tz_falls_back_and_warns(self, mock_get_client, mock_logger):
        """Invalid IANA tz_name logs a warning once and falls back to America/Toronto."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message({
            "urgent_items": [{
                "title": "Sign slip",
                "due_date": "2026-05-02",
                "course_or_context": None,
                "confidence": 0.9,
                "source_email_excerpt": "x",
                "source_email_index": 1,
            }]
        })
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture(), tz_name="America/Torono")

        assert len(result) == 1
        # Fell back to Toronto
        assert result[0].due_date.tzinfo == ZoneInfo("America/Toronto")
        # Warning emitted exactly once mentioning the bad tz name
        warn_calls = [c for c in mock_logger.warning.call_args_list if "tz_name" in (c.args[0] if c.args else "")]
        assert len(warn_calls) == 1

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_extract_drops_item_with_bad_index(self, mock_get_client):
        """source_email_index out of range is dropped; valid items kept."""
        from app.services.parent_digest_ai_service import extract_digest_items

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_tool_use_message({
            "urgent_items": [
                {
                    "title": "Valid",
                    "due_date": "2026-05-02",
                    "course_or_context": None,
                    "confidence": 0.9,
                    "source_email_excerpt": "x",
                    "source_email_index": 1,
                },
                {
                    "title": "Out-of-range",
                    "due_date": "2026-05-03",
                    "course_or_context": None,
                    "confidence": 0.9,
                    "source_email_excerpt": "y",
                    "source_email_index": 99,
                },
                {
                    "title": "Bad date",
                    "due_date": "not-a-date",
                    "course_or_context": None,
                    "confidence": 0.9,
                    "source_email_excerpt": "z",
                    "source_email_index": 2,
                },
            ]
        })
        mock_get_client.return_value = mock_client

        result = await extract_digest_items(_emails_fixture())
        assert len(result) == 1
        assert result[0].title == "Valid"


class TestSectionedDigest:

    def _mock_anthropic_message(self, text: str, in_tok: int = 100, out_tok: int = 50):
        msg = MagicMock()
        msg.content = [MagicMock(text=text)]
        msg.usage.input_tokens = in_tok
        msg.usage.output_tokens = out_tok
        return msg

    def _emails(self):
        return [{
            "sender_name": "Ms. Johnson",
            "sender_email": "teacher@school.ca",
            "subject": "Field trip",
            "body": "Permission slip due Friday",
        }]

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_sectioned_digest_returns_valid_json(self, mock_get_client):
        """Valid AI JSON response parses into the SectionedDigest dict shape."""
        from app.services.parent_digest_ai_service import generate_sectioned_digest

        payload = {
            "urgent": ["Permission slip due today"],
            "announcements": ["New classroom schedule posted"],
            "action_items": ["Sign field trip form"],
            "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
        }
        client = MagicMock()
        client.messages.create.return_value = self._mock_anthropic_message(
            json.dumps(payload)
        )
        mock_get_client.return_value = client

        result = await generate_sectioned_digest(self._emails(), "Alex", "Sarah")

        assert result["urgent"] == ["Permission slip due today"]
        assert result["announcements"] == ["New classroom schedule posted"]
        assert result["action_items"] == ["Sign field trip form"]
        assert result["overflow"] == {"urgent": 0, "announcements": 0, "action_items": 0}
        assert "legacy_blob" not in result or result.get("legacy_blob") is None

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_sectioned_digest_caps_items_at_three(self, mock_get_client):
        """AI returning 5 urgent items is truncated to 3 by the Pydantic validator."""
        from app.schemas.parent_email_digest import SectionedDigest
        from app.services.parent_digest_ai_service import generate_sectioned_digest

        payload = {
            "urgent": ["u1", "u2", "u3", "u4", "u5"],
            "announcements": [],
            "action_items": [],
            "overflow": {"urgent": 2, "announcements": 0, "action_items": 0},
        }
        client = MagicMock()
        client.messages.create.return_value = self._mock_anthropic_message(
            json.dumps(payload)
        )
        mock_get_client.return_value = client

        raw = await generate_sectioned_digest(self._emails(), "Alex", "Sarah")

        # The Pydantic model caps at 3; the raw dict from the service MAY still
        # carry 5 but the SectionedDigest pass enforces the 3-cap for renderers.
        validated = SectionedDigest(**raw)
        assert len(validated.urgent) == 3
        assert validated.urgent == ["u1", "u2", "u3"]

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.generate_parent_digest")
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_sectioned_digest_bad_json_falls_back_to_legacy_blob(
        self, mock_get_client, mock_legacy
    ):
        """Garbage JSON from the AI triggers legacy_blob fallback, no crash."""
        from app.services.parent_digest_ai_service import generate_sectioned_digest

        client = MagicMock()
        client.messages.create.return_value = self._mock_anthropic_message(
            "this is not JSON at all, just prose"
        )
        mock_get_client.return_value = client

        async def _legacy_fn(emails, child, parent, digest_format="full"):
            return "<h3>Legacy HTML Digest</h3>"

        mock_legacy.side_effect = _legacy_fn

        result = await generate_sectioned_digest(self._emails(), "Alex", "Sarah")

        assert result.get("legacy_blob") == "<h3>Legacy HTML Digest</h3>"
        assert mock_legacy.called

    @pytest.mark.asyncio
    async def test_sectioned_digest_empty_emails_returns_all_empty_sections(self):
        """Empty email list short-circuits to all-empty sections with zero overflow."""
        from app.services.parent_digest_ai_service import generate_sectioned_digest

        result = await generate_sectioned_digest([], "Alex", "Sarah")
        assert result["urgent"] == []
        assert result["announcements"] == []
        assert result["action_items"] == []
        assert result["overflow"] == {"urgent": 0, "announcements": 0, "action_items": 0}

    @pytest.mark.asyncio
    @patch("app.services.parent_digest_ai_service.get_anthropic_client")
    async def test_sectioned_digest_strips_json_code_fence(self, mock_get_client):
        """Common AI failure: wraps JSON in ```json ... ``` — parser strips and succeeds."""
        from app.services.parent_digest_ai_service import generate_sectioned_digest

        payload = {
            "urgent": ["x"],
            "announcements": [],
            "action_items": [],
            "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
        }
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        client = MagicMock()
        client.messages.create.return_value = self._mock_anthropic_message(fenced)
        mock_get_client.return_value = client

        result = await generate_sectioned_digest([{"body": "x"}], "Alex", "Sarah")
        assert result.get("urgent") == ["x"]
        assert result.get("legacy_blob") is None or "legacy_blob" not in result
