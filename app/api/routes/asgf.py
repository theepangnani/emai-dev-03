"""ASGF (AI Study Guide Factory) API routes."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_current_user_sse
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.task import Task
from app.models.user import User, UserRole
from app.schemas.asgf import (
    ActiveSessionItem,
    ActiveSessionsResponse,
    ASGFContextDataResponse,
    ASGFQuizResponse,
    ASGFQuizQuestion,
    ASGFSlideResponse,
    ASGFUsageResponse,
    AssignmentOptionsResponse,
    AssignmentOption,
    AssignRequest,
    AssignResponse,
    ChildItem,
    CompleteSessionRequest,
    CompleteSessionResponse,
    ComprehensionSignalRequest,
    ComprehensionSignalResponse,
    CourseSuggestion,
    CourseItem,
    CreateSessionRequest,
    CreateSessionResponse,
    FileUploadResponse,
    IntentClassifyRequest,
    IntentClassifyResponse,
    MultiFileUploadResponse,
    ResumeSessionResponse,
    ReviewTopicsResponse,
    ReviewTopicItem,
    TaskItem,
)
from app.services.asgf_cost_service import check_session_cap
from app.services import asgf_service
from app.services.asgf_assignment_service import (
    assign_material,
    detect_course,
    get_role_options,
    resolve_student_id,
)
from app.models.learning_history import LearningHistory
from app.services.asgf_ingestion_service import ASGFIngestionService
from app.services.asgf_slide_service import ASGFSlideService
from app.services.file_processor import FileProcessingError, process_file
from app.services.storage_service import save_file

logger = get_logger(__name__)

router = APIRouter(prefix="/asgf", tags=["ASGF"])


def _get_user_role(user: User) -> str:
    """Normalize user role to a plain string value."""
    role = user.role
    return role.value if hasattr(role, "value") else role

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
    """Classify a question into subject, grade level, topic, and Bloom's tier.

    When confidence < 0.5, the response includes ``alternatives`` — a list of
    possible subject/topic interpretations so the frontend can offer
    disambiguation chips.
    """
    result = await asgf_service.classify_intent(body.question)
    if result.confidence < 0.5 and result.subject:
        result.alternatives = await asgf_service.get_intent_alternatives(body.question)
    return result


# --- GET /asgf/usage (#3405) -----------------------------------------------

@router.get("/usage", response_model=ASGFUsageResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_asgf_usage(
    request: Request,
    child_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return remaining ASGF sessions this month for the current user's child."""
    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    student_id: int | None = None
    if child_id and role == "parent":
        # Verify the child belongs to this parent
        valid = (
            db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == current_user.id,
                Student.id == child_id,
            )
            .first()
        )
        if valid:
            student_id = valid[0]
    elif role == "student":
        student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student_row:
            student_id = student_row.id
    elif role == "parent" and not child_id:
        first_child = (
            db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .first()
        )
        if first_child:
            student_id = first_child[0]

    if not student_id:
        raise HTTPException(status_code=404, detail="No linked student found.")

    cap_info = check_session_cap(student_id, db)
    return ASGFUsageResponse(**cap_info)


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
        filename = os.path.basename(upload_file.filename or "unknown")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Persist to uploads dir (reuse existing storage service)
        stored_name = await asyncio.to_thread(save_file, content, filename)
        # NOTE: file_id is returned to the client but is NOT persisted to the
        # database or linked to any session record.  This is a known limitation
        # (#3481) — file-to-session linking will be added when the ingestion
        # pipeline is wired to sessions.
        file_id = uuid4().hex

        # Extract text preview (best-effort — partial success per file)
        text_preview = ""
        extraction_failed = False
        try:
            extracted = await asyncio.to_thread(process_file, content, filename)
            text_preview = (extracted[:TEXT_PREVIEW_LENGTH] + "...") if len(extracted) > TEXT_PREVIEW_LENGTH else extracted
        except FileProcessingError:
            text_preview = "(text extraction unavailable)"
            extraction_failed = True
        except Exception as exc:
            logger.warning("ASGF text extraction failed for %s: %s", filename, exc)
            text_preview = "(text extraction unavailable)"
            extraction_failed = True

        results.append(
            FileUploadResponse(
                file_id=file_id,
                filename=filename,
                file_type=ext,
                file_size_bytes=len(content),
                text_preview=text_preview,
                extraction_failed=extraction_failed,
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

    role = _get_user_role(current_user)

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
    role = _get_user_role(current_user)

    # --- Verify parent-child relationship (#3482) ---
    if body.child_id and role == "parent":
        verified_child = (
            db.query(Student)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == current_user.id,
                Student.id == int(body.child_id),
            )
            .first()
        )
        if not verified_child:
            raise HTTPException(
                status_code=404,
                detail="Child not found or not linked to your account",
            )

    # --- Session cap enforcement (#3405) ---
    cap_student_id: int | None = None
    if body.child_id and role == "parent":
        cap_student_id = int(body.child_id)
    elif role == "student":
        cap_student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if cap_student_row:
            cap_student_id = cap_student_row.id
    elif role == "parent" and not body.child_id:
        first_child = (
            db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .first()
        )
        if first_child:
            cap_student_id = first_child[0]

    if cap_student_id:
        cap_info = check_session_cap(cap_student_id, db)
        if not cap_info["can_start"]:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Monthly ASGF session limit reached ({cap_info['limit']} sessions). "
                    "Upgrade your plan for unlimited sessions."
                ),
            )

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

    # --- Resolve student_id early for adaptive context (#3403) ---
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

    if not student_id:
        raise HTTPException(
            status_code=400,
            detail="Could not determine student for this session. Please select a child or ensure your student profile is set up.",
        )

    # Fetch adaptive context for repeat sessions (#3403)
    adaptive_context: dict | None = None
    if student_id:
        from app.services.asgf_learning_history_service import get_adaptive_context
        adaptive_context = get_adaptive_context(
            student_id=student_id, topic=body.question, db=db,
        )

    # Assemble context
    context_package = await asgf_service.assemble_context_package(
        question=body.question,
        ingestion_result=ingestion_result,
        student_profile=student_profile,
        classroom_context=classroom_context,
        session_metadata=session_metadata,
        adaptive_context=adaptive_context,
    )

    # Generate plan
    plan = await asgf_service.generate_learning_cycle_plan(context_package)

    session_id = uuid4().hex

    # --- Persist session to learning_history (#3436) ---

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


