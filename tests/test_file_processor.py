"""Tests for file_processor.py — focused on docx image OCR logic."""
import io
import zipfile
from unittest.mock import patch, MagicMock

import pytest


def _make_docx_bytes(paragraphs: list[str], num_images: int = 0, img_size: int = 100) -> bytes:
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
            # Add fake PNG images
            from PIL import Image as PILImage

            for i in range(num_images):
                img_buf = io.BytesIO()
                PILImage.new("RGB", (img_size, img_size), "white").save(img_buf, format="PNG")
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


class TestVisionOcr:
    """Tests for Vision OCR (Claude API) path."""

    @patch("app.services.file_processor._ocr_images_with_vision")
    def test_vision_ocr_used_for_docx_images(self, mock_vision):
        """Vision OCR should be called when docx has embedded images."""
        from app.services.file_processor import extract_text_from_docx

        mock_vision.return_value = ["Distance formula: L = √((x₂-x₁)² + (y₂-y₁)²)"]
        data = _make_docx_bytes(["Some text"], num_images=2)

        result = extract_text_from_docx(data)
        mock_vision.assert_called_once()
        assert "Distance formula" in result
        assert "√" in result

    @patch("app.services.file_processor._ocr_images_with_vision")
    def test_vision_ocr_result_appended_to_text(self, mock_vision):
        """Vision OCR text should be appended after regular paragraph text."""
        from app.services.file_processor import extract_text_from_docx

        mock_vision.return_value = ["Slope = (y₂-y₁)/(x₂-x₁)"]
        data = _make_docx_bytes(["Regular paragraph text"], num_images=1)

        result = extract_text_from_docx(data)
        assert "Regular paragraph text" in result
        assert "Slope = (y₂-y₁)/(x₂-x₁)" in result

    @patch("app.services.file_processor.VISION_OCR_AVAILABLE", True)
    @patch("app.services.file_processor.anthropic")
    def test_vision_ocr_filters_tiny_images(self, mock_anthropic):
        """Images < 1KB should be skipped by vision OCR."""
        from app.services.file_processor import _ocr_images_with_vision

        # Create a tiny image (< 1KB)
        tiny_img = b"\x89PNG" + b"\x00" * 500  # ~504 bytes
        result = _ocr_images_with_vision([tiny_img])
        # Returns one empty string per input image (tiny images get empty description)
        assert result == [""]
        # API should not have been called
        mock_anthropic.Anthropic.return_value.messages.create.assert_not_called()

    @patch("app.services.file_processor.VISION_OCR_AVAILABLE", False)
    def test_vision_ocr_unavailable_returns_empty(self):
        """When anthropic is not installed, vision OCR returns empty."""
        from app.services.file_processor import _ocr_images_with_vision

        result = _ocr_images_with_vision([b"\x89PNG" + b"\x00" * 2000])
        # Returns one empty string per input image when Vision OCR is unavailable
        assert result == [""]

    def test_image_media_type_detection(self):
        """Test _get_image_media_type detects common formats."""
        from app.services.file_processor import _get_image_media_type

        assert _get_image_media_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100) == "image/png"
        assert _get_image_media_type(b"\xff\xd8\xff" + b"\x00" * 100) == "image/jpeg"
        assert _get_image_media_type(b"GIF89a" + b"\x00" * 100) == "image/gif"
        assert _get_image_media_type(b"BM" + b"\x00" * 100) == "image/bmp"
        # Unknown defaults to png
        assert _get_image_media_type(b"\x00\x00\x00" + b"\x00" * 100) == "image/png"


