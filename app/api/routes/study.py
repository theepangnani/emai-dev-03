import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse as _StreamingResponse, JSONResponse
from sqlalchemy import or_, and_, func as sa_func
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.utils import escape_like
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.domains.study.services import StudyService
from app.models.study_guide import StudyGuide
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.course_content import CourseContent
from app.services.storage_service import save_file
from app.models.student import Student, parent_students
from app.models.course import student_courses
from app.models.task import Task
from app.models.user import User, UserRole
from app.schemas.study import (
    StudyGuideCreate,
    StudyGuideUpdate,
    StudyGuideResponse,
    QuizGenerateRequest,
    QuizResponse,
    QuizQuestion,
    FlashcardGenerateRequest,
    FlashcardSetResponse,
    Flashcard,
    MindMapGenerateRequest,
    MindMapResponse,
    MindMapData,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    AutoCreatedTask,
    GenerateChildRequest,
    StudyGuideTreeNode,
    StudyGuideTreeResponse,
    SaveQAAsGuideRequest,
    SaveQAAsMaterialRequest,
    ClassifyDocumentResponse,
    WorksheetGenerateRequest,
    WorksheetResponse,
    WeakAreaAnalyzeRequest,
)
from app.api.deps import get_current_user, can_access_course
from app.services.audit_service import log_action
from app.models.content_image import ContentImage
from app.services.ai_service import generate_study_guide, generate_study_guide_stream, generate_quiz, generate_flashcards, generate_mind_map, generate_content, check_content_safe, check_texts_safe, get_last_ai_usage, get_max_tokens_for_document_type, SUB_GUIDE_MAX_TOKENS
from app.services.ai_usage import check_ai_usage, increment_ai_usage, log_ai_usage
from app.services.notification_service import notify_parents_of_student
from app.models.notification import NotificationType
from app.services.file_processor import (
    process_file,
    get_supported_formats,
    FileProcessingError,
    MAX_FILE_SIZE,
    MIN_EXTRACTION_CHARS,
    _ocr_images_with_vision,
    check_extracted_text_sufficient,
)

logger = get_logger(__name__)

# User-facing error when extracted text is too short for AI generation (#2217)
INSUFFICIENT_TEXT_MSG = (
    "We couldn't read enough text from this document. "
    "Please try a different file or format."
)
# Lower minimum for parent open-ended questions (#2861)
MIN_QUESTION_CHARS = 10

# Template keys passed via study_goal_text — internal selectors, not user text.
# These must NOT be persisted to course_content.study_goal_text.
_TEMPLATE_GOAL_KEYS = frozenset({'problem_solver'})

# Guide type display labels for child guide title generation (#3371)
GUIDE_TYPE_LABELS = {
    "study_guide": "Study Guide",
    "quiz": "Quiz",
    "flashcards": "Flashcards",
    "problem_solver": "Problem Solver",
}


def _cleanup_empty_guide(guide_id: int, logger) -> None:
    """Delete a study guide record if it has no content (stream failure cleanup)."""
    try:
        from app.db.database import SessionLocal
        with SessionLocal() as db:
            guide = db.get(StudyGuide, guide_id)
            if guide and not guide.content:
                db.delete(guide)
                db.commit()
                logger.info("Deleted empty study guide %d after stream failure", guide_id)
    except Exception as e:
        logger.warning("Failed to clean up empty guide %d: %s", guide_id, e)


def _apply_parent_question_guards(
    body, description: str, title: str, current_user: User,
) -> tuple[str, str]:
    """Validate and transform parent_question requests (#2861, #2868).

    Returns:
        Tuple of (description, title) — possibly prefixed/auto-titled.
    """
    if body.document_type != "parent_question":
        return description, title

    # Role guard: parent_question is parent-only
    from app.models.user import UserRole
    if not current_user.has_role(UserRole.PARENT):
        raise HTTPException(status_code=403, detail="Only parents can use the question feature")

    # Lower minimum content length for free-form questions
    if len(description.strip()) < MIN_QUESTION_CHARS:
        raise HTTPException(status_code=422, detail="Please enter a question (at least 10 characters)")

    # Prefix so AI clearly sees it's a question, not source material
    description = f"PARENT'S QUESTION:\n{description}"

    # Auto-title from question text when no title provided
    if title == "Study Guide":
        question_preview = (body.content or "").strip()[:60]
        if len((body.content or "").strip()) > 60:
            question_preview += "..."
        title = f"Study Guide: {question_preview}" if question_preview else "Study Guide"

    return description, title


router = APIRouter(prefix="/study", tags=["Study Tools"])


def _get_user_interests(user: User) -> list[str] | None:
    """Parse interests JSON string from user record."""
    if not user.interests:
        return None
    try:
        parsed = json.loads(user.interests)
        return parsed if isinstance(parsed, list) and parsed else None
    except (json.JSONDecodeError, TypeError):
        return None


# ============================================
# Helper Functions
# ============================================


def _get_images_metadata(db: Session, course_content_id: int | None) -> list[dict]:
    """Query ContentImage records for a course content and return metadata dicts."""
    if not course_content_id:
        return []
    content_images = (
        db.query(ContentImage)
        .filter(ContentImage.course_content_id == course_content_id)
        .order_by(ContentImage.position_index)
        .limit(20)
        .all()
    )
    return [
        {
            "id": img.id,
            "position_index": img.position_index,
            "description": img.description,
            "position_context": img.position_context,
        }
        for img in content_images
    ]


def _append_unplaced_images(content: str, images_metadata: list[dict]) -> str:
    """Append any images not referenced by the AI to an 'Additional Figures' section."""
    if not images_metadata:
        return content

    # Find all {{IMG-N}} markers in the generated content
    placed = set()
    for match in re.finditer(r'\{\{IMG-(\d+)\}\}', content):
        placed.add(int(match.group(1)))

    # Find unplaced images
    unplaced = []
    for img in images_metadata:
        img_num = img['position_index'] + 1  # IMG-N is 1-indexed
        if img_num not in placed:
            unplaced.append(img)

    if not unplaced:
        return content

    # Append Additional Figures section
    section = "\n\n---\n\n## Additional Figures from Source Material\n\n"
    for img in unplaced:
        img_num = img['position_index'] + 1
        desc = img.get('description') or f"Image {img_num}"
        section += f"![{desc}]({{{{IMG-{img_num}}}}})\n"
        if img.get('position_context'):
            ctx = img['position_context'][:150]
            section += f"*Found near: \"{ctx}\"*\n\n"
        else:
            section += "\n"

    return content + section


def enforce_study_guide_limit(db: Session, user: User) -> None:
    """Enforce role-based study guide limit. Archives oldest active guides when limit reached."""
    limit = (
        settings.max_study_guides_per_parent
        if user.role == UserRole.PARENT
        else settings.max_study_guides_per_student
    )
    count = db.query(StudyGuide).filter(
        StudyGuide.user_id == user.id,
        StudyGuide.archived_at.is_(None),
    ).count()
    if count >= limit:
        guides_to_archive = count - limit + 1
        oldest_guides = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.user_id == user.id,
                StudyGuide.archived_at.is_(None),
            )
            .order_by(StudyGuide.created_at.asc())
            .limit(guides_to_archive)
            .all()
        )
        for guide in oldest_guides:
            guide.archived_at = datetime.now(timezone.utc)




def get_student_enrolled_course_ids(db: Session, user_id: int) -> list[int]:
    """Get course IDs for a student's enrolled courses."""
    student = db.query(Student).options(selectinload(Student.courses)).filter(Student.user_id == user_id).first()
    if not student:
        return []
    return [c.id for c in student.courses]


def get_linked_children_user_ids(db: Session, parent_id: int) -> list[int]:
    """Get user_ids of all children linked to a parent."""
    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == parent_id
    ).all()
    student_ids = [r[0] for r in rows]
    if not student_ids:
        return []
    students = db.query(Student.user_id).filter(Student.id.in_(student_ids)).all()
    return [s[0] for s in students]


def get_children_course_ids(db: Session, parent_id: int, student_user_id: int | None = None) -> list[int]:
    """Get course IDs for a parent's linked children (optionally filtered to one child)."""
    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == parent_id
    ).all()
    child_sids = [r[0] for r in rows]
    if not child_sids:
        return []

    if student_user_id:
        child_student = db.query(Student).options(selectinload(Student.courses)).filter(
            Student.user_id == student_user_id,
            Student.id.in_(child_sids),
        ).first()
        if not child_student:
            return []
        return [c.id for c in child_student.courses]

    enrolled = db.query(student_courses.c.course_id).filter(
        student_courses.c.student_id.in_(child_sids)
    ).all()
    return [r[0] for r in enrolled]


def strip_json_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from AI responses."""
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


def ensure_course_and_content(
    db: Session, user: User, title: str, text_content: str | None,
    course_id: int | None, course_content_id: int | None,
) -> tuple[int, int]:
    """Ensure a course + course_content exist for a study guide.

    Returns (course_id, course_content_id).  If course_content_id is already
    provided it is returned as-is.  If course_id is missing the user's default
    'My Materials' course is created/fetched.  A new CourseContent row is
    always created when course_content_id is None.
    """
    from app.api.routes.courses import get_or_create_default_course

    # Resolve existing course_content
    if course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
        if cc:
            return cc.course_id, cc.id

    # Resolve course
    if course_id:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            course = get_or_create_default_course(db, user)
    else:
        course = get_or_create_default_course(db, user)

    # Create CourseContent
    cc = CourseContent(
        course_id=course.id,
        title=title,
        text_content=text_content,
        content_type="other",
        created_by_user_id=user.id,
    )
    db.add(cc)
    db.flush()  # get cc.id without committing
    return course.id, cc.id




def _notify_parents_of_study_material(
    db: Session, user: User, study_guide_id: int, title: str,
) -> None:
    """Notify parents when a student generates study material. Safe to call — never raises."""
    if user.role != UserRole.STUDENT:
        return
    try:
        notify_parents_of_student(
            db=db,
            student_user=user,
            title=f"New study material: {title}",
            content=f"{user.full_name} created \"{title}\".",
            notification_type=NotificationType.STUDY_GUIDE_CREATED,
            link=f"/study/guides/{study_guide_id}",
            source_type="study_guide",
            source_id=study_guide_id,
        )
    except Exception:
        pass  # Never break primary action


CRITICAL_DATES_SEPARATOR = "--- CRITICAL_DATES ---"


def parse_critical_dates(content: str) -> tuple[str, list[dict]]:
    """Parse CRITICAL_DATES section from AI response.

    Returns (clean_content, dates_list). If no dates section found, returns
    original content and empty list.
    """
    if CRITICAL_DATES_SEPARATOR not in content:
        return content, []

    parts = content.split(CRITICAL_DATES_SEPARATOR, 1)
    clean_content = parts[0].rstrip()
    dates_raw = parts[1].strip()

    # Strip markdown code fences if present
    dates_raw = strip_json_fences(dates_raw)

    try:
        dates = json.loads(dates_raw)
        if not isinstance(dates, list):
            return clean_content, []
        # Validate each entry has required fields
        valid_dates = []
        for d in dates:
            if isinstance(d, dict) and d.get("date") and d.get("title"):
                valid_dates.append({
                    "date": str(d["date"]),
                    "title": str(d["title"]),
                    "priority": str(d.get("priority", "medium")),
                })
        return clean_content, valid_dates
    except (json.JSONDecodeError, TypeError):
        return clean_content, []


SUGGESTION_TOPICS_SEPARATOR = "--- SUGGESTION_TOPICS ---"


def parse_suggestion_topics(content: str) -> tuple[str, list[dict]]:
    """Parse SUGGESTION_TOPICS section from AI response.
    Returns (clean_content, topics_list).
    """
    if SUGGESTION_TOPICS_SEPARATOR not in content:
        return content, []

    parts = content.split(SUGGESTION_TOPICS_SEPARATOR, 1)
    clean_content = parts[0].rstrip()
    topics_raw = parts[1].strip()
    topics_raw = strip_json_fences(topics_raw)

    try:
        topics = json.loads(topics_raw)
        if not isinstance(topics, list):
            return clean_content, []
        valid = []
        for t in topics:
            if isinstance(t, dict) and t.get("label"):
                valid.append({
                    "label": str(t["label"])[:60],
                    "description": str(t.get("description", ""))[:200],
                })
        return clean_content, valid[:6]
    except (json.JSONDecodeError, TypeError):
        return clean_content, []


# Month name → number mapping for date scanning
_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Regex: "Due Mar 3", "Due: March 15", "due date: Feb 25", "Due by Apr 1"
_DUE_DATE_PATTERN = re.compile(
    r"(?:due(?:\s+date)?[\s:]*(?:by\s+)?)"
    r"([A-Za-z]+)\s+(\d{1,2})"
    r"(?:[,\s]+(\d{4}))?",
    re.IGNORECASE,
)


def scan_content_for_dates(source_content: str, title: str) -> list[dict]:
    """Scan source content for common due date patterns as a fallback.

    Returns a list of date dicts compatible with auto_create_tasks_from_dates().
    Only returns dates that are in the future (from today).
    """
    results = []
    now = datetime.now()

    for match in _DUE_DATE_PATTERN.finditer(source_content):
        month_str = match.group(1).lower()
        day = int(match.group(2))
        year_str = match.group(3)

        month = _MONTH_MAP.get(month_str)
        if not month or day < 1 or day > 31:
            continue

        if year_str:
            year = int(year_str)
        else:
            # Infer year: use current year, bump to next year if date is in the past
            year = now.year
            try:
                candidate = datetime(year, month, day)
            except ValueError:
                continue
            if candidate.date() < now.date():
                year += 1

        try:
            due = datetime(year, month, day)
        except ValueError:
            continue

        results.append({
            "date": due.strftime("%Y-%m-%d"),
            "title": f"{title} — due {due.strftime('%b %d')}",
            "priority": "medium",
        })

    return results


def auto_create_tasks_from_dates(
    db: Session,
    dates: list[dict],
    user: User,
    study_guide_id: int,
    course_id: int | None,
    course_content_id: int | None,
) -> list[dict]:
    """Create tasks from extracted critical dates. Returns list of created task summaries."""
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)

    created_tasks = []
    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)

    for d in dates:
        try:
            due_date = datetime.strptime(d["date"], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
        except (ValueError, TypeError):
            logger.warning(f"Skipping invalid date in auto-task creation: {d.get('date')}")
            continue

        # Reject dates more than 1 year in the past — likely extracted from
        # article content rather than actual student deadlines (#841)
        if due_date < one_year_ago:
            logger.warning(f"Skipping historical date in auto-task creation: {d.get('date')} '{d.get('title')}'")
            continue

        # Determine who the task should be assigned to
        assigned_to = None
        if user.role == UserRole.PARENT:
            child_ids = get_linked_children_user_ids(db, user.id)
            if child_ids and course_id:
                # Find which child is enrolled in the source course
                enrolled_child = db.query(Student.user_id).join(
                    student_courses, Student.id == student_courses.c.student_id
                ).filter(
                    student_courses.c.course_id == course_id,
                    Student.user_id.in_(child_ids),
                ).first()
                assigned_to = enrolled_child[0] if enrolled_child else child_ids[0]
            elif child_ids:
                assigned_to = child_ids[0]

        # Resolve legacy student_id from assigned user (required by prod DB schema)
        legacy_student_id = None
        if assigned_to:
            student_rec = db.query(Student).filter(Student.user_id == assigned_to).first()
            if student_rec:
                legacy_student_id = student_rec.id

        priority = d.get("priority", "medium")
        if priority not in ("low", "medium", "high"):
            priority = "medium"

        try:
            task = Task(
                title=d["title"],
                description=f"Auto-created from class material generation",
                due_date=due_date,
                priority=priority,
                created_by_user_id=user.id,
                assigned_to_user_id=assigned_to,
                parent_id=user.id,
                student_id=legacy_student_id,
                study_guide_id=study_guide_id,
                course_id=course_id,
                course_content_id=course_content_id,
            )
            db.add(task)
            db.flush()
            created_tasks.append({
                "id": task.id,
                "title": task.title,
                "due_date": d["date"],
                "priority": priority,
            })
            logger.info(f"Auto-created task '{task.title}' due {d['date']} from study guide {study_guide_id}")
        except Exception:
            logger.exception(f"Failed to auto-create task '{d.get('title')}' for study guide {study_guide_id}")
            db.rollback()

    return created_tasks


# ============================================
# Duplicate Detection
# ============================================


@router.post("/check-duplicate", response_model=DuplicateCheckResponse)
def check_duplicate(
    request: DuplicateCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a similar study guide already exists before generating."""
    study_service = StudyService(db)
    result = study_service.check_duplicate(
        title=request.title,
        guide_type=request.guide_type,
        user_id=current_user.id,
        assignment_id=request.assignment_id,
    )

    if result["exists"]:
        return DuplicateCheckResponse(
            exists=True,
            existing_guide=result["existing_guide"],
            message=result["message"],
        )

    return DuplicateCheckResponse(exists=False)


