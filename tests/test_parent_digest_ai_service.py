"""Tests for sectioned 3×3 digest path in parent_digest_ai_service (#3956).

Covers:
- Valid JSON parses into the SectionedDigest dict shape
- AI returning more than 3 items per section is truncated by the Pydantic cap
- Garbage JSON falls back to legacy_blob without crashing
"""

import json
from unittest.mock import MagicMock, patch

import pytest


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
