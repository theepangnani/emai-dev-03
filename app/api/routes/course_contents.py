from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.content_image import ContentImage
from app.models.course_content import CourseContent
from app.models.source_file import SourceFile
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.api.deps import get_current_user, can_access_course
from app.models.notification import NotificationType
from app.services.notification_service import notify_parents_of_student
from app.services.ai_usage import check_ai_usage, increment_ai_usage
from app.services.storage_service import get_file_path, delete_file, save_file
from app.services.storage_limits import check_upload_allowed, record_upload, record_deletion
from app.services.file_processor import process_file, extract_images_from_file, FileProcessingError
from app.models.content_image import ContentImage
from app.models.resource_link import ResourceLink
from app.core.config import settings
from app.services.link_extraction_service import extract_and_enrich_links
from app.schemas.course_content import (
    BulkCategorizeRequest,
    CourseContentCreate,
    CourseContentUpdate,
    CourseContentResponse,
    CourseContentUpdateResponse,
)
from app.schemas.content_image import ContentImageResponse
from app.schemas.source_file import SourceFileResponse

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


def _populate_source_files_count(resp: CourseContentResponse, item) -> CourseContentResponse:
    """Set source_files_count on a response from an ORM item's relationship."""
    try:
        resp.source_files_count = item.source_files.count()
    except Exception:
        resp.source_files_count = 0
    return resp


def _to_response(item, db: Session | None = None) -> CourseContentResponse:
    """Convert an ORM CourseContent to a response with source_files_count."""
    resp = CourseContentResponse.model_validate(item)
    return _populate_source_files_count(resp, item)


def _strip_urls_for_school(
    items: list, school_ids: set[int]
) -> list[CourseContentResponse]:
    """Convert ORM items to Pydantic and strip URLs for school courses.

    For school courses, reference/download URLs are hidden and a
    `download_restricted` flag is set for the frontend (#550).
    """
    results = []
    for item in items:
        resp = _to_response(item)
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


def _extract_and_store_links(db: Session, course_content_id: int, text: str) -> None:
    """Extract URLs from text and create ResourceLink records.

    Skips extraction if links already exist for this course_content_id (dedup).
    Failures are logged but never propagate — upload must not be blocked.
    """
    if not text:
        return
    try:
        # Deduplication: skip if links already exist for this content
        existing = (
            db.query(ResourceLink.id)
            .filter(ResourceLink.course_content_id == course_content_id)
            .first()
        )
        if existing:
            return

        extracted = extract_and_enrich_links(text)
        if not extracted:
            return

        for link_data in extracted:
            resource_link = ResourceLink(
                course_content_id=course_content_id,
                url=link_data.url,
                resource_type=link_data.resource_type,
                title=link_data.title,
                topic_heading=link_data.topic_heading,
                description=link_data.description,
                thumbnail_url=link_data.thumbnail_url,
                youtube_video_id=link_data.youtube_video_id,
                display_order=link_data.display_order,
            )
            db.add(resource_link)
        db.commit()
        logger.info("Extracted %d resource links for content %d", len(extracted), course_content_id)
    except Exception as e:
        db.rollback()
        logger.warning("Link extraction failed for content %d: %s", course_content_id, e)


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

    # Extract and store resource links from text content (#1321)
    _extract_and_store_links(db, content.id, data.text_content)

    # Trigger AI generation in background if requested (#552)
    source_text = data.text_content or data.description or ""
    if ai_tool != "none" and source_text:
        # Check AI usage limit before dispatching background generation
        check_ai_usage(current_user, db)
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

    return _to_response(content)


MAX_UPLOAD_SIZE = settings.max_upload_size_mb * 1024 * 1024


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
        from app.services.ai_usage import increment_ai_usage
        from app.models.study_guide import StudyGuide
        from app.models.user import User

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

            # Increment AI usage after successful generation
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                increment_ai_usage(user, db, generation_type=ai_tool, course_material_id=content_id)

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

    check_upload_allowed(current_user, len(file_content))
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
    record_upload(db, current_user, len(file_content))
    db.commit()
    db.refresh(content)

    # Extract and store images from the uploaded file (#1309)
    try:
        images = extract_images_from_file(file_content, filename)
        for img_data in images:
            content_image = ContentImage(
                course_content_id=content.id,
                image_data=img_data['image_data'],
                media_type=img_data['media_type'],
                description=img_data['description'],
                position_context=img_data['position_context'],
                position_index=img_data['position_index'],
                file_size=img_data['file_size'],
            )
            db.add(content_image)
        if images:
            db.commit()
            logger.info("Stored %d images for content %d", len(images), content.id)
    except Exception as e:
        db.rollback()
        logger.warning("Image extraction failed for %s: %s", filename, e)

    # Extract and store resource links from text content (#1321)
    _extract_and_store_links(db, content.id, extracted_text)

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
        # Check AI usage limit before dispatching background generation
        check_ai_usage(current_user, db)
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

    return _to_response(content)


