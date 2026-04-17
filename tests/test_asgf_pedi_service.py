"""Unit tests for ASGF PEDI enrichment service (#3404)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_learning_history(**overrides):
    """Create a mock LearningHistory row."""
    row = MagicMock()
    row.id = overrides.get("id", 1)
    row.student_id = overrides.get("student_id", 42)
    row.session_id = overrides.get("session_id", "sess-001")
    row.session_type = overrides.get("session_type", "asgf")
    row.question_asked = overrides.get("question_asked", "What is photosynthesis?")
    row.subject = overrides.get("subject", "Science")
    row.topic_tags = overrides.get("topic_tags", ["photosynthesis"])
    row.grade_level = overrides.get("grade_level", "Grade 9")
    row.overall_score_pct = overrides.get("overall_score_pct", 80)
    row.weak_concepts = overrides.get("weak_concepts", [])
    row.created_at = overrides.get(
        "created_at", datetime.now(timezone.utc) - timedelta(days=1)
    )
    return row


class TestGetAsgfDigestData:
    """Tests for get_asgf_digest_data."""

    @pytest.mark.asyncio
    async def test_no_sessions_returns_empty(self):
        from app.services.asgf_pedi_service import get_asgf_digest_data

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = await get_asgf_digest_data(42, since, db)

        assert result["session_count"] == 0
        assert result["top_subjects"] == []
        assert result["xp_trend"] == "stable"
        assert result["weak_topics"] == []
        assert result["session_summaries"] == []

    @pytest.mark.asyncio
    async def test_returns_session_count_and_subjects(self):
        from app.services.asgf_pedi_service import get_asgf_digest_data

        db = MagicMock()
        sessions = [
            _make_learning_history(id=1, subject="Math", session_id="s1"),
            _make_learning_history(id=2, subject="Math", session_id="s2"),
            _make_learning_history(id=3, subject="Science", session_id="s3"),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sessions
        # Mock the XP trend query (avg score)
        db.query.return_value.filter.return_value.scalar.return_value = None

        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = await get_asgf_digest_data(42, since, db)

        assert result["session_count"] == 3
        assert result["top_subjects"][0] == "Math"
        assert "Science" in result["top_subjects"]

    @pytest.mark.asyncio
    async def test_weak_topics_extracted_from_strings(self):
        from app.services.asgf_pedi_service import get_asgf_digest_data

        db = MagicMock()
        sessions = [
            _make_learning_history(
                weak_concepts=["fractions", "decimals"],
            ),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sessions
        db.query.return_value.filter.return_value.scalar.return_value = None

        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = await get_asgf_digest_data(42, since, db)

        assert "decimals" in result["weak_topics"]
        assert "fractions" in result["weak_topics"]

    @pytest.mark.asyncio
    async def test_weak_topics_extracted_from_dicts(self):
        from app.services.asgf_pedi_service import get_asgf_digest_data

        db = MagicMock()
        sessions = [
            _make_learning_history(
                weak_concepts=[{"name": "algebra"}, {"topic": "geometry"}],
            ),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sessions
        db.query.return_value.filter.return_value.scalar.return_value = None

        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = await get_asgf_digest_data(42, since, db)

        assert "algebra" in result["weak_topics"]
        assert "geometry" in result["weak_topics"]

    @pytest.mark.asyncio
    async def test_session_summaries_truncated(self):
        from app.services.asgf_pedi_service import get_asgf_digest_data

        db = MagicMock()
        long_question = "A" * 200
        sessions = [
            _make_learning_history(question_asked=long_question),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sessions
        db.query.return_value.filter.return_value.scalar.return_value = None

        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = await get_asgf_digest_data(42, since, db)

        summary = result["session_summaries"][0]["summary"]
        assert len(summary) == 120
        assert summary.endswith("...")

    @pytest.mark.asyncio
    async def test_session_summaries_contain_expected_keys(self):
        from app.services.asgf_pedi_service import get_asgf_digest_data

        db = MagicMock()
        sessions = [
            _make_learning_history(
                subject="Math",
                overall_score_pct=75,
                question_asked="What is 2+2?",
            ),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sessions
        db.query.return_value.filter.return_value.scalar.return_value = None

        since = datetime.now(timezone.utc) - timedelta(days=7)
        result = await get_asgf_digest_data(42, since, db)

        summary = result["session_summaries"][0]
        assert "date" in summary
        assert summary["subject"] == "Math"
        assert summary["score"] == 75
        assert summary["summary"] == "What is 2+2?"


class TestHasContentWithAsgf:
    """Test that has_content considers ASGF summaries."""

    def test_has_content_with_asgf_only(self):
        from app.services.daily_digest_service import has_content

        briefing = MagicMock()
        briefing.total_overdue = 0
        briefing.total_due_today = 0
        briefing.total_upcoming = 0

        assert has_content(briefing, ile_summaries=None, asgf_summaries={42: {"session_count": 1}})

    def test_has_content_empty_when_nothing(self):
        from app.services.daily_digest_service import has_content

        briefing = MagicMock()
        briefing.total_overdue = 0
        briefing.total_due_today = 0
        briefing.total_upcoming = 0

        assert not has_content(briefing, ile_summaries=None, asgf_summaries=None)
