"""Tests for file_processor.py — focused on docx image OCR logic."""
import io
import zipfile
from unittest.mock import patch, MagicMock

import pytest


def _make_docx_bytes(paragraphs: list[str], num_images: int = 0) -> bytes:
    """Build a minimal .docx (ZIP) with python-docx, optionally injecting fake images."""
    from docx import Document

    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)

    buf = io.BytesIO()
    doc.save(buf)

    if num_images > 0:
        # Re-open ZIP and add fake image files into word/media/
        buf.seek(0)
        new_buf = io.BytesIO()
        with zipfile.ZipFile(buf, "r") as zin, zipfile.ZipFile(new_buf, "w") as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            # Add fake PNG images (1x1 white pixel)
            from PIL import Image as PILImage

            for i in range(num_images):
                img_buf = io.BytesIO()
                PILImage.new("RGB", (100, 100), "white").save(img_buf, format="PNG")
                zout.writestr(f"word/media/image{i + 1}.png", img_buf.getvalue())
        return new_buf.getvalue()

    buf.seek(0)
    return buf.getvalue()


class TestDocxImageExtraction:
    """Verify _extract_images_from_docx returns embedded images."""

    def test_no_images(self):
        from app.services.file_processor import _extract_images_from_docx

        data = _make_docx_bytes(["Hello world"])
        assert _extract_images_from_docx(data) == []

    def test_extracts_images(self):
        from app.services.file_processor import _extract_images_from_docx

        data = _make_docx_bytes(["Hello"], num_images=3)
        images = _extract_images_from_docx(data)
        assert len(images) == 3
        # Each should be valid PNG bytes
        for img_bytes in images:
            assert img_bytes[:4] == b"\x89PNG"


class TestDocxOcrAlwaysRuns:
    """OCR should run on ALL embedded images regardless of text length."""

    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_ocr_runs_with_plenty_of_text(self, mock_tesseract):
        """OCR should run even when document has >200 chars of regular text."""
        from app.services.file_processor import extract_text_from_docx

        long_text = "This is a paragraph with plenty of text content. " * 10  # ~500 chars
        data = _make_docx_bytes([long_text], num_images=2)

        mock_tesseract.image_to_string.return_value = "OCR result from screenshot"

        result = extract_text_from_docx(data)
        # OCR should have been called for each image
        assert mock_tesseract.image_to_string.call_count == 2
        assert "OCR result from screenshot" in result

    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_ocr_runs_with_single_image(self, mock_tesseract):
        """OCR should run even with just 1 image."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Short text"], num_images=1)

        mock_tesseract.image_to_string.return_value = "Math: 2x + 3 = 7"

        result = extract_text_from_docx(data)
        assert mock_tesseract.image_to_string.call_count == 1
        assert "Math: 2x + 3 = 7" in result

    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_ocr_skips_empty_results(self, mock_tesseract):
        """OCR results with no text should be skipped."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Some text"], num_images=2)

        mock_tesseract.image_to_string.side_effect = ["", "Useful text"]

        result = extract_text_from_docx(data)
        assert "Useful text" in result

    @patch("app.services.file_processor.OCR_AVAILABLE", False)
    def test_no_ocr_when_unavailable(self):
        """When OCR is not available, should still extract text without error."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Regular text"], num_images=2)
        result = extract_text_from_docx(data)
        assert "Regular text" in result

    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_no_images_means_no_ocr(self, mock_tesseract):
        """No images means OCR should not be attempted."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Just text, no images"])
        extract_text_from_docx(data)
        mock_tesseract.image_to_string.assert_not_called()