# --- GET /asgf/generate-slides (SSE stream) --------------------------------

@router.get("/generate-slides")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def generate_slides_stream(
    request: Request,
    session_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_sse),
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

    # Look up session from learning_history (#3435)
    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    # Auth check: verify session belongs to current user
    _verify_session_ownership(history_row, current_user, db)

    learning_cycle_plan = history_row.slides_generated or {}
    context_package = history_row.documents_uploaded or {}

    async def event_stream():
        yield (
            f"event: start\n"
            f"data: {json.dumps({'session_id': session_id, 'total_slides': 7})}\n\n"
        )

        slide_service = ASGFSlideService()
        slide_count = 0
        generated_slides: list[dict] = []

        try:
            async for slide in slide_service.generate_slides(
                learning_cycle_plan=learning_cycle_plan,
                context_package=context_package,
            ):
                slide_count += 1
                generated_slides.append(slide)
                yield f"event: slide\ndata: {json.dumps(slide)}\n\n"

            # Persist generated slides back to learning_history (#3478)
            try:
                persist_row = (
                    db.query(LearningHistory)
                    .filter(LearningHistory.session_id == session_id)
                    .first()
                )
                if persist_row:
                    existing = persist_row.slides_generated or {}
                    if isinstance(existing, dict):
                        existing["_generated_slides"] = generated_slides
                        persist_row.slides_generated = existing
                        db.commit()
            except Exception:
                db.rollback()
                logger.warning("ASGF: failed to persist generated slides for session %s", session_id)

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

    # --- Persist the signal in learning_history (best-effort) ---
    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )

    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    _verify_session_ownership(history_row, current_user, db)

    if history_row:
        # Append signal to _comprehension_signals key within slides_generated
        existing = history_row.slides_generated or {}
        if isinstance(existing, dict):
            signals = existing.get("_comprehension_signals", [])
            signals.append(
                {
                    "slide_number": body.slide_number,
                    "signal": body.signal,
                }
            )
            existing["_comprehension_signals"] = signals
            history_row.slides_generated = existing
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
        raw = history_row.slides_generated
        # Search _generated_slides key for actual slide content (#3480)
        search_list: list = []
        if isinstance(raw, dict):
            search_list = raw.get("_generated_slides", [])
        elif isinstance(raw, list):
            search_list = raw
        for entry in search_list:
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


