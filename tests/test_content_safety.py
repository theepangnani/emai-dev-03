"""Tests for content safety batch helper (#2213)."""

from unittest.mock import patch

import pytest

from app.services.ai_service import check_content_safe, check_texts_safe


class TestCheckTextsSafe:
    """Tests for the check_texts_safe() batch helper."""

    @patch("app.services.ai_service.check_content_safe", return_value=(True, ""))
    def test_all_safe(self, mock_check):
        safe, reason = check_texts_safe("hello", "world")
        assert safe is True
        assert reason == ""
        assert mock_check.call_count == 2

    @patch("app.services.ai_service.check_content_safe")
    def test_first_unsafe_short_circuits(self, mock_check):
        mock_check.side_effect = [
            (False, "Content not appropriate"),
            (True, ""),
        ]
        safe, reason = check_texts_safe("bad", "good")
        assert safe is False
        assert "not appropriate" in reason
        # Should stop after the first failure
        assert mock_check.call_count == 1

    @patch("app.services.ai_service.check_content_safe", return_value=(True, ""))
    def test_skips_none_and_empty(self, mock_check):
        safe, reason = check_texts_safe(None, "", "   ", "actual text")
        assert safe is True
        # Only "actual text" should be checked
        assert mock_check.call_count == 1

    def test_all_empty_returns_safe(self):
        safe, reason = check_texts_safe(None, "", "   ")
        assert safe is True
        assert reason == ""

    def test_no_args_returns_safe(self):
        safe, reason = check_texts_safe()
        assert safe is True
        assert reason == ""

    @patch("app.services.ai_service.check_content_safe")
    def test_second_text_unsafe(self, mock_check):
        mock_check.side_effect = [
            (True, ""),
            (False, "Unsafe content detected"),
        ]
        safe, reason = check_texts_safe("ok text", "bad text")
        assert safe is False
        assert "Unsafe" in reason


class TestCheckTextsSafeImportedInStudy:
    """Verify check_texts_safe is used in study route."""

    def test_check_texts_safe_imported(self):
        import inspect
        from app.api.routes.study import generate_study_guide_endpoint
        source = inspect.getsource(generate_study_guide_endpoint)
        assert "check_texts_safe" in source
