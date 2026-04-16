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
    ASGFQuizResponse,
    ASGFQuizQuestion,
    ASGFSlideRequest,
    ASGFSlideResponse,
    ChildItem,
    ComprehensionSignalRequest,
    ComprehensionSignalResponse,
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

    # --- Persist session to learning_history (#3436) ---
    from app.models.learning_history import LearningHistory

    # Resolve student_id (required FK)
    student_id: int | None = None
    if body.child_id and role == "parent":
        student_id = int(body.child_id)
    elif role == "student":
        student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student_row:
            student_id = student_row.id
    elif role == "parent" and not body.child_id:
        # Use the first linked child if none specified
        first_child = (
            db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .first()
        )
        if first_child:
            student_id = first_child[0]

    if student_id:
        history_row = LearningHistory(
            student_id=student_id,
            session_id=session_id,
            session_type="asgf",
            question_asked=body.question,
            subject=context_package.subject or plan.topic_classification.get("subject", ""),
            grade_level=context_package.grade_level or plan.topic_classification.get("grade_level", ""),
            topic_tags=[plan.topic_classification.get("subject", "")],
            slides_generated=plan.model_dump(),
            documents_uploaded=context_package.model_dump(),
        )
        try:
            db.add(history_row)
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("ASGF session: failed to persist session %s to learning_history", session_id)
    else:
        logger.warning("ASGF session: no student_id resolved, skipping persistence for session %s", session_id)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream 7-slide mini-lesson content via SSE.

    Accepts a session_id (from POST /asgf/session) and looks up the
    persisted plan and context_package from learning_history.

    Event types:
      - ``event: start``  -- session metadata
      - ``event: slide``  -- individual slide JSON
      - ``event: done``   -- generation complete
      - ``event: error``  -- generation error
    """
    from app.models.learning_history import LearningHistory

    # Look up session from learning_history (#3435)
    session_id = body.session_id
    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    # Auth check: verify session belongs to current user
    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    owner_user_ids: list[int] = []
    if role == "student":
        student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student_row:
            owner_user_ids.append(student_row.id)
    elif role == "parent":
        child_ids = [
            sid
            for (sid,) in db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        owner_user_ids.extend(child_ids)

    if history_row.student_id not in owner_user_ids:
        raise HTTPException(status_code=404, detail="Session not found")

    learning_cycle_plan = history_row.slides_generated or {}
    context_package = history_row.documents_uploaded or {}

    async def event_stream():
        yield (
            f"event: start\n"
            f"data: {json.dumps({'session_id': session_id, 'total_slides': 7})}\n\n"
        )

        slide_service = ASGFSlideService()
        slide_count = 0

        try:
            async for slide in slide_service.generate_slides(
                learning_cycle_plan=learning_cycle_plan,
                context_package=context_package,
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

    # --- "still_confused" -> generate re-explanation ---
    logger.info(
        "ASGF signal: user=%d session=%s slide=%d signal=still_confused -- generating re-explanation",
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


# --- POST /asgf/session/{session_id}/quiz (#3400) ------------------------

@router.post(
    "/session/{session_id}/quiz",
    response_model=ASGFQuizResponse,
)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_quiz(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate slide-anchored quiz questions for a completed ASGF session.

    Retrieves the session's slides and learning cycle plan from
    learning_history and uses GPT-4o-mini to produce 3-5 MCQ questions.
    """
    from app.models.learning_history import LearningHistory
    from app.services.asgf_quiz_service import generate_asgf_quiz

    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    # Auth check: verify session belongs to current user
    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    owner_student_ids: list[int] = []
    if role == "student":
        student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student_row:
            owner_student_ids.append(student_row.id)
    elif role == "parent":
        child_ids = [
            sid
            for (sid,) in db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        owner_student_ids.extend(child_ids)

    if history_row.student_id not in owner_student_ids:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract slides from session data
    # slides_generated stores the plan initially, then slide events are appended
    raw_data = history_row.slides_generated or {}
    slides: list[dict] = []

    if isinstance(raw_data, list):
        # If it's a list, filter for actual slide entries (have title/body)
        slides = [
            entry for entry in raw_data
            if isinstance(entry, dict) and "title" in entry and ("body" in entry or "content" in entry)
        ]
    elif isinstance(raw_data, dict):
        # Plan dict — extract slide_plan items as lightweight slides
        slide_plan = raw_data.get("slide_plan", [])
        for i, sp in enumerate(slide_plan):
            if isinstance(sp, dict):
                slides.append({
                    "slide_number": i,
                    "title": sp.get("title", f"Slide {i + 1}"),
                    "body": sp.get("brief", ""),
                    "bloom_tier": sp.get("bloom_tier", ""),
                })

    if not slides:
        raise HTTPException(
            status_code=400,
            detail="No slide content found for this session. Complete the slide lesson first.",
        )

    learning_cycle_plan = {}
    if isinstance(raw_data, dict):
        learning_cycle_plan = raw_data
    context_package = history_row.documents_uploaded or {}

    questions = await generate_asgf_quiz(
        slides=slides,
        learning_cycle_plan=learning_cycle_plan,
        context_package=context_package,
    )

    if not questions:
        raise HTTPException(
            status_code=500,
            detail="Quiz generation failed. Please try again.",
        )

    logger.info(
        "ASGF quiz: user=%d session=%s questions=%d",
        current_user.id,
        session_id,
        len(questions),
    )

    return ASGFQuizResponse(
        session_id=session_id,
        questions=[ASGFQuizQuestion(**q) for q in questions],
    )
