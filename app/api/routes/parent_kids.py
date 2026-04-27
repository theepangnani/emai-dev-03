"""CB-KIDPHOTO-001 (#4301) — kid profile photo upload + delete.

Parent uploads a profile photo for a linked child. Photo replaces the
initial avatar in the My Hub bridge view. RBAC: PARENT only, must be
linked to the student via ``parent_students``. MFIPPA-compliant audit
logging — never logs image bytes or PII.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.services.audit_service import log_action
from app.services.kid_photo_service import (
    delete_from_gcs,
    process_image,
    upload_to_gcs,
    validate_image,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parent", tags=["parent-kids"])


def _verify_parent_child(db: Session, parent_user_id: int, student_id: int) -> Student:
    """Returns the Student or raises 403 if not linked to this parent."""
    student = (
        db.query(Student)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(
            parent_students.c.parent_id == parent_user_id,
            Student.id == student_id,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=403, detail="Not your child or student not found")
    return student


@router.post("/children/{student_id}/photo")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def upload_kid_photo(
    request: Request,
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Upload (or replace) a child's profile photo. Returns the new URL."""
    student = _verify_parent_child(db, current_user.id, student_id)

    raw = await validate_image(file)
    processed = process_image(raw)

    previous_url = student.profile_photo_url
    new_url = upload_to_gcs(processed, student_id)

    student.profile_photo_url = new_url
    db.add(student)

    log_action(
        db,
        user_id=current_user.id,
        action="parent_uploaded_kid_photo",
        resource_type="student",
        resource_id=student_id,
        details={"replaced_existing": bool(previous_url)},
    )
    db.commit()

    # Best-effort cleanup of the previous object — after commit so a delete
    # failure cannot block the upload.
    if previous_url and previous_url != new_url:
        delete_from_gcs(previous_url)

    return {"profile_photo_url": new_url}


@router.delete("/children/{student_id}/photo", status_code=204)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def delete_kid_photo(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Remove the child's profile photo. Always 204 on success."""
    student = _verify_parent_child(db, current_user.id, student_id)

    previous_url = student.profile_photo_url
    student.profile_photo_url = None
    db.add(student)

    log_action(
        db,
        user_id=current_user.id,
        action="parent_deleted_kid_photo",
        resource_type="student",
        resource_id=student_id,
        details={"had_photo": bool(previous_url)},
    )
    db.commit()

    if previous_url:
        delete_from_gcs(previous_url)

    return Response(status_code=204)
