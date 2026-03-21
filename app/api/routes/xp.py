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


@router.post("/streak/recover")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def recover_streak(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attempt to recover a broken streak."""
    from app.services.streak_service import StreakService
    result = StreakService.recover_streak(db, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not eligible for streak recovery",
        )
    return result


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
    from app.models.student import student_teachers

    # Verify the target is a student
    target_user = db.query(User).filter(User.id == body.student_user_id).first()
    if not target_user or target_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=404, detail="Student not found")

    # Weekly cap differs by role
    weekly_cap = 50  # default for parents and admins

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
        weekly_cap = 50

    # Teachers can only award to students linked via student_teachers
    elif current_user.role == UserRole.TEACHER:
        student = db.query(Student).filter(Student.user_id == body.student_user_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        link = (
            db.query(student_teachers)
            .filter(
                student_teachers.c.student_id == student.id,
                student_teachers.c.teacher_user_id == current_user.id,
            )
            .first()
        )
        if not link:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only award points to your linked students",
            )
        weekly_cap = 30

    from app.services.xp_service import XpService
    result = XpService.award_brownie_points(
        db,
        student_user_id=body.student_user_id,
        points=body.points,
        awarder_id=current_user.id,
        reason=body.reason,
        weekly_cap=weekly_cap,
    )
    if result.awarded == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message,
        )
    db.commit()
    return result


@router.get("/award/remaining")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_brownie_remaining(
    request: Request,
    student_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN)),
):
    """Get remaining weekly brownie points cap for a specific student."""
    weekly_cap = 30 if current_user.role == UserRole.TEACHER else 50
    from app.services.xp_service import XpService
    remaining = XpService.get_weekly_brownie_remaining(
        db, current_user.id, student_user_id, weekly_cap,
    )
    return {"remaining": remaining, "weekly_cap": weekly_cap}
