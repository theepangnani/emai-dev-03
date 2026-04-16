"""ASGF (AI Study Guide Factory) API routes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.task import Task
from app.models.user import User, UserRole
from app.schemas.asgf import (
    ASGFContextDataResponse,
    ChildItem,
    ComprehensionSignalRequest,
    ComprehensionSignalResponse,
    CourseItem,
    FileUploadResponse,
    IntentClassifyRequest,
    IntentClassifyResponse,
    MultiFileUploadResponse,
    TaskItem,
)
from app.services import asgf_service
from app.services.file_processor import FileProcessingError, process_file
from app.services.storage_service import save_file

logger = get_logger(__name__)

router = APIRouter(prefix="/asgf", tags=["ASGF"])

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


# --- POST /asgf/classify-intent ------------------------------------------

@router.post("/classify-intent", response_model=IntentClassifyResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def classify_intent(
    request: Request,
    body: IntentClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """Classify a question into subject, grade level, topic, and Bloom's tier."""
    return await asgf_service.classify_intent(body.question)


# --- POST /asgf/upload ----------------------------------------------------

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


# --- GET /asgf/context-data -----------------------------------------------

@router.get("/context-data", response_model=ASGFContextDataResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_context_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return children, courses, and upcoming tasks for the ASGF context panel."""
    children_out: list[ChildItem] = []
    courses_out: list[CourseItem] = []
    tasks_out: list[TaskItem] = []

    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    # --- Children (parent only) ---
    if role == "parent":
        rows = (
            db.query(Student)
            .options(selectinload(Student.user))
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        for s in rows:
            children_out.append(
                ChildItem(
                    id=str(s.id),
                    name=s.user.full_name if s.user else f"Student #{s.id}",
                    grade=str(s.grade_level) if s.grade_level is not None else "",
                    board=s.school_name or "",
                )
            )

    # --- Courses ---
    student_ids: list[int] = []
    if role == "parent":
        student_ids = [int(c.id) for c in children_out]
    elif role == "student":
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            student_ids = [student.id]

    if student_ids:
        course_rows = (
            db.query(Course)
            .join(student_courses, student_courses.c.course_id == Course.id)
            .filter(student_courses.c.student_id.in_(student_ids))
            .options(selectinload(Course.teacher))
            .distinct()
            .all()
        )
    elif role == "teacher":
        from app.models.teacher import Teacher

        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_rows = (
                db.query(Course)
                .filter(Course.teacher_id == teacher.id)
                .options(selectinload(Course.teacher))
                .all()
            )
        else:
            course_rows = []
    else:
        course_rows = []

    for c in course_rows:
        courses_out.append(
            CourseItem(
                id=str(c.id),
                name=c.name,
                teacher=c.teacher_name or "",
            )
        )

    # --- Upcoming tasks ---
    now = datetime.now(timezone.utc)
    task_user_ids = [current_user.id]
    if role == "parent" and children_out:
        child_user_rows = (
            db.query(Student.user_id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        task_user_ids.extend(uid for (uid,) in child_user_rows)

    upcoming = (
        db.query(Task)
        .filter(
            Task.assigned_to_user_id.in_(task_user_ids),
            Task.is_completed == False,  # noqa: E712
            Task.archived_at.is_(None),
            Task.due_date.isnot(None),
            Task.due_date >= now,
        )
        .order_by(Task.due_date.asc())
        .limit(20)
        .all()
    )

    for t in upcoming:
        due_str = ""
        if t.due_date:
            due_str = t.due_date.strftime("%Y-%m-%d") if hasattr(t.due_date, "strftime") else str(t.due_date)
        tasks_out.append(
            TaskItem(
                id=str(t.id),
                title=t.title,
                due_date=due_str,
            )
        )

    return ASGFContextDataResponse(
        children=children_out,
        courses=courses_out,
        upcoming_tasks=tasks_out,
    )


# --- POST /asgf/session/{session_id}/signal (#3399) ----------------------

@router.post(
    "/session/{session_id}/signal",
    response_model=ComprehensionSignalResponse,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def record_comprehension_signal(
    session_id: str,
    body: ComprehensionSignalRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a per-slide comprehension signal (got_it / still_confused).

    If the signal is ``still_confused``, an AI re-explanation slide is
    generated and returned.  The signal is stored in the session's
    learning history for future analytics.
    """
    from app.models.learning_history import LearningHistory

    # --- Persist the signal in learning_history (best-effort) ---
    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )

    if history_row:
        # Append signal to the JSON slides_generated list
        signals: list = history_row.slides_generated or []
        signals.append(
            {
                "slide_number": body.slide_number,
                "signal": body.signal,
            }
        )
        history_row.slides_generated = signals
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.warning(
                "ASGF signal: failed to persist signal for session %s",
                session_id,
            )

    # --- If "got_it", just acknowledge ---
    if body.signal == "got_it":
        logger.info(
            "ASGF signal: user=%d session=%s slide=%d signal=got_it",
            current_user.id,
            session_id,
            body.slide_number,
        )
        return ComprehensionSignalResponse(acknowledged=True)

    # --- "still_confused" → generate re-explanation ---
    logger.info(
        "ASGF signal: user=%d session=%s slide=%d signal=still_confused — generating re-explanation",
        current_user.id,
        session_id,
        body.slide_number,
    )

    # Retrieve the original slide content from the session history
    slide_content: dict = {}
    context_package: dict | None = None
    if history_row and history_row.slides_generated:
        # Look for actual slide data stored at this slide number
        for entry in history_row.slides_generated:
            if (
                isinstance(entry, dict)
                and entry.get("slide_number") == body.slide_number
                and "title" in entry
            ):
                slide_content = entry
                break

    # If we couldn't find the slide in history, use a placeholder
    if not slide_content:
        slide_content = {
            "title": f"Slide {body.slide_number + 1}",
            "content": "The content for this slide.",
        }

    if history_row and history_row.question_asked:
        context_package = {"question": history_row.question_asked}

    try:
        re_explanation = await asgf_service.generate_re_explanation(
            slide_content=slide_content,
            context_package=context_package,
        )
    except Exception:
        logger.exception("ASGF re-explanation generation error")
        re_explanation = None

    return ComprehensionSignalResponse(
        acknowledged=True,
        re_explanation_slide=re_explanation,
    )