# ============================================
# Classification Endpoints
# ============================================


class ClassifyDocumentRequest(BaseModel):
    text_content: str = ""
    filename: str = ""


@router.post("/classify-document", response_model=ClassifyDocumentResponse)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def classify_document(
    request: Request,
    body: ClassifyDocumentRequest,
    current_user: User = Depends(get_current_user),
):
    """Auto-detect document type and subject from uploaded content (§6.105.3)."""
    from app.services.document_classifier import DocumentClassifierService
    result = await DocumentClassifierService.classify(body.text_content, body.filename)
    return result


# ============================================
# Generation Endpoints
# ============================================


@router.post("/generate", response_model=StudyGuideResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_study_guide_endpoint(
    request: Request,
    body: StudyGuideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a study guide from an assignment or custom content."""
    # Safety-check all user-provided text inputs
    for text_input in [body.focus_prompt, body.custom_prompt, body.content]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    study_service = StudyService(db)

    # Handle versioning
    version = 1
    parent_guide_id = None
    if body.regenerate_from_id:
        parent_guide_id, version = study_service.get_version_info(body.regenerate_from_id, current_user.id)

    # §6.106: Inherit document_type/study_goal from parent guide's course content on regeneration
    if body.regenerate_from_id and not body.document_type:
        parent_guide = db.query(StudyGuide).filter(StudyGuide.id == body.regenerate_from_id).first()
        if parent_guide and parent_guide.course_content_id:
            parent_cc = db.query(CourseContent).filter(CourseContent.id == parent_guide.course_content_id).first()
            if parent_cc:
                if not body.document_type and getattr(parent_cc, 'document_type', None):
                    body.document_type = parent_cc.document_type
                if not body.study_goal and getattr(parent_cc, 'study_goal', None):
                    body.study_goal = parent_cc.study_goal
                if not body.study_goal_text and getattr(parent_cc, 'study_goal_text', None):
                    body.study_goal_text = parent_cc.study_goal_text

    # Get source content
    assignment = None
    course = None
    title = body.title or "Study Guide"
    description = body.content or ""

    if body.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == body.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if assignment.course_id and not can_access_course(db, current_user, assignment.course_id):
            raise HTTPException(status_code=403, detail="No access to this assignment's course")
        title = f"Study Guide: {assignment.title}"
        description = assignment.description or ""
        course = assignment.course

    # Fallback: fetch text from CourseContent when no explicit content provided
    if not description and body.course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
        if cc:
            description = cc.text_content or cc.description or ""
            if not title or title == "Study Guide":
                title = f"Study Guide: {cc.title}"
            if not course and cc.course_id:
                course = db.query(Course).filter(Course.id == cc.course_id).first()

    if body.course_id and not course:
        course = db.query(Course).filter(Course.id == body.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if not can_access_course(db, current_user, body.course_id):
            raise HTTPException(status_code=403, detail="No access to this course")

    course_name = course.name if course else "General"
    due_date = str(assignment.due_date) if assignment and assignment.due_date else None

    if not description:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate a study guide",
        )

    # Parent question guards: role check, min-length, prefix, auto-title (#2861)
    description, title = _apply_parent_question_guards(body, description, title, current_user)

    # Gate: reject non-question content shorter than MIN_EXTRACTION_CHARS (#2217)
    if body.document_type != "parent_question" and len(description.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Check AI usage limit before generation
    check_ai_usage(current_user, db)

    # Fetch image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, body.course_content_id)

    # Generate study guide using AI
    try:
        raw_content, is_truncated = await generate_study_guide(
            assignment_title=title,
            assignment_description=description,
            course_name=course_name,
            due_date=due_date,
            custom_prompt=body.custom_prompt,
            focus_prompt=body.focus_prompt,
            images=images_metadata,
            interests=_get_user_interests(current_user),
            max_tokens=get_max_tokens_for_document_type(body.document_type),
            document_type=body.document_type,
            study_goal=body.study_goal,
            study_goal_text=body.study_goal_text,
        )
    except ValueError as e:
        from app.core.faq_errors import raise_with_faq_hint, AI_GENERATION_FAILED
        raise_with_faq_hint(
            status_code=500,
            detail=str(e),
            faq_code=AI_GENERATION_FAILED,
        )
    except Exception as e:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.error("Study guide generation failed: %s: %s", type(e).__name__, e)
        detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=500, detail=detail[:500])

    # Parse suggestion topics and critical dates from AI response
    content, suggestion_topics = parse_suggestion_topics(raw_content)
    content, critical_dates = parse_critical_dates(content)

    # Post-process to add unplaced images
    if images_metadata:
        content = _append_unplaced_images(content, images_metadata)

    # Deduplicate: return existing if same hash was created recently
    content_hash = study_service.compute_content_hash(title, "study_guide", body.assignment_id)
    existing = study_service.find_recent_duplicate(current_user.id, content_hash)
    if existing:
        return existing

    # Increment AI usage only when creating NEW content
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(
        current_user, db, generation_type="study_guide", course_material_id=body.course_content_id,
        is_regeneration=bool(body.regenerate_from_id), **_usage,
    )

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, title, description,
        course_id=body.course_id or (course.id if course else None),
        course_content_id=body.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=body.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=title,
        content=content,
        guide_type="study_guide",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
        focus_prompt=body.focus_prompt or None,
        is_truncated=is_truncated,
        suggestion_topics=json.dumps(suggestion_topics) if suggestion_topics else None,
    )
    db.add(study_guide)
    db.flush()

    # Auto-create tasks from critical dates (or fallback: scan source content, then generic review)
    if not critical_dates:
        critical_dates = scan_content_for_dates(description, title)
    if not critical_dates:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        critical_dates = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]

    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        resolved_course_id, resolved_cc_id,
    )

    log_action(db, user_id=current_user.id, action="create", resource_type="study_guide", resource_id=study_guide.id, details={"guide_type": "study_guide", "auto_tasks": len(created_tasks)})
    db.commit()
    db.refresh(study_guide)

    # Award XP for study guide creation (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "study_guide")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

    # Generate parent summary if applicable (§6.105.4)
    if body.document_type or body.study_goal:
        try:
            from app.services.parent_summary import ParentSummaryService
            parent_summary = await ParentSummaryService.generate(
                study_guide_content=content,
                student_name=current_user.full_name,
                subject=course_name,
                document_type=body.document_type,
                study_goal=body.study_goal,
            )
            if parent_summary:
                study_guide.parent_summary = parent_summary
                db.commit()
        except Exception as e:
            logger.warning(f"Parent summary generation failed: {e}")

    # Persist document_type and study_goal on course content (§6.105)
    if body.course_content_id and (body.document_type or body.study_goal):
        try:
            cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
            if cc:
                if body.document_type:
                    cc.document_type = body.document_type
                if body.study_goal:
                    cc.study_goal = body.study_goal
                if body.study_goal_text and body.study_goal_text not in _TEMPLATE_GOAL_KEYS:
                    cc.study_goal_text = body.study_goal_text
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist document type on course content: {e}")

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    # Fire-and-forget AI resource suggestions for NEW guides only (#2489)
    if not body.regenerate_from_id and resolved_cc_id:
        try:
            import asyncio
            from app.services.resource_suggestion_service import suggest_resources_background
            from app.db.database import SessionLocal
            asyncio.create_task(suggest_resources_background(
                topic=title,
                course_name=course_name,
                grade_level="",
                course_content_id=resolved_cc_id,
                user_id=current_user.id,
                db_factory=SessionLocal,
            ))
        except Exception as e:
            logger.warning(f"Resource suggestion task failed to launch: {e}")

    resp = StudyGuideResponse.model_validate(study_guide)
    resp.auto_created_tasks = [AutoCreatedTask(**t) for t in created_tasks]
    return resp


@router.post("/{guide_id}/continue", response_model=StudyGuideResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def continue_study_guide(
    guide_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Continue generating a truncated study guide."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
        StudyGuide.guide_type == "study_guide",
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    check_ai_usage(current_user, db)

    system_prompt = """You are an expert educational tutor. Continue the study guide from where it left off.
Do not repeat content already covered. Pick up exactly where the previous content ended.
Use simple language, practical examples, and clean Markdown formatting.
For math, use LaTeX notation with $...$ for inline math and $$...$$ for display equations."""

    prompt = f"""The following study guide may be complete or cut off. Continue it from where it left off, adding more detail, examples, or sections. Do not repeat any content already covered.

**Previous content:**
{guide.content}

Continue the study guide from here:"""

    from app.services.ai_service import generate_content
    try:
        continuation, stop_reason = await generate_content(prompt, system_prompt, max_tokens=4096)
    except Exception as e:
        logger.error("Study guide continuation failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"AI generation failed: {type(e).__name__}")

    guide.content = guide.content + "\n\n" + continuation
    guide.is_truncated = stop_reason == "max_tokens"

    _usage = get_last_ai_usage() or {}
    increment_ai_usage(current_user, db, generation_type="study_guide", **_usage)
    log_action(db, user_id=current_user.id, action="update", resource_type="study_guide", resource_id=guide.id, details={"action": "continue"})
    db.commit()
    db.refresh(guide)

    return StudyGuideResponse.model_validate(guide)


@router.post("/{guide_id}/continue-stream")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def continue_study_guide_stream(
    guide_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the continuation of a truncated study guide via SSE."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
        StudyGuide.guide_type == "study_guide",
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    check_ai_usage(current_user, db)

    system_prompt = """You are an expert educational tutor. Continue the study guide from where it left off.
Do not repeat content already covered. Pick up exactly where the previous content ended.
Use simple language, practical examples, and clean Markdown formatting.
For math, use LaTeX notation with $...$ for inline math and $$...$$ for display equations."""

    prompt = f"""The following study guide may be complete or cut off. Continue it from where it left off, adding more detail, examples, or sections. Do not repeat any content already covered.

**Previous content:**
{guide.content}

Continue the study guide from here:"""

    # Capture values before closing DB
    user_id = current_user.id
    existing_content = guide.content

    db.close()

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'guide_id': guide_id})}\n\n"

        full_content = ""
        is_truncated = False

        try:
            from app.services.ai_service import generate_content_stream
            async for event in generate_content_stream(prompt, system_prompt, max_tokens=4096):
                if event["event"] == "chunk":
                    yield f"event: chunk\ndata: {json.dumps({'text': event['data']})}\n\n"
                elif event["event"] == "done":
                    full_content = event["data"]["full_content"]
                    is_truncated = event["data"]["is_truncated"]
                elif event["event"] == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event['data']})}\n\n"
                    return
        except Exception as e:
            logger.error("SSE continue stream failed: %s: %s", type(e).__name__, e)
            yield f"event: error\ndata: {json.dumps({'message': 'AI generation failed. Please try again.'})}\n\n"
            return

        # Save in new DB session
        try:
            from app.db.database import SessionLocal
            with SessionLocal() as save_db:
                guide_obj = save_db.get(StudyGuide, guide_id)
                if guide_obj:
                    guide_obj.content = existing_content + "\n\n" + full_content
                    guide_obj.is_truncated = is_truncated

                    from app.models.user import User as _User
                    user = save_db.get(_User, user_id)
                    if user:
                        _usage = get_last_ai_usage() or {}
                        increment_ai_usage(user, save_db, generation_type="study_guide", **_usage)

                    log_action(save_db, user_id=user_id, action="update", resource_type="study_guide",
                               resource_id=guide_obj.id, details={"action": "continue", "streamed": True})
                    save_db.commit()
                    save_db.refresh(guide_obj)

                    resp = StudyGuideResponse.model_validate(guide_obj)
                    yield f"event: done\ndata: {json.dumps(resp.model_dump(mode='json'))}\n\n"
                else:
                    yield f"event: error\ndata: {json.dumps({'message': 'Guide record not found after streaming.'})}\n\n"

        except Exception as e:
            logger.error("Failed to save continued study guide: %s: %s", type(e).__name__, e)
            yield f"event: error\ndata: {json.dumps({'message': 'Failed to save continuation. Please try again.'})}\n\n"

    return _StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/quiz/generate", response_model=QuizResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_quiz_endpoint(
    request: Request,
    body: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a practice quiz from an assignment or custom content."""
    # Safety-check all user-provided text inputs
    for text_input in [body.focus_prompt, body.content]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    study_service = StudyService(db)

    # Handle versioning
    version = 1
    parent_guide_id = None
    if body.regenerate_from_id:
        parent_guide_id, version = study_service.get_version_info(body.regenerate_from_id, current_user.id)

    # §6.106: Inherit document_type/study_goal from parent guide's course content on regeneration
    if body.regenerate_from_id and not body.document_type:
        parent_guide = db.query(StudyGuide).filter(StudyGuide.id == body.regenerate_from_id).first()
        if parent_guide and parent_guide.course_content_id:
            parent_cc = db.query(CourseContent).filter(CourseContent.id == parent_guide.course_content_id).first()
            if parent_cc:
                if not body.document_type and getattr(parent_cc, 'document_type', None):
                    body.document_type = parent_cc.document_type
                if not body.study_goal and getattr(parent_cc, 'study_goal', None):
                    body.study_goal = parent_cc.study_goal
                if not body.study_goal_text and getattr(parent_cc, 'study_goal_text', None):
                    body.study_goal_text = parent_cc.study_goal_text

    topic = body.topic or "Quiz"
    content = body.content or ""

    if body.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == body.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if assignment.course_id and not can_access_course(db, current_user, assignment.course_id):
            raise HTTPException(status_code=403, detail="No access to this assignment's course")
        topic = assignment.title
        content = assignment.description or ""

    # Fallback: fetch text from CourseContent when no explicit content provided
    if not content and body.course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
        if cc:
            content = cc.text_content or cc.description or ""
            if not topic or topic == "Quiz":
                topic = cc.title

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate a quiz",
        )

    # Gate: reject content shorter than MIN_EXTRACTION_CHARS (#2217)
    if len(content.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Safety-check resolved content (may originate from assignment/course content)
    safe, reason = check_texts_safe(content, body.focus_prompt)
    if not safe:
        raise HTTPException(status_code=400, detail=reason)

    # Extract question count from focus prompt if user specified one
    num_questions = body.num_questions
    if body.focus_prompt and num_questions <= 10:
        m = re.search(r'(\d+)\s*(?:\w*\s*)(?:questions?|quizzes?|q\b)', body.focus_prompt, re.IGNORECASE)
        if m:
            requested = min(int(m.group(1)), 50)  # clamp to 50 max
            if requested >= 1:
                num_questions = requested

    # Check AI usage limit before generation
    check_ai_usage(current_user, db)

    # Fetch image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, body.course_content_id)

    # §6.106: Apply strategy context to quiz generation
    effective_focus = body.focus_prompt or ""
    if body.document_type:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        type_labels = {"teacher_notes": "teacher notes", "past_exam": "past exam", "mock_exam": "practice exam", "course_syllabus": "syllabus", "project_brief": "project brief", "lab_experiment": "lab material", "textbook_excerpt": "textbook reading"}
        doc_label = type_labels.get(body.document_type, body.document_type)
        effective_focus = f"This content is from {doc_label}. {effective_focus}".strip()

    # Generate quiz using AI
    critical_dates = []
    try:
        raw_quiz = await generate_quiz(
            topic=topic,
            content=content,
            num_questions=num_questions,
            focus_prompt=effective_focus or None,
            difficulty=body.difficulty,
            images=images_metadata,
            interests=_get_user_interests(current_user),
        )
        # Post-process to add unplaced images (before critical dates extraction)
        if images_metadata:
            raw_quiz = _append_unplaced_images(raw_quiz, images_metadata)
        # Parse critical dates before JSON parsing (dates come after JSON)
        raw_quiz, critical_dates = parse_critical_dates(raw_quiz)
        quiz_json = strip_json_fences(raw_quiz)
        questions_data = json.loads(quiz_json)
        questions = [QuizQuestion(**q) for q in questions_data]
    except json.JSONDecodeError:
        logger.error("Failed to parse quiz JSON response (first 500 chars): %s", raw_quiz[:500])
        raise HTTPException(status_code=500, detail="Failed to parse quiz response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Quiz generation failed: %s: %s", type(e).__name__, e)
        detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=500, detail=detail[:500])

    # Deduplicate: return existing if same hash was created recently
    content_hash = study_service.compute_content_hash(f"Quiz: {topic}", "quiz", body.assignment_id)
    existing = study_service.find_recent_duplicate(current_user.id, content_hash)
    if existing:
        existing_questions = [QuizQuestion(**q) for q in json.loads(existing.content)]
        return QuizResponse(
            id=existing.id, title=existing.title, questions=existing_questions,
            guide_type="quiz", course_content_id=existing.course_content_id,
            version=existing.version,
            parent_guide_id=existing.parent_guide_id, created_at=existing.created_at,
        )

    # Increment AI usage only when creating NEW content
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(
        current_user, db, generation_type="quiz", course_material_id=body.course_content_id,
        is_regeneration=bool(body.regenerate_from_id), **_usage,
    )

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, f"Quiz: {topic}", content,
        course_id=body.course_id,
        course_content_id=body.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=body.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=f"Quiz: {topic}",
        content=quiz_json,
        guide_type="quiz",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
        focus_prompt=body.focus_prompt or None,
    )
    db.add(study_guide)
    db.flush()

    # Auto-create tasks from critical dates (or fallback: scan source content, then generic review)
    if not critical_dates:
        critical_dates = scan_content_for_dates(content, f"Quiz: {topic}")
    if not critical_dates:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        critical_dates = [{"date": today_str, "title": f"Review: Quiz: {topic}", "priority": "medium"}]

    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        resolved_course_id, resolved_cc_id,
    )

    db.commit()
    db.refresh(study_guide)

    # Award XP for quiz generation (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "study_guide")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    return QuizResponse(
        id=study_guide.id,
        title=study_guide.title,
        questions=questions,
        guide_type="quiz",
        course_content_id=study_guide.course_content_id,
        version=study_guide.version,
        parent_guide_id=study_guide.parent_guide_id,
        created_at=study_guide.created_at,
        auto_created_tasks=[AutoCreatedTask(**t) for t in created_tasks],
    )


