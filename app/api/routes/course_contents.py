import mimetypes
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db, SessionLocal
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.content_image import ContentImage
from app.models.course_content import CourseContent
from app.models.source_file import SourceFile
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.api.deps import get_current_user, can_access_course, can_access_material
from app.models.notification import NotificationType
from app.services.notification_service import notify_parents_of_student
from app.services.ai_usage import check_ai_usage, increment_ai_usage
from app.services.storage_service import get_file_path, delete_file, save_file
from app.services.storage_limits import check_upload_allowed, record_upload, record_deletion
from app.services.file_processor import process_file, extract_images_from_file, FileProcessingError, check_extracted_text_sufficient
from app.models.content_image import ContentImage
from app.models.resource_link import ResourceLink
from app.core.config import settings
from app.services.link_extraction_service import extract_and_enrich_links
from app.services import gcs_service


from app.services.audit_service import log_action
from app.services.material_hierarchy import create_material_hierarchy, get_linked_materials, generate_sub_title
from app.schemas.course_content import (
    BulkArchiveRequest,
    BulkCategorizeRequest,
    CourseContentCreate,
    CourseContentUpdate,
    CourseContentResponse,
    CourseContentUpdateResponse,
    LinkedMaterialResponse,
    ReorderSubsRequest,
)
from app.schemas.content_image import ContentImageResponse
from app.schemas.source_file import SourceFileResponse

import logging
logger = logging.getLogger(__name__)


