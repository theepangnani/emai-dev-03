"""Classroom Data Import API routes (#57).

Supports multiple import pathways:
  - Copy/paste text from classroom portals
  - Screenshot OCR extraction
  - Email forwarding (SendGrid inbound webhook)
  - ICS calendar file upload
  - CSV template-based import

All pathways create an ImportSession that goes through:
  upload -> parse -> duplicate check -> ready_for_review -> commit

Routes:
  POST   /api/import/copypaste                  - paste text from classroom portal
  POST   /api/import/screenshot                 - upload screenshots for OCR
  POST   /api/import/email-forward              - SendGrid inbound parse webhook
  POST   /api/import/ics                        - upload .ics calendar file
  POST   /api/import/csv                        - upload CSV via template
  GET    /api/import/templates/csv              - download CSV template
  GET    /api/import/sessions                   - list user's import sessions
  GET    /api/import/sessions/{session_id}      - get session detail
  PATCH  /api/import/sessions/{session_id}      - update reviewed data
  POST   /api/import/sessions/{session_id}/commit - commit session to DB
  DELETE /api/import/sessions/{session_id}      - delete session
"""

import base64
import json
import logging
from datetime import date
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.import_session import ImportSession
from app.models.user import User
from app.schemas.classroom_import import (
    CopyPasteImportRequest,
    ImportCommitResponse,
    ImportSessionCreateResponse,
    ImportSessionListResponse,
    ImportSessionResponse,
    ImportSessionUpdate,
)
from app.services.classroom_import_service import (
    _check_duplicates,
    commit_session,
    create_session,
    parse_copypaste,
    parse_screenshots,
    preview_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["classroom-import"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_SCREENSHOT_FILES = 10
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_session_ownership(session: ImportSession | None, user: User) -> ImportSession:
    """Raise 404 if session not found, 403 if user does not own it."""
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import session not found.",
        )
    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this import session.",
        )
    return session


def _validate_file_extension(filename: str | None, allowed: set[str], label: str = "File") -> str:
    """Return the lowercase extension or raise 400."""
    if not filename or "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must have a valid file extension.",
        )
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} type '{ext}' not allowed. Supported: {', '.join(sorted(allowed))}",
        )
    return ext


# ---------------------------------------------------------------------------
# 1. Copy/Paste Import
# ---------------------------------------------------------------------------

@router.post("/copypaste", response_model=ImportSessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def import_copypaste(
    body: CopyPasteImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import classroom data by pasting text copied from a classroom portal."""
    try:
        if not body.text or not body.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text content is required and cannot be empty.",
            )

        # Create the import session
        session = create_session(
            db=db,
            user_id=current_user.id,
            student_id=body.student_id,
            source_type="copypaste",
            raw_data=body.text,
        )

        # Parse the pasted text
        parsed_data = parse_copypaste(
            text=body.text,
            source_hint=body.source_hint or "auto",
            today=str(date.today()),
        )

        # Check for duplicates against existing data
        duplicates = _check_duplicates(db, current_user.id, body.student_id, parsed_data)

        # Update session with parsed results
        session.parsed_data = json.dumps(parsed_data) if isinstance(parsed_data, (dict, list)) else parsed_data
        session.duplicate_info = json.dumps(duplicates) if duplicates else None
        session.status = "ready_for_review"
        db.commit()
        db.refresh(session)

        logger.info(
            f"Copy/paste import session created | session_id={session.id} "
            f"| user={current_user.id} | student={body.student_id}"
        )

        return ImportSessionCreateResponse(
            session_id=session.id,
            status=session.status,
            item_count=len(parsed_data.get("items", [])) if isinstance(parsed_data, dict) else 0,
            duplicate_count=len(duplicates) if duplicates else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Copy/paste import failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process pasted text. Please try again.",
        )


# ---------------------------------------------------------------------------
# 2. Screenshot Import
# ---------------------------------------------------------------------------

@router.post("/screenshot", response_model=ImportSessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def import_screenshot(
    files: list[UploadFile] = File(...),
    student_id: int = Form(...),
    source_hint: str = Form("auto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import classroom data from screenshot images using OCR/AI extraction."""
    try:
        # Validate file count
        if len(files) > MAX_SCREENSHOT_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {MAX_SCREENSHOT_FILES} files allowed. Got {len(files)}.",
            )
        if len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one screenshot file is required.",
            )

        image_bytes_list: list[bytes] = []

        for f in files:
            # Validate file type
            _validate_file_extension(f.filename, ALLOWED_IMAGE_EXTENSIONS, label="Image")

            if f.content_type and f.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content type '{f.content_type}' not allowed. Upload PNG, JPG, WEBP, or GIF images.",
                )

            # Read and validate size
            file_bytes = await f.read()
            if len(file_bytes) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{f.filename}' is empty.",
                )
            if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"File '{f.filename}' is too large "
                        f"({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB."
                    ),
                )
            image_bytes_list.append(file_bytes)

        # Create the import session
        session = create_session(
            db=db,
            user_id=current_user.id,
            student_id=student_id,
            source_type="screenshot",
            raw_data=None,
        )

        # Parse screenshots via OCR/AI
        parsed_data = parse_screenshots(
            image_bytes_list=image_bytes_list,
            source_hint=source_hint,
            today=str(date.today()),
        )

        # Check for duplicates
        duplicates = _check_duplicates(db, current_user.id, student_id, parsed_data)

        # Update session
        session.parsed_data = json.dumps(parsed_data) if isinstance(parsed_data, (dict, list)) else parsed_data
        session.duplicate_info = json.dumps(duplicates) if duplicates else None
        session.status = "ready_for_review"
        db.commit()
        db.refresh(session)

        logger.info(
            f"Screenshot import session created | session_id={session.id} "
            f"| user={current_user.id} | student={student_id} | files={len(files)}"
        )

        return ImportSessionCreateResponse(
            session_id=session.id,
            status=session.status,
            item_count=len(parsed_data.get("items", [])) if isinstance(parsed_data, dict) else 0,
            duplicate_count=len(duplicates) if duplicates else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screenshot import failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process screenshots. Please try again.",
        )