# --- Helper: verify session ownership ------------------------------------

def _verify_session_ownership(
    history_row, current_user: User, db: Session
) -> None:
    """Verify the session belongs to the current user. Raises 404 if not."""
    role = _get_user_role(current_user)

    # Admins can access all sessions
    if role == "admin":
        return
    # Teachers can access sessions for students enrolled in their courses.
    # SECURITY NOTE: This is a basic scope check — it verifies the teacher
    # teaches at least one course the student is enrolled in, but does NOT
    # verify the session topic matches that course.  Full per-course scoping
    # is deferred to v2.
    if role == "teacher":
        from app.models.teacher import Teacher

        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            enrolled = (
                db.query(student_courses.c.student_id)
                .join(Course, Course.id == student_courses.c.course_id)
                .filter(Course.teacher_id == teacher.id)
                .all()
            )
            enrolled_ids = {sid for (sid,) in enrolled}
            if history_row.student_id in enrolled_ids:
                return
        # Teacher does not teach any course this student is in
        raise HTTPException(status_code=404, detail="Session not found")

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
    """Generate slide-anchored quiz questions for a completed ASGF session."""
    from app.services.asgf_quiz_service import generate_asgf_quiz

    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    _verify_session_ownership(history_row, current_user, db)

    raw_data = history_row.slides_generated or {}
    slides: list[dict] = _extract_slide_content(raw_data)

    if not slides:
        raise HTTPException(
            status_code=400,
            detail="No slide content found for this session. Complete the slide lesson first.",
        )

    learning_cycle_plan = raw_data if isinstance(raw_data, dict) else {}
    context_package = history_row.documents_uploaded or {}

    questions = await generate_asgf_quiz(
        slides=slides,
        learning_cycle_plan=learning_cycle_plan,
        context_package=context_package,
    )

    if not questions:
        raise HTTPException(status_code=500, detail="Quiz generation failed. Please try again.")

    logger.info("ASGF quiz: user=%d session=%s questions=%d", current_user.id, session_id, len(questions))
    return ASGFQuizResponse(session_id=session_id, questions=[ASGFQuizQuestion(**q) for q in questions])


# --- POST /asgf/session/{session_id}/complete (#3401) --------------------