@router.post("/flashcards/generate", response_model=FlashcardSetResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_flashcards_endpoint(
    request: Request,
    body: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate flashcards from an assignment or custom content."""
    # Safety-check all user-provided text inputs
    for text_input in [body.focus_prompt, body.content]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    study_service = StudyService(db)

    # Handle versioning
    version = 1
    parent_guide_id = None
    if body.regenerate_from_id:
        parent_guide_id, version = study_service.get_version_info(body.regenerate_from_id, current_user.id)

    # §6.106: Inherit document_type/study_goal from parent guide's course content on regeneration
    if body.regenerate_from_id and not body.document_type:
        parent_guide = db.query(StudyGuide).filter(StudyGuide.id == body.regenerate_from_id).first()
        if parent_guide and parent_guide.course_content_id:
            parent_cc = db.query(CourseContent).filter(CourseContent.id == parent_guide.course_content_id).first()
            if parent_cc:
                if not body.document_type and getattr(parent_cc, 'document_type', None):
                    body.document_type = parent_cc.document_type
                if not body.study_goal and getattr(parent_cc, 'study_goal', None):
                    body.study_goal = parent_cc.study_goal
                if not body.study_goal_text and getattr(parent_cc, 'study_goal_text', None):
                    body.study_goal_text = parent_cc.study_goal_text

    topic = body.topic or "Flashcards"
    content = body.content or ""

    if body.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == body.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if assignment.course_id and not can_access_course(db, current_user, assignment.course_id):
            raise HTTPException(status_code=403, detail="No access to this assignment's course")
        topic = assignment.title
        content = assignment.description or ""

    # Fallback: fetch text from CourseContent when no explicit content provided
    if not content and body.course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
        if cc:
            content = cc.text_content or cc.description or ""
            if not topic or topic == "Flashcards":
                topic = cc.title

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate flashcards",
        )

    # Gate: reject content shorter than MIN_EXTRACTION_CHARS (#2217)
    if len(content.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Safety-check resolved content (may originate from assignment/course content)
    safe, reason = check_texts_safe(content, body.focus_prompt)
    if not safe:
        raise HTTPException(status_code=400, detail=reason)

    # Check AI usage limit before generation
    check_ai_usage(current_user, db)

    # Fetch image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, body.course_content_id)

    # §6.106: Apply strategy context to flashcard generation
    effective_focus = body.focus_prompt or ""
    if body.document_type:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        type_labels = {"teacher_notes": "teacher notes", "past_exam": "past exam", "mock_exam": "practice exam", "course_syllabus": "syllabus", "project_brief": "project brief", "lab_experiment": "lab material", "textbook_excerpt": "textbook reading"}
        doc_label = type_labels.get(body.document_type, body.document_type)
        effective_focus = f"This content is from {doc_label}. {effective_focus}".strip()

    # Generate flashcards using AI
    critical_dates = []
    try:
        raw_cards = await generate_flashcards(
            topic=topic,
            content=content,
            num_cards=body.num_cards,
            focus_prompt=effective_focus or None,
            images=images_metadata,
            interests=_get_user_interests(current_user),
        )
        # Post-process to add unplaced images (before critical dates extraction)
        if images_metadata:
            raw_cards = _append_unplaced_images(raw_cards, images_metadata)
        # Parse critical dates before JSON parsing (dates come after JSON)
        raw_cards, critical_dates = parse_critical_dates(raw_cards)
        cards_json = strip_json_fences(raw_cards)
        cards_data = json.loads(cards_json)
        cards = [Flashcard(**c) for c in cards_data]
    except json.JSONDecodeError:
        logger.error("Failed to parse flashcards JSON response (first 500 chars): %s", raw_cards[:500])
        raise HTTPException(status_code=500, detail="Failed to parse flashcards response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Flashcard generation failed: %s: %s", type(e).__name__, e)
        detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=500, detail=detail[:500])

    # Deduplicate: return existing if same hash was created recently
    content_hash = study_service.compute_content_hash(f"Flashcards: {topic}", "flashcards", body.assignment_id)
    existing = study_service.find_recent_duplicate(current_user.id, content_hash)
    if existing:
        existing_cards = [Flashcard(**c) for c in json.loads(existing.content)]
        return FlashcardSetResponse(
            id=existing.id, title=existing.title, cards=existing_cards,
            guide_type="flashcards", course_content_id=existing.course_content_id,
            version=existing.version,
            parent_guide_id=existing.parent_guide_id, created_at=existing.created_at,
        )

    # Increment AI usage only when creating NEW content
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(
        current_user, db, generation_type="flashcards", course_material_id=body.course_content_id,
        is_regeneration=bool(body.regenerate_from_id), **_usage,
    )

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, f"Flashcards: {topic}", content,
        course_id=body.course_id,
        course_content_id=body.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=body.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=f"Flashcards: {topic}",
        content=cards_json,
        guide_type="flashcards",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
        focus_prompt=body.focus_prompt or None,
    )
    db.add(study_guide)
    db.flush()

    # Auto-create tasks from critical dates (or fallback: scan source content, then generic review)
    if not critical_dates:
        critical_dates = scan_content_for_dates(content, f"Flashcards: {topic}")
    if not critical_dates:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        critical_dates = [{"date": today_str, "title": f"Review: Flashcards: {topic}", "priority": "medium"}]

    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        resolved_course_id, resolved_cc_id,
    )

    db.commit()
    db.refresh(study_guide)

    # Award XP for flashcard generation (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "flashcard_deck")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    return FlashcardSetResponse(
        id=study_guide.id,
        title=study_guide.title,
        cards=cards,
        guide_type="flashcards",
        course_content_id=study_guide.course_content_id,
        version=study_guide.version,
        parent_guide_id=study_guide.parent_guide_id,
        created_at=study_guide.created_at,
        auto_created_tasks=[AutoCreatedTask(**t) for t in created_tasks],
    )


@router.post("/mind-map/generate", response_model=MindMapResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_mind_map_endpoint(
    request: Request,
    body: MindMapGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a mind map from an assignment or custom content."""
    # Safety-check all user-provided text inputs
    for text_input in [body.focus_prompt, body.content]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    study_service = StudyService(db)

    # Handle versioning
    version = 1
    parent_guide_id = None
    if body.regenerate_from_id:
        parent_guide_id, version = study_service.get_version_info(body.regenerate_from_id, current_user.id)

    topic = body.topic or "Mind Map"
    content = body.content or ""

    if body.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == body.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if assignment.course_id and not can_access_course(db, current_user, assignment.course_id):
            raise HTTPException(status_code=403, detail="No access to this assignment's course")
        topic = assignment.title
        content = assignment.description or ""

    # Fallback: fetch text from CourseContent when no explicit content provided
    if not content and body.course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
        if cc:
            content = cc.text_content or cc.description or ""
            if not topic or topic == "Mind Map":
                topic = cc.title

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate a mind map",
        )

    # Check AI usage limit before generation
    check_ai_usage(current_user, db)

    # Fetch image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, body.course_content_id)

    # Generate mind map using AI
    try:
        raw_map = await generate_mind_map(
            topic=topic,
            content=content,
            focus_prompt=body.focus_prompt,
            images=images_metadata,
        )
        map_json = strip_json_fences(raw_map)
        mind_map_data = json.loads(map_json)
        # Validate structure
        mind_map = MindMapData(**mind_map_data)
    except json.JSONDecodeError:
        logger.error("Failed to parse mind map JSON response (first 500 chars): %s", raw_map[:500])
        raise HTTPException(status_code=500, detail="Failed to parse mind map response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Mind map generation failed: %s: %s", type(e).__name__, e)
        detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=500, detail=detail[:500])

    # Deduplicate: return existing if same hash was created recently
    content_hash = study_service.compute_content_hash(f"Mind Map: {topic}", "mind_map", body.assignment_id)
    existing = study_service.find_recent_duplicate(current_user.id, content_hash)
    if existing:
        existing_data = MindMapData(**json.loads(existing.content))
        return MindMapResponse(
            id=existing.id, title=existing.title, mind_map=existing_data,
            guide_type="mind_map", version=existing.version,
            parent_guide_id=existing.parent_guide_id, created_at=existing.created_at,
        )

    # Increment AI usage only when creating NEW content
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(
        current_user, db, generation_type="mind_map", course_material_id=body.course_content_id,
        is_regeneration=bool(body.regenerate_from_id), **_usage,
    )

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, f"Mind Map: {topic}", content,
        course_id=body.course_id,
        course_content_id=body.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=body.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=f"Mind Map: {topic}",
        content=map_json,
        guide_type="mind_map",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
        focus_prompt=body.focus_prompt or None,
    )
    db.add(study_guide)
    db.flush()

    # Create a generic review task
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    critical_dates = [{"date": today_str, "title": f"Review: Mind Map: {topic}", "priority": "medium"}]
    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        resolved_course_id, resolved_cc_id,
    )

    db.commit()
    db.refresh(study_guide)

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    return MindMapResponse(
        id=study_guide.id,
        title=study_guide.title,
        mind_map=mind_map,
        guide_type="mind_map",
        version=study_guide.version,
        parent_guide_id=study_guide.parent_guide_id,
        created_at=study_guide.created_at,
        auto_created_tasks=[AutoCreatedTask(**t) for t in created_tasks],
    )


