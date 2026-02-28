from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.course_content import CourseContent
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.api.deps import get_current_user, can_access_course
from app.models.notification import NotificationType
from app.services.notification_service import notify_parents_of_student
from app.services.storage_service import get_file_path, delete_file, save_file
from app.services.file_processor import process_file, FileProcessingError
from app.schemas.course_content import (
    CourseContentCreate,
    CourseContentUpdate,
    CourseContentResponse,
    CourseContentUpdateResponse,
)

import logging
logger = logging.getLogger(__name__)

_ONE_YEAR = timedelta(days=365)
_SEVEN_YEARS = timedelta(days=365 * 7)

VALID_AI_TOOLS = {"study_guide", "quiz", "flashcards", "none"}

router = APIRouter(prefix="/course-contents", tags=["Course Contents"])


def _get_school_course_ids(db: Session, course_ids: list[int]) -> set[int]:
    """Return the subset of course_ids that have classroom_type='school'."""
    if not course_ids:
        return set()
    rows = (
        db.query(Course.id)
        .filter(Course.id.in_(course_ids), Course.classroom_type == "school")
        .all()
    )
    return {r[0] for r in rows}


def _strip_urls_for_school(
    items: list, school_ids: set[int]
) -> list[CourseContentResponse]:
    """Convert ORM items to Pydantic and strip URLs for school courses.

    For school courses, reference/download URLs are hidden and a
    `download_restricted` flag is set for the frontend (#550).
    """
    results = []
    for item in items:
        resp = CourseContentResponse.model_validate(item)
        if item.course_id in school_ids:
            resp.reference_url = None
            resp.google_classroom_url = None
            resp.download_restricted = True
        results.append(resp)
    return results


def _can_modify_content(db: Session, user: User, content: CourseContent) -> bool:
    """Check if user can modify (edit/delete) a content item.
    Allowed for: the creator, admins, and parents of the creator."""
    if content.created_by_user_id == user.id:
        return True
    if user.has_role(UserRole.ADMIN):
        return True
    if user.role == UserRole.PARENT:
        child_student_ids = [
            r[0] for r in db.query(parent_students.c.student_id).filter(
                parent_students.c.parent_id == user.id
            ).all()
        ]
        if child_student_ids:
            child_user_ids = [
                r[0] for r in db.query(Student.user_id).filter(
                    Student.id.in_(child_student_ids)
                ).all()
            ]
            if content.created_by_user_id in child_user_ids:
                return True
    return False


