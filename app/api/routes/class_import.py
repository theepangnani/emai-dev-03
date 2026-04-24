"""CB-ONBOARD-001 backend routes (#3985).

Three endpoints mounted under /api/courses:
  - GET  /google-classroom/preview   — preview classes+teachers from connected Google
  - POST /parse-screenshot           — parse an uploaded GC screenshot via Claude vision
  - POST /bulk                       — bulk-create classes+teachers from a normalized list

Reuses existing helpers from courses.py and google_classroom service.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.encryption import decrypt_token
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.class_import import (
    BulkCreateRequest,
    BulkCreatedItem,
    BulkCreateResult,
    BulkFailedItem,
    GoogleClassroomPreviewCourse,
    GoogleClassroomPreviewResponse,
    ParseScreenshotResponse,
    ParsedScreenshotRow,
)
from app.services.audit_service import log_action
from app.services.class_import_service import (
    AlreadyImportedError,
    import_one_row,
    parse_screenshot_with_vision,
)
from app.services.google_classroom import (
    list_course_teachers,
    list_courses,
)

logger = logging.getLogger(__name__)

# Match the existing courses router — this file's prefix is re-mounted under /api
router = APIRouter(prefix="/courses", tags=["class-import"])

CLASSROOM_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/classroom.courses.readonly"
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _looks_like_allowed_image(data: bytes) -> bool:
    """Sniff the first few bytes to confirm JPEG, PNG, or WebP content.

    Defends against clients that send a non-image payload with an image MIME
    type. Standard-library only — no PIL dependency.
    """
    if len(data) < 12:
        return False
    # JPEG: FF D8 FF
    if data[:3] == b"\xff\xd8\xff":
        return True
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    # WebP: "RIFF" ???? "WEBP"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return False


def _is_google_connected(user: User) -> bool:
    """Return True when the user has a live Google Classroom token."""
    if not user.google_access_token:
        return False
    # If scopes list is tracked, require the classroom scope.
    if user.google_granted_scopes:
        return user.has_google_scope(CLASSROOM_READONLY_SCOPE)
    # Legacy accounts without scope tracking — allow through (fall through to API).
    return True


@router.get(
    "/google-classroom/preview",
    response_model=GoogleClassroomPreviewResponse,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def preview_google_classroom(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview Google Classroom courses+teachers for bulk import.

    Returns a 200 with ``connected: false`` when the user hasn't OAuth'd
    (frontend renders a "Connect Google" CTA instead of erroring).
    """
    if not _is_google_connected(current_user):
        return GoogleClassroomPreviewResponse(
            connected=False,
            connect_url="/api/google/auth",
            courses=[],
        )

    access_token = decrypt_token(current_user.google_access_token)
    refresh_token = decrypt_token(current_user.google_refresh_token)

    try:
        gc_courses, _creds = list_courses(access_token, refresh_token)
    except Exception as e:
        logger.warning("Google Classroom preview: list_courses failed: %s", e)
        return GoogleClassroomPreviewResponse(
            connected=True,
            error="Google Classroom temporarily unavailable",
            courses=[],
        )

    # Collect existing gc_ids so we can mark duplicates.
    gc_ids = [c.get("id") for c in gc_courses if c.get("id")]
    existing_map: dict[str, int] = {}
    if gc_ids:
        rows = (
            db.query(Course.google_classroom_id, Course.id)
            .filter(Course.google_classroom_id.in_(gc_ids))
            .all()
        )
        existing_map = {gcid: cid for gcid, cid in rows}

    def _fetch_teacher(
        gc_id: str,
    ) -> tuple[str, str | None, str | None]:
        try:
            teachers, _ = list_course_teachers(
                access_token, gc_id, refresh_token
            )
            if teachers:
                profile = teachers[0].get("profile") or {}
                name_obj = profile.get("name") or {}
                return (
                    gc_id,
                    name_obj.get("fullName") or None,
                    profile.get("emailAddress") or None,
                )
        except Exception as e:
            logger.warning(
                "Google Classroom preview: list_course_teachers failed for %s: %s",
                gc_id,
                e,
            )
        return gc_id, None, None

    teacher_by_id: dict[str, tuple[str | None, str | None]] = {}
    course_gc_ids = [c.get("id") for c in gc_courses if c.get("id")]
    if course_gc_ids:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_fetch_teacher, cid) for cid in course_gc_ids]
            for fut in as_completed(futures):
                gc_id, t_name, t_email = fut.result()
                teacher_by_id[gc_id] = (t_name, t_email)

    out_courses: list[GoogleClassroomPreviewCourse] = []
    for c in gc_courses:
        gc_id = c.get("id")
        if not gc_id:
            continue

        class_name = c.get("name") or ""
        section = c.get("section") or None

        teacher_name, teacher_email = teacher_by_id.get(gc_id, (None, None))

        existing_course_id = existing_map.get(gc_id)
        out_courses.append(
            GoogleClassroomPreviewCourse(
                class_name=class_name,
                section=section,
                teacher_name=teacher_name,
                teacher_email=teacher_email,
                google_classroom_id=gc_id,
                existing=existing_course_id is not None,
                existing_course_id=existing_course_id,
            )
        )

    return GoogleClassroomPreviewResponse(
        connected=True,
        courses=out_courses,
    )


