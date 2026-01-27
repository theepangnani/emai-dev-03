"""
File processor service for extracting text from various document formats.
Supports: PDF, Word, Excel, PowerPoint, Images (OCR), Text, and ZIP archives.
"""

import io
import os
import zipfile
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.core.logging_config import get_logger

# Document processing
import PyPDF2
from docx import Document as WordDocument
from pptx import Presentation
from openpyxl import load_workbook
from PIL import Image

# OCR (optional - requires Tesseract installed)
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
SUPPORTED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.txt', '.md', '.rtf',
    '.xlsx', '.xls', '.csv',
    '.pptx', '.ppt',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp',
    '.zip'
}

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}

logger = get_logger(__name__)


class FileProcessingError(Exception):
    """Custom exception for file processing errors."""
    pass


def validate_file(file_content: bytes, filename: str) -> None:
    """Validate file size and extension."""
    file_size_mb = len(file_content) / (1024 * 1024)
    logger.debug(f"Validating file: {filename}, size: {file_size_mb:.2f} MB")

    if len(file_content) > MAX_FILE_SIZE:
        logger.warning(f"File too large: {filename} ({file_size_mb:.2f} MB)")
        raise FileProcessingError(
            f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        logger.warning(f"Unsupported file type: {ext} for file {filename}")
        raise FileProcessingError(
            f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text_parts = []
        page_count = len(pdf_reader.pages)
        logger.debug(f"Processing PDF with {page_count} pages")
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        logger.debug(f"Extracted text from {len(text_parts)} pages")
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF extraction failed: {str(e)}")
        raise FileProcessingError(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from Word document (.docx)."""
    try:
        doc = WordDocument(io.BytesIO(file_content))
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_parts.append(" | ".join(row_text))
        return "\n\n".join(text_parts)
    except Exception as e:
        raise FileProcessingError(f"Failed to extract text from Word document: {str(e)}")


def extract_text_from_pptx(file_content: bytes) -> str:
    """Extract text from PowerPoint presentation (.pptx)."""
    try:
        prs = Presentation(io.BytesIO(file_content))
        text_parts = []
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = [f"--- Slide {slide_num} ---"]
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text)
            if len(slide_text) > 1:  # More than just the slide header
                text_parts.append("\n".join(slide_text))
        return "\n\n".join(text_parts)
    except Exception as e:
        raise FileProcessingError(f"Failed to extract text from PowerPoint: {str(e)}")


def extract_text_from_xlsx(file_content: bytes) -> str:
    """Extract text from Excel spreadsheet (.xlsx)."""
    try:
        wb = load_workbook(io.BytesIO(file_content), data_only=True)
        text_parts = []
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_text = [f"--- Sheet: {sheet_name} ---"]
            for row in sheet.iter_rows(values_only=True):
                row_values = [str(cell) if cell is not None else "" for cell in row]
                if any(v.strip() for v in row_values):
                    sheet_text.append(" | ".join(row_values))
            if len(sheet_text) > 1:
                text_parts.append("\n".join(sheet_text))
        return "\n\n".join(text_parts)
    except Exception as e:
        raise FileProcessingError(f"Failed to extract text from Excel: {str(e)}")


def extract_text_from_image(file_content: bytes, filename: str) -> str:
    """Extract text from image using OCR."""
    if not OCR_AVAILABLE:
        raise FileProcessingError(
            "OCR is not available. Please install Tesseract and pytesseract."
        )

    try:
        image = Image.open(io.BytesIO(file_content))
        # Convert to RGB if necessary (for PNG with alpha channel, etc.)
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        text = pytesseract.image_to_string(image)
        if not text.strip():
            return f"[Image: {filename} - No text detected via OCR]"
        return text.strip()
    except Exception as e:
        raise FileProcessingError(f"Failed to extract text from image: {str(e)}")


def extract_text_from_text_file(file_content: bytes, filename: str) -> str:
    """Extract text from plain text files."""
    try:
        # Try common encodings
        for encoding in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
            try:
                return file_content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise FileProcessingError("Unable to decode text file with any supported encoding")
    except Exception as e:
        raise FileProcessingError(f"Failed to read text file: {str(e)}")


def extract_text_from_zip(file_content: bytes, filename: str) -> str:
    """Extract and process all supported files from a ZIP archive recursively."""
    logger.info(f"Processing ZIP archive: {filename}")
    try:
        extracted_texts = []
        total_size = 0
        files_processed = 0
        files_skipped = 0

        with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zip_file:
            file_count = len([f for f in zip_file.infolist() if not f.is_dir()])
            logger.debug(f"ZIP contains {file_count} files")

            for zip_info in zip_file.infolist():
                # Skip directories
                if zip_info.is_dir():
                    continue

                # Check file extension
                file_ext = Path(zip_info.filename).suffix.lower()
                if file_ext not in SUPPORTED_EXTENSIONS or file_ext == '.zip':
                    # Skip unsupported files and nested zips (to prevent zip bombs)
                    logger.debug(f"Skipping unsupported file in ZIP: {zip_info.filename}")
                    files_skipped += 1
                    continue

                # Check cumulative size
                total_size += zip_info.file_size
                if total_size > MAX_FILE_SIZE:
                    logger.warning(f"ZIP extraction exceeded size limit at {total_size / (1024*1024):.2f} MB")
                    raise FileProcessingError(
                        f"Total extracted size exceeds {MAX_FILE_SIZE // (1024*1024)} MB limit"
                    )

                # Extract and process file
                inner_content = zip_file.read(zip_info.filename)
                try:
                    inner_text = process_file(inner_content, zip_info.filename)
                    if inner_text.strip():
                        extracted_texts.append(f"=== {zip_info.filename} ===\n{inner_text}")
                        files_processed += 1
                except FileProcessingError as e:
                    logger.debug(f"Failed to process file in ZIP: {zip_info.filename} - {str(e)}")
                    files_skipped += 1
                    continue

        logger.info(f"ZIP processing complete: {files_processed} files processed, {files_skipped} skipped")

        if not extracted_texts:
            raise FileProcessingError("No supported files found in ZIP archive")

        return "\n\n".join(extracted_texts)
    except zipfile.BadZipFile:
        logger.error(f"Invalid ZIP file: {filename}")
        raise FileProcessingError("Invalid or corrupted ZIP file")
    except Exception as e:
        if isinstance(e, FileProcessingError):
            raise
        logger.error(f"ZIP processing failed: {str(e)}")
        raise FileProcessingError(f"Failed to process ZIP archive: {str(e)}")


def process_file(file_content: bytes, filename: str) -> str:
    """
    Process a file and extract its text content.

    Args:
        file_content: Raw bytes of the file
        filename: Original filename (used to determine file type)

    Returns:
        Extracted text content

    Raises:
        FileProcessingError: If file cannot be processed
    """
    logger.info(f"Processing file: {filename}")
    validate_file(file_content, filename)

    ext = Path(filename).suffix.lower()

    if ext == '.pdf':
        return extract_text_from_pdf(file_content)

    elif ext in ('.doc', '.docx'):
        if ext == '.doc':
            raise FileProcessingError(
                "Legacy .doc format is not supported. Please convert to .docx"
            )
        return extract_text_from_docx(file_content)

    elif ext == '.pptx':
        return extract_text_from_pptx(file_content)

    elif ext == '.ppt':
        raise FileProcessingError(
            "Legacy .ppt format is not supported. Please convert to .pptx"
        )

    elif ext in ('.xlsx', '.xls'):
        if ext == '.xls':
            raise FileProcessingError(
                "Legacy .xls format is not supported. Please convert to .xlsx"
            )
        return extract_text_from_xlsx(file_content)

    elif ext == '.csv':
        return extract_text_from_text_file(file_content, filename)

    elif ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_content, filename)

    elif ext in ('.txt', '.md', '.rtf'):
        return extract_text_from_text_file(file_content, filename)

    elif ext == '.zip':
        return extract_text_from_zip(file_content, filename)

    else:
        raise FileProcessingError(f"Unsupported file type: {ext}")


async def process_uploaded_file(file: BinaryIO, filename: str) -> str:
    """
    Async wrapper for processing uploaded files.

    Args:
        file: File-like object with read() method
        filename: Original filename

    Returns:
        Extracted text content
    """
    file_content = file.read()
    return process_file(file_content, filename)


def get_supported_formats() -> dict:
    """Return information about supported file formats."""
    return {
        "documents": [".pdf", ".docx", ".txt", ".md", ".rtf"],
        "spreadsheets": [".xlsx", ".csv"],
        "presentations": [".pptx"],
        "images": list(IMAGE_EXTENSIONS),
        "archives": [".zip"],
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "ocr_available": OCR_AVAILABLE,
    }
