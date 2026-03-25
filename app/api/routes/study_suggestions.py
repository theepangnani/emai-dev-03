"""Study Suggestions API routes (#2227)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.study_suggestions import StudySuggestionsResponse
from app.services.study_suggestions_service import get_study_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/students", tags=["study-suggestions"])


@router.get("/me/study-suggestions", response_model=StudySuggestionsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def my_study_suggestions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Get study time suggestions for the current student."""
    return get_study_suggestions(db, current_user.id)


@router.get("/{student_id}/study-suggestions", response_model=StudySuggestionsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def student_study_suggestions(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get study time suggestions for a student.

    Access: the student themselves, a linked parent, or an admin.
    student_id here is the students table PK (not user_id).
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Admin sees all
    if current_user.role == UserRole.ADMIN:
        return get_study_suggestions(db, student.user_id)

    # Student sees own
    if current_user.role == UserRole.STUDENT and student.user_id == current_user.id:
        return get_study_suggestions(db, student.user_id)

    # Parent sees linked children
    if current_user.role == UserRole.PARENT:
        link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student_id,
            )
            .first()
        )
        if link:
            return get_study_suggestions(db, student.user_id)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
