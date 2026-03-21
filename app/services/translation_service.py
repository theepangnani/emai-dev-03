"""
Translation Service for multilingual parent summaries (#2015).

Uses Claude Haiku for cost-efficient translation of parent-facing summaries.
Translations are cached in the translated_summaries table to avoid redundant API calls.
"""
from app.core.logging_config import get_logger
from app.services.ai_service import get_anthropic_client

logger = get_logger(__name__)


class TranslationService:
    """Service for translating parent summaries using Claude Haiku."""

    SUPPORTED_LANGUAGES = {
        "en": "English",
        "fr": "French",
        "ta": "Tamil",
        "zh": "Mandarin Chinese (Simplified)",
        "pa": "Punjabi",
        "ur": "Urdu",
    }

    @staticmethod
    def translate(text: str, target_language: str) -> str:
        """Translate text using Claude Haiku. Returns original if target is English.

        Args:
            text: The text to translate.
            target_language: ISO language code (e.g. "fr", "ta").

        Returns:
            Translated text, or original text if target is English or unsupported.
        """
        if target_language == "en" or not target_language:
            return text

        lang_name = TranslationService.SUPPORTED_LANGUAGES.get(target_language)
        if not lang_name:
            logger.warning(f"Unsupported language code: {target_language}, returning original")
            return text

        try:
            client = get_anthropic_client()
            result = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                system="You are a professional translator specializing in educational content for parents.",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Translate the following parent-friendly educational summary to {lang_name}. "
                        "Keep it warm, clear, and actionable. "
                        "Preserve any numbered lists or formatting. "
                        "Return ONLY the translated text, nothing else.\n\n"
                        f"{text}"
                    ),
                }],
            )
            translated = result.content[0].text.strip()
            logger.info(
                f"Translated summary to {lang_name} ({len(text)} -> {len(translated)} chars)"
            )
            return translated
        except Exception as e:
            logger.warning(f"Translation to {lang_name} failed: {e}")
            return text
