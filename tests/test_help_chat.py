"""Tests for help chat service error handling and intent classification."""

import sys
import pytest
from unittest.mock import patch, MagicMock
from types import ModuleType

from app.services.help_chat_service import HelpChatService
from app.services.intent_classifier import classify_intent


def _make_mock_embedding_module(side_effect):
    """Create a mock module for help_embedding_service with a given side_effect on search."""
    mod = ModuleType("app.services.help_embedding_service")
    mock_service = MagicMock()
    mock_service.search.side_effect = side_effect
    mod.help_embedding_service = mock_service  # type: ignore[attr-defined]
    return mod


@pytest.mark.asyncio
async def test_auth_error_returns_specific_message():
    """Regression: generic errors should include error type + /help link."""
    service = HelpChatService()

    class AuthenticationError(Exception):
        pass

    mock_mod = _make_mock_embedding_module(AuthenticationError("Invalid API key"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="How do I connect Google Classroom?",
            user_id=1,
            user_role="parent",
        )

    assert "/help" in result.reply, "Error reply must include /help link"
    assert "configuration" in result.reply.lower() or "error" in result.reply.lower()
    assert "I'm having trouble right now" not in result.reply


@pytest.mark.asyncio
async def test_timeout_error_returns_unreachable_message():
    """Timeout errors should say the service is unreachable."""
    service = HelpChatService()

    class TimeoutError(Exception):
        pass

    mock_mod = _make_mock_embedding_module(TimeoutError("Connection timed out"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="Help me",
            user_id=2,
            user_role="student",
        )

    assert "/help" in result.reply
    assert "unreachable" in result.reply.lower()


@pytest.mark.asyncio
async def test_generic_error_returns_unexpected_message():
    """Unknown errors should say 'unexpected' and still include /help link."""
    service = HelpChatService()

    mock_mod = _make_mock_embedding_module(ValueError("something weird"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="What is this?",
            user_id=3,
            user_role="teacher",
        )

    assert "/help" in result.reply
    assert "unexpected" in result.reply.lower()


@pytest.mark.asyncio
async def test_rate_limit_error_returns_overloaded_message():
    """API rate limit errors should mention overloaded."""
    service = HelpChatService()

    class RateLimitError(Exception):
        pass

    mock_mod = _make_mock_embedding_module(RateLimitError("Rate limit exceeded"))
    with patch.dict(sys.modules, {"app.services.help_embedding_service": mock_mod}):
        result = await service.generate_response(
            message="Help",
            user_id=4,
            user_role="admin",
        )

    assert "/help" in result.reply
    assert "overloaded" in result.reply.lower()


# --- Intent classifier tests ---


def test_classify_intent_search():
    assert classify_intent("find my courses") == "search"
    assert classify_intent("show me my tasks") == "search"
    assert classify_intent("list my study guides") == "search"
    assert classify_intent("where is my assignment") == "search"


def test_classify_intent_action():
    assert classify_intent("upload a file") == "action"
    assert classify_intent("create a new task") == "action"
    assert classify_intent("add a course") == "action"
    assert classify_intent("generate study guide") == "action"


def test_classify_intent_help():
    assert classify_intent("how do I connect Google Classroom") == "help"
    assert classify_intent("what is ClassBridge") == "help"
    assert classify_intent("explain the dashboard") == "help"
    assert classify_intent("how to create a task") == "help"
    assert classify_intent("how to find my courses") == "help"


def test_classify_intent_defaults_to_help():
    assert classify_intent("") == "help"
    assert classify_intent("how does this platform work for teachers") == "help"


# --- Existing help chat service tests ---


@pytest.mark.asyncio
async def test_embedding_service_retries_after_failed_init():
    """Regression: embedding service should retry initialization after failure, not stay broken."""
    from app.services.help_embedding_service import HelpEmbeddingService

    service = HelpEmbeddingService()

    # Simulate failed init (e.g. OpenAI key missing)
    with patch.object(service, "_load_yaml", side_effect=RuntimeError("API down")):
        await service.initialize()

    # After failure, _initialized should still be False so it retries
    assert service._initialized is False, "Service should allow retry after failed init"
    assert service.chunks == [], "Chunks should be empty after failed init"