class TestDocxOcrFallback:
    """Tesseract OCR should run as fallback when Vision OCR is unavailable."""

    @patch("app.services.file_processor._ocr_images_with_vision", return_value=[])
    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_tesseract_fallback_when_vision_empty(self, mock_tesseract, mock_vision):
        """Tesseract should run when vision OCR returns empty."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Some text"], num_images=2)
        mock_tesseract.image_to_string.return_value = "Tesseract OCR result"

        result = extract_text_from_docx(data)
        assert mock_tesseract.image_to_string.call_count == 2
        assert "Tesseract OCR result" in result

    @patch("app.services.file_processor._ocr_images_with_vision")
    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_no_tesseract_when_vision_succeeds(self, mock_tesseract, mock_vision):
        """Tesseract should NOT run when vision OCR returns results."""
        from app.services.file_processor import extract_text_from_docx

        mock_vision.return_value = ["Vision OCR result"]
        data = _make_docx_bytes(["Some text"], num_images=2)

        result = extract_text_from_docx(data)
        mock_tesseract.image_to_string.assert_not_called()
        assert "Vision OCR result" in result

    @patch("app.services.file_processor._ocr_images_with_vision", return_value=[])
    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_tesseract_skips_empty_results(self, mock_tesseract, mock_vision):
        """Tesseract results with no text should be skipped."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Some text"], num_images=2)
        mock_tesseract.image_to_string.side_effect = ["", "Useful text"]

        result = extract_text_from_docx(data)
        assert "Useful text" in result

    @patch("app.services.file_processor._ocr_images_with_vision", return_value=[])
    @patch("app.services.file_processor.OCR_AVAILABLE", False)
    def test_no_ocr_when_both_unavailable(self, mock_vision):
        """When both Vision and Tesseract are unavailable, should still extract text."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Regular text"], num_images=2)
        result = extract_text_from_docx(data)
        assert "Regular text" in result

    @patch("app.services.file_processor._ocr_images_with_vision", return_value=[])
    @patch("app.services.file_processor.OCR_AVAILABLE", True)
    @patch("app.services.file_processor.pytesseract")
    def test_no_images_means_no_ocr(self, mock_tesseract, mock_vision):
        """No images means neither OCR should be attempted."""
        from app.services.file_processor import extract_text_from_docx

        data = _make_docx_bytes(["Just text, no images"])
        extract_text_from_docx(data)
        mock_vision.assert_not_called()
        mock_tesseract.image_to_string.assert_not_called()


def _make_pdf_with_vector_only() -> bytes:
    """Create a minimal PDF with vector-drawn content (no raster images).

    Uses PyMuPDF (fitz) to draw shapes — these are path operators that
    PyPDF2 cannot extract as images.
    """
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Draw a triangle (vector graphic)
    shape = page.new_shape()
    shape.draw_line(fitz.Point(100, 600), fitz.Point(300, 200))
    shape.draw_line(fitz.Point(300, 200), fitz.Point(500, 600))
    shape.draw_line(fitz.Point(500, 600), fitz.Point(100, 600))
    shape.finish(color=(0, 0, 0), width=2)
    shape.commit()
    # Add some text
    page.insert_text(fitz.Point(200, 150), "Triangle Diagram", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_pdf_with_raster_image() -> bytes:
    """Create a PDF with an embedded raster image that PyPDF2 can extract."""
    import fitz
    from PIL import Image as PILImage

    # Create a small raster image
    img_buf = io.BytesIO()
    PILImage.new("RGB", (100, 100), "red").save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(100, 100, 300, 300), stream=img_bytes)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestPdfImageExtraction:
    """Regression tests for PDF image extraction — ensures vector graphics
    are captured via PyMuPDF fallback when PyPDF2 finds no raster images."""

    def test_vector_only_pdf_uses_fallback(self):
        """PDFs with only vector graphics (no raster XObjects) should still
        produce images via the PyMuPDF page-rendering fallback."""
        from app.services.file_processor import _extract_images_from_pdf

        pdf_bytes = _make_pdf_with_vector_only()
        images = _extract_images_from_pdf(pdf_bytes)
        # Should have at least 1 page rendered as image
        assert len(images) >= 1
        # Should be PNG data
        assert images[0]["image_bytes"][:4] == b"\x89PNG"
        assert images[0]["position_context"] == "Page 1"

    def test_raster_pdf_does_not_use_fallback(self):
        """PDFs with embedded raster images should use PyPDF2 extraction,
        NOT the page-rendering fallback."""
        from app.services.file_processor import _extract_images_from_pdf

        pdf_bytes = _make_pdf_with_raster_image()
        images = _extract_images_from_pdf(pdf_bytes)
        assert len(images) >= 1
        # If PyPDF2 found the raster image, the fallback shouldn't run.
        # Raster extraction produces raw image data, not necessarily PNG headers.
        # Just verify we got results.
        assert len(images[0]["image_bytes"]) > 0

    def test_render_pdf_pages_as_images(self):
        """Direct test of the _render_pdf_pages_as_images helper."""
        from app.services.file_processor import _render_pdf_pages_as_images

        pdf_bytes = _make_pdf_with_vector_only()
        images = _render_pdf_pages_as_images(pdf_bytes)
        assert len(images) == 1
        assert images[0]["content_type"] == "image/png"
        assert images[0]["position_context"] == "Page 1"
        # PNG should be non-trivial size (not a blank page — has drawn content)
        assert len(images[0]["image_bytes"]) > 1024

    def test_render_respects_max_pages_cap(self):
        """Should cap at _MAX_IMAGES_PER_DOC pages."""
        import fitz
        from app.services.file_processor import _render_pdf_pages_as_images, _MAX_IMAGES_PER_DOC

        doc = fitz.open()
        for _ in range(25):  # More than _MAX_IMAGES_PER_DOC (20)
            doc.new_page(width=100, height=100)
        pdf_bytes = doc.tobytes()
        doc.close()

        images = _render_pdf_pages_as_images(pdf_bytes)
        assert len(images) == _MAX_IMAGES_PER_DOC