def _content_disposition(filename: str) -> str:
    """Build a Content-Disposition header that handles non-ASCII filenames (RFC 5987)."""
    # ASCII-safe fallback: replace non-ASCII chars with underscores
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
    # UTF-8 encoded filename per RFC 5987
    utf8_name = quote(filename, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'


_ONE_YEAR = timedelta(days=365)
_SEVEN_YEARS = timedelta(days=365 * 7)

VALID_AI_TOOLS = {"study_guide", "quiz", "flashcards", "none"}


def _filename_to_title(filename: str) -> str:
    """Strip file extension and clean up name to create a material title from filename."""
    import os
    name, _ = os.path.splitext(filename)
    name = name or filename
    # Replace underscores and hyphens with spaces for a cleaner title
    name = name.replace("_", " ").replace("-", " ")
    # Collapse multiple spaces
    name = " ".join(name.split())
    return name


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


def _populate_source_files_count(resp: CourseContentResponse, item, db: Session | None = None) -> CourseContentResponse:
    """Set source_files_count on a response from an ORM item's relationship."""
    try:
        own_count = item.source_files.count()
    except Exception:
        own_count = 0

    # For materials in a group, also count source files from all linked materials
    group_id = getattr(item, 'material_group_id', None)
    if group_id and db:
        try:
            group_count = (
                db.query(SourceFile)
                .join(CourseContent, SourceFile.course_content_id == CourseContent.id)
                .filter(
                    CourseContent.material_group_id == group_id,
                    CourseContent.id != item.id,
                    CourseContent.archived_at.is_(None),
                )
                .count()
            )
            own_count += group_count
            logger.info("source_files_count for content %d: own=%d group=%d total=%d is_master=%s group_id=%s",
                        item.id, own_count - group_count, group_count, own_count,
                        getattr(item, 'is_master', 'N/A'), group_id)
        except Exception as e:
            logger.warning("Failed to count group source files for content %d: %s", item.id, e)

    resp.source_files_count = own_count
    return resp


def _to_response(item, db: Session | None = None) -> CourseContentResponse:
    """Convert an ORM CourseContent to a response with source_files_count."""
    resp = CourseContentResponse.model_validate(item)
    # Try to get db from object_session if not passed
    if db is None:
        from sqlalchemy.orm import object_session
        db = object_session(item)
    return _populate_source_files_count(resp, item, db)


def _strip_urls_for_school(
    items: list, school_ids: set[int], db: Session | None = None
) -> list[CourseContentResponse]:
    """Convert ORM items to Pydantic and strip URLs for school courses.

    For school courses, reference/download URLs are hidden and a
    `download_restricted` flag is set for the frontend (#550).
    """
    results = []
    for item in items:
        resp = _to_response(item, db)
        if item.course_id in school_ids:
            resp.reference_url = None
            resp.google_classroom_url = None
            resp.download_restricted = True
        results.append(resp)
    return results


def _can_modify_content(db: Session, user: User, content: CourseContent) -> bool:
    """Check if user can modify (edit/delete) a content item.
    Allowed for: the creator and parents of the creator."""
    if content.created_by_user_id == user.id:
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
        source_type="local_upload",
    )
    db.add(content)
    log_action(
        db,
        user_id=current_user.id,
        action="material_upload",
        resource_type="course_content",
        resource_id=None,
        details={"course_id": data.course_id, "title": data.title},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
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

    return _to_response(content, db)


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

            # Look up user interests for AI personalization
            _user = db.query(User).filter(User.id == user_id).first()
            _interests = None
            if _user and _user.interests:
                import json as _json
                try:
                    _parsed = _json.loads(_user.interests)
                    _interests = _parsed if isinstance(_parsed, list) and _parsed else None
                except Exception:
                    pass

            # Fetch image metadata for prompt enrichment
            images_metadata = []
            content_images = (
                db.query(ContentImage)
                .filter(ContentImage.course_content_id == content_id)
                .order_by(ContentImage.position_index)
                .all()
            )
            for img in content_images:
                images_metadata.append({
                    "id": img.id,
                    "description": img.description or "",
                    "position_context": img.position_context or "",
                    "position_index": img.position_index,
                })

            if ai_tool == "study_guide":
                raw_content = await generate_study_guide(
                    assignment_title=title,
                    assignment_description=text_content,
                    course_name=course_name,
                    custom_prompt=ai_custom_prompt or None,
                    interests=_interests,
                    images=images_metadata or None,
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
                    interests=_interests,
                    images=images_metadata or None,
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
                    interests=_interests,
                    images=images_metadata or None,
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

            # Flush to get guide ID, then create tasks from dates
            db.flush()

            from app.api.routes.study import parse_critical_dates, scan_content_for_dates, auto_create_tasks_from_dates

            clean_content, critical_dates = parse_critical_dates(raw_content)
            guide.content = clean_content

            if not critical_dates:
                critical_dates = scan_content_for_dates(text_content, title)

            if not critical_dates:
                from datetime import date as _date
                critical_dates = [{
                    "date": _date.today().isoformat(),
                    "title": f"Review: {title}",
                    "priority": "medium",
                }]

            auto_create_tasks_from_dates(db, critical_dates, _user, guide.id, course_id, content_id)

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
        source_type="local_upload",
    )
    db.add(content)
    record_upload(db, current_user, len(file_content))
    log_action(
        db,
        user_id=current_user.id,
        action="material_upload",
        resource_type="course_content",
        resource_id=None,
        details={
            "course_id": course_id,
            "filename": filename,
            "file_size": len(file_content),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(content)

    # Store file as SourceFile for Cloud Run persistence (#1557)
    try:
        if settings.use_gcs:
            _gcs_path = f"source-files/{content.id}/{filename}"
            gcs_service.upload_file(_gcs_path, file_content, file.content_type or "application/octet-stream")
            source = SourceFile(
                course_content_id=content.id,
                filename=filename,
                file_type=file.content_type,
                file_size=len(file_content),
                gcs_path=_gcs_path,
                source_type="local_upload",
            )
            db.add(source)
            db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Failed to store SourceFile for single upload: %s", e)

    # Extract and store images from the uploaded file (#1309)
    try:
        images = extract_images_from_file(file_content, filename)
        for img_data in images:
            if settings.use_gcs:
                _img_gcs_path = f"content-images/{content.id}/{img_data['position_index']}.jpg"
                gcs_service.upload_file(_img_gcs_path, img_data['image_data'], img_data['media_type'])
                content_image = ContentImage(
                    course_content_id=content.id,
                    gcs_path=_img_gcs_path,
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

    # Detect assessment dates from uploaded content (non-blocking)
    try:
        from app.services.assessment_detector import detect_assessments
        from app.models.detected_event import DetectedEvent
        detected = detect_assessments(extracted_text, filename, course_id)
        for evt in detected:
            db.add(DetectedEvent(
                student_id=current_user.id,
                course_id=course_id,
                course_content_id=content.id,
                event_type=evt["event_type"],
                event_title=evt["event_title"],
                event_date=evt["event_date"],
                source=evt["source"],
            ))
        if detected:
            db.commit()
    except Exception as e:
        logger.warning("Assessment detection failed (non-blocking): %s", e)

    # Award XP for file upload (non-blocking)
    try:
        from app.services.xp_service import XpService
        XpService.award_xp(db, current_user.id, "upload")
    except Exception as e:
        logger.warning(f"XP award failed (non-blocking): {e}")

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
    # Block AI generation when extracted text is too short (#2217)
    if ai_tool_normalized != "none" and extracted_text:
        try:
            check_extracted_text_sufficient(extracted_text, filename)
        except FileProcessingError:
            # Text too short — skip AI generation silently (file is still stored)
            ai_tool_normalized = "none"
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

    return _to_response(content, db)


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

    # Max 10 files per upload (#1740)
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per upload. Please reduce the number of files.",
        )

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

    # === Material Hierarchy (#1740) ===
    content_title = title or _filename_to_title(file_entries[0][0])
    logger.warning("UPLOAD-MULTI DEBUG: use_gcs=%s, bucket=%s, file_count=%d", settings.use_gcs, settings.gcs_bucket_name, len(file_entries))

    if len(file_entries) == 1:
        # Single file: no hierarchy, create as before
        content = CourseContent(
            course_id=course_id,
            title=content_title,
            content_type=content_type,
            text_content=combined_text,
            original_filename=file_entries[0][0],
            file_size=total_size,
            mime_type=file_entries[0][2],
            created_by_user_id=current_user.id,
            source_type="local_upload",
        )
        db.add(content)
        db.flush()

        # Store as SourceFile
        if settings.use_gcs:
            fname, fbytes, fmime = file_entries[0]
            _gcs_path = f"source-files/{content.id}/{fname}"
            gcs_service.upload_file(_gcs_path, fbytes, fmime or "application/octet-stream")
            source = SourceFile(
                course_content_id=content.id,
                filename=fname,
                file_type=fmime,
                file_size=len(fbytes),
                gcs_path=_gcs_path,
                source_type="local_upload",
            )
            db.add(source)
    else:
        # Multiple files: first file becomes master, rest become sub-materials
        # Per §6.98 Rule 3: N files → 1 master (first file) + (N-1) subs
        first_fname, first_fbytes, first_fmime = file_entries[0]
        first_text = text_parts[0] if text_parts else None

        master = CourseContent(
            course_id=course_id,
            title=content_title,
            content_type=content_type,
            text_content=first_text,
            original_filename=first_fname,
            file_size=len(first_fbytes),
            mime_type=first_fmime,
            created_by_user_id=current_user.id,
            source_type="local_upload",
        )
        db.add(master)
        db.flush()  # Get master.id

        # Store first file as SourceFile on the master
        if settings.use_gcs:
            _gcs_path = f"source-files/{master.id}/{first_fname}"
            gcs_service.upload_file(_gcs_path, first_fbytes, first_fmime or "application/octet-stream")
            source = SourceFile(
                course_content_id=master.id,
                filename=first_fname,
                file_type=first_fmime,
                file_size=len(first_fbytes),
                gcs_path=_gcs_path,
                source_type="local_upload",
            )
            db.add(source)

        # Create sub-materials for remaining files (2nd, 3rd, etc.)
        sub_materials = []
        for idx, (fname, fbytes, fmime) in enumerate(file_entries[1:], 2):
            sub_title = _filename_to_title(fname)
            # Extract text for this specific file
            sub_text = text_parts[idx - 1] if idx - 1 < len(text_parts) else None

            sub = CourseContent(
                course_id=course_id,
                title=sub_title,
                content_type=content_type,
                text_content=sub_text,
                original_filename=fname,
                file_size=len(fbytes),
                mime_type=fmime,
                created_by_user_id=current_user.id,
                source_type="local_upload",
            )
            db.add(sub)
            db.flush()  # Get sub.id

            # Store file as SourceFile on the sub-material
            if settings.use_gcs:
                _gcs_path = f"source-files/{sub.id}/{fname}"
                gcs_service.upload_file(_gcs_path, fbytes, fmime or "application/octet-stream")
                logger.warning("UPLOAD-MULTI DEBUG: Creating SourceFile for sub %d, gcs_path=%s", sub.id, _gcs_path)
                source = SourceFile(
                    course_content_id=sub.id,
                    filename=fname,
                    file_type=fmime,
                    file_size=len(fbytes),
                    gcs_path=_gcs_path,
                    source_type="local_upload",
                )
                db.add(source)
            else:
                logger.warning("UPLOAD-MULTI DEBUG: use_gcs is FALSE, skipping SourceFile for sub %d", sub.id)

            sub_materials.append(sub)

        # Link master + subs
        create_material_hierarchy(db, master, sub_materials)
        content = master  # Return master as the response

    record_upload(db, current_user, total_size)
    log_action(
        db,
        user_id=current_user.id,
        action="material_upload",
        resource_type="course_content",
        resource_id=None,
        details={
            "course_id": course_id,
            "filename": file_entries[0][0],
            "file_size": total_size,
            "file_count": len(file_entries),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
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
            if settings.use_gcs:
                _img_gcs_path = f"content-images/{content.id}/{idx}.jpg"
                gcs_service.upload_file(_img_gcs_path, img_data['image_data'], img_data['media_type'])
                content_image = ContentImage(
                    course_content_id=content.id,
                    gcs_path=_img_gcs_path,
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

    # Detect assessment dates from uploaded content (non-blocking)
    try:
        from app.services.assessment_detector import detect_assessments
        from app.models.detected_event import DetectedEvent
        detected = detect_assessments(combined_text, content_title, course_id)
        for evt in detected:
            db.add(DetectedEvent(
                student_id=current_user.id,
                course_id=course_id,
                course_content_id=content.id,
                event_type=evt["event_type"],
                event_title=evt["event_title"],
                event_date=evt["event_date"],
                source=evt["source"],
            ))
        if detected:
            db.commit()
    except Exception as e:
        logger.warning("Assessment detection failed (non-blocking): %s", e)

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
    # Block AI generation when extracted text is too short (#2217)
    if ai_tool_normalized != "none" and combined_text:
        try:
            check_extracted_text_sufficient(combined_text, content_title)
        except FileProcessingError:
            # Text too short — skip AI generation silently (files are still stored)
            ai_tool_normalized = "none"
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

    return _to_response(content, db)


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


@router.post("/bulk-archive")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def bulk_archive(
    request: Request,
    data: BulkArchiveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive multiple course content items."""
    from datetime import datetime, timezone
    contents = db.query(CourseContent).filter(
        CourseContent.id.in_(data.content_ids),
        CourseContent.archived_at.is_(None),
    ).all()
    if not contents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching content items found")
    archived = 0
    for content in contents:
        if _can_modify_content(db, current_user, content):
            content.archived_at = datetime.now(timezone.utc)
            archived += 1
    db.commit()
    return {"archived": archived}


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
    students = db.query(Student).options(selectinload(Student.user)).filter(Student.id.in_(child_sids)).all()
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
            return _strip_urls_for_school(items, school_ids, db)

    results = [_to_response(item, db) for item in items]

    # Strip text_content for non-trust-circle users (e.g. admins)
    if items and current_user.has_role(UserRole.ADMIN):
        for resp in results:
            resp.text_content = None

    return results


def _get_visible_course_ids(db: Session, user: User, student_user_id: int | None = None) -> list[int]:
    """Return course IDs visible to the user for cross-course content listing."""

    if user.role == UserRole.STUDENT:
        # Courses created by the user + enrolled courses
        created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        ids = {r[0] for r in created}
        student = db.query(Student).options(selectinload(Student.courses)).filter(Student.user_id == user.id).first()
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
            child_student = db.query(Student).options(selectinload(Student.courses)).filter(
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

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

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
    log_action(
        db,
        user_id=current_user.id,
        action="material_view",
        resource_type="course_content",
        resource_id=content.id,
        details={"course_id": content.course_id, "filename": content.original_filename},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(content)

    # Strip URLs for students on school courses (#550)
    if current_user.role == UserRole.STUDENT:
        school_ids = _get_school_course_ids(db, [content.course_id])
        if content.course_id in school_ids:
            resp = _to_response(content, db)
            resp.reference_url = None
            resp.google_classroom_url = None
            resp.download_restricted = True
            return resp

    return _to_response(content, db)


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

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

    # Restrict downloads for students on school courses (#550)
    if current_user.role == UserRole.STUDENT:
        school_ids = _get_school_course_ids(db, [content.course_id])
        if content.course_id in school_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Downloads are restricted for school classroom content. "
                       "You can view assignment details but cannot download documents.",
            )

    log_action(
        db,
        user_id=current_user.id,
        action="material_download",
        resource_type="course_content",
        resource_id=content.id,
        details={
            "course_id": content.course_id,
            "filename": content.original_filename,
            "file_size": content.file_size,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    # Try disk file first, fall back to SourceFile in DB (#1557)
    if content.file_path:
        file_abs = get_file_path(content.file_path)
        if file_abs.exists():
            return FileResponse(
                path=str(file_abs),
                filename=content.original_filename or content.file_path,
                media_type=content.mime_type or "application/octet-stream",
            )

    # Fall back to first SourceFile (multi-file uploads or disk file lost)
    source = (
        db.query(SourceFile)
        .filter(SourceFile.course_content_id == content_id)
        .order_by(SourceFile.id)
        .first()
    )
    if source:
        filename = source.filename or content.original_filename or f"file-{content_id}"
        media_type = source.file_type or content.mime_type or "application/octet-stream"
        if source.gcs_path:
            file_bytes = gcs_service.download_file(source.gcs_path)
            return Response(
                content=file_bytes,
                media_type=media_type,
                headers={
                    "Content-Disposition": _content_disposition(filename),
                    "Content-Length": str(len(file_bytes)),
                },
            )

    # File is gone and no SourceFile — clear stale file_path so has_file becomes false
    if content.file_path:
        content.file_path = None
        content.original_filename = None
        content.file_size = None
        content.mime_type = None
        db.commit()

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original file is no longer available")


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
    _populate_source_files_count(resp, content, db)
    resp.archived_guides_count = archived_guides_count
    return resp


@router.post("/{content_id}/add-files", response_model=CourseContentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def add_files_to_material(
    request: Request,
    content_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add files to an existing material, creating or extending a material hierarchy.

    - Standalone material: promotes to master and creates sub-materials for new files.
    - Master material: adds new sub-materials to the existing group.
    - Sub-material: finds the parent master and adds new subs to that group.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per upload. Please reduce the number of files.",
        )

    # Look up the target content
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    if not _can_modify_content(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this content")

    # Read all files and validate total size
    file_entries: list[tuple[str, bytes, str | None]] = []
    total_size = 0
    for f in files:
        file_bytes = await f.read()
        total_size += len(file_bytes)
        if total_size > MAX_UPLOAD_SIZE * 5:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total upload size exceeds {(MAX_UPLOAD_SIZE * 5) // (1024*1024)} MB limit",
            )
        file_entries.append((f.filename or "unknown", file_bytes, f.content_type))

    check_upload_allowed(current_user, total_size)

    # Determine the master material
    if not content.is_master and content.parent_content_id:
        # Sub-material: find parent master
        master = db.query(CourseContent).filter(CourseContent.id == content.parent_content_id).first()
        if not master:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent master material not found")
    elif content.is_master:
        # Already a master
        master = content
    else:
        # Standalone material: promote to master
        master = content
        create_material_hierarchy(db, master, [])
        db.flush()

    # Count existing sub-materials to determine next part number
    existing_sub_count = db.query(CourseContent).filter(
        CourseContent.parent_content_id == master.id,
        CourseContent.archived_at.is_(None),
    ).count()

    # Extract text from new files
    text_parts: list[str] = []
    for fname, fbytes, _ in file_entries:
        try:
            extracted = process_file(fbytes, fname)
            if extracted.strip():
                text_parts.append(f"--- [{fname}] ---\n{extracted}")
        except FileProcessingError as e:
            logger.warning("Text extraction failed for %s: %s", fname, e)
            text_parts.append(f"--- [{fname}] ---\n(text extraction failed)")

    # Create sub-materials for each new file
    new_subs: list[CourseContent] = []
    for idx, (fname, fbytes, fmime) in enumerate(file_entries, 1):
        part_number = existing_sub_count + idx
        sub_title = _filename_to_title(fname)
        sub_text = text_parts[idx - 1] if idx - 1 < len(text_parts) else None

        sub = CourseContent(
            course_id=master.course_id,
            title=sub_title,
            content_type=master.content_type,
            text_content=sub_text,
            original_filename=fname,
            file_size=len(fbytes),
            mime_type=fmime,
            created_by_user_id=current_user.id,
            parent_content_id=master.id,
            is_master=False,
            material_group_id=master.material_group_id,
            source_type="local_upload",
        )
        db.add(sub)
        db.flush()

        # Store file as SourceFile
        if settings.use_gcs:
            _gcs_path = f"source-files/{sub.id}/{fname}"
            gcs_service.upload_file(_gcs_path, fbytes, fmime or "application/octet-stream")
            source = SourceFile(
                course_content_id=sub.id,
                filename=fname,
                file_type=fmime,
                file_size=len(fbytes),
                gcs_path=_gcs_path,
                source_type="local_upload",
            )
            db.add(source)

        new_subs.append(sub)

    # Append new text to master's text_content
    new_text = "\n\n".join(text_parts) if text_parts else None
    if new_text:
        if master.text_content:
            master.text_content = master.text_content + "\n\n" + new_text
        else:
            master.text_content = new_text

    record_upload(db, current_user, total_size)
    db.commit()
    db.refresh(master)

    # Extract and store images from new files
    try:
        # Determine starting image index from existing images
        existing_image_count = db.query(ContentImage).filter(
            ContentImage.course_content_id == master.id,
        ).count()

        all_images: list[dict] = []
        for fname, fbytes, _ in file_entries:
            file_images = extract_images_from_file(fbytes, fname)
            all_images.extend(file_images)

        for idx, img_data in enumerate(all_images):
            img_idx = existing_image_count + idx
            img_data['position_index'] = img_idx
            if settings.use_gcs:
                _img_gcs_path = f"content-images/{master.id}/{img_idx}.jpg"
                gcs_service.upload_file(_img_gcs_path, img_data['image_data'], img_data['media_type'])
                content_image = ContentImage(
                    course_content_id=master.id,
                    gcs_path=_img_gcs_path,
                    media_type=img_data['media_type'],
                    description=img_data['description'],
                    position_context=img_data['position_context'],
                    position_index=img_data['position_index'],
                    file_size=img_data['file_size'],
                )
                db.add(content_image)
        if all_images:
            db.commit()
            logger.info("Stored %d images for content %d (add-files)", len(all_images), master.id)
    except Exception as e:
        db.rollback()
        logger.warning("Image extraction failed for add-files: %s", e)

    return _to_response(master, db)


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
            if settings.use_gcs:
                _img_gcs_path = f"content-images/{content.id}/{img_data['position_index']}.jpg"
                gcs_service.upload_file(_img_gcs_path, img_data['image_data'], img_data['media_type'])
                content_image = ContentImage(
                    course_content_id=content.id,
                    gcs_path=_img_gcs_path,
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
    _populate_source_files_count(resp, content, db)
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
    if content.is_master:
        db.query(CourseContent).filter(
            CourseContent.parent_content_id == content.id,
            CourseContent.archived_at.is_(None),
        ).update({"archived_at": content.archived_at}, synchronize_session="fetch")
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
    if content.is_master:
        db.query(CourseContent).filter(
            CourseContent.parent_content_id == content.id,
            CourseContent.archived_at.isnot(None),
        ).update({"archived_at": None}, synchronize_session="fetch")
    db.commit()
    db.refresh(content)
    return _to_response(content, db)


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

    # Cascade permanent delete to sub-materials
    if content.is_master:
        subs = db.query(CourseContent).filter(
            CourseContent.parent_content_id == content.id,
        ).all()
        for sub in subs:
            if sub.file_size and sub.created_by_user_id:
                creator = db.query(User).filter(User.id == sub.created_by_user_id).first()
                if creator:
                    record_deletion(db, creator, sub.file_size)
            _permanent_delete_content(db, sub)

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
    source_files = db.query(SourceFile).filter(SourceFile.course_content_id == content.id).all()
    for sf in source_files:
        if sf.gcs_path:
            gcs_service.delete_file(sf.gcs_path)
    db.query(SourceFile).filter(SourceFile.course_content_id == content.id).delete()
    content_images = db.query(ContentImage).filter(ContentImage.course_content_id == content.id).all()
    for ci in content_images:
        if ci.gcs_path:
            gcs_service.delete_file(ci.gcs_path)
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

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

    if content.material_group_id:
        # Get source files from master + all sub-materials in the group
        sub_ids = [
            r[0] for r in db.query(CourseContent.id).filter(
                CourseContent.material_group_id == content.material_group_id,
                CourseContent.archived_at.is_(None),
            ).all()
        ]
        files = (
            db.query(SourceFile)
            .filter(SourceFile.course_content_id.in_(sub_ids))
            .order_by(SourceFile.created_at)
            .all()
        )
    else:
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

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

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

    log_action(
        db,
        user_id=current_user.id,
        action="material_download",
        resource_type="source_file",
        resource_id=file_id,
        details={
            "course_id": content.course_id,
            "filename": source.filename,
            "file_size": source.file_size,
            "content_id": content_id,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    media_type = source.file_type
    if not media_type:
        media_type = mimetypes.guess_type(source.filename or "")[0] or "application/octet-stream"
    filename = source.filename or f"file-{file_id}"

    if source.gcs_path:
        file_bytes = gcs_service.download_file(source.gcs_path)
        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": _content_disposition(filename),
                "Content-Length": str(len(file_bytes)),
            },
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file data not available")


# ── Linked Materials endpoints (#1740) ────────────────────────────

@router.get("/{content_id}/linked-materials", response_model=list[LinkedMaterialResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_linked_materials_endpoint(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all materials linked to this content (master + siblings in the same group)."""
    content = db.query(CourseContent).filter(CourseContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

    linked = get_linked_materials(db, content_id)
    # Convert to response with has_file computed
    results = []
    for m in linked:
        results.append(LinkedMaterialResponse(
            id=m.id,
            title=m.title,
            is_master=m.is_master,
            content_type=m.content_type,
            has_file=m.file_path is not None,
            original_filename=m.original_filename,
            created_at=m.created_at,
        ))
    return results


@router.put("/{content_id}/reorder-subs")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def reorder_sub_materials(
    request: Request,
    content_id: int,
    data: ReorderSubsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder sub-materials within a master material group."""
    content = db.query(CourseContent).filter(
        CourseContent.id == content_id,
        CourseContent.archived_at.is_(None),
    ).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not content.is_master:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only master materials can have sub-materials reordered")

    if not can_access_course(db, current_user, content.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    # Validate all sub_ids belong to this master's group
    subs = db.query(CourseContent).filter(
        CourseContent.parent_content_id == content.id,
        CourseContent.archived_at.is_(None),
    ).all()
    sub_id_set = {s.id for s in subs}

    for sid in data.sub_ids:
        if sid not in sub_id_set:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sub-material {sid} does not belong to this master group",
            )

    # Update display_order
    sub_map = {s.id: s for s in subs}
    for order, sid in enumerate(data.sub_ids, 1):
        sub_map[sid].display_order = order

    db.commit()
    return {"status": "ok", "reordered": len(data.sub_ids)}


# ── Delete Sub-Material endpoint (#993) ───────────────────────────

@router.delete("/{content_id}/sub-materials/{sub_id}", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_sub_material(
    request: Request,
    content_id: int,
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sub-material from a master group. Demotes master if last sub removed."""
    master = db.query(CourseContent).filter(
        CourseContent.id == content_id,
        CourseContent.archived_at.is_(None),
    ).first()
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not master.is_master:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only master materials can have sub-materials deleted")

    if not can_access_course(db, current_user, master.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    sub = db.query(CourseContent).filter(
        CourseContent.id == sub_id,
        CourseContent.parent_content_id == content_id,
        CourseContent.archived_at.is_(None),
    ).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-material not found in this group")

    # Track file size for storage quota
    if sub.file_size and sub.created_by_user_id:
        creator = db.query(User).filter(User.id == sub.created_by_user_id).first()
        if creator:
            record_deletion(db, creator, sub.file_size)

    # Delete sub's source files, images, study guides
    db.query(SourceFile).filter(SourceFile.course_content_id == sub_id).delete()
    db.query(ContentImage).filter(ContentImage.course_content_id == sub_id).delete()
    db.query(StudyGuide).filter(StudyGuide.course_content_id == sub_id).delete()
    db.query(ResourceLink).filter(ResourceLink.course_content_id == sub_id).delete()
    db.delete(sub)
    db.flush()

    # Check remaining subs
    remaining = db.query(CourseContent).filter(
        CourseContent.parent_content_id == content_id,
        CourseContent.archived_at.is_(None),
    ).count()

    if remaining == 0:
        # Demote master back to standalone
        master.is_master = False
        master.material_group_id = None

    db.commit()
    db.refresh(master)
    return {"status": "ok", "remaining_subs": remaining, "is_master": master.is_master}


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

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

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

    if not can_access_material(db, current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this material")

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

    if image.gcs_path:
        image_bytes = gcs_service.download_file(image.gcs_path)
        return Response(
            content=image_bytes,
            media_type=image.media_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image data not available")
