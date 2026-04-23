"""CB-ONBOARD-001 backend routes (#3985).

Three endpoints mounted under /api/courses:
  - GET  /google-classroom/preview   — preview classes+teachers from connected Google
  - POST /parse-screenshot           — parse an uploaded GC screenshot via Claude vision
  - POST /bulk                       — bulk-create classes+teachers from a normalized list

Reuses existing helpers from courses.py and google_classroom service.
"""
from __future__ import annotations

import logging

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
    BulkCreateResult,
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

    out_courses: list[GoogleClassroomPreviewCourse] = []
    for c in gc_courses:
        gc_id = c.get("id")
        if not gc_id:
            continue

        class_name = c.get("name") or ""
        section = c.get("section") or None

        teacher_name: str | None = None
        teacher_email: str | None = None
        try:
            teachers, _ = list_course_teachers(
                access_token, gc_id, refresh_token
            )
            if teachers:
                # Use the first teacher in the roster as the primary.
                profile = teachers[0].get("profile") or {}
                name_obj = profile.get("name") or {}
                teacher_name = name_obj.get("fullName") or None
                teacher_email = profile.get("emailAddress") or None
        except Exception as e:
            logger.debug(
                "Google Classroom preview: list_course_teachers failed for %s: %s",
                gc_id,
                e,
            )

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

    # Normalize jpg -> jpeg for Anthropic vision API
    media_type = "image/jpeg" if content_type == "image/jpg" else content_type

    try:
        rows = parse_screenshot_with_vision(data, media_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "Could not parse screenshot. Try a clearer image."},
        )
    except Exception as e:
        logger.error("parse_screenshot vision call failed: %s", e)
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
    created: list[dict] = []
    failed: list[dict] = []

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
                {
                    "index": idx,
                    "course_id": course.id,
                    "name": course.name,
                }
            )
        except AlreadyImportedError as e:
            nested.rollback()
            failed.append(
                {
                    "index": idx,
                    "error": "already_imported",
                    "existing_course_id": e.existing_course_id,
                }
            )
        except HTTPException as e:
            nested.rollback()
            failed.append(
                {
                    "index": idx,
                    "error": str(e.detail) if e.detail else "http_error",
                }
            )
        except ValidationError as e:
            nested.rollback()
            failed.append(
                {"index": idx, "error": "validation_error", "details": e.errors()}
            )
        except Exception as e:
            logger.exception("bulk_create: row %d failed", idx)
            nested.rollback()
            failed.append({"index": idx, "error": f"{type(e).__name__}: {e}"})

    db.commit()
    return BulkCreateResult(created=created, failed=failed)