# ---------------------------------------------------------------------------
# 3. Email Forward Import (SendGrid Inbound Parse Webhook)
# ---------------------------------------------------------------------------

@router.post("/email-forward", status_code=status.HTTP_200_OK)
async def import_email_forward(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive forwarded classroom emails via SendGrid inbound parse webhook.

    This endpoint does NOT require JWT auth — it is called by SendGrid's
    inbound parse webhook. Authentication is handled via webhook signature
    verification in production.
    """
    try:
        # Parse the multipart form data from SendGrid
        form_data = await request.form()

        sender = form_data.get("from", "")
        to_address = form_data.get("to", "")
        subject = form_data.get("subject", "")
        text_body = form_data.get("text", "")
        html_body = form_data.get("html", "")
        envelope_raw = form_data.get("envelope", "{}")

        # Import the email parser
        from app.services.classroom_email_parser import parse_classroom_email

        parsed_data = parse_classroom_email(
            sender=str(sender),
            to_address=str(to_address),
            subject=str(subject),
            text_body=str(text_body),
            html_body=str(html_body),
        )

        # Try to identify the user from the sender email
        from app.models.user import User as UserModel
        user = db.query(UserModel).filter(UserModel.email == str(sender)).first()

        if user:
            session = create_session(
                db=db,
                user_id=user.id,
                student_id=parsed_data.get("student_id"),
                source_type="email",
                raw_data=json.dumps({
                    "from": str(sender),
                    "to": str(to_address),
                    "subject": str(subject),
                    "text": str(text_body)[:5000],  # Truncate for storage
                }),
            )
            session.parsed_data = json.dumps(parsed_data) if isinstance(parsed_data, (dict, list)) else parsed_data
            session.status = "ready_for_review"
            db.commit()
            db.refresh(session)

            logger.info(
                f"Email import session created | session_id={session.id} "
                f"| user={user.id} | from={sender}"
            )
        else:
            logger.warning(f"Email import received from unknown sender: {sender}")

        # Always return 200 to acknowledge the webhook
        return {"status": "ok", "message": "Email received and processed."}

    except Exception as e:
        logger.error(f"Email forward import failed: {e}", exc_info=True)
        # Still return 200 so SendGrid doesn't retry endlessly
        return {"status": "error", "message": "Email received but processing failed."}


# ---------------------------------------------------------------------------
# 4. ICS Calendar Import
# ---------------------------------------------------------------------------

@router.post("/ics", response_model=ImportSessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def import_ics(
    file: UploadFile = File(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import classroom data from an .ics calendar file."""
    try:
        # Validate file extension
        _validate_file_extension(file.filename, {".ics"}, label="Calendar file")

        # Read file content
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded ICS file is empty.",
            )
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB.",
            )

        file_content = file_bytes.decode("utf-8", errors="replace")

        # Create the import session
        session = create_session(
            db=db,
            user_id=current_user.id,
            student_id=student_id,
            source_type="ics",
            raw_data=file_content,
        )

        # Parse the ICS file
        from app.services.ics_parser import parse_ics_file

        parsed_data = parse_ics_file(file_content)

        # Check for duplicates
        duplicates = _check_duplicates(db, current_user.id, student_id, parsed_data)

        # Update session
        session.parsed_data = json.dumps(parsed_data) if isinstance(parsed_data, (dict, list)) else parsed_data
        session.duplicate_info = json.dumps(duplicates) if duplicates else None
        session.status = "ready_for_review"
        db.commit()
        db.refresh(session)

        logger.info(
            f"ICS import session created | session_id={session.id} "
            f"| user={current_user.id} | student={student_id} | file={file.filename}"
        )

        return ImportSessionCreateResponse(
            session_id=session.id,
            status=session.status,
            item_count=len(parsed_data.get("items", [])) if isinstance(parsed_data, dict) else 0,
            duplicate_count=len(duplicates) if duplicates else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ICS import failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process ICS file. Please ensure it is a valid iCalendar file.",
        )


