"""Tests for weekly and daily digest cron jobs, conversation starters, and translation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.briefing import DailyBriefingResponse
from app.schemas.weekly_digest import ChildDigest, WeeklyDigestResponse
from app.services.weekly_digest_service import (
    _build_conversation_starter,
    _translate_digest,
)
from app.services.daily_digest_service import _translate_briefing


# ── Conversation starter tests ────────────────────────────────


class TestBuildConversationStarter:
    def test_returns_none_when_no_guide(self):
        assert _build_conversation_starter("Emma Smith", None) is None

    def test_builds_starter_from_guide(self):
        guide = MagicMock()
        guide.title = "Cell Division"
        result = _build_conversation_starter("Emma Smith", guide)
        assert result is not None
        assert "Emma" in result
        assert "Cell Division" in result
        assert "ask them" in result

    def test_uses_first_name_only(self):
        guide = MagicMock()
        guide.title = "Fractions"
        result = _build_conversation_starter("John Alexander Doe", guide)
        assert result.startswith("John studied")

    def test_handles_single_name(self):
        guide = MagicMock()
        guide.title = "Photosynthesis"
        result = _build_conversation_starter("Alex", guide)
        assert "Alex studied Photosynthesis" in result


# ── Weekly digest job tests ───────────────────────────────────


@pytest.mark.asyncio
class TestSendWeeklyDigests:
    @patch("app.jobs.weekly_digest.SessionLocal")
    @patch("app.jobs.weekly_digest.send_weekly_digest_email", new_callable=AsyncMock)
    async def test_sends_to_opted_in_parents(self, mock_send, mock_session_cls):
        parent1 = MagicMock(id=1)
        parent2 = MagicMock(id=2)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = [
            parent1,
            parent2,
        ]
        mock_send.return_value = True

        from app.jobs.weekly_digest import send_weekly_digests

        await send_weekly_digests()

        assert mock_send.call_count == 2
        mock_send.assert_any_call(mock_db, 1)
        mock_send.assert_any_call(mock_db, 2)
        mock_db.close.assert_called_once()

    @patch("app.jobs.weekly_digest.SessionLocal")
    @patch("app.jobs.weekly_digest.send_weekly_digest_email", new_callable=AsyncMock)
    async def test_handles_no_parents(self, mock_send, mock_session_cls):
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        from app.jobs.weekly_digest import send_weekly_digests

        await send_weekly_digests()

        mock_send.assert_not_called()
        mock_db.close.assert_called_once()

    @patch("app.jobs.weekly_digest.SessionLocal")
    @patch("app.jobs.weekly_digest.send_weekly_digest_email", new_callable=AsyncMock)
    async def test_continues_on_individual_failure(self, mock_send, mock_session_cls):
        parent1 = MagicMock(id=1)
        parent2 = MagicMock(id=2)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = [
            parent1,
            parent2,
        ]
        mock_send.side_effect = [Exception("email failed"), True]

        from app.jobs.weekly_digest import send_weekly_digests

        await send_weekly_digests()

        assert mock_send.call_count == 2
        mock_db.close.assert_called_once()


# ── Daily digest job tests ────────────────────────────────────


@pytest.mark.asyncio
class TestSendDailyDigests:
    @patch("app.jobs.daily_digest_job.SessionLocal")
    @patch("app.jobs.daily_digest_job.send_daily_digest_email", new_callable=AsyncMock)
    async def test_sends_to_opted_in_parents(self, mock_send, mock_session_cls):
        parent1 = MagicMock(id=1)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = [parent1]
        mock_send.return_value = True

        from app.jobs.daily_digest_job import send_daily_digests

        await send_daily_digests()

        mock_send.assert_called_once_with(mock_db, 1)
        mock_db.close.assert_called_once()

    @patch("app.jobs.daily_digest_job.SessionLocal")
    @patch("app.jobs.daily_digest_job.send_daily_digest_email", new_callable=AsyncMock)
    async def test_handles_no_parents(self, mock_send, mock_session_cls):
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        from app.jobs.daily_digest_job import send_daily_digests

        await send_daily_digests()

        mock_send.assert_not_called()
        mock_db.close.assert_called_once()

    @patch("app.jobs.daily_digest_job.SessionLocal")
    @patch("app.jobs.daily_digest_job.send_daily_digest_email", new_callable=AsyncMock)
    async def test_continues_on_individual_failure(self, mock_send, mock_session_cls):
        parent1 = MagicMock(id=1)
        parent2 = MagicMock(id=2)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = [
            parent1,
            parent2,
        ]
        mock_send.side_effect = [Exception("fail"), True]

        from app.jobs.daily_digest_job import send_daily_digests

        await send_daily_digests()

        assert mock_send.call_count == 2
        mock_db.close.assert_called_once()

    @patch("app.jobs.daily_digest_job.SessionLocal")
    @patch("app.jobs.daily_digest_job.send_daily_digest_email", new_callable=AsyncMock)
    async def test_skipped_counted_when_no_content(self, mock_send, mock_session_cls):
        """When send returns False (no content), it counts as skipped not failed."""
        parent1 = MagicMock(id=1)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = [parent1]
        mock_send.return_value = False

        from app.jobs.daily_digest_job import send_daily_digests

        await send_daily_digests()

        mock_send.assert_called_once_with(mock_db, 1)
        mock_db.close.assert_called_once()


# ── Weekly digest translation tests ──────────────────────────


class TestWeeklyDigestTranslation:
    def test_english_parent_no_translation(self):
        """English parent should get digest with no translation calls."""
        digest = WeeklyDigestResponse(
            week_start="2026-03-14",
            week_end="2026-03-21",
            greeting="Hi Sarah",
            overall_summary="2/3 tasks completed.",
            children=[
                ChildDigest(
                    student_id=1,
                    full_name="Emma Smith",
                    highlight="2/3 tasks done",
                    conversation_starter="Emma studied Fractions this week",
                ),
            ],
        )
        result = _translate_digest(digest, "en")
        assert result.greeting == "Hi Sarah"
        assert result.overall_summary == "2/3 tasks completed."
        assert result.children[0].highlight == "2/3 tasks done"

    @patch("app.services.weekly_digest_service.TranslationService.translate")
    def test_tamil_parent_translation_called(self, mock_translate):
        """Non-English parent should have key fields translated."""
        mock_translate.side_effect = lambda text, lang: f"[ta]{text}"

        digest = WeeklyDigestResponse(
            week_start="2026-03-14",
            week_end="2026-03-21",
            greeting="Hi Sarah",
            overall_summary="2/3 tasks completed.",
            children=[
                ChildDigest(
                    student_id=1,
                    full_name="Emma Smith",
                    highlight="2/3 tasks done",
                    conversation_starter="Emma studied Fractions",
                ),
            ],
        )
        result = _translate_digest(digest, "ta")
        assert result.greeting == "[ta]Hi Sarah"
        assert result.overall_summary == "[ta]2/3 tasks completed."
        assert result.children[0].highlight == "[ta]2/3 tasks done"
        assert result.children[0].conversation_starter == "[ta]Emma studied Fractions"
        assert mock_translate.call_count == 4

    @patch("app.services.weekly_digest_service.TranslationService.translate")
    def test_translation_failure_falls_back_to_english(self, mock_translate):
        """If translation raises, English text is preserved."""
        mock_translate.side_effect = Exception("API down")

        digest = WeeklyDigestResponse(
            week_start="2026-03-14",
            week_end="2026-03-21",
            greeting="Hi Sarah",
            overall_summary="All clear.",
        )
        result = _translate_digest(digest, "ta")
        assert result.greeting == "Hi Sarah"
        assert result.overall_summary == "All clear."

    @patch("app.services.weekly_digest_service.TranslationService.translate")
    def test_child_without_conversation_starter_skipped(self, mock_translate):
        """Children with no conversation_starter should not trigger translation for it."""
        mock_translate.side_effect = lambda text, lang: f"[fr]{text}"

        digest = WeeklyDigestResponse(
            week_start="2026-03-14",
            week_end="2026-03-21",
            greeting="Hi Sarah",
            overall_summary="Quiet week.",
            children=[
                ChildDigest(
                    student_id=1,
                    full_name="Emma Smith",
                    highlight="No activity this week",
                    conversation_starter=None,
                ),
            ],
        )
        result = _translate_digest(digest, "fr")
        # greeting + overall_summary + highlight = 3 calls (no conversation_starter)
        assert mock_translate.call_count == 3
        assert result.children[0].conversation_starter is None


# ── Weekly digest email translation integration ──────────────


@pytest.mark.asyncio
class TestSendWeeklyDigestEmailTranslation:
    @patch("app.services.weekly_digest_service.send_email", new_callable=AsyncMock)
    @patch("app.core.security.get_unsubscribe_url", return_value="http://unsub")
    @patch("app.services.weekly_digest_service.generate_weekly_digest")
    @patch("app.services.weekly_digest_service.TranslationService.translate")
    async def test_subject_translated_for_non_english(
        self, mock_translate, mock_gen, mock_unsub, mock_send
    ):
        mock_translate.side_effect = lambda text, lang: f"[ta]{text}"
        mock_gen.return_value = WeeklyDigestResponse(
            week_start="2026-03-14",
            week_end="2026-03-21",
            greeting="Hi Sarah",
            overall_summary="All clear.",
        )
        mock_send.return_value = True

        parent = MagicMock()
        parent.id = 1
        parent.email = "sarah@example.com"
        parent.preferred_language = "ta"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = parent

        from app.services.weekly_digest_service import send_weekly_digest_email

        result = await send_weekly_digest_email(mock_db, 1)

        assert result is True
        call_args = mock_send.call_args
        subject = call_args[0][1]
        assert subject.startswith("[ta]")

    @patch("app.services.weekly_digest_service.send_email", new_callable=AsyncMock)
    @patch("app.core.security.get_unsubscribe_url", return_value="http://unsub")
    @patch("app.services.weekly_digest_service.generate_weekly_digest")
    @patch("app.services.weekly_digest_service.TranslationService.translate")
    async def test_subject_not_translated_for_english(
        self, mock_translate, mock_gen, mock_unsub, mock_send
    ):
        mock_gen.return_value = WeeklyDigestResponse(
            week_start="2026-03-14",
            week_end="2026-03-21",
            greeting="Hi Sarah",
            overall_summary="All clear.",
        )
        mock_send.return_value = True

        parent = MagicMock()
        parent.id = 1
        parent.email = "sarah@example.com"
        parent.preferred_language = "en"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = parent

        from app.services.weekly_digest_service import send_weekly_digest_email

        result = await send_weekly_digest_email(mock_db, 1)

        assert result is True
        mock_translate.assert_not_called()


# ── Daily digest translation tests ──────────────────────────


class TestDailyDigestTranslation:
    def test_english_parent_no_translation(self):
        """English parent briefing should not be translated."""
        briefing = DailyBriefingResponse(
            date="2026-03-21",
            greeting="Good morning, Sarah",
        )
        result = _translate_briefing(briefing, "en")
        assert result.greeting == "Good morning, Sarah"

    @patch("app.services.daily_digest_service.TranslationService.translate")
    def test_tamil_parent_greeting_translated(self, mock_translate):
        mock_translate.side_effect = lambda text, lang: f"[ta]{text}"

        briefing = DailyBriefingResponse(
            date="2026-03-21",
            greeting="Good morning, Sarah",
        )
        result = _translate_briefing(briefing, "ta")
        assert result.greeting == "[ta]Good morning, Sarah"
        assert mock_translate.call_count == 1

    @patch("app.services.daily_digest_service.TranslationService.translate")
    def test_translation_failure_falls_back_to_english(self, mock_translate):
        mock_translate.side_effect = Exception("API down")

        briefing = DailyBriefingResponse(
            date="2026-03-21",
            greeting="Good morning, Sarah",
        )
        result = _translate_briefing(briefing, "ta")
        assert result.greeting == "Good morning, Sarah"


# ── Daily digest email translation integration ───────────────


@pytest.mark.asyncio
class TestSendDailyDigestEmailTranslation:
    @patch("app.services.daily_digest_service.send_email", new_callable=AsyncMock)
    @patch("app.core.security.get_unsubscribe_url", return_value="http://unsub")
    @patch("app.services.daily_digest_service.get_daily_briefing")
    @patch("app.services.daily_digest_service.TranslationService.translate")
    async def test_subject_translated_for_non_english(
        self, mock_translate, mock_briefing, mock_unsub, mock_send
    ):
        mock_translate.side_effect = lambda text, lang: f"[ta]{text}"
        mock_briefing.return_value = DailyBriefingResponse(
            date="2026-03-21",
            greeting="Good morning, Sarah",
            total_overdue=1,
        )
        mock_send.return_value = True

        parent = MagicMock()
        parent.id = 1
        parent.email = "sarah@example.com"
        parent.preferred_language = "ta"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = parent

        from app.services.daily_digest_service import send_daily_digest_email

        result = await send_daily_digest_email(mock_db, 1)

        assert result is True
        call_args = mock_send.call_args
        subject = call_args[0][1]
        assert subject.startswith("[ta]")

    @patch("app.services.daily_digest_service.send_email", new_callable=AsyncMock)
    @patch("app.core.security.get_unsubscribe_url", return_value="http://unsub")
    @patch("app.services.daily_digest_service.get_daily_briefing")
    @patch("app.services.daily_digest_service.TranslationService.translate")
    async def test_subject_not_translated_for_english(
        self, mock_translate, mock_briefing, mock_unsub, mock_send
    ):
        mock_briefing.return_value = DailyBriefingResponse(
            date="2026-03-21",
            greeting="Good morning, Sarah",
            total_overdue=1,
        )
        mock_send.return_value = True

        parent = MagicMock()
        parent.id = 1
        parent.email = "sarah@example.com"
        parent.preferred_language = "en"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = parent

        from app.services.daily_digest_service import send_daily_digest_email

        result = await send_daily_digest_email(mock_db, 1)

        assert result is True
        mock_translate.assert_not_called()
