"""Tests for Cross-Document Intelligence Service (§6.105.6, #1978)."""
import pytest
from app.services.cross_document import CrossDocumentService


class TestKeywordExtraction:
    """Test the keyword extraction helper."""

    def test_extracts_keywords(self):
        """Should extract meaningful keywords from text."""
        text = "Photosynthesis converts sunlight into chemical energy in plants"
        keywords = CrossDocumentService._extract_keywords(text)
        assert "photosynthesis" in keywords
        assert "converts" in keywords
        assert "sunlight" in keywords
        # Stop words excluded
        assert "into" not in keywords
        assert "the" not in keywords

    def test_empty_text(self):
        """Empty text should return empty dict."""
        assert CrossDocumentService._extract_keywords("") == {}

    def test_stop_words_filtered(self):
        """Common stop words should be filtered out."""
        text = "the and or but this that these those"
        keywords = CrossDocumentService._extract_keywords(text)
        assert len(keywords) == 0

    def test_short_words_excluded(self):
        """Words shorter than 3 chars should be excluded."""
        text = "a go to me he is"
        keywords = CrossDocumentService._extract_keywords(text)
        assert len(keywords) == 0


class TestInsightGeneration:
    """Test the insight generation helper."""

    def test_notes_exam_combo(self):
        """Notes + exam should generate specific insight."""
        insight = CrossDocumentService._generate_insight(
            new_title="Unit Test 3",
            related_title="Chapter 5 Notes",
            shared_topics=["photosynthesis", "respiration"],
            new_doc_type="past_exam",
            related_doc_type="teacher_notes",
            same_course=True,
        )
        assert "notes" in insight.lower() or "exam" in insight.lower()
        assert "photosynthesis" in insight

    def test_same_course_insight(self):
        """Same course materials should mention course context."""
        insight = CrossDocumentService._generate_insight(
            new_title="Doc A",
            related_title="Doc B",
            shared_topics=["algebra"],
            new_doc_type=None,
            related_doc_type=None,
            same_course=True,
        )
        assert "same course" in insight.lower()

    def test_cross_course_insight(self):
        """Cross-course materials should mention cross-course connection."""
        insight = CrossDocumentService._generate_insight(
            new_title="Doc A",
            related_title="Doc B",
            shared_topics=["statistics"],
            new_doc_type=None,
            related_doc_type=None,
            same_course=False,
        )
        assert "cross-course" in insight.lower() or "Cross-course" in insight
