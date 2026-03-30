"""Tests for resource_suggestion_service (issue #2489, section 6.57.2)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.teacher import Teacher  # noqa: F401 — load Teacher before Course resolves relationship
from app.models.course import Course  # noqa: F401 — trigger relationship resolution after Teacher loaded

from app.services.resource_suggestion_service import (
    TRUSTED_DOMAINS,
    _build_prompt,
    _extract_youtube_video_id,
    _is_trusted_domain,
    _parse_ai_response,
    suggest_resources,
)


# ---------------------------------------------------------------------------
# Unit tests — helper functions
# ---------------------------------------------------------------------------


class TestIsTrustedDomain:
    def test_youtube(self):
        assert _is_trusted_domain("https://www.youtube.com/watch?v=abc123")

    def test_khan_academy(self):
        assert _is_trusted_domain("https://www.khanacademy.org/math/algebra")

    def test_untrusted(self):
        assert not _is_trusted_domain("https://example.com/resource")

    def test_subdomain_trusted(self):
        assert _is_trusted_domain("https://en.wikipedia.org/wiki/Math")

    def test_empty_url(self):
        assert not _is_trusted_domain("")

    def test_malformed(self):
        assert not _is_trusted_domain("not-a-url")


class TestExtractYoutubeVideoId:
    def test_watch_url(self):
        assert _extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert _extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert _extract_youtube_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_non_youtube(self):
        assert _extract_youtube_video_id("https://example.com/watch?v=abc") is None

    def test_empty(self):
        assert _extract_youtube_video_id("") is None


class TestParseAiResponse:
    def test_plain_json(self):
        data = '{"youtube": [], "web": []}'
        result = _parse_ai_response(data)
        assert result == {"youtube": [], "web": []}

    def test_json_in_code_fence(self):
        data = '```json\n{"youtube": [{"title": "Test"}], "web": []}\n```'
        result = _parse_ai_response(data)
        assert result["youtube"][0]["title"] == "Test"

    def test_invalid_json(self):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            _parse_ai_response("not json at all")


class TestBuildPrompt:
    def test_contains_topic(self):
        prompt = _build_prompt("Quadratics", "Math", "Grade 10")
        assert "Quadratics" in prompt
        assert "Math" in prompt
        assert "Grade 10" in prompt
        assert "Ontario" in prompt

    def test_contains_trusted_channels(self):
        prompt = _build_prompt("Topic", "Course", "Grade 9")
        assert "Khan Academy" in prompt
        assert "3Blue1Brown" in prompt


# ---------------------------------------------------------------------------
# Integration test — suggest_resources with mocked AI
# ---------------------------------------------------------------------------

MOCK_AI_RESPONSE = json.dumps({
    "youtube": [
        {
            "title": "Quadratic Equations - Khan Academy",
            "url": "https://www.youtube.com/watch?v=abcdef12345",
            "description": "Learn about quadratic equations",
            "topic_heading": "Quadratic Equations",
        },
    ],
    "web": [
        {
            "title": "Quadratics on Khan Academy",
            "url": "https://www.khanacademy.org/math/algebra/quadratics",
            "description": "Interactive exercises for quadratics",
            "topic_heading": "Practice",
        },
    ],
})


@pytest.fixture()
def mock_db():
    """Create a mock DB session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.mark.asyncio
