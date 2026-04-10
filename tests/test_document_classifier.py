"""Tests for Document Type Auto-Detection Service (§6.105.3, #1975)."""
import json
import pytest
from unittest.mock import patch, MagicMock, call
from app.services.document_classifier import DocumentClassifierService, VALID_DOCUMENT_TYPES, VALID_SUBJECTS


class TestDocumentClassifierService:
    """Test the document classification service."""

    def test_empty_text_returns_custom(self):
        """Empty text should return custom with 0 confidence."""
        result = DocumentClassifierService.classify("", "test.pdf")
        assert result["document_type"] == "custom"
        assert result["detected_subject"] == "unknown"
        assert result["confidence"] == 0.0

    def test_none_text_returns_custom(self):
        """None/whitespace text should return custom."""
        result = DocumentClassifierService.classify("   ", "test.pdf")
        assert result["document_type"] == "custom"
        assert result["detected_subject"] == "unknown"
        assert result["confidence"] == 0.0

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_successful_classification(self, mock_client):
        """Should return parsed document type from AI response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "teacher_notes", "detected_subject": "math", "confidence": 0.85}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify("Chapter 5 Notes: Quadratic Functions...", "ch5_notes.pdf")
        assert result["document_type"] == "teacher_notes"
        assert result["detected_subject"] == "math"
        assert result["confidence"] == 0.85

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_invalid_type_falls_back(self, mock_client):
        """Invalid document type from AI should fall back to custom."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "invalid", "detected_subject": "math", "confidence": 0.9}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify("Some content", "file.pdf")
        assert result["document_type"] == "custom"
        assert result["confidence"] == 0.0

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_json_parse_error_returns_custom(self, mock_client):
        """Malformed JSON should return custom."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not json")]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify("Some content", "file.pdf")
        assert result["document_type"] == "custom"
        assert result["detected_subject"] == "unknown"
        assert result["confidence"] == 0.0

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_api_error_returns_custom(self, mock_client):
        """API errors should return custom (fail-open)."""
        mock_client.return_value.messages.create.side_effect = Exception("API error")

        result = DocumentClassifierService.classify("Some content", "file.pdf")
        assert result["document_type"] == "custom"
        assert result["detected_subject"] == "unknown"
        assert result["confidence"] == 0.0

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_markdown_fences_stripped(self, mock_client):
        """Should handle AI responses wrapped in markdown code fences."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"document_type": "past_exam", "detected_subject": "science", "confidence": 0.7}\n```')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify("Exam questions...", "exam.pdf")
        assert result["document_type"] == "past_exam"
        assert result["detected_subject"] == "science"

    def test_all_valid_types_are_defined(self):
        """VALID_DOCUMENT_TYPES should include the 11 types (8 original + 3 UTDF additions)."""
        assert len(VALID_DOCUMENT_TYPES) == 11
        assert "custom" in VALID_DOCUMENT_TYPES
        assert "worksheet" in VALID_DOCUMENT_TYPES
        assert "student_test" in VALID_DOCUMENT_TYPES
        assert "quiz_paper" in VALID_DOCUMENT_TYPES

    # ── UTDF Tests (S15 #2961) ───────────────────────────────────

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_classify_math_exam(self, mock_client):
        """Math exam content should return detected_subject='math' with high confidence."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "past_exam", "detected_subject": "math", "confidence": 0.92}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify(
            "Grade 10 Math Final Exam\nQuestion 1: Solve 2x + 5 = 17\nQuestion 2: Factor x^2 - 9",
            "math_exam_2025.pdf",
        )
        assert result["detected_subject"] == "math"
        assert result["confidence"] >= 0.80

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_classify_uses_2000_chars(self, mock_client):
        """Classifier should send first 2000 chars of extracted text to the AI."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "teacher_notes", "detected_subject": "science", "confidence": 0.8}')]
        mock_client.return_value.messages.create.return_value = mock_response

        # Create text longer than 2000 chars
        long_text = "A" * 3000
        DocumentClassifierService.classify(long_text, "notes.pdf")

        # Verify the user message sent to the AI contains at most 2000 chars of the original
        call_args = mock_client.return_value.messages.create.call_args
        user_message = call_args[1]["messages"][0]["content"]
        # The text_snippet is extracted_text[:2000], the user message also includes filename prefix
        assert "A" * 2000 in user_message
        # Should NOT contain the full 3000 chars
        assert "A" * 2001 not in user_message

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_classify_retries_on_timeout(self, mock_client):
        """Timeout on first attempt should fall back to custom (fail-open)."""
        import httpx
        mock_client.return_value.messages.create.side_effect = Exception("Connection timed out")

        result = DocumentClassifierService.classify("Some math content", "test.pdf")
        assert result["document_type"] == "custom"
        assert result["detected_subject"] == "unknown"
        assert result["confidence"] == 0.0

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_classify_mixed_subject(self, mock_client):
        """Multi-subject content should return detected_subject='mixed'."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "teacher_notes", "detected_subject": "mixed", "confidence": 0.75}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify(
            "Math: Solve for x. English: Write an essay. Science: Describe photosynthesis.",
            "mixed_review.pdf",
        )
        assert result["detected_subject"] == "mixed"

    @patch("app.services.document_classifier.get_anthropic_client")
    def test_invalid_subject_falls_back_to_unknown(self, mock_client):
        """Invalid detected_subject from AI should fall back to 'unknown'."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "teacher_notes", "detected_subject": "history", "confidence": 0.8}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = DocumentClassifierService.classify("World War II notes", "history.pdf")
        assert result["detected_subject"] == "unknown"

    def test_valid_subjects_defined(self):
        """VALID_SUBJECTS should include the expected subject values."""
        assert "math" in VALID_SUBJECTS
        assert "science" in VALID_SUBJECTS
        assert "english" in VALID_SUBJECTS
        assert "french" in VALID_SUBJECTS
        assert "mixed" in VALID_SUBJECTS
        assert "unknown" in VALID_SUBJECTS