@router.post(
    "/parse-screenshot",
    response_model=ParseScreenshotResponse,
)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def parse_screenshot(
    request: Request,
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Parse a Google Classroom screenshot into a list of class/teacher rows.

    Uses Claude vision. Always returns a JSON array (possibly empty).
    """
    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type. Use JPEG, PNG, or WebP.",
        )

    data = await image.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty upload.",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image too large (max 10 MB).",
        )
    if not _looks_like_allowed_image(data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload contents do not look like a JPEG, PNG, or WebP image.",
        )

    # Normalize jpg -> jpeg for Anthropic vision API
    media_type = "image/jpeg" if content_type == "image/jpg" else content_type

    try:
        rows = await asyncio.to_thread(
            parse_screenshot_with_vision, data, media_type
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "Could not parse screenshot. Try a clearer image."},
        )
    except anthropic.APIError:
        logger.exception("parse_screenshot: Anthropic API error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "AI vision service unavailable. Please try again."},
        )
    except Exception:
        logger.exception("parse_screenshot: unexpected error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "Could not parse screenshot. Try a clearer image."},
        )

    parsed_rows = [
        ParsedScreenshotRow(
            class_name=r["class_name"],
            section=r.get("section"),
            teacher_name=r["teacher_name"],
            teacher_email=None,
        )
        for r in rows
    ]
    return ParseScreenshotResponse(parsed=parsed_rows)


@router.post("/bulk", response_model=BulkCreateResult)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def bulk_create(
    request: Request,
    body: BulkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk-create classes+teachers from an import list.

    Each row is processed independently — one bad row does not abort the
    batch. Rows that point at an existing google_classroom_id are reported
    under ``failed`` with ``error: "already_imported"``.
    """
    created: list[BulkCreatedItem] = []
    failed: list[BulkFailedItem] = []

    for idx, row in enumerate(body.rows):
        # SAVEPOINT per row so one failure rolls back only that row.
        nested = db.begin_nested()
        try:
            course = import_one_row(db, row, current_user)
            log_action(
                db,
                user_id=current_user.id,
                action="bulk_import",
                resource_type="course",
                resource_id=course.id,
                details={"name": course.name},
            )
            nested.commit()
            created.append(
                BulkCreatedItem(
                    index=idx,
                    course_id=course.id,
                    name=course.name,
                )
            )
        except AlreadyImportedError as e:
            nested.rollback()
            failed.append(
                BulkFailedItem(
                    index=idx,
                    error="already_imported",
                    existing_course_id=e.existing_course_id,
                )
            )
        except HTTPException as e:
            nested.rollback()
            failed.append(
                BulkFailedItem(
                    index=idx,
                    error=str(e.detail) if e.detail else "http_error",
                )
            )
        except ValidationError as e:
            nested.rollback()
            failed.append(
                BulkFailedItem(
                    index=idx, error="validation_error", details=e.errors()
                )
            )
        except Exception as e:
            logger.exception("bulk_create: row %d failed", idx)
            nested.rollback()
            failed.append(
                BulkFailedItem(
                    index=idx, error=f"{type(e).__name__}: {e}"
                )
            )

    db.commit()
    return BulkCreateResult(created=created, failed=failed)
