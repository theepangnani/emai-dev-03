"""Age-based consent endpoints for MFIPPA compliance (#783).

Consent requirements by age:
  - Under 16: Parent provides consent on child's behalf
  - 16-17:    Both student AND parent must consent
  - 18+:      Student alone provides consent
"""
import logging
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.schemas.consent import ConsentStatusResponse, GiveConsentRequest
from app.api.deps import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent", tags=["Consent"])


def _calculate_age(dob: date) -> int:
    """Calculate age from date of birth."""
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
    )


def _build_consent_status(student: Student) -> ConsentStatusResponse:
    """Build a ConsentStatusResponse from a Student record."""
    age = _calculate_age(student.date_of_birth) if student.date_of_birth else None

    requires_parent = False
    requires_student = False

    if age is not None:
        if age < 16:
            requires_parent = True
        elif age < 18:
            requires_parent = True
            requires_student = True
        else:
            requires_student = True
    else:
        # No DOB — assume student consent required (conservative default)
        requires_student = True

    return ConsentStatusResponse(
        student_id=student.id,
        consent_status=student.consent_status or "pending",
        age=age,
        requires_parent_consent=requires_parent,
        requires_student_consent=requires_student,
        parent_consent_given=student.parent_consent_given_at is not None,
        student_consent_given=student.student_consent_given_at is not None,
        parent_consent_given_at=student.parent_consent_given_at,
        student_consent_given_at=student.student_consent_given_at,
    )


def _resolve_consent_status(student: Student) -> str:
    """Determine the current consent_status based on age and consent timestamps."""
    age = _calculate_age(student.date_of_birth) if student.date_of_birth else None

    if age is not None and age < 16:
        # Parent-only consent
        if student.parent_consent_given_at:
            return "given"
        return "parent_only"
    elif age is not None and age < 18:
        # Dual consent required
        if student.parent_consent_given_at and student.student_consent_given_at:
            return "given"
        return "dual_required"
    else:
        # 18+ or no DOB — student consent only
        if student.student_consent_given_at:
            return "given"
        return "pending"


@router.get("/status/{student_id}", response_model=ConsentStatusResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_consent_status(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check the consent status of a student. Accessible by the student themselves,
    their linked parent, or an admin."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Authorization: student (self), parent (linked), or admin
    is_self = student.user_id == current_user.id
    is_admin = current_user.has_role(UserRole.ADMIN)
    is_parent = False
    if current_user.has_role(UserRole.PARENT):
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student.id,
        ).first()
        is_parent = link is not None

    if not (is_self or is_parent or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return _build_consent_status(student)


@router.post("/give")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def give_consent(
    request: Request,
    body: GiveConsentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student gives their own consent. Only valid for students aged 16+ or those
    without a DOB on record."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No student profile found for current user",
        )

    if not body.accept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent must be accepted to use the platform",
        )

    # Check age restriction
    if student.date_of_birth:
        age = _calculate_age(student.date_of_birth)
        if age < 16:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students under 16 require parent consent. Please ask your parent to consent on your behalf.",
            )

    student.student_consent_given_at = datetime.now(timezone.utc)
    student.consent_status = _resolve_consent_status(student)
    db.commit()
    db.refresh(student)

    logger.info("Student %s (user %s) gave consent, status=%s", student.id, current_user.id, student.consent_status)
    return {"message": "Consent recorded", "consent_status": student.consent_status}


@router.post("/give-for-child/{student_id}")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def give_consent_for_child(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Parent gives consent on behalf of their linked child."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Verify parent-child link
    link = db.query(parent_students).filter(
        parent_students.c.parent_id == current_user.id,
        parent_students.c.student_id == student.id,
    ).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not linked to this student",
        )

    student.parent_consent_given_at = datetime.now(timezone.utc)
    student.consent_status = _resolve_consent_status(student)
    db.commit()
    db.refresh(student)

    logger.info(
        "Parent %s gave consent for student %s, status=%s",
        current_user.id, student.id, student.consent_status,
    )
    return {"message": "Parent consent recorded", "consent_status": student.consent_status}
