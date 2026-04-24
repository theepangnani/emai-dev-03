"""Tests for the safety service (CB-TUTOR-002 Phase 1, #4064)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.safety_service import ModerationResult, moderate, scrub_pii


# -- scrub_pii ---------------------------------------------------------------


def test_scrub_pii_redacts_phone_dashes() -> None:
    scrubbed, redactions = scrub_pii("call me at 416-555-1234")
    assert "416-555-1234" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "phone" in redactions


def test_scrub_pii_redacts_phone_parenthesis() -> None:
    scrubbed, redactions = scrub_pii("My number is (647) 555-9876.")
    assert "(647) 555-9876" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "phone" in redactions


def test_scrub_pii_redacts_phone_with_country_code() -> None:
    scrubbed, redactions = scrub_pii("Call +1 905-555-0000 tonight")
    assert "905-555-0000" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "phone" in redactions


def test_scrub_pii_redacts_email() -> None:
    scrubbed, redactions = scrub_pii("Email me at parent@example.com please")
    assert "parent@example.com" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "email" in redactions


def test_scrub_pii_redacts_sin_dashed() -> None:
    scrubbed, redactions = scrub_pii("SIN is 123-456-789 for records")
    assert "123-456-789" not in scrubbed
    assert "[REDACTED_SIN]" in scrubbed
    assert "sin" in redactions


def test_scrub_pii_redacts_sin_spaced() -> None:
    """Space-separated SIN still matches."""
    scrubbed, redactions = scrub_pii("SIN is 123 456 789 for records")
    assert "123 456 789" not in scrubbed
    assert "[REDACTED_SIN]" in scrubbed
    assert "sin" in redactions


def test_scrub_pii_does_not_match_bare_nine_digits() -> None:
    """Bare 9-digit runs no longer match — avoids false positives on
    student IDs and partial phone numbers (#4078)."""
    scrubbed, redactions = scrub_pii("student id 123456789 please")
    assert "[REDACTED_SIN]" not in scrubbed
    assert "sin" not in redactions


def test_scrub_pii_does_not_match_ten_digit_phone_as_sin() -> None:
    """10-digit phone number must not be flagged as a SIN.

    The phone pattern may still redact it as a phone, but never as a SIN.
    """
    _, redactions = scrub_pii("Call 4165551234 anytime")
    assert "sin" not in redactions


def test_scrub_pii_multiple_redactions() -> None:
    text = "Email alice@example.com or call 416-555-1234."
    scrubbed, redactions = scrub_pii(text)
    assert "alice@example.com" not in scrubbed
    assert "416-555-1234" not in scrubbed
    assert "email" in redactions
    assert "phone" in redactions


def test_scrub_pii_leaves_clean_text_alone() -> None:
    text = "What is 2 + 2?"
    scrubbed, redactions = scrub_pii(text)
    assert scrubbed == text
    assert redactions == []


def test_scrub_pii_handles_empty() -> None:
    scrubbed, redactions = scrub_pii("")
    assert scrubbed == ""
    assert redactions == []


# -- moderate ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_moderate_fails_closed_when_api_key_missing(monkeypatch) -> None:
    """Default fail_mode='closed': missing key returns flagged with
    category 'moderation_unavailable' so callers can surface an outage
    message rather than streaming unfiltered content (#4084)."""
    from app.services import safety_service

    monkeypatch.setattr(safety_service.settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(
        safety_service.settings, "moderation_fail_mode", "closed", raising=False
    )
    result = await moderate("anything")
    assert isinstance(result, ModerationResult)
    assert result.flagged is True
    assert result.categories == ["moderation_unavailable"]


@pytest.mark.asyncio
async def test_moderate_fails_open_when_api_key_missing_and_mode_open(
    monkeypatch,
) -> None:
    """fail_mode='open' restores the legacy permissive behaviour (#4084)."""
    from app.services import safety_service

    monkeypatch.setattr(safety_service.settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(
        safety_service.settings, "moderation_fail_mode", "open", raising=False
    )
    result = await moderate("anything")
    assert result.flagged is False
    assert result.categories == []


@pytest.mark.asyncio
async def test_moderate_fails_closed_when_api_raises(monkeypatch) -> None:
    """An APIError with fail_mode='closed' returns flagged=True (#4084)."""
    import openai as _openai

    from app.services import safety_service

    monkeypatch.setattr(
        safety_service.settings, "openai_api_key", "sk-test", raising=False
    )
    monkeypatch.setattr(
        safety_service.settings, "moderation_fail_mode", "closed", raising=False
    )

    async def _raise(*args, **kwargs):
        raise _openai.APITimeoutError(request=None)

    fake_client = SimpleNamespace(
        moderations=SimpleNamespace(create=_raise),
    )
    with patch.object(
        safety_service.openai, "AsyncOpenAI", return_value=fake_client
    ):
        result = await moderate("anything")
    assert result.flagged is True
    assert result.categories == ["moderation_unavailable"]


@pytest.mark.asyncio
async def test_moderate_fails_open_when_api_raises_and_mode_open(monkeypatch) -> None:
    """An APIError with fail_mode='open' returns an unflagged result (#4084)."""
    import openai as _openai

    from app.services import safety_service

    monkeypatch.setattr(
        safety_service.settings, "openai_api_key", "sk-test", raising=False
    )
    monkeypatch.setattr(
        safety_service.settings, "moderation_fail_mode", "open", raising=False
    )

    async def _raise(*args, **kwargs):
        raise _openai.APITimeoutError(request=None)

    fake_client = SimpleNamespace(
        moderations=SimpleNamespace(create=_raise),
    )
    with patch.object(
        safety_service.openai, "AsyncOpenAI", return_value=fake_client
    ):
        result = await moderate("anything")
    assert result.flagged is False
    assert result.categories == []


@pytest.mark.asyncio
async def test_moderate_returns_unflagged_for_empty_input() -> None:
    result = await moderate("")
    assert result.flagged is False
    assert result.categories == []


@pytest.mark.asyncio
async def test_moderate_flags_from_openai_response(monkeypatch) -> None:
    from app.services import safety_service

    monkeypatch.setattr(
        safety_service.settings, "openai_api_key", "sk-test", raising=False
    )

    categories = SimpleNamespace(
        model_dump=lambda: {
            "hate": True,
            "violence": False,
            "self-harm": True,
        }
    )
    fake_result = SimpleNamespace(flagged=True, categories=categories)
    fake_response = SimpleNamespace(results=[fake_result])

    mock_create = AsyncMock(return_value=fake_response)
    fake_client = SimpleNamespace(
        moderations=SimpleNamespace(create=mock_create),
    )

    with patch.object(
        safety_service.openai, "AsyncOpenAI", return_value=fake_client
    ):
        result = await moderate("some text")

    assert result.flagged is True
    assert "hate" in result.categories
    assert "self-harm" in result.categories
    assert "violence" not in result.categories
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_moderate_returns_unflagged_for_clean_text(monkeypatch) -> None:
    from app.services import safety_service

    monkeypatch.setattr(
        safety_service.settings, "openai_api_key", "sk-test", raising=False
    )

    categories = SimpleNamespace(
        model_dump=lambda: {"hate": False, "violence": False}
    )
    fake_result = SimpleNamespace(flagged=False, categories=categories)
    fake_response = SimpleNamespace(results=[fake_result])

    mock_create = AsyncMock(return_value=fake_response)
    fake_client = SimpleNamespace(
        moderations=SimpleNamespace(create=mock_create),
    )

    with patch.object(
        safety_service.openai, "AsyncOpenAI", return_value=fake_client
    ):
        result = await moderate("What is 2+2?")

    assert result.flagged is False
    assert result.categories == []