# ---------------------------------------------------------------------------
# 5. CSV Template Import
# ---------------------------------------------------------------------------

@router.post("/csv", response_model=ImportSessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def import_csv(
    file: UploadFile = File(...),
    student_id: int = Form(...),
    template_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import classroom data from a CSV file using a predefined template."""
    try:
        # Validate template type
        valid_template_types = {"assignments", "materials", "grades"}
        if template_type not in valid_template_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid template_type '{template_type}'. Must be one of: {', '.join(sorted(valid_template_types))}",
            )

        # Validate file extension
        _validate_file_extension(file.filename, {".csv"}, label="CSV file")

        # Read file content
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded CSV file is empty.",
            )
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB.",
            )

        file_content = file_bytes.decode("utf-8", errors="replace")

        # Create the import session
        session = create_session(
            db=db,
            user_id=current_user.id,
            student_id=student_id,
            source_type="csv",
            raw_data=file_content,
        )

        # Parse the CSV file
        from app.services.csv_import_parser import parse_csv_import

        parsed_data = parse_csv_import(file_content, template_type)

        # Check for duplicates
        duplicates = _check_duplicates(db, current_user.id, student_id, parsed_data)

        # Update session
        session.parsed_data = json.dumps(parsed_data) if isinstance(parsed_data, (dict, list)) else parsed_data
        session.duplicate_info = json.dumps(duplicates) if duplicates else None
        session.status = "ready_for_review"
        db.commit()
        db.refresh(session)

        logger.info(
            f"CSV import session created | session_id={session.id} "
            f"| user={current_user.id} | student={student_id} "
            f"| template={template_type} | file={file.filename}"
        )

        return ImportSessionCreateResponse(
            session_id=session.id,
            status=session.status,
            item_count=len(parsed_data.get("items", [])) if isinstance(parsed_data, dict) else 0,
            duplicate_count=len(duplicates) if duplicates else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process CSV file. Please ensure it matches the template format.",
        )


# ---------------------------------------------------------------------------
# 6. CSV Template Download
# ---------------------------------------------------------------------------

@router.get("/templates/csv")
def download_csv_template(
    type: str = Query(..., description="Template type: assignments, materials, or grades"),
    current_user: User = Depends(get_current_user),
):
    """Download a CSV template for bulk importing classroom data."""
    valid_types = {"assignments", "materials", "grades"}
    if type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template type '{type}'. Must be one of: {', '.join(sorted(valid_types))}",
        )

    try:
        from app.services.csv_import_parser import get_csv_template

        csv_content = get_csv_template(type)

        import io
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="classbridge_import_{type}_template.csv"',
            },
        )
    except Exception as e:
        logger.error(f"CSV template download failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate CSV template.",
        )


# ---------------------------------------------------------------------------
# 7. List Import Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[ImportSessionListResponse])
def list_import_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all import sessions for the current user, newest first."""
    try:
        sessions = (
            db.query(ImportSession)
            .filter(ImportSession.user_id == current_user.id)
            .order_by(ImportSession.created_at.desc())
            .all()
        )
        return [
            ImportSessionListResponse(
                id=s.id,
                source_type=s.source_type,
                status=s.status,
                student_id=s.student_id,
                item_count=_count_items(s.parsed_data),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"Failed to list import sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve import sessions.",
        )


# ---------------------------------------------------------------------------
# 8. Get Import Session Detail
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_model=ImportSessionResponse)
def get_import_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed view of a single import session including parsed data."""
    try:
        session = db.query(ImportSession).filter(ImportSession.id == session_id).first()
        _assert_session_ownership(session, current_user)
        return _session_to_response(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get import session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve import session.",
        )


# ---------------------------------------------------------------------------
# 9. Update Import Session (Review Edits)
# ---------------------------------------------------------------------------

@router.patch("/sessions/{session_id}", response_model=ImportSessionResponse)
def update_import_session(
    session_id: int,
    body: ImportSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the reviewed data for an import session before committing."""
    try:
        session = db.query(ImportSession).filter(ImportSession.id == session_id).first()
        _assert_session_ownership(session, current_user)

        if session.status not in ("ready_for_review", "pending"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update session in '{session.status}' status. Must be 'ready_for_review' or 'pending'.",
            )

        # Update reviewed data
        if body.reviewed_data is not None:
            session.reviewed_data = (
                json.dumps(body.reviewed_data)
                if isinstance(body.reviewed_data, (dict, list))
                else body.reviewed_data
            )

        db.commit()
        db.refresh(session)

        logger.info(f"Import session updated | session_id={session.id} | user={current_user.id}")

        return _session_to_response(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update import session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update import session.",
        )


# ---------------------------------------------------------------------------
# 10. Commit Import Session
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/commit", response_model=ImportCommitResponse)
def commit_import_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a reviewed import session, writing parsed data into the database."""
    try:
        session = db.query(ImportSession).filter(ImportSession.id == session_id).first()
        _assert_session_ownership(session, current_user)

        if session.status != "ready_for_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot commit session in '{session.status}' status. Must be 'ready_for_review'.",
            )

        result = commit_session(db=db, session_id=session_id, user_id=current_user.id)

        logger.info(
            f"Import session committed | session_id={session_id} "
            f"| user={current_user.id} | result={result}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to commit import session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to commit import session. Please try again.",
        )


# ---------------------------------------------------------------------------
# 11. Delete Import Session
# ---------------------------------------------------------------------------

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_import_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an import session. Only the owning user can delete."""
    try:
        session = db.query(ImportSession).filter(ImportSession.id == session_id).first()
        _assert_session_ownership(session, current_user)

        db.delete(session)
        db.commit()

        logger.info(f"Import session deleted | session_id={session_id} | user={current_user.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete import session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete import session.",
        )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _count_items(parsed_data_str: str | None) -> int:
    """Safely count parsed items from JSON string."""
    if not parsed_data_str:
        return 0
    try:
        data = json.loads(parsed_data_str) if isinstance(parsed_data_str, str) else parsed_data_str
        if isinstance(data, dict):
            return len(data.get("items", []))
        if isinstance(data, list):
            return len(data)
        return 0
    except (json.JSONDecodeError, TypeError):
        return 0


def _session_to_response(session: ImportSession) -> ImportSessionResponse:
    """Convert an ImportSession ORM object to the response schema."""
    parsed = None
    if session.parsed_data:
        try:
            parsed = json.loads(session.parsed_data) if isinstance(session.parsed_data, str) else session.parsed_data
        except (json.JSONDecodeError, TypeError):
            parsed = None

    reviewed = None
    if session.reviewed_data:
        try:
            reviewed = json.loads(session.reviewed_data) if isinstance(session.reviewed_data, str) else session.reviewed_data
        except (json.JSONDecodeError, TypeError):
            reviewed = None

    duplicate_info = None
    if hasattr(session, "duplicate_info") and session.duplicate_info:
        try:
            duplicate_info = json.loads(session.duplicate_info) if isinstance(session.duplicate_info, str) else session.duplicate_info
        except (json.JSONDecodeError, TypeError):
            duplicate_info = None

    return ImportSessionResponse(
        id=session.id,
        user_id=session.user_id,
        student_id=session.student_id,
        source_type=session.source_type,
        status=session.status,
        parsed_data=parsed,
        reviewed_data=reviewed,
        duplicate_info=duplicate_info,
        item_count=_count_items(session.parsed_data),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
