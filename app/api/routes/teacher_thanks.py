import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.teacher_thanks import TeacherThanks
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role
from app.schemas.teacher_thanks import (
    TeacherThanksCreate,
    TeacherThanksResponse,
    TeacherThanksCount,
    TeacherThanksStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teachers", tags=["Teacher Thanks"])


@router.get("/me/thanks-count", response_model=TeacherThanksCount)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_my_thanks_count(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """Get thanks count for the currently logged-in teacher."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher profile not found")

    total_count = (
        db.query(sa_func.count(TeacherThanks.id))
        .filter(TeacherThanks.teacher_id == teacher.id)
        .scalar()
    ) or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_count = (
        db.query(sa_func.count(TeacherThanks.id))
        .filter(
            TeacherThanks.teacher_id == teacher.id,
            TeacherThanks.created_at >= week_ago,
        )
        .scalar()
    ) or 0

    return TeacherThanksCount(teacher_id=teacher.id, total_count=total_count, week_count=week_count)


@router.post("/{teacher_id}/thank", response_model=TeacherThanksResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def send_thanks(
    request: Request,
    teacher_id: int,
    body: TeacherThanksCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.PARENT)),
):
    """Send a thank-you to a teacher (one per student per teacher per day)."""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = (
        db.query(TeacherThanks)
        .filter(
            TeacherThanks.from_user_id == current_user.id,
            TeacherThanks.teacher_id == teacher_id,
            TeacherThanks.created_at >= today_start,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have already thanked this teacher today",
        )

    thanks = TeacherThanks(
        from_user_id=current_user.id,
        teacher_id=teacher_id,
        course_id=body.course_id,
        message=body.message,
    )
    db.add(thanks)
    db.commit()
    db.refresh(thanks)
    logger.info("User %d sent thanks to teacher %d", current_user.id, teacher_id)
    return thanks


@router.get("/{teacher_id}/thanks-count", response_model=TeacherThanksCount)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_thanks_count(
    request: Request,
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total and this-week thanks count for a teacher."""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    total_count = (
        db.query(sa_func.count(TeacherThanks.id))
        .filter(TeacherThanks.teacher_id == teacher_id)
        .scalar()
    ) or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_count = (
        db.query(sa_func.count(TeacherThanks.id))
        .filter(
            TeacherThanks.teacher_id == teacher_id,
            TeacherThanks.created_at >= week_ago,
        )
        .scalar()
    ) or 0

    return TeacherThanksCount(teacher_id=teacher_id, total_count=total_count, week_count=week_count)


@router.get("/{teacher_id}/thanks-status", response_model=TeacherThanksStatus)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_thanks_status(
    request: Request,
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.PARENT)),
):
    """Check if current user already thanked this teacher today."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = (
        db.query(TeacherThanks.id)
        .filter(
            TeacherThanks.from_user_id == current_user.id,
            TeacherThanks.teacher_id == teacher_id,
            TeacherThanks.created_at >= today_start,
        )
        .first()
    )
    return TeacherThanksStatus(thanked_today=existing is not None)
