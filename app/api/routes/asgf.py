"""ASGF (Ask-a-Question / Study Guide Flow) routes.

Provides multi-file upload for personalized study sessions.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User
from app.schemas.asgf import FileUploadResponse, MultiFileUploadResponse
from app.services.file_processor import (
    FileProcessingError,
    process_file,
)
from app.services.storage_service import save_file

logger = get_logger(__name__)

router = APIRouter(prefix="/asgf", tags=["asgf"])

# --- constants -----------------------------------------------------------
MAX_FILES = 5
MAX_TOTAL_BYTES = 25 * 1024 * 1024  # 25 MB
ACCEPTED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}
TEXT_PREVIEW_LENGTH = 200


def _validate_extension(filename: str) -> str:
    """Return the lower-cased extension if accepted, else raise 400."""
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        ext = f".{ext}"
    if ext not in ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(ACCEPTED_EXTENSIONS))}",
        )
    return ext


@router.post("/upload", response_model=MultiFileUploadResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def upload_asgf_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload up to 5 documents (25 MB total) for an ASGF study session.

    Accepted types: PDF, DOCX, JPG, PNG.
    Returns extracted text previews for each file.
    """
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES} files allowed per upload.",
        )

    # Read all files and validate
    file_data: list[tuple[UploadFile, bytes]] = []
    total_bytes = 0
    for f in files:
        _validate_extension(f.filename or "")
        if f.size and f.size > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{f.filename}' exceeds size limit.",
            )
        try:
            content = await f.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read file '{f.filename}': {exc}")
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload size exceeds {MAX_TOTAL_BYTES // (1024 * 1024)} MB limit.",
            )
        file_data.append((f, content))

    results: list[FileUploadResponse] = []
    for upload_file, content in file_data:
        filename = upload_file.filename or "unknown"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Persist to uploads dir (reuse existing storage service)
        stored_name = await asyncio.to_thread(save_file, content, filename)
        file_id = uuid4().hex

        # Extract text preview (best-effort)
        text_preview = ""
        try:
            extracted = await asyncio.to_thread(process_file, content, filename)
            text_preview = (extracted[:TEXT_PREVIEW_LENGTH] + "...") if len(extracted) > TEXT_PREVIEW_LENGTH else extracted
        except FileProcessingError:
            text_preview = "(text extraction unavailable)"
        except Exception as exc:
            logger.warning("ASGF text extraction failed for %s: %s", filename, exc)
            text_preview = "(text extraction unavailable)"

        results.append(
            FileUploadResponse(
                file_id=file_id,
                filename=filename,
                file_type=ext,
                file_size_bytes=len(content),
                text_preview=text_preview,
            )
        )

    logger.info(
        "ASGF upload: user=%d, files=%d, total_bytes=%d",
        current_user.id,
        len(results),
        total_bytes,
    )

    return MultiFileUploadResponse(files=results, total_size_bytes=total_bytes)