# ============================================
# Answer Key Generation (§18.2, #2957, #3021)
# ============================================


@router.post("/worksheets/{worksheet_id}/answer-key")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def generate_answer_key(
    worksheet_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an answer key for a worksheet and store it on the same row."""
    from app.schemas.study import AnswerKeyResponse

    # Look up the study guide
    guide = db.query(StudyGuide).filter(StudyGuide.id == worksheet_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Worksheet not found")

    # Validate guide_type is worksheet
    if guide.guide_type != "worksheet":
        raise HTTPException(status_code=400, detail="Study guide is not a worksheet")

    # Access control: owner or parent of owner
    has_access = guide.user_id == current_user.id
    if not has_access and current_user.role == UserRole.PARENT:
        children_user_ids = get_linked_children_user_ids(db, current_user.id)
        has_access = guide.user_id in children_user_ids
    if not has_access:
        raise HTTPException(status_code=404, detail="Worksheet not found")

    # Check AI usage (free, but still logged per PRD §18.2)
    check_ai_usage(current_user, db)

    # If already generated, return existing
    if guide.answer_key_markdown:
        return AnswerKeyResponse.model_validate(guide)

    # Generate answer key via AI
    system_prompt = (
        "You are an expert teacher creating an answer key for a student worksheet. "
        "Provide clear, numbered answers that match the worksheet questions exactly. "
        "For math problems, include step-by-step solutions showing all work. "
        "For English/French language questions, include brief explanations of why each answer is correct. "
        "Use clean Markdown formatting. Use LaTeX notation ($...$) for math expressions."
    )

    prompt = f"""Generate a complete answer key for the following worksheet.
Match each answer to its corresponding question number.

**Worksheet content:**
{guide.content}

Provide the full answer key in Markdown format:"""

    from app.services.ai_service import generate_content
    try:
        answer_key, _stop_reason = await generate_content(
            prompt, system_prompt, max_tokens=4096, temperature=0.3
        )
    except Exception as e:
        logger.error("Answer key generation failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"AI generation failed: {type(e).__name__}")

    # Store on the same row
    guide.answer_key_markdown = answer_key

    # Log usage with 0 credits (free per PRD §18.2)
    _usage = get_last_ai_usage() or {}
    log_ai_usage(
        current_user, db,
        generation_type="answer_key",
        credits_used=0,
        prompt_tokens=_usage.get("prompt_tokens"),
        completion_tokens=_usage.get("completion_tokens"),
        total_tokens=_usage.get("total_tokens"),
        estimated_cost_usd=_usage.get("estimated_cost_usd"),
        model_name=_usage.get("model_name"),
    )

    log_action(db, user_id=current_user.id, action="create", resource_type="answer_key", resource_id=guide.id)
    db.commit()
    db.refresh(guide)

    return AnswerKeyResponse.model_validate(guide)


# ============================================
# List / Get / Delete / Versions
# ============================================


@router.get("/guides", response_model=list[StudyGuideResponse])
def list_study_guides(
    guide_type: str | None = None,
    course_id: int | None = None,
    course_content_id: int | None = None,
    include_children: bool = False,
    include_archived: bool = False,
    student_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List study guides with role-based visibility.
    - Students: own guides + guides tagged to enrolled courses
    - Parents: own guides; with include_children=true also children's guides
    """
    if current_user.role == UserRole.STUDENT:
        enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
        query = db.query(StudyGuide).filter(
            or_(
                StudyGuide.user_id == current_user.id,
                and_(
                    StudyGuide.course_id.in_(enrolled_course_ids) if enrolled_course_ids else False,
                    StudyGuide.course_id.isnot(None),
                )
            )
        )
    elif current_user.role == UserRole.PARENT:
        # Parents see: own guides + all guides tagged to children's courses
        children_course_ids = get_children_course_ids(db, current_user.id, student_user_id)
        conditions = [StudyGuide.user_id == current_user.id]
        if children_course_ids:
            conditions.append(
                and_(
                    StudyGuide.course_id.in_(children_course_ids),
                    StudyGuide.course_id.isnot(None),
                )
            )
        if include_children:
            child_user_ids = get_linked_children_user_ids(db, current_user.id)
            if child_user_ids:
                conditions.append(StudyGuide.user_id.in_(child_user_ids))
        query = db.query(StudyGuide).filter(or_(*conditions))
    else:
        # Default: own guides only
        query = db.query(StudyGuide).filter(StudyGuide.user_id == current_user.id)

    if not include_archived:
        query = query.filter(StudyGuide.archived_at.is_(None))
    if guide_type:
        query = query.filter(StudyGuide.guide_type == guide_type)
    if course_id:
        query = query.filter(StudyGuide.course_id == course_id)
    if course_content_id:
        query = query.filter(StudyGuide.course_content_id == course_content_id)

    return query.order_by(StudyGuide.created_at.desc()).all()


def _maybe_translate_parent_summary(guide: StudyGuide, user: User, db: Session) -> StudyGuideResponse:
    """Build a StudyGuideResponse, translating parent_summary if the user prefers a non-English language."""
    resp = StudyGuideResponse.model_validate(guide)
    lang = user.preferred_language or "en"
    if lang == "en" or not guide.parent_summary:
        return resp

    # Check translation cache
    from app.models.translated_summary import TranslatedSummary
    cached = db.query(TranslatedSummary).filter(
        TranslatedSummary.study_guide_id == guide.id,
        TranslatedSummary.language == lang,
    ).first()
    if cached:
        resp.parent_summary = cached.translated_text
        return resp

    # Translate on demand and cache
    from app.services.translation_service import TranslationService
    translated = TranslationService.translate(guide.parent_summary, lang)
    if translated != guide.parent_summary:
        try:
            ts = TranslatedSummary(
                study_guide_id=guide.id,
                language=lang,
                translated_text=translated,
            )
            db.add(ts)
            db.commit()
        except Exception:
            db.rollback()
    resp.parent_summary = translated
    return resp


@router.get("/guides/{guide_id}", response_model=StudyGuideResponse)
def get_study_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific study guide with role-based access control."""
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)

    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        logger.info(f"Study guide {guide_id} not found in DB (user={current_user.id})")
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Owner always has access
    if guide.user_id == current_user.id:
        return _maybe_translate_parent_summary(guide, current_user, db)

    # Parent can view guides from children's courses or created by children
    if current_user.role == UserRole.PARENT:
        children_user_ids = get_linked_children_user_ids(db, current_user.id)
        if guide.user_id in children_user_ids:
            return _maybe_translate_parent_summary(guide, current_user, db)
        if guide.course_id:
            children_course_ids = get_children_course_ids(db, current_user.id)
            if guide.course_id in children_course_ids:
                return _maybe_translate_parent_summary(guide, current_user, db)

    # Student can view course-tagged guides for enrolled courses
    if current_user.role == UserRole.STUDENT and guide.course_id:
        enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
        if guide.course_id in enrolled_course_ids:
            return _maybe_translate_parent_summary(guide, current_user, db)

    logger.warning(f"Study guide {guide_id} access denied for user={current_user.id} role={current_user.role} (owner={guide.user_id})")
    raise HTTPException(status_code=404, detail="Study guide not found")


@router.get("/guides/{guide_id}/versions", response_model=list[StudyGuideResponse])
def list_guide_versions(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of a study guide."""
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Find the root guide
    root_id = guide.parent_guide_id if guide.parent_guide_id else guide.id

    # Get all versions (root + children)
    versions = (
        db.query(StudyGuide)
        .filter(
            or_(
                StudyGuide.id == root_id,
                StudyGuide.parent_guide_id == root_id,
            ),
            StudyGuide.user_id == current_user.id,
        )
        .order_by(StudyGuide.version.desc())
        .all()
    )

    if not versions:
        raise HTTPException(status_code=404, detail="Study guide not found")

    return versions


@router.get("/guides/{guide_id}/children", response_model=list[StudyGuideResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_child_guides(
    request: Request,
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sub-guides generated from this study guide."""
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Must be owner, parent of owner, admin, or shared-with user
    if guide.user_id != current_user.id:
        if current_user.role == UserRole.ADMIN or getattr(current_user, 'has_role', lambda r: False)(UserRole.ADMIN):
            pass  # Admin can see all
        elif guide.shared_with_user_id == current_user.id:
            pass  # Shared with this user
        elif current_user.role == UserRole.PARENT:
            child_ids = [r[0] for r in db.query(parent_students.c.student_id).filter(parent_students.c.parent_id == current_user.id).all()]
            child_user_ids = [r[0] for r in db.query(Student.user_id).filter(Student.id.in_(child_ids)).all()] if child_ids else []
            if guide.user_id not in child_user_ids:
                raise HTTPException(status_code=404, detail="Study guide not found")
        elif current_user.role == UserRole.STUDENT:
            # Students can see guides tagged to their enrolled courses
            if guide.course_id:
                enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
                if guide.course_id not in enrolled_course_ids:
                    raise HTTPException(status_code=404, detail="Study guide not found")
            else:
                raise HTTPException(status_code=404, detail="Study guide not found")
        else:
            raise HTTPException(status_code=404, detail="Study guide not found")

    # Query children where parent_guide_id = guide_id
    children = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.parent_guide_id == guide_id,
            StudyGuide.archived_at.is_(None),
        )
        .order_by(StudyGuide.created_at.desc())
        .all()
    )

    # Filter to only sub_guides (not version regenerations)
    # If relationship_type column exists, use it; otherwise include all
    result = []
    for child in children:
        rt = getattr(child, 'relationship_type', None)
        if rt is None or rt == 'sub_guide':
            result.append(child)

    return result


@router.get("/guides/{guide_id}/tree", response_model=StudyGuideTreeResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_study_guide_tree(
    request: Request,
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the full parent-child tree for a study guide."""
    # 1. Find the requested guide
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Access check — must be owner, parent of owner, admin, or shared-with user
    if guide.user_id != current_user.id:
        if current_user.role == UserRole.ADMIN or getattr(current_user, 'has_role', lambda r: False)(UserRole.ADMIN):
            pass
        elif guide.shared_with_user_id == current_user.id:
            pass
        elif current_user.role == UserRole.PARENT:
            child_ids = [r[0] for r in db.query(parent_students.c.student_id).filter(parent_students.c.parent_id == current_user.id).all()]
            child_user_ids = [r[0] for r in db.query(Student.user_id).filter(Student.id.in_(child_ids)).all()] if child_ids else []
            if guide.user_id not in child_user_ids:
                raise HTTPException(status_code=404, detail="Study guide not found")
        else:
            raise HTTPException(status_code=404, detail="Study guide not found")

    # 2. Walk up to root
    root = guide
    visited = {root.id}
    while root.parent_guide_id is not None:
        parent = db.query(StudyGuide).filter(StudyGuide.id == root.parent_guide_id).first()
        if not parent or parent.id in visited:
            break
        visited.add(parent.id)
        root = parent

    # 3. Build path from root to current guide
    current_path: list[int] = []

    def _find_path(node_id: int, target_id: int, path: list[int]) -> bool:
        path.append(node_id)
        if node_id == target_id:
            return True
        children = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.parent_guide_id == node_id,
                StudyGuide.archived_at.is_(None),
            )
            .all()
        )
        sub_guides = [c for c in children if getattr(c, 'relationship_type', None) in (None, 'sub_guide')]
        for child in sub_guides:
            if _find_path(child.id, target_id, path):
                return True
        path.pop()
        return False

    _find_path(root.id, guide_id, current_path)

    # 4. Build tree recursively from root
    def _build_node(sg: StudyGuide) -> StudyGuideTreeNode:
        children = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.parent_guide_id == sg.id,
                StudyGuide.archived_at.is_(None),
            )
            .order_by(StudyGuide.created_at.asc())
            .all()
        )
        sub_guides = [c for c in children if getattr(c, 'relationship_type', None) in (None, 'sub_guide')]
        return StudyGuideTreeNode(
            id=sg.id,
            title=sg.title,
            guide_type=sg.guide_type,
            created_at=sg.created_at,
            children=[_build_node(c) for c in sub_guides],
        )

    tree_root = _build_node(root)

    return StudyGuideTreeResponse(root=tree_root, current_path=current_path)


