"""XP / Gamification API routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.schemas.xp import (
    BrowniePointRequest,
    BrowniePointResponse,
    XpSummaryResponse,
    XpHistoryResponse,
    XpLedgerEntry,
    BadgeResponse,
    StreakResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/xp", tags=["xp"])


@router.get("/summary", response_model=XpSummaryResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_xp_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's XP summary (level, streak, total XP)."""
    from app.services.xp_service import XpService
    return XpService.get_summary(db, current_user.id)


@router.get("/history", response_model=XpHistoryResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_xp_history(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated XP history for current user."""
    from app.services.xp_service import XpService
    return XpService.get_history(db, current_user.id, limit=limit, offset=offset)


@router.get("/badges", response_model=list[BadgeResponse])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_badges(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all badges (earned and unearned) for current user."""
    from app.services.xp_service import XpService
    return XpService.get_badges(db, current_user.id)


@router.get("/streak", response_model=StreakResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_streak(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current streak info."""
    from app.services.xp_service import XpService
    return XpService.get_streak(db, current_user.id)


@router.get("/children/{student_id}/summary", response_model=XpSummaryResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_child_xp_summary(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """Parent endpoint: get child's XP summary."""
    # Verify parent-child relationship (admins bypass)
    if current_user.role != UserRole.ADMIN:
        student = (
            db.query(Student)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == current_user.id,
                Student.id == student_id,
            )
            .first()
        )
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your child or student not found",
            )
        child_user_id = student.user_id
    else:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        child_user_id = student.user_id

    from app.services.xp_service import XpService
    return XpService.get_summary(db, child_user_id)


@router.post("/award", response_model=BrowniePointResponse)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def award_brownie_points(
    request: Request,
    body: BrowniePointRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN)),
):
    """Parent/Teacher awards brownie points to a student."""
    # Verify the target is a student
    target_user = db.query(User).filter(User.id == body.student_user_id).first()
    if not target_user or target_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=404, detail="Student not found")

    # Parents can only award to their own children
    if current_user.role == UserRole.PARENT:
        student = (
            db.query(Student)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == current_user.id,
                Student.user_id == body.student_user_id,
            )
            .first()
        )
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only award points to your own children",
            )

    from app.services.xp_service import XpService
    result = XpService.award_brownie_points(
        db,
        student_user_id=body.student_user_id,
        points=body.points,
        awarder_id=current_user.id,
        reason=body.reason,
    )
    return result
