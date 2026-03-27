"""Tests for the empty-file extraction gate (#2217).

AI generation endpoints must reject content shorter than MIN_EXTRACTION_CHARS (50)
with HTTP 422 and a user-friendly error message.
"""

import pytest
from fastapi import HTTPException

from app.services.file_processor import MIN_EXTRACTION_CHARS


SHORT_TEXT = "Too short."  # 10 chars
EXACTLY_49 = "A" * 49
EXACTLY_50 = "A" * 50
LONG_ENOUGH_TEXT = "A" * 60

EXPECTED_DETAIL = (
    "We couldn't read enough text from this document. "
    "Please try a different file or format."
)


class TestMinExtractionConstant:
    def test_constant_is_50(self):
        assert MIN_EXTRACTION_CHARS == 50


class TestGateImports:
    """Verify the constant and message are importable from the study route module."""

    def test_insufficient_text_msg_defined(self):
        from app.api.routes.study import INSUFFICIENT_TEXT_MSG
        assert "couldn't read enough text" in INSUFFICIENT_TEXT_MSG

    def test_min_extraction_chars_imported(self):
        from app.api.routes.study import MIN_EXTRACTION_CHARS as imported
        assert imported == 50


class TestGateLogic:
    """Verify the < 50 char threshold triggers the correct HTTP 422 response."""

    def _apply_gate(self, text: str):
        """Reproduce the gate check used in all five endpoints."""
        from app.api.routes.study import INSUFFICIENT_TEXT_MSG, MIN_EXTRACTION_CHARS
        if len(text.strip()) < MIN_EXTRACTION_CHARS:
            raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    def test_short_text_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            self._apply_gate(SHORT_TEXT)
        assert exc_info.value.status_code == 422
        assert EXPECTED_DETAIL in exc_info.value.detail

    def test_empty_text_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            self._apply_gate("")
        assert exc_info.value.status_code == 422

    def test_whitespace_only_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            self._apply_gate("   \n\t  ")
        assert exc_info.value.status_code == 422

    def test_exactly_49_chars_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            self._apply_gate(EXACTLY_49)
        assert exc_info.value.status_code == 422

    def test_exactly_50_chars_passes(self):
        self._apply_gate(EXACTLY_50)

    def test_long_text_passes(self):
        self._apply_gate(LONG_ENOUGH_TEXT)

    def test_whitespace_padded_short_text_raises_422(self):
        """Leading/trailing whitespace is stripped before the length check."""
        padded = "   short   "
        with pytest.raises(HTTPException) as exc_info:
            self._apply_gate(padded)
        assert exc_info.value.status_code == 422


class TestGatePresenceInEndpoints:
    """Verify that the gate check exists in all five generation endpoint functions."""

    def test_study_guide_endpoint_has_gate(self):
        import inspect
        from app.api.routes.study import generate_study_guide_endpoint
        source = inspect.getsource(generate_study_guide_endpoint)
        assert "MIN_EXTRACTION_CHARS" in source
        assert "422" in source

    def test_quiz_endpoint_has_gate(self):
        import inspect
        from app.api.routes.study import generate_quiz_endpoint
        source = inspect.getsource(generate_quiz_endpoint)
        assert "MIN_EXTRACTION_CHARS" in source
        assert "422" in source

    def test_flashcards_endpoint_has_gate(self):
        import inspect
        from app.api.routes.study import generate_flashcards_endpoint
        source = inspect.getsource(generate_flashcards_endpoint)
        assert "MIN_EXTRACTION_CHARS" in source
        assert "422" in source

    def test_upload_generate_endpoint_has_gate(self):
        import inspect
        from app.api.routes.study import generate_from_file_upload
        source = inspect.getsource(generate_from_file_upload)
        assert "MIN_EXTRACTION_CHARS" in source
        assert "422" in source

    def test_paste_generate_endpoint_has_gate(self):
        import inspect
        from app.api.routes.study import generate_from_text_and_images
        source = inspect.getsource(generate_from_text_and_images)
        assert "MIN_EXTRACTION_CHARS" in source
        assert "422" in source
