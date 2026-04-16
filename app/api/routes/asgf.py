"""ASGF (AI Study Guide Factory) API routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
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
    ASGFSlideRequest,
    ASGFSlideResponse,
    ChildItem,
    CourseItem,
    CreateSessionRequest,
    CreateSessionResponse,
    FileUploadResponse,
    IntentClassifyRequest,
    IntentClassifyResponse,
    MultiFileUploadResponse,
    TaskItem,
)
from app.services import asgf_service
from app.services.asgf_ingestion_service import ASGFIngestionService
from app.services.asgf_slide_service import ASGFSlideService
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


# --- POST /asgf/session -----------------------------------------------------

@router.post("/session", response_model=CreateSessionResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def create_asgf_session(
    request: Request,
    body: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new ASGF session: assemble context and generate a learning cycle plan.

    Accepts a question and optional context fields (child_id, subject, grade, course_id).
    Runs context assembly + plan generation and returns a session preview.
    """
    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    # Build student profile from child_id if provided
    student_profile: dict = {}
    if body.child_id and role == "parent":
        student = (
            db.query(Student)
            .options(selectinload(Student.user))
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == current_user.id,
                Student.id == int(body.child_id),
            )
            .first()
        )
        if student:
            student_profile = {
                "grade": str(student.grade_level) if student.grade_level else "",
                "school": student.school_name or "",
            }
    elif role == "student":
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            student_profile = {
                "grade": str(student.grade_level) if student.grade_level else "",
                "school": student.school_name or "",
            }

    if body.grade:
        student_profile["grade"] = body.grade

    # Build classroom context from course_id if provided
    classroom_context: dict = {}
    if body.course_id:
        course = db.query(Course).filter(Course.id == int(body.course_id)).first()
        if course:
            classroom_context = {
                "course_name": course.name,
                "teacher": course.teacher_name or "",
            }

    if body.subject:
        classroom_context["subject"] = body.subject

    # Session metadata
    session_metadata: dict = {
        "role": role,
        "user_id": current_user.id,
    }

    # For now, ingestion result is empty (files not linked to sessions yet).
    # Future milestones will wire uploaded file_ids to the ingestion pipeline.
    ingestion_result: dict = {
        "concepts": [],
        "gap_data": {"weak_topics": [], "previously_studied": []},
        "document_metadata": [],
    }

    # Assemble context
    context_package = await asgf_service.assemble_context_package(
        question=body.question,
        ingestion_result=ingestion_result,
        student_profile=student_profile,
        classroom_context=classroom_context,
        session_metadata=session_metadata,
    )

    # Generate plan
    plan = await asgf_service.generate_learning_cycle_plan(context_package)

    session_id = uuid4().hex

    logger.info(
        "ASGF session created: session_id=%s, user=%d, topic=%s",
        session_id,
        current_user.id,
        plan.topic_classification.get("subject", "unknown"),
    )

    return CreateSessionResponse(
        session_id=session_id,
        topic=context_package.topic or plan.topic_classification.get("subject", ""),
        subject=context_package.subject or plan.topic_classification.get("subject", ""),
        grade_level=context_package.grade_level or plan.topic_classification.get("grade_level", ""),
        slide_count=len(plan.slide_plan),
        quiz_count=len(plan.quiz_plan),
        estimated_time_min=plan.estimated_session_time_min,
    )


# --- POST /asgf/generate-slides (SSE stream) --------------------------------

@router.post("/generate-slides")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def generate_slides_stream(
    request: Request,
    body: ASGFSlideRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream 7-slide mini-lesson content via SSE.

    Accepts a learning_cycle_plan and context_package (output of the
    ingestion pipeline) and streams one slide at a time as SSE events.

    Event types:
      - ``event: start``  -- session metadata
      - ``event: slide``  -- individual slide JSON
      - ``event: done``   -- generation complete
      - ``event: error``  -- generation error
    """
    session_id = uuid4().hex

    async def event_stream():
        yield (
            f"event: start\n"
            f"data: {json.dumps({'session_id': session_id, 'total_slides': 7})}\n\n"
        )

        slide_service = ASGFSlideService()
        slide_count = 0

        try:
            async for slide in slide_service.generate_slides(
                learning_cycle_plan=body.learning_cycle_plan,
                context_package=body.context_package,
            ):
                slide_count += 1
                yield f"event: slide\ndata: {json.dumps(slide)}\n\n"

            yield (
                f"event: done\n"
                f"data: {json.dumps({'session_id': session_id, 'slides_generated': slide_count})}\n\n"
            )

        except Exception as e:
            logger.error("ASGF slide stream error: %s", e)
            yield (
                f"event: error\n"
                f"data: {json.dumps({'message': 'Slide generation failed. Please try again.'})}\n\n"
            )

    logger.info(
        "ASGF generate-slides: user=%d, session=%s",
        current_user.id,
        session_id,
    )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
