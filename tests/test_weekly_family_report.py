"""Tests for weekly family report card email (#2228) — gamification data,
AI encouragement, and forward-to-family CTA in the digest email."""

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.weekly_digest import ChildDigest, WeeklyDigestResponse
from app.services.weekly_digest_service import (
    _generate_encouragement,
    _translate_digest,
    render_digest_email_html,
)


# ── AI encouragement tests ─────────────────────────────────


class TestGenerateEncouragement:
    def test_returns_none_when_no_activity(self):
        result = _generate_encouragement("Emma Smith", 0, 0, 0, 0)
        assert result is None

    @patch("openai.OpenAI")
    @patch("app.core.config.settings")
    def test_returns_ai_response(self, mock_settings, mock_openai_cls):
        mock_settings.openai_api_key = "test-key"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "Great job, Emma!"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = _generate_encouragement("Emma Smith", 150, 5, 3, 45)

        assert result == "Great job, Emma!"
        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "Emma" in user_msg
        assert "150 XP" in user_msg
        assert "5-day streak" in user_msg
        assert "3 quizzes" in user_msg
        assert "45 minutes" in user_msg

    @patch("openai.OpenAI")
    @patch("app.core.config.settings")
    def test_returns_none_on_ai_failure(self, mock_settings, mock_openai_cls):
        mock_settings.openai_api_key = "test-key"
        mock_openai_cls.side_effect = Exception("API down")

        result = _generate_encouragement("Emma Smith", 100, 0, 0, 0)
        assert result is None

    @patch("openai.OpenAI")
    @patch("app.core.config.settings")
    def test_only_includes_nonzero_stats(self, mock_settings, mock_openai_cls):
        """When only XP is nonzero, prompt should only mention XP."""
        mock_settings.openai_api_key = "test-key"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "Keep it up!"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        _generate_encouragement("John Doe", 50, 0, 0, 0)

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "50 XP" in user_msg
        assert "streak" not in user_msg
        assert "quizzes" not in user_msg
        assert "minutes" not in user_msg


# ── Schema gamification fields tests ────────────────────────


class TestChildDigestGamificationFields:
    def test_default_values(self):
        child = ChildDigest(student_id=1, full_name="Emma")
        assert child.xp_earned == 0
        assert child.current_streak == 0
        assert child.study_minutes == 0
        assert child.encouragement is None

    def test_populated_values(self):
        child = ChildDigest(
            student_id=1,
            full_name="Emma",
            xp_earned=200,
            current_streak=7,
            study_minutes=90,
            encouragement="Amazing week!",
        )
        assert child.xp_earned == 200
        assert child.current_streak == 7
        assert child.study_minutes == 90
        assert child.encouragement == "Amazing week!"


# ── Email HTML template tests ───────────────────────────────


class TestRenderDigestEmailGamification:
    def _make_digest(self, **child_kwargs) -> WeeklyDigestResponse:
        defaults = {
            "student_id": 1,
            "full_name": "Emma Smith",
            "highlight": "Great week",
        }
        defaults.update(child_kwargs)
        return WeeklyDigestResponse(
            week_start="2026-03-18",
            week_end="2026-03-25",
            greeting="Hi Sarah",
            overall_summary="Good week.",
            children=[ChildDigest(**defaults)],
        )

    def test_streak_badge_rendered(self):
        digest = self._make_digest(current_streak=5)
        html = render_digest_email_html(digest)
        assert "5-day streak" in html
        assert "&#128293;" in html  # fire emoji

    def test_xp_badge_rendered(self):
        digest = self._make_digest(xp_earned=250)
        html = render_digest_email_html(digest)
        assert "250 XP" in html
        assert "&#11088;" in html  # star emoji

    def test_study_minutes_badge_rendered(self):
        digest = self._make_digest(study_minutes=60)
        html = render_digest_email_html(digest)
        assert "60 min" in html
        assert "&#9201;" in html  # timer emoji

    def test_no_badges_when_zero(self):
        digest = self._make_digest(xp_earned=0, current_streak=0, study_minutes=0)
        html = render_digest_email_html(digest)
        assert "&#128293;" not in html
        assert "&#11088;" not in html
        assert "&#9201;" not in html

    def test_encouragement_rendered(self):
        digest = self._make_digest(encouragement="Keep up the great work, Emma!")
        html = render_digest_email_html(digest)
        assert "Keep up the great work, Emma!" in html
        assert "ecfdf5" in html  # green background

    def test_no_encouragement_when_none(self):
        digest = self._make_digest(encouragement=None)
        html = render_digest_email_html(digest)
        assert "ecfdf5" not in html

    def test_forward_to_family_cta(self):
        digest = self._make_digest()
        html = render_digest_email_html(digest)
        assert "Forward to Family" in html
        assert "mailto:?" in html


# ── Translation includes encouragement ──────────────────────


class TestTranslateDigestEncouragement:
    @patch("app.services.weekly_digest_service.TranslationService.translate")
    def test_encouragement_translated(self, mock_translate):
        mock_translate.side_effect = lambda text, lang: f"[fr]{text}"

        digest = WeeklyDigestResponse(
            week_start="2026-03-18",
            week_end="2026-03-25",
            greeting="Hi Sarah",
            overall_summary="Good week.",
            children=[
                ChildDigest(
                    student_id=1,
                    full_name="Emma",
                    highlight="Great week",
                    encouragement="Keep it up!",
                ),
            ],
        )
        result = _translate_digest(digest, "fr")
        assert result.children[0].encouragement == "[fr]Keep it up!"

    @patch("app.services.weekly_digest_service.TranslationService.translate")
    def test_none_encouragement_not_translated(self, mock_translate):
        mock_translate.side_effect = lambda text, lang: f"[fr]{text}"

        digest = WeeklyDigestResponse(
            week_start="2026-03-18",
            week_end="2026-03-25",
            greeting="Hi Sarah",
            overall_summary="Good week.",
            children=[
                ChildDigest(
                    student_id=1,
                    full_name="Emma",
                    highlight="No activity",
                    encouragement=None,
                ),
            ],
        )
        result = _translate_digest(digest, "fr")
        assert result.children[0].encouragement is None
        # greeting + overall_summary + highlight = 3 (no encouragement call)
        assert mock_translate.call_count == 3