@router.post("/", response_model=CourseContentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_course_content(
    request: Request,
    data: CourseContentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new content item for a course. Must have access to the course.

    Optionally triggers AI study material generation as a background task:
    - ai_tool: "study_guide", "quiz", "flashcards", or "none" (default)
    - ai_custom_prompt: custom instructions for AI generation (optional)
    """
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if not can_access_course(db, current_user, data.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    # Validate ai_tool if provided
    ai_tool = (data.ai_tool or "none").strip().lower()
    if ai_tool not in VALID_AI_TOOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ai_tool. Must be one of: {', '.join(sorted(VALID_AI_TOOLS))}",
        )

    content = CourseContent(
        course_id=data.course_id,
        title=data.title,
        description=data.description,
        text_content=data.text_content,
        content_type=data.content_type,
        reference_url=data.reference_url,
        google_classroom_url=data.google_classroom_url,
        created_by_user_id=current_user.id,
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    # Notify parents when a student uploads material
    if current_user.role == UserRole.STUDENT:
        try:
            notify_parents_of_student(
                db=db,
                student_user=current_user,
                title=f"{current_user.full_name} uploaded class material",
                content=f"{current_user.full_name} uploaded \"{data.title}\" to {course.name}.",
                notification_type=NotificationType.MATERIAL_UPLOADED,
                link=f"/courses/{data.course_id}",
                source_type="course_content",
                source_id=content.id,
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to notify parents of student upload: {e}")

    # Trigger AI generation in background if requested (#552)
    source_text = data.text_content or data.description or ""
    if ai_tool != "none" and source_text:
        background_tasks.add_task(
            _run_ai_generation_background,
            content_id=content.id,
            user_id=current_user.id,
            course_id=data.course_id,
            ai_tool=ai_tool,
            ai_custom_prompt=(data.ai_custom_prompt or "").strip() or None,
            title=data.title,
            text_content=source_text,
            course_name=course.name,
        )

    return content


MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


def _run_ai_generation_background(
    content_id: int,
    user_id: int,
    course_id: int,
    ai_tool: str,
    ai_custom_prompt: str | None,
    title: str,
    text_content: str,
    course_name: str,
):
    """Background task: generate an AI study material for uploaded content.

    Runs in its own DB session so the upload response returns immediately.
    """
    import asyncio

    async def _generate():
        from app.services.ai_service import generate_study_guide, generate_quiz, generate_flashcards
        from app.models.study_guide import StudyGuide

        db = SessionLocal()
        try:
            logger.info(
                "Background AI generation started | content_id=%s | tool=%s | user=%s",
                content_id, ai_tool, user_id,
            )

            if ai_tool == "study_guide":
                raw_content = await generate_study_guide(
                    assignment_title=title,
                    assignment_description=text_content,
                    course_name=course_name,
                    custom_prompt=ai_custom_prompt or None,
                )
                guide = StudyGuide(
                    user_id=user_id,
                    course_id=course_id,
                    course_content_id=content_id,
                    title=f"Study Guide: {title}",
                    content=raw_content,
                    guide_type="study_guide",
                )
                db.add(guide)

            elif ai_tool == "quiz":
                raw_content = await generate_quiz(
                    topic=title,
                    content=text_content,
                    num_questions=5,
                )
                guide = StudyGuide(
                    user_id=user_id,
                    course_id=course_id,
                    course_content_id=content_id,
                    title=f"Quiz: {title}",
                    content=raw_content,
                    guide_type="quiz",
                )
                db.add(guide)

            elif ai_tool == "flashcards":
                raw_content = await generate_flashcards(
                    topic=title,
                    content=text_content,
                    num_cards=10,
                )
                guide = StudyGuide(
                    user_id=user_id,
                    course_id=course_id,
                    course_content_id=content_id,
                    title=f"Flashcards: {title}",
                    content=raw_content,
                    guide_type="flashcards",
                )
                db.add(guide)

            db.commit()
            logger.info(
                "Background AI generation completed | content_id=%s | tool=%s",
                content_id, ai_tool,
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Background AI generation failed | content_id=%s | tool=%s | error=%s",
                content_id, ai_tool, e,
            )
        finally:
            db.close()

    # Run the async generation in a new event loop for the background thread
    asyncio.run(_generate())


@router.post("/upload", response_model=CourseContentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def upload_course_content_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    course_id: int = Form(...),
    title: str = Form(""),
    content_type: str = Form("notes"),
    ai_tool: str = Form("none"),
    ai_custom_prompt: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file as course content. Saves the original file and extracts text.

    Optionally triggers AI study material generation as a background task:
    - ai_tool: "study_guide", "quiz", "flashcards", or "none" (default)
    - ai_custom_prompt: custom instructions for AI generation (optional)
    """
    # Validate ai_tool
    ai_tool_normalized = ai_tool.strip().lower()
    if ai_tool_normalized not in VALID_AI_TOOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ai_tool. Must be one of: {', '.join(sorted(VALID_AI_TOOLS))}",
        )

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if not can_access_course(db, current_user, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_UPLOAD_SIZE // (1024*1024)} MB limit",
        )

    filename = file.filename or "unknown"
    stored_path = save_file(file_content, filename)

    # Extract text from uploaded file
    extracted_text = ""
    try:
        extracted_text = process_file(file_content, filename)
    except FileProcessingError as e:
        logger.warning("Text extraction failed for %s: %s", filename, e)

    content = CourseContent(
        course_id=course_id,
        title=title or filename,
        content_type=content_type,
        text_content=extracted_text or None,
        file_path=stored_path,
        original_filename=filename,
        file_size=len(file_content),
        mime_type=file.content_type,
        created_by_user_id=current_user.id,
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    # Notify parents when a student uploads material
    if current_user.role == UserRole.STUDENT:
        try:
            notify_parents_of_student(
                db=db,
                student_user=current_user,
                title=f"{current_user.full_name} uploaded class material",
                content=f'{current_user.full_name} uploaded "{title or filename}" to {course.name}.',
                notification_type=NotificationType.MATERIAL_UPLOADED,
                link=f"/courses/{course_id}",
                source_type="course_content",
                source_id=content.id,
            )
            db.commit()
        except Exception as e:
            logger.warning("Failed to notify parents of student upload: %s", e)

    # Trigger AI generation in background if requested (#552)
    if ai_tool_normalized != "none" and extracted_text:
        background_tasks.add_task(
            _run_ai_generation_background,
            content_id=content.id,
            user_id=current_user.id,
            course_id=course_id,
            ai_tool=ai_tool_normalized,
            ai_custom_prompt=ai_custom_prompt.strip() or None,
            title=title or filename,
            text_content=extracted_text,
            course_name=course.name,
        )

    return content


@router.get("/linked-course-ids")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_linked_course_ids(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return course IDs that have enrolled students who are children of the current parent.

    Used by the frontend to determine which course materials are 'unlinked'
    (i.e., not assigned to any of the parent's children). Only meaningful for parents.
    """
    if current_user.role != UserRole.PARENT:
        return {"linked_course_ids": [], "children": []}

    # Get parent's children student IDs
    child_rows = (
        db.query(parent_students.c.student_id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    )
    child_sids = [r[0] for r in child_rows]
    if not child_sids:
        return {"linked_course_ids": [], "children": []}

    # Get course IDs where these children are enrolled
    enrolled = (
        db.query(student_courses.c.course_id, student_courses.c.student_id)
        .filter(student_courses.c.student_id.in_(child_sids))
        .all()
    )

    # Build a map: course_id -> list of student_ids enrolled
    course_to_students: dict[int, list[int]] = {}
    for course_id, student_id in enrolled:
        course_to_students.setdefault(course_id, []).append(student_id)

    # Get child info (student_id, user_id, full_name) for the frontend
    children_info = []
    students = db.query(Student).filter(Student.id.in_(child_sids)).all()
    for s in students:
        children_info.append({
            "student_id": s.id,
            "user_id": s.user_id,
            "full_name": s.user.full_name if s.user else f"Student #{s.id}",
        })

    return {
        "linked_course_ids": list(course_to_students.keys()),
        "course_student_map": course_to_students,
        "children": children_info,
    }


@router.get("/", response_model=list[CourseContentResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_course_contents(
    request: Request,
    course_id: Optional[int] = Query(None, description="Filter by course ID"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    student_user_id: Optional[int] = Query(None, description="Filter by child (parent only)"),
    include_archived: bool = Query(False, description="Include archived items"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List content items. If course_id is given, scoped to that course.
    Otherwise returns all course contents visible to the user across courses."""
    if course_id:
        if not can_access_course(db, current_user, course_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")
        query = db.query(CourseContent).filter(CourseContent.course_id == course_id)
    else:
        # Cross-course: all content visible to the user
        visible_course_ids = _get_visible_course_ids(db, current_user, student_user_id)
        query = db.query(CourseContent).filter(CourseContent.course_id.in_(visible_course_ids))

    if not include_archived:
        query = query.filter(CourseContent.archived_at.is_(None))

    if content_type:
        query = query.filter(CourseContent.content_type == content_type.strip().lower())

    items = query.order_by(CourseContent.created_at.desc()).all()

    # Strip reference_url and google_classroom_url for students on school courses
    if current_user.role == UserRole.STUDENT and items:
        cids = list({item.course_id for item in items})
        school_ids = _get_school_course_ids(db, cids)
        if school_ids:
            return _strip_urls_for_school(items, school_ids)

    return items


def _get_visible_course_ids(db: Session, user: User, student_user_id: int | None = None) -> list[int]:
    """Return course IDs visible to the user for cross-course content listing."""

    if user.role == UserRole.STUDENT:
        # Courses created by the user + enrolled courses
        created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        ids = {r[0] for r in created}
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            ids.update(c.id for c in student.courses)
        return list(ids)

    if user.role == UserRole.PARENT:
        # Get children's student IDs
        child_rows = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == user.id
        ).all()
        child_sids = [r[0] for r in child_rows]

        if student_user_id:
            # Specific child selected — only courses this child is enrolled in
            child_student = db.query(Student).filter(
                Student.user_id == student_user_id,
                Student.id.in_(child_sids),
            ).first()
            if not child_student:
                return []
            ids = {c.id for c in child_student.courses}
            # Also include courses created by this child
            child_created = db.query(Course.id).filter(Course.created_by_user_id == student_user_id).all()
            ids.update(r[0] for r in child_created)
            return list(ids)

        # No child selected — show all children's courses + parent-created courses
        created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        ids = {r[0] for r in created}
        if child_sids:
            enrolled = db.query(student_courses.c.course_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            ids.update(r[0] for r in enrolled)
            # Also include courses created by children
            child_user_ids = db.query(Student.user_id).filter(Student.id.in_(child_sids)).all()
            child_uids = [r[0] for r in child_user_ids]
            if child_uids:
                child_created = db.query(Course.id).filter(Course.created_by_user_id.in_(child_uids)).all()
                ids.update(r[0] for r in child_created)

            # Also include courses created by co-parents (other parents of same children)
            co_parent_rows = db.query(parent_students.c.parent_id).filter(
                parent_students.c.student_id.in_(child_sids),
                parent_students.c.parent_id != user.id,
            ).all()
            co_parent_uids = [r[0] for r in co_parent_rows]
            if co_parent_uids:
                co_created = db.query(Course.id).filter(
                    Course.created_by_user_id.in_(co_parent_uids)
                ).all()
                ids.update(r[0] for r in co_created)
        return list(ids)

    # Courses created by the user (teacher fallback)
    created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
    ids = {r[0] for r in created}

    if user.role == UserRole.TEACHER:
        from app.models.teacher import Teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            taught = db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ids.update(r[0] for r in taught)

    elif user.role == UserRole.ADMIN:
        all_ids = db.query(Course.id).all()
        return [r[0] for r in all_ids]

    return list(ids)


@router.get("/{content_id}", response_model=CourseContentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_course_content(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single content item. Must have access to its course.
    On-access: auto-archives after 1 year, permanently deletes after 7 years from last view."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    now = datetime.now(timezone.utc)

    # On-access: permanent delete if last viewed > 7 years ago
    if content.last_viewed_at:
        last_view = content.last_viewed_at
        if last_view.tzinfo is None:
            last_view = last_view.replace(tzinfo=timezone.utc)
        if (now - last_view) > _SEVEN_YEARS:
            _permanent_delete_content(db, content)
            db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    # On-access: auto-archive if created > 1 year ago and not already archived
    if content.archived_at is None and content.created_at:
        created = content.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created) > _ONE_YEAR:
            content.archived_at = now

    # Update last viewed
    content.last_viewed_at = now
    db.commit()
    db.refresh(content)

    # Strip URLs for students on school courses (#550)
    if current_user.role == UserRole.STUDENT:
        school_ids = _get_school_course_ids(db, [content.course_id])
        if content.course_id in school_ids:
            resp = CourseContentResponse.model_validate(content)
            resp.reference_url = None
            resp.google_classroom_url = None
            resp.download_restricted = True
            return resp

    return content


@router.get("/{content_id}/download")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def download_course_content_file(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the original uploaded file for a content item.

    Students cannot download files from school-type courses (classroom_type='school').
    Parents and teachers are not restricted.
    """
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    # Restrict downloads for students on school courses (#550)
    if current_user.role == UserRole.STUDENT:
        school_ids = _get_school_course_ids(db, [content.course_id])
        if content.course_id in school_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Downloads are restricted for school classroom content. "
                       "You can view assignment details but cannot download documents.",
            )

    if not content.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No file attached to this content")

    file_abs = get_file_path(content.file_path)
    if not file_abs.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    return FileResponse(
        path=str(file_abs),
        filename=content.original_filename or content.file_path,
        media_type=content.mime_type or "application/octet-stream",
    )


@router.patch("/{content_id}", response_model=CourseContentUpdateResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_course_content(
    request: Request,
    content_id: int,
    data: CourseContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a content item. Only the creator or an admin can update.
    If text_content changes, linked study guides are automatically archived."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if not _can_modify_content(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can edit content")

    update_data = data.model_dump(exclude_unset=True)

    # Validate course_id if being changed
    if "course_id" in update_data and update_data["course_id"] != content.course_id:
        target_course = db.query(Course).filter(Course.id == update_data["course_id"]).first()
        if not target_course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target course not found")

    text_content_changed = (
        "text_content" in update_data
        and update_data["text_content"] != content.text_content
    )

    for field, value in update_data.items():
        setattr(content, field, value)

    # Archive linked study guides when source text changes
    archived_guides_count = 0
    if text_content_changed:
        now = datetime.now(timezone.utc)
        guides = db.query(StudyGuide).filter(
            StudyGuide.course_content_id == content_id,
            StudyGuide.archived_at.is_(None),
        ).all()
        for guide in guides:
            guide.archived_at = now
            archived_guides_count += 1

    db.commit()
    db.refresh(content)

    resp = CourseContentUpdateResponse.model_validate(content)
    resp.archived_guides_count = archived_guides_count
    return resp


@router.put("/{content_id}/replace-file", response_model=CourseContentUpdateResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def replace_course_content_file(
    request: Request,
    content_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace the file for an existing content item. Re-extracts text and archives linked study guides."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if not _can_modify_content(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can replace content")

    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_UPLOAD_SIZE // (1024*1024)} MB limit",
        )

    # Delete old file from storage
    if content.file_path:
        try:
            delete_file(content.file_path)
        except Exception as e:
            logger.warning("Failed to delete old file %s: %s", content.file_path, e)

    # Save new file
    filename = file.filename or "unknown"
    stored_path = save_file(file_content, filename)

    # Extract text from new file
    extracted_text = ""
    try:
        extracted_text = process_file(file_content, filename)
    except FileProcessingError as e:
        logger.warning("Text extraction failed for %s: %s", filename, e)

    # Update record
    content.file_path = stored_path
    content.original_filename = filename
    content.file_size = len(file_content)
    content.mime_type = file.content_type
    content.text_content = extracted_text or None

    # Archive linked study guides since source content changed
    archived_guides_count = 0
    now = datetime.now(timezone.utc)
    guides = db.query(StudyGuide).filter(
        StudyGuide.course_content_id == content_id,
        StudyGuide.archived_at.is_(None),
    ).all()
    for guide in guides:
        guide.archived_at = now
        archived_guides_count += 1

    db.commit()
    db.refresh(content)

    resp = CourseContentUpdateResponse.model_validate(content)
    resp.archived_guides_count = archived_guides_count
    return resp


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_course_content(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete (archive) a content item. Only the creator or an admin can delete."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if not _can_modify_content(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can delete content")

    content.archived_at = datetime.now(timezone.utc)
    db.commit()


@router.patch("/{content_id}/restore", response_model=CourseContentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def restore_course_content(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore an archived content item. Only the creator or an admin can restore."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if not _can_modify_content(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can restore content")
    if content.archived_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content is not archived")

    content.archived_at = None
    db.commit()
    db.refresh(content)
    return content


@router.delete("/{content_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def permanent_delete_course_content(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete an archived content item and its linked study guides.
    Only works on already-archived items. Only the creator or an admin can delete."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if not _can_modify_content(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can permanently delete content")
    if content.archived_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content must be archived before permanent deletion")

    _permanent_delete_content(db, content)
    db.commit()


def _permanent_delete_content(db: Session, content: CourseContent):
    """Hard-delete a content item, its stored file, and all linked study guides."""
    if content.file_path:
        delete_file(content.file_path)
    db.query(StudyGuide).filter(StudyGuide.course_content_id == content.id).delete()
    db.delete(content)