@router.post("/guides/{guide_id}/generate-child", response_model=StudyGuideResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_child_guide(
    request: Request,
    guide_id: int,
    body: GenerateChildRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a child sub-guide from selected text within a parent guide."""
    # Fetch parent guide and validate access (same logic as get_study_guide)
    parent_guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not parent_guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    has_access = False
    if parent_guide.user_id == current_user.id:
        has_access = True
    elif current_user.role == UserRole.PARENT:
        children_user_ids = get_linked_children_user_ids(db, current_user.id)
        if parent_guide.user_id in children_user_ids:
            has_access = True
        elif parent_guide.course_id:
            children_course_ids = get_children_course_ids(db, current_user.id)
            if parent_guide.course_id in children_course_ids:
                has_access = True
    elif current_user.role == UserRole.STUDENT and parent_guide.course_id:
        enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
        if parent_guide.course_id in enrolled_course_ids:
            has_access = True
    elif current_user.role == UserRole.ADMIN:
        has_access = True
    # Shared-with user
    if parent_guide.shared_with_user_id == current_user.id:
        has_access = True

    if not has_access:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # §6.106: Inherit document_type/study_goal from parent guide's course content
    if not body.document_type and parent_guide.course_content_id:
        parent_cc = db.query(CourseContent).filter(CourseContent.id == parent_guide.course_content_id).first()
        if parent_cc:
            if not body.document_type and getattr(parent_cc, 'document_type', None):
                body.document_type = parent_cc.document_type
            if not body.study_goal and getattr(parent_cc, 'study_goal', None):
                body.study_goal = parent_cc.study_goal
            if not body.study_goal_text and getattr(parent_cc, 'study_goal_text', None):
                body.study_goal_text = parent_cc.study_goal_text

    # Validate topic text safety
    safe, reason = check_content_safe(body.topic)
    if not safe:
        raise HTTPException(status_code=400, detail=reason)
    if body.custom_prompt:
        safe, reason = check_content_safe(body.custom_prompt)
        if not safe:
            raise HTTPException(status_code=400, detail=reason)

    # Check AI usage limit
    check_ai_usage(current_user, db)

    topic_preview = body.topic[:100]
    parent_content_truncated = parent_guide.content[:8000]

    # Deduplicate: check for existing sub-guide with same parent + topic
    title = f"{GUIDE_TYPE_LABELS.get(body.guide_type, 'Study Guide')}: {topic_preview}"
    existing_child = db.query(StudyGuide).filter(
        StudyGuide.user_id == current_user.id,
        StudyGuide.parent_guide_id == guide_id,
        StudyGuide.guide_type == body.guide_type,
        StudyGuide.generation_context == body.topic,
        StudyGuide.archived_at.is_(None),
    ).first()
    if existing_child:
        return StudyGuideResponse.model_validate(existing_child)

    study_service = StudyService(db)
    content_hash = study_service.compute_content_hash(title, body.guide_type, parent_guide.course_content_id)

    generated_content = ""
    is_truncated = False
    critical_dates: list[dict] = []

    # §6.106: Apply strategy context to sub-guide generation
    effective_custom_prompt = body.custom_prompt
    if body.document_type and not effective_custom_prompt:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        effective_custom_prompt = StudyGuideStrategyService.get_system_prompt(body.document_type)

    # problem_solver: inject the problem_solver template via service method
    if body.guide_type == "problem_solver" and not effective_custom_prompt:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        effective_custom_prompt = StudyGuideStrategyService.get_prompt_template(template_key="problem_solver")

    if body.guide_type in ("study_guide", "problem_solver"):
        try:
            raw_content, is_truncated = await generate_study_guide(
                assignment_title=f"Sub-guide: {topic_preview}",
                assignment_description=parent_content_truncated,
                course_name="General",
                focus_prompt=body.topic,
                custom_prompt=effective_custom_prompt,
                max_tokens=body.max_tokens or SUB_GUIDE_MAX_TOKENS,
            )
            raw_content, _ = parse_suggestion_topics(raw_content)
            raw_content, critical_dates = parse_critical_dates(raw_content)
            generated_content = raw_content
        except ValueError as e:
            from app.core.faq_errors import raise_with_faq_hint, AI_GENERATION_FAILED
            raise_with_faq_hint(status_code=500, detail=str(e), faq_code=AI_GENERATION_FAILED)
        except Exception as e:
            logger.error("Child study guide generation failed: %s: %s", type(e).__name__, e)
            detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
            raise HTTPException(status_code=500, detail=detail[:500])

    elif body.guide_type == "quiz":
        try:
            raw_quiz = await generate_quiz(
                topic=topic_preview,
                content=parent_content_truncated,
                focus_prompt=body.topic,
                num_questions=5,
            )
            raw_quiz, _ = parse_suggestion_topics(raw_quiz)
            raw_quiz, critical_dates = parse_critical_dates(raw_quiz)
            generated_content = strip_json_fences(raw_quiz)
            # Validate JSON parses
            json.loads(generated_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse child quiz JSON response")
            raise HTTPException(status_code=500, detail="Failed to parse quiz response")
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error("Child quiz generation failed: %s: %s", type(e).__name__, e)
            detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
            raise HTTPException(status_code=500, detail=detail[:500])

    elif body.guide_type == "flashcards":
        try:
            raw_cards = await generate_flashcards(
                topic=topic_preview,
                content=parent_content_truncated,
                focus_prompt=body.topic,
                num_cards=10,
            )
            raw_cards, _ = parse_suggestion_topics(raw_cards)
            raw_cards, critical_dates = parse_critical_dates(raw_cards)
            generated_content = strip_json_fences(raw_cards)
            # Validate JSON parses
            json.loads(generated_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse child flashcards JSON response")
            raise HTTPException(status_code=500, detail="Failed to parse flashcards response")
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error("Child flashcards generation failed: %s: %s", type(e).__name__, e)
            detail = f"AI generation failed: {type(e).__name__}: {str(e)}"
            raise HTTPException(status_code=500, detail=detail[:500])

    # Increment AI usage
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(
        current_user, db, generation_type=body.guide_type,
        is_regeneration=False, **_usage,
    )

    # Enforce limit and save
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        course_id=parent_guide.course_id,
        course_content_id=parent_guide.course_content_id,
        title=title,
        content=generated_content,
        guide_type=body.guide_type,
        version=1,
        parent_guide_id=guide_id,
        relationship_type="sub_guide",
        generation_context=body.topic,
        focus_prompt=body.custom_prompt,
        is_truncated=is_truncated,
        content_hash=content_hash,
    )
    db.add(study_guide)
    db.flush()

    # Auto-create tasks
    if not critical_dates:
        critical_dates = scan_content_for_dates(generated_content, title)
    if not critical_dates:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        critical_dates = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]

    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        parent_guide.course_id, parent_guide.course_content_id,
    )

    log_action(db, user_id=current_user.id, action="create", resource_type="study_guide", resource_id=study_guide.id, details={"guide_type": body.guide_type, "parent_guide_id": guide_id, "relationship_type": "sub_guide", "auto_tasks": len(created_tasks)})
    db.commit()
    db.refresh(study_guide)

    # §6.106: Generate parent summary for sub-guide
    if body.document_type or body.study_goal:
        try:
            from app.services.parent_summary import ParentSummaryService
            parent_summary = await ParentSummaryService.generate(
                study_guide_content=generated_content,
                student_name=current_user.full_name,
                subject=parent_guide.course.name if parent_guide.course else None,
                document_type=body.document_type,
                study_goal=body.study_goal,
            )
            if parent_summary:
                study_guide.parent_summary = parent_summary
                db.commit()
        except Exception as e:
            logger.warning(f"Sub-guide parent summary generation failed: {e}")

    resp = StudyGuideResponse.model_validate(study_guide)
    resp.auto_created_tasks = [AutoCreatedTask(**t) for t in created_tasks]
    return resp


@router.post("/guides/{guide_id}/generate-child-stream")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_child_guide_stream(
    request: Request,
    guide_id: int,
    body: GenerateChildRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a child sub-guide via SSE. Returns existing JSON if dedup hit."""
    # Fetch parent guide and validate access (same as generate_child_guide)
    parent_guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not parent_guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    has_access = False
    if parent_guide.user_id == current_user.id:
        has_access = True
    elif current_user.role == UserRole.PARENT:
        children_user_ids = get_linked_children_user_ids(db, current_user.id)
        if parent_guide.user_id in children_user_ids:
            has_access = True
        elif parent_guide.course_id:
            children_course_ids = get_children_course_ids(db, current_user.id)
            if parent_guide.course_id in children_course_ids:
                has_access = True
    elif current_user.role == UserRole.STUDENT and parent_guide.course_id:
        enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
        if parent_guide.course_id in enrolled_course_ids:
            has_access = True
    elif current_user.role == UserRole.ADMIN:
        has_access = True
    if parent_guide.shared_with_user_id == current_user.id:
        has_access = True
    if not has_access:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Only study_guide and problem_solver types support streaming; others fall back to non-streaming
    if body.guide_type not in ("study_guide", "problem_solver"):
        return await generate_child_guide(request, guide_id, body, db, current_user)

    # Inherit document_type/study_goal from parent's course content
    if not body.document_type and parent_guide.course_content_id:
        parent_cc = db.query(CourseContent).filter(CourseContent.id == parent_guide.course_content_id).first()
        if parent_cc:
            if not body.document_type and getattr(parent_cc, 'document_type', None):
                body.document_type = parent_cc.document_type
            if not body.study_goal and getattr(parent_cc, 'study_goal', None):
                body.study_goal = parent_cc.study_goal
            if not body.study_goal_text and getattr(parent_cc, 'study_goal_text', None):
                body.study_goal_text = parent_cc.study_goal_text

    # Validate safety
    safe, reason = check_content_safe(body.topic)
    if not safe:
        raise HTTPException(status_code=400, detail=reason)
    if body.custom_prompt:
        safe, reason = check_content_safe(body.custom_prompt)
        if not safe:
            raise HTTPException(status_code=400, detail=reason)

    check_ai_usage(current_user, db)

    topic_preview = body.topic[:100]
    parent_content_truncated = parent_guide.content[:8000]

    title = f"{GUIDE_TYPE_LABELS.get(body.guide_type, 'Study Guide')}: {topic_preview}"

    # Dedup check — return existing as plain JSON (not SSE)
    existing_child = db.query(StudyGuide).filter(
        StudyGuide.user_id == current_user.id,
        StudyGuide.parent_guide_id == guide_id,
        StudyGuide.guide_type == body.guide_type,
        StudyGuide.generation_context == body.topic,
        StudyGuide.archived_at.is_(None),
    ).first()
    if existing_child:
        return JSONResponse(content=StudyGuideResponse.model_validate(existing_child).model_dump(mode="json"))

    # Strategy context
    effective_custom_prompt = body.custom_prompt
    if body.document_type and not effective_custom_prompt:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        effective_custom_prompt = StudyGuideStrategyService.get_system_prompt(body.document_type)

    # problem_solver: inject the problem_solver template via service method
    if body.guide_type == "problem_solver" and not effective_custom_prompt:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        effective_custom_prompt = StudyGuideStrategyService.get_prompt_template(template_key="problem_solver")

    study_service = StudyService(db)
    content_hash = study_service.compute_content_hash(title, body.guide_type, parent_guide.course_content_id)

    # Create placeholder record
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        course_id=parent_guide.course_id,
        course_content_id=parent_guide.course_content_id,
        title=title,
        content="",
        guide_type=body.guide_type,
        version=1,
        parent_guide_id=guide_id,
        relationship_type="sub_guide",
        generation_context=body.topic,
        focus_prompt=body.custom_prompt,
        is_truncated=False,
        content_hash=content_hash,
    )
    db.add(study_guide)
    db.commit()
    db.refresh(study_guide)
    child_guide_id = study_guide.id

    # Capture values before closing DB
    user_id = current_user.id
    parent_course_id = parent_guide.course_id
    parent_cc_id = parent_guide.course_content_id
    doc_type = body.document_type
    study_goal_val = body.study_goal
    study_goal_text_val = body.study_goal_text
    max_tokens = body.max_tokens or SUB_GUIDE_MAX_TOKENS

    db.close()

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'guide_id': child_guide_id})}\n\n"

        full_content = ""
        is_truncated = False

        try:
            async for event in generate_study_guide_stream(
                assignment_title=f"Sub-guide: {topic_preview}",
                assignment_description=parent_content_truncated,
                course_name="General",
                focus_prompt=body.topic,
                custom_prompt=effective_custom_prompt,
                max_tokens=max_tokens,
            ):
                if event["event"] == "chunk":
                    yield f"event: chunk\ndata: {json.dumps({'text': event['data']})}\n\n"
                elif event["event"] == "done":
                    full_content = event["data"]["full_content"]
                    is_truncated = event["data"]["is_truncated"]
                elif event["event"] == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event['data']})}\n\n"
                    return
        except Exception as e:
            logger.error("SSE child guide stream failed: %s: %s", type(e).__name__, e)
            _cleanup_empty_guide(child_guide_id, logger)
            # Log activity for failed generation (#3076)
            try:
                from app.db.database import SessionLocal
                with SessionLocal() as log_db:
                    log_action(log_db, user_id=user_id, action="error", resource_type="study_guide",
                               resource_id=child_guide_id, details=f"Stream generation failed: {type(e).__name__}: {e}")
            except Exception:
                pass  # Don't let logging failure mask the original error
            yield f"event: error\ndata: {json.dumps({'message': 'AI generation failed. Please try again.'})}\n\n"
            return

        # Post-process
        processed_content, suggestion_topics = parse_suggestion_topics(full_content)
        processed_content, critical_dates = parse_critical_dates(processed_content)

        # Save in new DB session
        try:
            from app.db.database import SessionLocal
            with SessionLocal() as save_db:
                guide = save_db.get(StudyGuide, child_guide_id)
                if guide:
                    guide.content = processed_content
                    guide.is_truncated = is_truncated
                    if suggestion_topics:
                        guide.suggestion_topics = json.dumps(suggestion_topics)

                    from app.models.user import User as _User
                    user = save_db.get(_User, user_id)
                    if user:
                        _usage = get_last_ai_usage() or {}
                        increment_ai_usage(
                            user, save_db, generation_type="study_guide",
                            is_regeneration=False, **_usage,
                        )

                    # Auto-create tasks
                    if not critical_dates:
                        critical_dates_inner = scan_content_for_dates(processed_content, title)
                    else:
                        critical_dates_inner = critical_dates
                    if not critical_dates_inner:
                        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        critical_dates_inner = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]

                    created_tasks = auto_create_tasks_from_dates(
                        save_db, critical_dates_inner, user, guide.id,
                        parent_course_id, parent_cc_id,
                    )

                    log_action(save_db, user_id=user_id, action="create", resource_type="study_guide",
                               resource_id=guide.id,
                               details={"guide_type": "study_guide", "parent_guide_id": guide_id,
                                        "relationship_type": "sub_guide", "auto_tasks": len(created_tasks),
                                        "streamed": True})
                    save_db.commit()
                    save_db.refresh(guide)

                    # Award XP
                    try:
                        from app.services.xp_service import XpService
                        XpService.award_xp(save_db, user_id, "study_guide")
                    except Exception as e:
                        logger.warning(f"XP award failed (non-blocking): {e}")

                    resp = StudyGuideResponse.model_validate(guide)
                    resp.auto_created_tasks = [AutoCreatedTask(**t) for t in created_tasks]
                    yield f"event: done\ndata: {json.dumps(resp.model_dump(mode='json'))}\n\n"
                else:
                    yield f"event: error\ndata: {json.dumps({'message': 'Guide record not found after streaming.'})}\n\n"
        except Exception as e:
            logger.error("Failed to save streamed child guide: %s: %s", type(e).__name__, e)
            yield f"event: error\ndata: {json.dumps({'message': 'Failed to save sub-guide. Please try again.'})}\n\n"

    return _StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/guides/{guide_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete (archive) a study guide (owner or parent of owner)."""
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    # Owner can always archive; parents can archive their children's guides
    if guide.user_id != current_user.id:
        if current_user.role == UserRole.PARENT:
            child_user_ids = get_linked_children_user_ids(db, current_user.id)
            if guide.user_id not in child_user_ids:
                raise HTTPException(status_code=404, detail="Study guide not found")
        else:
            raise HTTPException(status_code=404, detail="Study guide not found")
    guide.archived_at = datetime.now(timezone.utc)
    log_action(db, user_id=current_user.id, action="archive", resource_type="study_guide", resource_id=guide_id)
    db.commit()
    return None


@router.patch("/guides/{guide_id}/restore", response_model=StudyGuideResponse)
def restore_study_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore an archived study guide (owner only)."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    if guide.archived_at is None:
        raise HTTPException(status_code=400, detail="Study guide is not archived")
    guide.archived_at = None
    db.commit()
    db.refresh(guide)
    return guide


@router.delete("/guides/{guide_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete_study_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete an archived study guide (owner only)."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    if guide.archived_at is None:
        raise HTTPException(status_code=400, detail="Study guide must be archived before permanent deletion")
    db.delete(guide)
    log_action(db, user_id=current_user.id, action="delete", resource_type="study_guide", resource_id=guide_id)
    db.commit()
    return None


@router.patch("/guides/{guide_id}", response_model=StudyGuideResponse)
def update_study_guide(
    guide_id: int,
    update: StudyGuideUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a study guide (owner only). Supports assigning/categorizing to a course."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    if update.title is not None:
        guide.title = update.title

    if update.course_id is not None or update.course_content_id is not None:
        resolved_course_id, resolved_cc_id = ensure_course_and_content(
            db, current_user, guide.title, guide.content,
            course_id=update.course_id or guide.course_id,
            course_content_id=update.course_content_id,
        )
        guide.course_id = resolved_course_id
        guide.course_content_id = resolved_cc_id

    db.commit()
    db.refresh(guide)
    return guide


# ============================================
# File Upload Endpoints
# ============================================


@router.get("/upload/formats")
def get_upload_formats():
    """Get information about supported file upload formats."""
    return get_supported_formats()


@router.post("/generate-with-images", response_model=StudyGuideResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def generate_from_text_and_images(
    request: Request,
    content: str = Form(""),
    title: Optional[str] = Form(None),
    guide_type: str = Form("study_guide"),
    num_questions: int = Form(5),
    num_cards: int = Form(10),
    course_id: Optional[int] = Form(None),
    course_content_id: Optional[int] = Form(None),
    focus_prompt: Optional[str] = Form(None),
    difficulty: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate study material from pasted text content combined with pasted images.
    Images are OCR'd via Vision API and the extracted text is combined with the
    user's pasted text content for AI generation.

    Maximum 10 images, each up to 10 MB.
    """
    study_service = StudyService(db)

    if guide_type not in ("study_guide", "quiz", "flashcards"):
        raise HTTPException(
            status_code=400,
            detail="guide_type must be one of: study_guide, quiz, flashcards"
        )

    # Validate and read image data
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images allowed")

    image_bytes_list = []
    for img in images:
        img_data = await img.read()
        if len(img_data) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"Image '{img.filename}' exceeds 10 MB limit"
            )
        if img_data:
            image_bytes_list.append(img_data)

    # OCR images via Vision API
    ocr_parts = []
    if image_bytes_list:
        ocr_parts = _ocr_images_with_vision(image_bytes_list)

    # Combine pasted text + OCR extracted text
    combined_parts = []
    if content.strip():
        combined_parts.append(content.strip())
    if ocr_parts:
        combined_parts.append("--- Extracted from images ---")
        combined_parts.extend(ocr_parts)

    extracted_text = "\n\n".join(combined_parts)

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No content provided. Please paste text or include images with readable content."
        )

    # Gate: reject content shorter than MIN_EXTRACTION_CHARS (#2217)
    if len(extracted_text.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Safety-check all user-provided text inputs (#2213)
    for text_input in [focus_prompt, extracted_text]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    if not title:
        # Generate a sensible default title from the first line of content
        first_line = content.strip().split('\n')[0][:60] if content.strip() else "Pasted Content"
        title = first_line if first_line else "Pasted Content"

    # Check AI usage limit before generation
    check_ai_usage(current_user, db)

    # Fetch image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, course_content_id)

    # Generate the appropriate study material (same pattern as /upload/generate)
    critical_dates = []
    try:
        if guide_type == "quiz":
            raw_quiz = await generate_quiz(
                topic=title,
                content=extracted_text,
                num_questions=num_questions,
                focus_prompt=focus_prompt,
                difficulty=difficulty,
                images=images_metadata,
                interests=_get_user_interests(current_user),
            )
            # Post-process to add unplaced images (before critical dates extraction)
            if images_metadata:
                raw_quiz = _append_unplaced_images(raw_quiz, images_metadata)
            raw_quiz, critical_dates = parse_critical_dates(raw_quiz)
            quiz_json = strip_json_fences(raw_quiz)
            questions_data = json.loads(quiz_json)
            questions = [QuizQuestion(**q) for q in questions_data]

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Quiz: {title}",
                content=quiz_json,
                guide_type="quiz",
                content_hash=study_service.compute_content_hash(f"Quiz: {title}", "quiz"),
                focus_prompt=focus_prompt or None,
            )

        elif guide_type == "flashcards":
            raw_cards = await generate_flashcards(
                topic=title,
                content=extracted_text,
                num_cards=num_cards,
                focus_prompt=focus_prompt,
                images=images_metadata,
                interests=_get_user_interests(current_user),
            )
            # Post-process to add unplaced images (before critical dates extraction)
            if images_metadata:
                raw_cards = _append_unplaced_images(raw_cards, images_metadata)
            raw_cards, critical_dates = parse_critical_dates(raw_cards)
            cards_json = strip_json_fences(raw_cards)
            cards_data = json.loads(cards_json)
            cards = [Flashcard(**c) for c in cards_data]

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Flashcards: {title}",
                content=cards_json,
                guide_type="flashcards",
                content_hash=study_service.compute_content_hash(f"Flashcards: {title}", "flashcards"),
                focus_prompt=focus_prompt or None,
            )

        else:  # study_guide
            raw_content, is_truncated = await generate_study_guide(
                assignment_title=title,
                assignment_description=extracted_text,
                course_name="Pasted Content",
                focus_prompt=focus_prompt,
                images=images_metadata,
                interests=_get_user_interests(current_user),
            )
            content_result, critical_dates = parse_critical_dates(raw_content)
            # Post-process to add unplaced images
            if images_metadata:
                content_result = _append_unplaced_images(content_result, images_metadata)

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Study Guide: {title}",
                content=content_result,
                guide_type="study_guide",
                content_hash=study_service.compute_content_hash(f"Study Guide: {title}", "study_guide"),
                focus_prompt=focus_prompt or None,
                is_truncated=is_truncated,
            )

    except json.JSONDecodeError:
        raw = locals().get("raw_quiz") or locals().get("raw_cards") or ""
        logger.error("Failed to parse AI JSON response from paste (first 500 chars): %s", raw[:500])
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Deduplicate: return existing if same hash was created recently
    if study_guide.content_hash:
        existing = study_service.find_recent_duplicate(current_user.id, study_guide.content_hash)
        if existing:
            return existing

    # Increment AI usage only when creating NEW content
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(current_user, db, generation_type=guide_type, course_material_id=course_content_id, **_usage)

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, title, extracted_text,
        course_id=course_id,
        course_content_id=course_content_id,
    )
    study_guide.course_id = resolved_course_id
    study_guide.course_content_id = resolved_cc_id

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    db.add(study_guide)
    db.flush()

    # Auto-create tasks from critical dates (or fallback review task)
    if not critical_dates:
        critical_dates = scan_content_for_dates(extracted_text, title)
    if not critical_dates:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        critical_dates = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]

    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        resolved_course_id, resolved_cc_id,
    )

    db.commit()
    db.refresh(study_guide)

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    resp = StudyGuideResponse.model_validate(study_guide)
    resp.auto_created_tasks = [AutoCreatedTask(**t) for t in created_tasks]
    return resp