@router.post("/session/{session_id}/complete", response_model=CompleteSessionResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def complete_session(
    session_id: str,
    body: CompleteSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete an ASGF session and auto-save as Class Material."""
    from app.services.asgf_save_service import auto_save_session

    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    _verify_session_ownership(history_row, current_user, db)

    if history_row.material_id is not None:
        return CompleteSessionResponse(material_id=history_row.material_id, summary="Session already saved.")

    slides = _extract_slide_content(history_row.slides_generated)
    quiz_dicts = [qr.model_dump() for qr in body.quiz_results]

    try:
        material_id, summary = await auto_save_session(
            session_id=session_id, slides=slides, quiz_results=quiz_dicts,
            student_id=history_row.student_id, db=db,
        )
    except ValueError as e:
        logger.error("ASGF complete session error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("ASGF complete session unexpected error")
        raise HTTPException(status_code=500, detail="Failed to save session. Please try again.")

    logger.info("ASGF session completed: session_id=%s, user=%d, material_id=%d", session_id, current_user.id, material_id)
    return CompleteSessionResponse(material_id=material_id, summary=summary)


# --- GET /asgf/session/{session_id}/assignment-options (#3402) ----------------

@router.get("/session/{session_id}/assignment-options", response_model=AssignmentOptionsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_assignment_options(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return role-aware assignment options and auto-detected course for a session."""

    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    _verify_session_ownership(history_row, current_user, db)

    role = _get_user_role(current_user)

    options = [AssignmentOption(**o) for o in get_role_options(role)]

    suggested_course: CourseSuggestion | None = None
    student_id = resolve_student_id(
        user_id=current_user.id, role=role, child_id=history_row.student_id, db=db,
    )

    if student_id:
        topic = history_row.question_asked or ""
        subject = history_row.subject or ""
        course_match = await detect_course(topic=topic, subject=subject, student_id=student_id, db=db)
        if course_match.get("course_id"):
            suggested_course = CourseSuggestion(
                course_id=course_match["course_id"],
                course_name=course_match["course_name"],
                confidence=course_match["confidence"],
            )

    return AssignmentOptionsResponse(role=role, options=options, suggested_course=suggested_course)


# --- POST /asgf/session/{session_id}/assign (#3402) --------------------------

@router.post("/session/{session_id}/assign", response_model=AssignResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def assign_session_material(
    session_id: str,
    body: AssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute the assignment choice for a session's material."""

    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    _verify_session_ownership(history_row, current_user, db)

    material_id = history_row.material_id or history_row.id
    course_id = int(body.course_id) if body.course_id else None

    result = await assign_material(
        material_id=material_id, assignment_type=body.assignment_type,
        course_id=course_id, due_date=body.due_date, db=db,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return AssignResponse(success=result["success"], message=result["message"])


# --- Session resume helpers -----------------------------------------------

SESSION_EXPIRY_HOURS = 24


def _extract_signals(slides_generated) -> list[dict]:
    """Extract comprehension signals from the slides_generated JSON."""
    signals: list[dict] = []
    if isinstance(slides_generated, dict):
        # Signals are stored under _comprehension_signals key (#3478)
        for entry in slides_generated.get("_comprehension_signals", []):
            if isinstance(entry, dict) and "signal" in entry and "slide_number" in entry:
                signals.append({"slide_number": entry["slide_number"], "signal": entry["signal"]})
    elif isinstance(slides_generated, list):
        for entry in slides_generated:
            if isinstance(entry, dict) and "signal" in entry and "slide_number" in entry:
                signals.append({"slide_number": entry["slide_number"], "signal": entry["signal"]})
    return signals


def _extract_slide_content(slides_generated) -> list[dict]:
    """Extract actual slide content from slides_generated JSON."""
    slides: list[dict] = []
    if isinstance(slides_generated, dict):
        # Prefer _generated_slides (persisted after SSE stream) (#3478)
        generated = slides_generated.get("_generated_slides", [])
        if generated:
            for entry in generated:
                if isinstance(entry, dict) and "title" in entry:
                    slides.append(entry)
        else:
            # Fallback to slide_plan summaries if slides not yet generated
            slide_plan = slides_generated.get("slide_plan", [])
            for i, sp in enumerate(slide_plan):
                if isinstance(sp, dict):
                    slides.append({
                        "slide_number": i,
                        "title": sp.get("title", f"Slide {i + 1}"),
                        "body": sp.get("brief", ""),
                        "bloom_tier": sp.get("bloom_tier", ""),
                    })
    elif isinstance(slides_generated, list):
        for entry in slides_generated:
            if isinstance(entry, dict) and "title" in entry and ("body" in entry or "content" in entry):
                slides.append(entry)
    return slides


# --- GET /asgf/session/{session_id}/resume (#3409) -------------------------

@router.get("/session/{session_id}/resume", response_model=ResumeSessionResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def resume_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return session state for resumption within 24 hours of creation."""

    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.session_id == session_id)
        .first()
    )
    if not history_row:
        raise HTTPException(status_code=404, detail="Session not found")

    _verify_session_ownership(history_row, current_user, db)

    # Check 24h expiry
    created = history_row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    expires_at = created + timedelta(hours=SESSION_EXPIRY_HOURS)
    now = datetime.now(timezone.utc)

    if now > expires_at:
        raise HTTPException(status_code=410, detail="Session expired")

    # Already completed sessions cannot be resumed
    if history_row.material_id is not None:
        raise HTTPException(status_code=400, detail="Session already completed")

    signals = _extract_signals(history_row.slides_generated)
    slides = _extract_slide_content(history_row.slides_generated)

    # Current slide index = number of signals given (user moves forward after each signal)
    current_slide_index = len(signals)

    # Quiz progress from quiz_results if any partial results stored
    quiz_progress: list[dict] = []
    if history_row.quiz_results and isinstance(history_row.quiz_results, list):
        quiz_progress = history_row.quiz_results

    logger.info("ASGF resume: user=%d session=%s slide_index=%d", current_user.id, session_id, current_slide_index)

    return ResumeSessionResponse(
        session_id=session_id,
        current_slide_index=current_slide_index,
        signals_given=signals,
        quiz_progress=quiz_progress,
        slides=slides,
        created_at=created.isoformat(),
        expires_at=expires_at.isoformat(),
    )


# --- GET /asgf/active-sessions (#3409) -------------------------------------

@router.get("/active-sessions", response_model=ActiveSessionsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_active_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return resumable ASGF sessions (created within 24h, not yet completed)."""

    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    # Resolve student IDs owned by current user
    student_ids: list[int] = []
    if role == "student":
        student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student_row:
            student_ids.append(student_row.id)
    elif role == "parent":
        child_ids = [
            sid
            for (sid,) in db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        student_ids.extend(child_ids)

    if not student_ids:
        return ActiveSessionsResponse(sessions=[])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_EXPIRY_HOURS)

    rows = (
        db.query(LearningHistory)
        .filter(
            LearningHistory.student_id.in_(student_ids),
            LearningHistory.session_type == "asgf",
            LearningHistory.material_id.is_(None),
            LearningHistory.created_at >= cutoff,
        )
        .order_by(LearningHistory.created_at.desc())
        .limit(10)
        .all()
    )

    sessions: list[ActiveSessionItem] = []
    for row in rows:
        slides = _extract_slide_content(row.slides_generated)
        created = row.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        sessions.append(
            ActiveSessionItem(
                session_id=row.session_id,
                question=row.question_asked or "",
                subject=row.subject or "",
                created_at=created.isoformat() if created else "",
                slide_count=len(slides),
            )
        )

    logger.info("ASGF active-sessions: user=%d count=%d", current_user.id, len(sessions))
    return ActiveSessionsResponse(sessions=sessions)


# --- GET /asgf/student/{student_id}/review-topics (#3403) --------------------

@router.get("/student/{student_id}/review-topics", response_model=ReviewTopicsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def get_review_topics(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return topics due for spaced-repetition review for a student.

    Parents can query for their linked children; students can query for themselves.
    """
    from app.services.asgf_learning_history_service import get_spaced_repetition_topics

    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    # Auth: verify the requester owns this student
    allowed_student_ids: list[int] = []
    if role == "student":
        student_row = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student_row:
            allowed_student_ids.append(student_row.id)
    elif role == "parent":
        child_ids = [
            sid
            for (sid,) in db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        ]
        allowed_student_ids.extend(child_ids)

    if student_id not in allowed_student_ids:
        raise HTTPException(status_code=404, detail="Student not found")

    topics = get_spaced_repetition_topics(student_id=student_id, db=db)

    return ReviewTopicsResponse(
        student_id=student_id,
        topics=[ReviewTopicItem(**t) for t in topics],
    )