async def test_suggest_resources_success(mock_db):
    """Test successful resource suggestion with mocked AI and URL validation."""
    with (
        patch("app.services.resource_suggestion_service.settings") as mock_settings,
        patch("app.services.resource_suggestion_service.generate_content", new_callable=AsyncMock) as mock_gen,
        patch("app.services.resource_suggestion_service.get_last_ai_usage") as mock_usage,
        patch("app.services.resource_suggestion_service.log_ai_usage") as mock_log,
        patch("app.services.resource_suggestion_service._validate_urls", new_callable=AsyncMock) as mock_validate,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_gen.return_value = (MOCK_AI_RESPONSE, "end_turn")
        mock_usage.return_value = {
            "prompt_tokens": 100, "completion_tokens": 200,
            "total_tokens": 300, "model_name": "claude-sonnet-4-6",
            "estimated_cost_usd": 0.001,
        }
        mock_validate.return_value = {
            "https://www.youtube.com/watch?v=abcdef12345": True,
            "https://www.khanacademy.org/math/algebra/quadratics": True,
        }

        result = await suggest_resources(
            topic="Quadratic Equations",
            course_name="Grade 10 Math",
            grade_level="Grade 10",
            course_content_id=42,
            user_id=1,
            db=mock_db,
        )

        assert len(result) == 2
        # Check that ResourceLink objects were added
        assert mock_db.add.call_count == 2
        assert mock_db.commit.call_count >= 1

        # Verify source is ai_suggested
        for rl in result:
            assert rl.source == "ai_suggested"
            assert rl.course_content_id == 42

        # Verify AI usage was logged
        mock_log.assert_called_once()


@pytest.mark.asyncio
async def test_suggest_resources_no_api_key(mock_db):
    """Returns empty when API key is not configured."""
    with patch("app.services.resource_suggestion_service.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""

        result = await suggest_resources(
            topic="Topic", course_name="Course", grade_level="Grade 9",
            course_content_id=1, user_id=1, db=mock_db,
        )
        assert result == []


@pytest.mark.asyncio
async def test_suggest_resources_ai_failure(mock_db):
    """Returns empty on AI call failure."""
    with (
        patch("app.services.resource_suggestion_service.settings") as mock_settings,
        patch("app.services.resource_suggestion_service.generate_content", new_callable=AsyncMock) as mock_gen,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_gen.side_effect = Exception("AI service down")

        result = await suggest_resources(
            topic="Topic", course_name="Course", grade_level="Grade 9",
            course_content_id=1, user_id=1, db=mock_db,
        )
        assert result == []


@pytest.mark.asyncio
async def test_suggest_resources_untrusted_filtered(mock_db):
    """Resources from untrusted domains are filtered out."""
    untrusted_response = json.dumps({
        "youtube": [],
        "web": [
            {
                "title": "Sketchy Site",
                "url": "https://untrusted-site.com/math",
                "description": "Some resource",
                "topic_heading": "Math",
            },
        ],
    })

    with (
        patch("app.services.resource_suggestion_service.settings") as mock_settings,
        patch("app.services.resource_suggestion_service.generate_content", new_callable=AsyncMock) as mock_gen,
        patch("app.services.resource_suggestion_service.get_last_ai_usage") as mock_usage,
        patch("app.services.resource_suggestion_service.log_ai_usage"),
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_gen.return_value = (untrusted_response, "end_turn")
        mock_usage.return_value = {}

        result = await suggest_resources(
            topic="Topic", course_name="Course", grade_level="Grade 9",
            course_content_id=1, user_id=1, db=mock_db,
        )
        assert result == []


@pytest.mark.asyncio
async def test_suggest_resources_invalid_urls_skipped(mock_db):
    """Resources with invalid URLs (failing HEAD check) are skipped."""
    with (
        patch("app.services.resource_suggestion_service.settings") as mock_settings,
        patch("app.services.resource_suggestion_service.generate_content", new_callable=AsyncMock) as mock_gen,
        patch("app.services.resource_suggestion_service.get_last_ai_usage") as mock_usage,
        patch("app.services.resource_suggestion_service.log_ai_usage"),
        patch("app.services.resource_suggestion_service._validate_urls", new_callable=AsyncMock) as mock_validate,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_gen.return_value = (MOCK_AI_RESPONSE, "end_turn")
        mock_usage.return_value = {}
        # Both URLs fail validation
        mock_validate.return_value = {
            "https://www.youtube.com/watch?v=abcdef12345": False,
            "https://www.khanacademy.org/math/algebra/quadratics": False,
        }

        result = await suggest_resources(
            topic="Topic", course_name="Course", grade_level="Grade 9",
            course_content_id=1, user_id=1, db=mock_db,
        )
        assert result == []