@router.post("/upload/generate", response_model=StudyGuideResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def generate_from_file_upload(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    guide_type: str = Form("study_guide"),
    num_questions: int = Form(5),
    num_cards: int = Form(10),
    course_id: Optional[int] = Form(None),
    course_content_id: Optional[int] = Form(None),
    focus_prompt: Optional[str] = Form(None),
    difficulty: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate study material from an uploaded file.

    Supports: PDF, DOCX, PPTX, XLSX, TXT, images (OCR), and ZIP archives.
    Maximum file size: 100 MB.
    """
    study_service = StudyService(db)

    if guide_type not in ("study_guide", "quiz", "flashcards"):
        raise HTTPException(
            status_code=400,
            detail="guide_type must be one of: study_guide, quiz, flashcards"
        )

    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    stored_path = save_file(file_content, file.filename or "unknown")

    try:
        extracted_text = process_file(file_content, file.filename or "unknown")
    except FileProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from the uploaded file"
        )

    # Gate: reject content shorter than MIN_EXTRACTION_CHARS (#2217)
    if len(extracted_text.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Safety-check all user-provided text inputs (#2213)
    for text_input in [focus_prompt, extracted_text]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    if not title:
        base_name = file.filename.rsplit('.', 1)[0] if file.filename else "Uploaded File"
        title = base_name

    # Check AI usage limit before generation
    check_ai_usage(current_user, db)

    # Fetch image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, course_content_id)

    # Generate the appropriate study material
    critical_dates = []
    try:
        if guide_type == "quiz":
            raw_quiz = await generate_quiz(
                topic=title,
                content=extracted_text,
                num_questions=num_questions,
                focus_prompt=focus_prompt,
                difficulty=difficulty,
                images=images_metadata,
                interests=_get_user_interests(current_user),
            )
            # Post-process to add unplaced images (before critical dates extraction)
            if images_metadata:
                raw_quiz = _append_unplaced_images(raw_quiz, images_metadata)
            raw_quiz, critical_dates = parse_critical_dates(raw_quiz)
            quiz_json = strip_json_fences(raw_quiz)
            questions_data = json.loads(quiz_json)
            questions = [QuizQuestion(**q) for q in questions_data]

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Quiz: {title}",
                content=quiz_json,
                guide_type="quiz",
                content_hash=study_service.compute_content_hash(f"Quiz: {title}", "quiz"),
                focus_prompt=focus_prompt or None,
            )

        elif guide_type == "flashcards":
            raw_cards = await generate_flashcards(
                topic=title,
                content=extracted_text,
                num_cards=num_cards,
                focus_prompt=focus_prompt,
                images=images_metadata,
                interests=_get_user_interests(current_user),
            )
            # Post-process to add unplaced images (before critical dates extraction)
            if images_metadata:
                raw_cards = _append_unplaced_images(raw_cards, images_metadata)
            raw_cards, critical_dates = parse_critical_dates(raw_cards)
            cards_json = strip_json_fences(raw_cards)
            cards_data = json.loads(cards_json)
            cards = [Flashcard(**c) for c in cards_data]

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Flashcards: {title}",
                content=cards_json,
                guide_type="flashcards",
                content_hash=study_service.compute_content_hash(f"Flashcards: {title}", "flashcards"),
                focus_prompt=focus_prompt or None,
            )

        else:  # study_guide
            raw_content, is_truncated = await generate_study_guide(
                assignment_title=title,
                assignment_description=extracted_text,
                course_name="Uploaded Content",
                focus_prompt=focus_prompt,
                images=images_metadata,
                interests=_get_user_interests(current_user),
            )
            content, critical_dates = parse_critical_dates(raw_content)
            # Post-process to add unplaced images
            if images_metadata:
                content = _append_unplaced_images(content, images_metadata)

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Study Guide: {title}",
                content=content,
                guide_type="study_guide",
                content_hash=study_service.compute_content_hash(f"Study Guide: {title}", "study_guide"),
                focus_prompt=focus_prompt or None,
                is_truncated=is_truncated,
            )

    except json.JSONDecodeError:
        raw = locals().get("raw_quiz") or locals().get("raw_cards") or ""
        logger.error("Failed to parse AI JSON response from upload (first 500 chars): %s", raw[:500])
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Deduplicate: return existing if same hash was created recently
    if study_guide.content_hash:
        existing = study_service.find_recent_duplicate(current_user.id, study_guide.content_hash)
        if existing:
            return existing

    # Increment AI usage only when creating NEW content
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(current_user, db, generation_type=guide_type, course_material_id=course_content_id, **_usage)

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, title, extracted_text,
        course_id=course_id,
        course_content_id=course_content_id,
    )
    study_guide.course_id = resolved_course_id
    study_guide.course_content_id = resolved_cc_id

    # Attach file metadata to CourseContent record
    if resolved_cc_id:
        cc_rec = db.query(CourseContent).filter(CourseContent.id == resolved_cc_id).first()
        if cc_rec and not cc_rec.file_path:
            cc_rec.file_path = stored_path
            cc_rec.original_filename = file.filename
            cc_rec.file_size = len(file_content)
            cc_rec.mime_type = file.content_type

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    db.add(study_guide)
    db.flush()

    # Auto-create tasks from critical dates (or fallback review task)
    if not critical_dates:
        critical_dates = scan_content_for_dates(extracted_text, title)
    if not critical_dates:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        critical_dates = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]

    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        resolved_course_id, resolved_cc_id,
    )

    db.commit()
    db.refresh(study_guide)

    # Award XP for file upload generation (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "upload")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    resp = StudyGuideResponse.model_validate(study_guide)
    resp.auto_created_tasks = [AutoCreatedTask(**t) for t in created_tasks]
    return resp


@router.post("/upload/extract-text")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def extract_text_from_upload(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Extract text from an uploaded file without generating study material."""
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    try:
        extracted_text = process_file(file_content, file.filename or "unknown")
    except FileProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "filename": file.filename,
        "text": extracted_text,
        "character_count": len(extracted_text),
        "word_count": len(extracted_text.split()),
    }


# ---------------------------------------------------------------------------
# §6.114 — Study Guide Contextual Q&A save endpoints
# ---------------------------------------------------------------------------

_AI_UNCERTAINTY_PHRASES = [
    "i'm not sure", "i don't know", "could you clarify", "not clear",
    "doesn't appear", "cannot find", "i don't have", "unclear",
    "i'm unable to", "i cannot determine", "not enough information",
    "i'm not certain",
]


def _has_ai_uncertainty(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _AI_UNCERTAINTY_PHRASES)

@router.post("/guides/{guide_id}/qa/save-as-guide", response_model=StudyGuideResponse)
async def save_qa_as_guide(
    guide_id: int,
    request: SaveQAAsGuideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a Q&A response as a sub-guide. No AI credits consumed."""

    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    if guide.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the guide owner")
    if _has_ai_uncertainty(request.content):
        raise HTTPException(status_code=422, detail="Cannot save an uncertain AI response as a study guide")

    title = request.title.strip() if request.title else f"Q&A: {guide.title}"
    new_guide = StudyGuide(
        user_id=current_user.id,
        title=title[:255],
        content=request.content,
        guide_type="study_guide",
        course_id=guide.course_id,
        course_content_id=guide.course_content_id,
        parent_guide_id=guide.id,
        relationship_type="sub_guide",
        generation_context="Q&A response",
        version=1,
    )
    db.add(new_guide)
    db.commit()
    db.refresh(new_guide)

    log_action(db, current_user.id, "study_guide_create", "study_guide", new_guide.id,
               details=f"Saved Q&A response as sub-guide of #{guide_id}")

    return StudyGuideResponse.model_validate(new_guide)


@router.post("/guides/{guide_id}/qa/save-as-material")
async def save_qa_as_material(
    guide_id: int,
    request: SaveQAAsMaterialRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a Q&A response as a course material. No AI credits consumed."""

    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    if guide.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the guide owner")
    if not guide.course_id:
        raise HTTPException(status_code=400, detail="Study guide has no associated course")
    if _has_ai_uncertainty(request.content):
        raise HTTPException(status_code=422, detail="Cannot save an uncertain AI response as course material")

    title = request.title.strip() if request.title else f"Q&A Notes: {guide.title}"
    new_content = CourseContent(
        course_id=guide.course_id,
        title=title[:255],
        text_content=request.content,
        content_type="notes",
        created_by_user_id=current_user.id,
    )
    db.add(new_content)
    db.commit()
    db.refresh(new_content)

    log_action(db, current_user.id, "course_content_create", "course_content", new_content.id,
               details=f"Saved Q&A response as course material from guide #{guide_id}")

    return {
        "id": new_content.id,
        "title": new_content.title,
        "course_id": new_content.course_id,
        "content_type": new_content.content_type,
    }


# ============================================
# Streaming Generation Endpoint
# ============================================


@router.post("/generate-stream")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_study_guide_stream_endpoint(
    request: Request,
    body: StudyGuideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a study guide via SSE. Same logic as /generate but returns tokens incrementally."""

    # --- Pre-checks (same as /generate) ---
    # Safety-check all user-provided text inputs
    for text_input in [body.focus_prompt, body.custom_prompt, body.content]:
        if text_input:
            safe, reason = check_content_safe(text_input)
            if not safe:
                raise HTTPException(status_code=400, detail=reason)

    study_service = StudyService(db)

    # Handle versioning
    version = 1
    parent_guide_id = None
    if body.regenerate_from_id:
        parent_guide_id, version = study_service.get_version_info(body.regenerate_from_id, current_user.id)

    # Inherit document_type/study_goal from parent guide's course content on regeneration
    if body.regenerate_from_id and not body.document_type:
        parent_guide = db.query(StudyGuide).filter(StudyGuide.id == body.regenerate_from_id).first()
        if parent_guide and parent_guide.course_content_id:
            parent_cc = db.query(CourseContent).filter(CourseContent.id == parent_guide.course_content_id).first()
            if parent_cc:
                if not body.document_type and getattr(parent_cc, 'document_type', None):
                    body.document_type = parent_cc.document_type
                if not body.study_goal and getattr(parent_cc, 'study_goal', None):
                    body.study_goal = parent_cc.study_goal
                if not body.study_goal_text and getattr(parent_cc, 'study_goal_text', None):
                    body.study_goal_text = parent_cc.study_goal_text

    # Resolve source content
    assignment = None
    course = None
    title = body.title or "Study Guide"
    description = body.content or ""

    if body.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == body.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if assignment.course_id and not can_access_course(db, current_user, assignment.course_id):
            raise HTTPException(status_code=403, detail="No access to this assignment's course")
        title = f"Study Guide: {assignment.title}"
        description = assignment.description or ""
        course = assignment.course

    if not description and body.course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
        if cc:
            description = cc.text_content or cc.description or ""
            if not title or title == "Study Guide":
                title = f"Study Guide: {cc.title}"
            if not course and cc.course_id:
                course = db.query(Course).filter(Course.id == cc.course_id).first()

    if body.course_id and not course:
        course = db.query(Course).filter(Course.id == body.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if not can_access_course(db, current_user, body.course_id):
            raise HTTPException(status_code=403, detail="No access to this course")

    course_name = course.name if course else "General"
    due_date = str(assignment.due_date) if assignment and assignment.due_date else None

    if not description:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate a study guide",
        )

    # Parent question guards: role check, min-length, prefix, auto-title (#2861)
    description, title = _apply_parent_question_guards(body, description, title, current_user)

    # Gate: reject non-question content shorter than MIN_EXTRACTION_CHARS (#2217)
    if body.document_type != "parent_question" and len(description.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Check AI usage limit
    check_ai_usage(current_user, db)

    # Image metadata for prompt enrichment
    images_metadata = _get_images_metadata(db, body.course_content_id)

    # Strategy pattern: select prompt template
    strategy_system_prompt = None
    if body.document_type or body.study_goal:
        from app.services.study_guide_strategy import StudyGuideStrategyService
        strategy_system_prompt = StudyGuideStrategyService.get_system_prompt(body.document_type)

    # Deduplicate check
    content_hash = study_service.compute_content_hash(title, "study_guide", body.assignment_id)
    existing = study_service.find_recent_duplicate(current_user.id, content_hash)
    if existing:
        return existing

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, title, description,
        course_id=body.course_id or (course.id if course else None),
        course_content_id=body.course_content_id,
    )

    # Enforce limit and create DB record early with empty content
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=body.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=title,
        content="",
        guide_type="study_guide",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
        focus_prompt=body.focus_prompt or None,
        is_truncated=False,
    )
    db.add(study_guide)
    db.commit()
    db.refresh(study_guide)
    guide_id = study_guide.id

    # Capture values needed during streaming before closing DB
    user_id = current_user.id
    user_interests = _get_user_interests(current_user)
    user_full_name = current_user.full_name
    user_role = current_user.role
    cc_id = body.course_content_id
    doc_type = body.document_type
    study_goal_val = body.study_goal
    study_goal_text_val = body.study_goal_text

    # Close DB session before streaming to avoid connection pool exhaustion
    db.close()

    async def event_stream():
        # Emit start event with guide_id
        yield f"event: start\ndata: {json.dumps({'guide_id': guide_id})}\n\n"

        full_content = ""
        is_truncated = False

        try:
            async for event in generate_study_guide_stream(
                assignment_title=title,
                assignment_description=description,
                course_name=course_name,
                due_date=due_date,
                custom_prompt=body.custom_prompt,
                focus_prompt=body.focus_prompt,
                images=images_metadata,
                interests=user_interests,
                document_type=doc_type,
                study_goal=study_goal_val,
                study_goal_text=study_goal_text_val,
                max_tokens=get_max_tokens_for_document_type(doc_type),
            ):
                if event["event"] == "chunk":
                    yield f"event: chunk\ndata: {json.dumps({'text': event['data']})}\n\n"
                elif event["event"] == "done":
                    full_content = event["data"]["full_content"]
                    is_truncated = event["data"]["is_truncated"]
                elif event["event"] == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event['data']})}\n\n"
                    return

        except Exception as e:
            logger.error("SSE study guide stream failed: %s: %s", type(e).__name__, e)
            _cleanup_empty_guide(guide_id, logger)
            # Log activity for failed generation (#3076)
            try:
                from app.db.database import SessionLocal
                with SessionLocal() as log_db:
                    log_action(log_db, user_id=user_id, action="error", resource_type="study_guide",
                               resource_id=guide_id, details=f"Stream generation failed: {type(e).__name__}: {e}")
            except Exception:
                pass  # Don't let logging failure mask the original error
            yield f"event: error\ndata: {json.dumps({'message': 'AI generation failed. Please try again.'})}\n\n"
            return

        # Post-process: parse critical dates, append unplaced images
        processed_content, suggestion_topics = parse_suggestion_topics(full_content)
        processed_content, critical_dates = parse_critical_dates(processed_content)
        if images_metadata:
            processed_content = _append_unplaced_images(processed_content, images_metadata)

        # Save completed content in a NEW DB session
        try:
            from app.db.database import SessionLocal
            with SessionLocal() as save_db:
                guide = save_db.get(StudyGuide, guide_id)
                if guide:
                    guide.content = processed_content
                    guide.is_truncated = is_truncated
                    guide.content_hash = content_hash
                    if suggestion_topics:
                        guide.suggestion_topics = json.dumps(suggestion_topics)

                    # Debit AI usage
                    from app.models.user import User as _User
                    user = save_db.get(_User, user_id)
                    if user:
                        increment_ai_usage(
                            user, save_db, generation_type="study_guide",
                            course_material_id=cc_id,
                            is_regeneration=bool(body.regenerate_from_id),
                        )

                    # Auto-create tasks from critical dates
                    if not critical_dates:
                        critical_dates_inner = scan_content_for_dates(description, title)
                    else:
                        critical_dates_inner = critical_dates
                    if not critical_dates_inner:
                        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        critical_dates_inner = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]

                    created_tasks = auto_create_tasks_from_dates(
                        save_db, critical_dates_inner, user, guide.id,
                        resolved_course_id, resolved_cc_id,
                    )

                    log_action(save_db, user_id=user_id, action="create", resource_type="study_guide",
                               resource_id=guide.id,
                               details={"guide_type": "study_guide", "auto_tasks": len(created_tasks), "streamed": True})
                    save_db.commit()
                    save_db.refresh(guide)

                    # Award XP (non-blocking)
                    try:
                        from app.services.xp_service import XpService
                        XpService.award_xp(save_db, user_id, "study_guide")
                    except Exception as e:
                        logger.warning(f"XP award failed (non-blocking): {e}")

                    # Persist document_type and study_goal on course content
                    if cc_id and (doc_type or study_goal_val):
                        try:
                            cc_obj = save_db.query(CourseContent).filter(CourseContent.id == cc_id).first()
                            if cc_obj:
                                if doc_type:
                                    cc_obj.document_type = doc_type
                                if study_goal_val:
                                    cc_obj.study_goal = study_goal_val
                                if study_goal_text_val and study_goal_text_val not in _TEMPLATE_GOAL_KEYS:
                                    cc_obj.study_goal_text = study_goal_text_val
                                save_db.commit()
                        except Exception as e:
                            logger.warning(f"Failed to persist document type on course content: {e}")

                    # Fire-and-forget AI resource suggestions for NEW guides (#2489)
                    if not body.regenerate_from_id and resolved_cc_id:
                        try:
                            import asyncio as _asyncio
                            from app.services.resource_suggestion_service import suggest_resources_background
                            from app.db.database import SessionLocal
                            _asyncio.create_task(suggest_resources_background(
                                topic=title,
                                course_name=course_name,
                                grade_level="",
                                course_content_id=resolved_cc_id,
                                user_id=user_id,
                                db_factory=SessionLocal,
                            ))
                        except Exception as e:
                            logger.warning(f"Resource suggestion task failed to launch: {e}")

                    # Build response
                    resp = StudyGuideResponse.model_validate(guide)
                    resp.auto_created_tasks = [AutoCreatedTask(**t) for t in created_tasks]
                    yield f"event: done\ndata: {json.dumps(resp.model_dump(mode='json'))}\n\n"
                else:
                    yield f"event: error\ndata: {json.dumps({'message': 'Guide record not found after streaming.'})}\n\n"

        except Exception as e:
            logger.error("Failed to save streamed study guide: %s: %s", type(e).__name__, e)
            yield f"event: error\ndata: {json.dumps({'message': 'Failed to save study guide. Please try again.'})}\n\n"

    return _StreamingResponse(event_stream(), media_type="text/event-stream")


# ============================================
# Worksheet Generation (#2956)
# ============================================

from app.services.study_guide_strategy import WORKSHEET_PROMPT_TEMPLATES, DIFFICULTY_LABELS


@router.post("/worksheets/generate", response_model=WorksheetResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_worksheet_endpoint(
    request: Request,
    body: WorksheetGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a printable worksheet from course content."""
    # Validate content access
    cc = db.query(CourseContent).filter(CourseContent.id == body.content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")
    if cc.course_id and not can_access_course(db, current_user, cc.course_id):
        raise HTTPException(status_code=403, detail="No access to this course content")

    source_text = cc.text_content or cc.description or ""
    if not source_text or len(source_text.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Safety check
    safe, reason = check_content_safe(source_text)
    if not safe:
        raise HTTPException(status_code=400, detail=reason)

    # Check AI usage
    check_ai_usage(current_user, db)

    # Build prompt
    template_prompt = WORKSHEET_PROMPT_TEMPLATES[body.template_key].format(
        num_questions=body.num_questions,
    )
    difficulty_desc = DIFFICULTY_LABELS[body.difficulty]

    prompt = (
        f"{template_prompt}\n\n"
        f"Difficulty: {difficulty_desc}\n\n"
        f"Format the worksheet in clean Markdown. "
        f"Use numbered lists (1., 2., ...) for questions. "
        f"Include a clear title at the top.\n\n"
        f"After the worksheet, add a section titled '## Answer Key' with answers to all questions.\n\n"
        f"--- SOURCE MATERIAL ---\n{source_text[:8000]}"
    )

    system_prompt = (
        "You are an experienced K-12 teacher creating worksheets for students. "
        "Produce clear, age-appropriate questions. Output valid Markdown only."
    )

    try:
        raw_content, _stop = await generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=2000,
            temperature=0.7,
        )
    except Exception as e:
        logger.error("Worksheet generation failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"AI generation failed: {type(e).__name__}")

    # Split content and answer key
    worksheet_md = raw_content
    answer_key_md = None
    answer_key_markers = ["## Answer Key", "## Answer key", "## ANSWER KEY"]
    for marker in answer_key_markers:
        if marker in raw_content:
            parts = raw_content.split(marker, 1)
            worksheet_md = parts[0].rstrip()
            answer_key_md = (marker + parts[1]).strip()
            break

    # Increment AI usage
    _usage = get_last_ai_usage() or {}
    increment_ai_usage(
        current_user, db, generation_type="worksheet", course_material_id=body.content_id,
        is_regeneration=False, **_usage,
    )

    # Enforce limit and save
    enforce_study_guide_limit(db, current_user)
    title = f"Worksheet: {cc.title}"

    study_guide = StudyGuide(
        user_id=current_user.id,
        course_id=cc.course_id,
        course_content_id=cc.id,
        title=title,
        content=worksheet_md,
        guide_type="worksheet",
        template_key=body.template_key,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        answer_key_markdown=answer_key_md,
    )
    db.add(study_guide)
    db.flush()

    # Auto-create review task
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    critical_dates = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]
    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        cc.course_id, cc.id,
    )

    db.commit()
    db.refresh(study_guide)

    # Award XP (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "study_guide")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    return WorksheetResponse(
        id=study_guide.id,
        user_id=study_guide.user_id,
        course_id=study_guide.course_id,
        course_content_id=study_guide.course_content_id,
        title=study_guide.title,
        content=study_guide.content,
        guide_type="worksheet",
        template_key=study_guide.template_key,
        num_questions=study_guide.num_questions,
        difficulty=study_guide.difficulty,
        answer_key_markdown=study_guide.answer_key_markdown,
        created_at=study_guide.created_at,
        auto_created_tasks=[AutoCreatedTask(**t) for t in created_tasks],
    )

# Weak Area Analysis (#2958)
# ============================================


@router.post("/weak-area/analyze", response_model=StudyGuideResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def analyze_weak_areas(
    request: Request,
    body: WeakAreaAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze a student's test to identify weak areas using Claude Sonnet."""
    import asyncio as _asyncio
    from app.services.ai_service import get_anthropic_client, _calc_cost

    # Validate content_id
    cc = db.query(CourseContent).filter(CourseContent.id == body.content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    text_content = cc.text_content or cc.description or ""
    if not text_content or len(text_content.strip()) < MIN_EXTRACTION_CHARS:
        raise HTTPException(status_code=422, detail=INSUFFICIENT_TEXT_MSG)

    # Check AI credits (costs 2 credits)
    check_ai_usage(current_user, db, cost=2)

    # Call Claude Sonnet for weak area analysis
    system_prompt = (
        "You are an expert educational analyst. Analyze the student's test and "
        "identify 2-5 specific weak areas where the student needs improvement. "
        "For each weak area, explain what the student got wrong or struggled with, "
        "why it matters, and suggest specific actions to improve."
    )
    user_prompt = (
        f"Here is the student's test/assessment document:\n\n"
        f"---\n{text_content}\n---\n\n"
        f"Please analyze this document and identify 2-5 specific weak areas. "
        f"Format your response as markdown with ## headings for each weak area. "
        f"Under each heading, include:\n"
        f"- **What went wrong:** Brief description\n"
        f"- **Why it matters:** Importance of this topic\n"
        f"- **How to improve:** Specific actionable suggestions\n\n"
        f"At the very end of your response, include a line in this exact format:\n"
        f"WEAK_TOPICS: [\"topic1\", \"topic2\", \"topic3\"]\n"
        f"where each topic is a short 2-5 word label for the weak area."
    )

    try:
        client = get_anthropic_client()
        message = await _asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_content = message.content[0].text
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
    except Exception as e:
        logger.error("Weak area analysis failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {type(e).__name__}")

    # Parse WEAK_TOPICS from response
    weak_topics_list = []
    analysis_content = raw_content
    import re as _re
    topics_match = _re.search(r'WEAK_TOPICS:\s*(\[.*?\])', raw_content, _re.DOTALL)
    if topics_match:
        try:
            weak_topics_list = json.loads(topics_match.group(1))
            # Remove the WEAK_TOPICS line from the display content
            analysis_content = raw_content[:topics_match.start()].rstrip()
        except json.JSONDecodeError:
            logger.warning("Failed to parse WEAK_TOPICS JSON from AI response")

    # Increment AI usage (2 credits for weak area analysis)
    cost = _calc_cost("claude-sonnet-4-20250514", input_tokens, output_tokens)
    increment_ai_usage(
        current_user, db, generation_type="weak_area_analysis",
        course_material_id=body.content_id,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=cost,
        model_name="claude-sonnet-4-20250514",
        wallet_debit_amount=2,
    )

    # Save as study guide
    title = f"Weak Area Analysis: {cc.title or 'Assessment'}"
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        course_id=cc.course_id,
        course_content_id=cc.id,
        title=title,
        content=analysis_content,
        guide_type="weak_area_analysis",
    )
    db.add(study_guide)
    db.flush()

    # Auto-create review task
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    critical_dates = [{"date": today_str, "title": f"Review: {title}", "priority": "medium"}]
    created_tasks = auto_create_tasks_from_dates(
        db, critical_dates, current_user, study_guide.id,
        cc.course_id, cc.id,
    )

    db.commit()
    db.refresh(study_guide)

    # Award XP (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "study_guide")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

    _notify_parents_of_study_material(db, current_user, study_guide.id, study_guide.title)

    logger.info(
        "Weak area analysis created | user_id=%s | guide_id=%s | topics=%s",
        current_user.id, study_guide.id, weak_topics_list,
    )

    return StudyGuideResponse.model_validate(study_guide)


@router.get("/worksheets/{worksheet_id}", response_model=WorksheetResponse)
async def get_worksheet(
    worksheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single worksheet by ID."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == worksheet_id,
        StudyGuide.guide_type == "worksheet",
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Worksheet not found")
    if guide.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your worksheet")
    return WorksheetResponse.model_validate(guide)


@router.get("/worksheets", response_model=list[WorksheetResponse])
async def list_worksheets(
    content_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List worksheets, optionally filtered by content_id."""
    query = db.query(StudyGuide).filter(
        StudyGuide.user_id == current_user.id,
        StudyGuide.guide_type == "worksheet",
        StudyGuide.archived_at.is_(None),
    )
    if content_id is not None:
        query = query.filter(StudyGuide.course_content_id == content_id)
    guides = query.order_by(StudyGuide.created_at.desc()).offset(skip).limit(limit).all()
    return [WorksheetResponse.model_validate(g) for g in guides]
