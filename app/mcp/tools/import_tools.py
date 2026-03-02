"""MCP tools for classroom data import.

Allows MCP clients (Claude Desktop, etc.) to help parents import
school data by parsing text/images and managing import sessions.

Exposes 5 FastAPI endpoints at /api/mcp/tools/import/... that allow LLM
clients to parse pasted text or screenshot images, preview parsed results,
list/view import sessions, and commit reviewed imports.

Auth: All endpoints require a valid JWT Bearer token (same pattern as
/api/mcp/tools/study endpoints).
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.import_session import ImportSession, ImportSessionStatus
from app.models.user import User, UserRole
from app.services.classroom_import_service import (
    create_session,
    parse_copypaste,
    parse_screenshots,
    preview_session,
    commit_session,
    _check_duplicates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp/tools/import", tags=["mcp-import-tools"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ParseTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Pasted school portal text to parse")
    source_hint: str = Field(
        "unknown",
        max_length=255,
        description="Hint about the source (e.g. 'Google Classroom', 'TeachAssist')",
    )
    student_id: Optional[int] = Field(
        None,
        description="Optional student ID to associate the import with",
    )


class ParseImageRequest(BaseModel):
    images: list[str] = Field(
        ...,
        min_length=1,
        description="List of base64-encoded screenshot images",
    )
    source_hint: str = Field(
        "unknown",
        max_length=255,
        description="Hint about the source (e.g. 'report card photo', 'schedule screenshot')",
    )
    student_id: Optional[int] = Field(
        None,
        description="Optional student ID to associate the import with",
    )


class ParsedItemResponse(BaseModel):
    type: str
    title: str
    course_name: Optional[str] = None
    due_date: Optional[str] = None
    grade: Optional[str] = None
    description: Optional[str] = None
    duplicate: bool = False


class ImportSessionSummary(BaseModel):
    id: int
    source_type: str
    source_hint: Optional[str] = None
    status: str
    items_parsed: int
    items_committed: int
    duplicates_skipped: int
    created_at: Optional[datetime] = None
    committed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImportSessionDetail(ImportSessionSummary):
    student_id: Optional[int] = None
    items: list[ParsedItemResponse] = []


class ImportPreviewResponse(BaseModel):
    session_id: int
    status: str
    source_type: str
    source_hint: Optional[str] = None
    items_parsed: int
    items: list[ParsedItemResponse]
    created_at: Optional[str] = None


class CommitResponse(BaseModel):
    session_id: int
    status: str
    items_committed: int = 0
    duplicates_skipped: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: verify session ownership
# ---------------------------------------------------------------------------


def _get_session_or_404(
    session_id: int,
    db: Session,
    current_user: User,
) -> ImportSession:
    """Retrieve an ImportSession by ID, enforcing ownership / RBAC."""
    session = db.query(ImportSession).filter(ImportSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import session not found",
        )
    # Only the owning user or an admin can access the session
    if session.user_id != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: not your import session",
        )
    return session


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/from-text",
    response_model=ImportPreviewResponse,
    operation_id="mcp_import_from_text",
)
def import_from_text(
    req: ParseTextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse pasted school portal text and create an import session.

    The MCP client (e.g. Claude Desktop) sends text that was copied from a
    school portal.  The service parses it into structured items (assignments,
    grades, etc.), checks for duplicates, and returns a preview so the user
    can review before committing.
    """
    logger.info(
        "MCP import from text: user=%s, source=%s, len=%d",
        current_user.id,
        req.source_hint,
        len(req.text),
    )

    # Parse the text
    try:
        items = parse_copypaste(req.text)
    except Exception as exc:
        logger.error("Failed to parse text: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse text: {exc}",
        )

    # Check for duplicates
    items = _check_duplicates(db, items, current_user.id, req.student_id)

    # Create session
    session = create_session(
        db=db,
        user_id=current_user.id,
        source_type="copypaste",
        source_hint=req.source_hint,
        student_id=req.student_id,
    )

    # Store parsed data
    session.parsed_data = json.dumps(items)
    session.raw_input = req.text
    session.items_parsed = len(items)
    session.status = ImportSessionStatus.PREVIEWING
    db.commit()
    db.refresh(session)

    return ImportPreviewResponse(
        session_id=session.id,
        status=session.status.value,
        source_type=session.source_type,
        source_hint=session.source_hint,
        items_parsed=session.items_parsed,
        items=[ParsedItemResponse(**item) for item in items],
        created_at=session.created_at.isoformat() if session.created_at else None,
    )


