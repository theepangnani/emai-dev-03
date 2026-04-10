"""Tests for Document Type Auto-Detection Service (§6.105.3, #1975)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.services.document_classifier import DocumentClassifierService, VALID_DOCUMENT_TYPES


class TestDocumentClassifierService:
    """Test the document classification service."""

    @pytest.mark.asyncio
    async def test_empty_text_returns_custom(self):
        """Empty text should return custom with 0 confidence."""
        result = await DocumentClassifierService.classify("", "test.pdf")
        assert result["document_type"] == "custom"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_none_text_returns_custom(self):
        """None/whitespace text should return custom."""
        result = await DocumentClassifierService.classify("   ", "test.pdf")
        assert result["document_type"] == "custom"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("app.services.document_classifier.get_anthropic_client")
    async def test_successful_classification(self, mock_client):
        """Should return parsed document type from AI response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "teacher_notes", "confidence": 0.85}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = await DocumentClassifierService.classify("Chapter 5 Notes: Quadratic Functions...", "ch5_notes.pdf")
        assert result["document_type"] == "teacher_notes"
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    @patch("app.services.document_classifier.get_anthropic_client")
    async def test_invalid_type_falls_back(self, mock_client):
        """Invalid document type from AI should fall back to custom."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"document_type": "invalid", "confidence": 0.9}')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = await DocumentClassifierService.classify("Some content", "file.pdf")
        assert result["document_type"] == "custom"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("app.services.document_classifier.get_anthropic_client")
    async def test_json_parse_error_returns_custom(self, mock_client):
        """Malformed JSON should return custom."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not json")]
        mock_client.return_value.messages.create.return_value = mock_response

        result = await DocumentClassifierService.classify("Some content", "file.pdf")
        assert result["document_type"] == "custom"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("app.services.document_classifier.get_anthropic_client")
    async def test_api_error_returns_custom(self, mock_client):
        """API errors should return custom (fail-open)."""
        mock_client.return_value.messages.create.side_effect = Exception("API error")

        result = await DocumentClassifierService.classify("Some content", "file.pdf")
        assert result["document_type"] == "custom"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("app.services.document_classifier.get_anthropic_client")
    async def test_markdown_fences_stripped(self, mock_client):
        """Should handle AI responses wrapped in markdown code fences."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"document_type": "past_exam", "confidence": 0.7}\n```')]
        mock_client.return_value.messages.create.return_value = mock_response

        result = await DocumentClassifierService.classify("Exam questions...", "exam.pdf")
        assert result["document_type"] == "past_exam"

    def test_all_valid_types_are_defined(self):
        """VALID_DOCUMENT_TYPES should have all 8 types."""
        assert len(VALID_DOCUMENT_TYPES) == 8
        assert "custom" in VALID_DOCUMENT_TYPES
