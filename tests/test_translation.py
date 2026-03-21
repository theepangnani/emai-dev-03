"""Tests for multilingual parent summaries (#2014, #2015)."""
import pytest
from unittest.mock import patch, MagicMock

from app.services.translation_service import TranslationService
from app.models.translated_summary import TranslatedSummary


class TestTranslationService:
    """Test TranslationService logic."""

    def test_english_returns_original(self):
        """English target language should return original text without API call."""
        text = "Your child is studying math."
        result = TranslationService.translate(text, "en")
        assert result == text

    def test_empty_language_returns_original(self):
        """Empty/None language should return original text."""
        text = "Your child is studying math."
        assert TranslationService.translate(text, "") == text

    def test_unsupported_language_returns_original(self):
        """Unsupported language code should return original text."""
        text = "Your child is studying math."
        result = TranslationService.translate(text, "xx")
        assert result == text

    @patch("app.services.translation_service.get_anthropic_client")
    def test_translate_french(self, mock_get_client):
        """Should call Claude API for French translation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Votre enfant etudie les mathematiques.")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = TranslationService.translate("Your child is studying math.", "fr")

        assert result == "Votre enfant etudie les mathematiques."
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert "French" in call_kwargs["messages"][0]["content"]

    @patch("app.services.translation_service.get_anthropic_client")
    def test_translate_tamil(self, mock_get_client):
        """Should call Claude API for Tamil translation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="translated tamil text")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = TranslationService.translate("Your child is studying math.", "ta")

        assert result == "translated tamil text"
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "Tamil" in call_kwargs["messages"][0]["content"]

    @patch("app.services.translation_service.get_anthropic_client")
    def test_translate_api_failure_returns_original(self, mock_get_client):
        """If Claude API fails, should return original text."""
        mock_get_client.side_effect = Exception("API error")

        text = "Your child is studying math."
        result = TranslationService.translate(text, "fr")
        assert result == text

    def test_supported_languages_complete(self):
        """All required languages should be in the supported map."""
        expected = {"en", "fr", "ta", "zh", "pa", "ur"}
        assert set(TranslationService.SUPPORTED_LANGUAGES.keys()) == expected


class TestTranslatedSummaryModel:
    """Test TranslatedSummary model definition."""

    def test_table_name(self):
        assert TranslatedSummary.__tablename__ == "translated_summaries"

    def test_has_required_columns(self):
        cols = {c.name for c in TranslatedSummary.__table__.columns}
        assert "id" in cols
        assert "study_guide_id" in cols
        assert "language" in cols
        assert "translated_text" in cols
        assert "created_at" in cols

    def test_unique_constraint(self):
        """Should have a unique constraint on (study_guide_id, language)."""
        constraints = [
            c for c in TranslatedSummary.__table__.constraints
            if hasattr(c, "columns")
            and {col.name for col in c.columns} == {"study_guide_id", "language"}
        ]
        assert len(constraints) == 1


class TestLanguagePreferenceSchema:
    """Test UpdateLanguageRequest validation."""

    def test_valid_languages(self):
        from app.schemas.user import UpdateLanguageRequest
        for code in ["en", "fr", "ta", "zh", "pa", "ur"]:
            req = UpdateLanguageRequest(preferred_language=code)
            assert req.preferred_language == code

    def test_invalid_language_rejected(self):
        from app.schemas.user import UpdateLanguageRequest
        with pytest.raises(Exception):
            UpdateLanguageRequest(preferred_language="xx")

    def test_empty_language_rejected(self):
        from app.schemas.user import UpdateLanguageRequest
        with pytest.raises(Exception):
            UpdateLanguageRequest(preferred_language="")


class TestUserResponseLanguage:
    """Test that UserResponse includes preferred_language."""

    def test_default_language_in_response(self):
        from app.schemas.user import UserResponse
        from datetime import datetime

        resp = UserResponse(
            id=1,
            email="test@test.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(),
        )
        assert resp.preferred_language == "en"

    def test_custom_language_in_response(self):
        from app.schemas.user import UserResponse
        from datetime import datetime

        resp = UserResponse(
            id=1,
            email="test@test.com",
            full_name="Test User",
            is_active=True,
            preferred_language="fr",
            created_at=datetime.now(),
        )
        assert resp.preferred_language == "fr"
