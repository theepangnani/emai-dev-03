"""Tests for check_texts_safe helper and quiz/flashcard safety gates (#2445)."""

from unittest.mock import patch

from app.services.ai_service import check_texts_safe


@patch("app.services.ai_service.check_content_safe", return_value=(True, ""))
def test_all_safe(mock_check):
    safe, reason = check_texts_safe("hello", "world")
    assert safe is True
    assert reason == ""
    assert mock_check.call_count == 2


@patch("app.services.ai_service.check_content_safe")
def test_first_text_unsafe(mock_check):
    mock_check.return_value = (False, "Blocked")
    safe, reason = check_texts_safe("bad content", "good content")
    assert safe is False
    assert reason == "Blocked"
    # Should stop at first failure
    mock_check.assert_called_once_with("bad content")


@patch("app.services.ai_service.check_content_safe", return_value=(True, ""))
def test_none_values_skipped(mock_check):
    safe, reason = check_texts_safe(None, "", "hello")
    assert safe is True
    # Only "hello" should be checked (None and "" are skipped)
    mock_check.assert_called_once_with("hello")


def test_no_args():
    safe, reason = check_texts_safe()
    assert safe is True
    assert reason == ""
