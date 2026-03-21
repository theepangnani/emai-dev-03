"""Tests for weekly and daily digest cron jobs and conversation starters."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.weekly_digest_service import _build_conversation_starter


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