@router.post("/upload-multi", response_model=CourseContentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def upload_multi_files(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    course_id: int = Form(...),
    title: str = Form(""),
    content_type: str = Form("notes"),
    ai_tool: str = Form("none"),
    ai_custom_prompt: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload multiple files as a single course content item.

    Each file is stored as a SourceFile for later view/download.
    Text is extracted from all files and combined into the CourseContent.text_content.

    Optionally triggers AI study material generation as a background task.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

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

    # Read all files and validate sizes
    file_entries: list[tuple[str, bytes, str | None]] = []
    total_size = 0
    for f in files:
        file_bytes = await f.read()
        total_size += len(file_bytes)
        if total_size > MAX_UPLOAD_SIZE * 5:  # Allow 5x single file limit for multi-file
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total upload size exceeds {(MAX_UPLOAD_SIZE * 5) // (1024*1024)} MB limit",
            )
        file_entries.append((f.filename or "unknown", file_bytes, f.content_type))

    check_upload_allowed(current_user, total_size)
    # Extract text from all files
    text_parts: list[str] = []
    for fname, fbytes, _ in file_entries:
        try:
            extracted = process_file(fbytes, fname)
            if extracted.strip():
                text_parts.append(f"--- [{fname}] ---\n{extracted}")
        except FileProcessingError as e:
            logger.warning("Text extraction failed for %s: %s", fname, e)
            text_parts.append(f"--- [{fname}] ---\n(text extraction failed)")

    combined_text = "\n\n".join(text_parts) if text_parts else None

    # Create the CourseContent record
    content_title = title or ", ".join(fname for fname, _, _ in file_entries)
    content = CourseContent(
        course_id=course_id,
        title=content_title,
        content_type=content_type,
        text_content=combined_text,
        original_filename=file_entries[0][0] if len(file_entries) == 1 else None,
        file_size=total_size,
        mime_type=file_entries[0][2] if len(file_entries) == 1 else "multipart/mixed",
        created_by_user_id=current_user.id,
    )
    db.add(content)
    db.flush()  # get content.id for FK

    # Store each file as a SourceFile
    for fname, fbytes, fmime in file_entries:
        source = SourceFile(
            course_content_id=content.id,
            filename=fname,
            file_type=fmime,
            file_size=len(fbytes),
            file_data=fbytes,
        )
        db.add(source)

    record_upload(db, current_user, total_size)
    db.commit()
    db.refresh(content)

    # Extract and store images from all uploaded files (#1309)
    try:
        all_images: list[dict] = []
        for fname, fbytes, _ in file_entries:
            file_images = extract_images_from_file(fbytes, fname)
            all_images.extend(file_images)
        # Re-index after merging images from multiple files
        for idx, img_data in enumerate(all_images):
            img_data['position_index'] = idx
            content_image = ContentImage(
                course_content_id=content.id,
                image_data=img_data['image_data'],
                media_type=img_data['media_type'],
                description=img_data['description'],
                position_context=img_data['position_context'],
                position_index=img_data['position_index'],
                file_size=img_data['file_size'],
            )
            db.add(content_image)
        if all_images:
            db.commit()
            logger.info("Stored %d images for content %d (multi-upload)", len(all_images), content.id)
    except Exception as e:
        db.rollback()
        logger.warning("Image extraction failed for multi-upload: %s", e)

    # Extract and store resource links from text content (#1321)
    _extract_and_store_links(db, content.id, combined_text)

    # Notify parents when a student uploads material
    if current_user.role == UserRole.STUDENT:
        try:
            notify_parents_of_student(
                db=db,
                student_user=current_user,
                title=f"{current_user.full_name} uploaded class material",
                content=f'{current_user.full_name} uploaded "{content_title}" to {course.name}.',
                notification_type=NotificationType.MATERIAL_UPLOADED,
                link=f"/courses/{course_id}",
                source_type="course_content",
                source_id=content.id,
            )
            db.commit()
        except Exception as e:
            logger.warning("Failed to notify parents of student upload: %s", e)

    # Trigger AI generation in background if requested
    if ai_tool_normalized != "none" and combined_text:
        check_ai_usage(current_user, db)
        background_tasks.add_task(
            _run_ai_generation_background,
            content_id=content.id,
            user_id=current_user.id,
            course_id=course_id,
            ai_tool=ai_tool_normalized,
            ai_custom_prompt=ai_custom_prompt.strip() or None,
            title=content_title,
            text_content=combined_text,
            course_name=course.name,
        )

    return _to_response(content)


@router.post("/bulk-categorize")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def bulk_categorize(
    request: Request,
    data: BulkCategorizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign multiple course content items to a category."""
    contents = db.query(CourseContent).filter(
        CourseContent.id.in_(data.content_ids),
    ).all()
    if not contents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching content items found")
    updated = 0
    for content in contents:
        if _can_modify_content(db, current_user, content):
            content.category = data.category
            updated += 1
    db.commit()
    return {"updated": updated, "category": data.category}


@router.get("/categories")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_categories(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all distinct categories for course contents accessible by the current user."""
    from sqlalchemy import distinct
    query = db.query(distinct(CourseContent.category)).filter(
        CourseContent.category.isnot(None),
        CourseContent.category != "",
        CourseContent.archived_at.is_(None),
    )
    # Scope to user's content
    if current_user.role == UserRole.PARENT:
        child_student_ids = [s.id for s in db.query(Student).join(parent_students).filter(parent_students.c.parent_id == current_user.id).all()]
        if child_student_ids:
            child_course_ids = [sc.course_id for sc in db.execute(student_courses.select().where(student_courses.c.student_id.in_(child_student_ids))).fetchall()]
            query = query.filter(CourseContent.course_id.in_(child_course_ids))
        else:
            query = query.filter(CourseContent.created_by_user_id == current_user.id)
    elif current_user.role == UserRole.STUDENT:
        query = query.filter(CourseContent.created_by_user_id == current_user.id)
    elif current_user.role == UserRole.TEACHER:
        query = query.filter(CourseContent.created_by_user_id == current_user.id)
    # ADMIN sees all
    categories = sorted([row[0] for row in query.all()])
    return categories


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

    return [_to_response(item) for item in items]


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
            resp = _to_response(content)
            resp.reference_url = None
            resp.google_classroom_url = None
            resp.download_restricted = True
            return resp

    return _to_response(content)


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
    _populate_source_files_count(resp, content)
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

    # Delete old images and extract new ones (#1309)
    db.query(ContentImage).filter(ContentImage.course_content_id == content_id).delete()

    # Delete old resource links so re-extraction starts fresh (#1321)
    db.query(ResourceLink).filter(ResourceLink.course_content_id == content_id).delete()

    db.commit()
    db.refresh(content)

    # Extract and store images from the replacement file (#1309)
    try:
        images = extract_images_from_file(file_content, filename)
        for img_data in images:
            content_image = ContentImage(
                course_content_id=content.id,
                image_data=img_data['image_data'],
                media_type=img_data['media_type'],
                description=img_data['description'],
                position_context=img_data['position_context'],
                position_index=img_data['position_index'],
                file_size=img_data['file_size'],
            )
            db.add(content_image)
        if images:
            db.commit()
            logger.info("Stored %d images for replaced content %d", len(images), content.id)
    except Exception as e:
        db.rollback()
        logger.warning("Image extraction failed for replaced file %s: %s", filename, e)

    # Extract and store resource links from replacement text (#1321)
    _extract_and_store_links(db, content.id, extracted_text)

    resp = CourseContentUpdateResponse.model_validate(content)
    _populate_source_files_count(resp, content)
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
    return _to_response(content)


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

    if content.file_size and content.created_by_user_id:
        creator = db.query(User).filter(User.id == content.created_by_user_id).first()
        if creator:
            record_deletion(db, creator, content.file_size)
    _permanent_delete_content(db, content)
    db.commit()


def _permanent_delete_content(db: Session, content: CourseContent):
    """Hard-delete a content item, its stored file, source files, images, and all linked study guides."""
    if content.file_path:
        delete_file(content.file_path)
    db.query(SourceFile).filter(SourceFile.course_content_id == content.id).delete()
    db.query(ContentImage).filter(ContentImage.course_content_id == content.id).delete()
    db.query(StudyGuide).filter(StudyGuide.course_content_id == content.id).delete()
    db.delete(content)


# ── Source Files endpoints (#1005) ────────────────────────────────

@router.get("/{content_id}/source-files", response_model=list[SourceFileResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_source_files(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List source files for a course content item. Must have access to the course."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    files = (
        db.query(SourceFile)
        .filter(SourceFile.course_content_id == content_id)
        .order_by(SourceFile.created_at)
        .all()
    )
    return files


@router.get("/{content_id}/source-files/{file_id}/download")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def download_source_file(
    request: Request,
    content_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download/view an individual source file. Must have access to the course."""
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
                detail="Downloads are restricted for school classroom content.",
            )

    source = (
        db.query(SourceFile)
        .filter(SourceFile.id == file_id, SourceFile.course_content_id == content_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")

    media_type = source.file_type or "application/octet-stream"
    filename = source.filename or f"file-{file_id}"

    return Response(
        content=source.file_data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(source.file_data)),
        },
    )


# ── Content Images endpoints (#1311) ──────────────────────────────

@router.get("/{content_id}/images", response_model=list[ContentImageResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_content_images(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List images extracted from a course content item, ordered by position."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    images = (
        db.query(ContentImage)
        .filter(ContentImage.course_content_id == content_id)
        .order_by(ContentImage.position_index)
        .all()
    )
    return images


@router.get("/{content_id}/images/{image_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_content_image(
    request: Request,
    content_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the raw binary of a single content image with correct Content-Type."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    image = (
        db.query(ContentImage)
        .filter(
            ContentImage.id == image_id,
            ContentImage.course_content_id == content_id,
        )
        .first()
    )
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    return Response(
        content=image.image_data,
        media_type=image.media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