@router.post(
    "/from-image",
    response_model=ImportPreviewResponse,
    operation_id="mcp_import_from_image",
)
def import_from_image(
    req: ParseImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse screenshot images and create an import session.

    The MCP client sends base64-encoded images of school portal screens.
    The service decodes them, runs OCR/parsing, checks for duplicates, and
    returns a preview.
    """
    logger.info(
        "MCP import from image: user=%s, source=%s, images=%d",
        current_user.id,
        req.source_hint,
        len(req.images),
    )

    # Decode images from base64
    decoded_images: list[bytes] = []
    for i, img_b64 in enumerate(req.images):
        try:
            decoded_images.append(base64.b64decode(img_b64))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 in image at index {i}: {exc}",
            )

    # Parse the images
    try:
        items = parse_screenshots(decoded_images)
    except Exception as exc:
        logger.error("Failed to parse screenshots: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse screenshots: {exc}",
        )

    # Check for duplicates
    items = _check_duplicates(db, items, current_user.id, req.student_id)

    # Create session
    session = create_session(
        db=db,
        user_id=current_user.id,
        source_type="screenshot",
        source_hint=req.source_hint,
        student_id=req.student_id,
    )

    # Store parsed data (images are not stored in raw_input for size reasons)
    session.parsed_data = json.dumps(items)
    session.raw_input = json.dumps({
        "image_count": len(decoded_images),
        "total_bytes": sum(len(img) for img in decoded_images),
    })
    session.items_parsed = len(items)
    session.status = ImportSessionStatus.PREVIEWING
    db.commit()
    db.refresh(session)

    return ImportPreviewResponse(
        session_id=session.id,
        status=session.status.value,
        source_type=session.source_type,
        source_hint=session.source_hint,
        items_parsed=session.items_parsed,
        items=[ParsedItemResponse(**{k: v for k, v in item.items() if k != "image_size_bytes"}) for item in items],
        created_at=session.created_at.isoformat() if session.created_at else None,
    )


@router.get(
    "/sessions",
    response_model=list[ImportSessionSummary],
    operation_id="mcp_list_import_sessions",
)
def list_import_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's recent import sessions (most recent 20)."""
    sessions = (
        db.query(ImportSession)
        .filter(ImportSession.user_id == current_user.id)
        .order_by(ImportSession.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        ImportSessionSummary(
            id=s.id,
            source_type=s.source_type,
            source_hint=s.source_hint,
            status=s.status.value if hasattr(s.status, "value") else s.status,
            items_parsed=s.items_parsed,
            items_committed=s.items_committed,
            duplicates_skipped=s.duplicates_skipped,
            created_at=s.created_at,
            committed_at=s.committed_at,
        )
        for s in sessions
    ]


@router.get(
    "/sessions/{session_id}",
    response_model=ImportSessionDetail,
    operation_id="mcp_get_import_session",
)
def get_import_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full detail of an import session including all parsed items."""
    session = _get_session_or_404(session_id, db, current_user)
    parsed = json.loads(session.parsed_data) if session.parsed_data else []

    return ImportSessionDetail(
        id=session.id,
        source_type=session.source_type,
        source_hint=session.source_hint,
        status=session.status.value if hasattr(session.status, "value") else session.status,
        items_parsed=session.items_parsed,
        items_committed=session.items_committed,
        duplicates_skipped=session.duplicates_skipped,
        created_at=session.created_at,
        committed_at=session.committed_at,
        student_id=session.student_id,
        items=[
            ParsedItemResponse(**{k: v for k, v in item.items() if k in ParsedItemResponse.model_fields})
            for item in parsed
        ],
    )


@router.post(
    "/sessions/{session_id}/commit",
    response_model=CommitResponse,
    operation_id="mcp_commit_import_session",
)
def commit_import_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a reviewed import session, creating real database records.

    Only sessions in 'previewing' or 'pending' status can be committed.
    Already-committed sessions return their existing result.
    """
    session = _get_session_or_404(session_id, db, current_user)

    if session.status not in (
        ImportSessionStatus.PENDING,
        ImportSessionStatus.PREVIEWING,
        ImportSessionStatus.COMMITTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot commit session with status '{session.status.value}'",
        )

    try:
        result = commit_session(db, session)
    except Exception as exc:
        logger.error("Failed to commit import session %d: %s", session_id, exc)
        session.status = ImportSessionStatus.FAILED
        session.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit import: {exc}",
        )

    return CommitResponse(**result)
