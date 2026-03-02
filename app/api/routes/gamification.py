"""Gamification API routes."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.gamification import UserBadge, XPTransaction
from app.models.user import User, UserRole
from app.schemas.gamification import (
    BadgeDefinitionResponse,
    LeaderboardOptInRequest,
    LeaderboardResponse,
    NewBadgeNotification,
    UserBadgeResponse,
    UserXPResponse,
    XPTransactionResponse,
)
from app.services.gamification import GamificationService

router = APIRouter(tags=["gamification"])


def _build_xp_response(svc: GamificationService, user_id: int) -> UserXPResponse:
    xp = svc.get_user_xp(user_id)
    data = svc.xp_response_data(xp)
    return UserXPResponse(**data)


# ---------------------------------------------------------------------------
# Badge definitions
# ---------------------------------------------------------------------------


@router.get("/badges/", response_model=List[BadgeDefinitionResponse])
def list_all_badges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active badge definitions."""
    from app.models.gamification import BadgeDefinition

    badges = db.query(BadgeDefinition).filter(BadgeDefinition.is_active.is_(True)).all()
    return badges


@router.get("/badges/mine", response_model=List[UserBadgeResponse])
def get_my_badges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return badges the current user has earned."""
    svc = GamificationService(db)
    user_badges = svc.get_user_badges(current_user.id)

    # Mark all as notified
    for ub in user_badges:
        if not ub.notified:
            ub.notified = True
    db.commit()

    return user_badges


@router.get("/badges/new", response_model=List[NewBadgeNotification])
def get_new_badge_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return badges earned but not yet notified (for toast display). Marks them as notified."""
    unnotified = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == current_user.id, UserBadge.notified.is_(False))
        .all()
    )
    result = []
    for ub in unnotified:
        ub.notified = True
        result.append(
            NewBadgeNotification(
                badge=BadgeDefinitionResponse.model_validate(ub.badge),
                xp_awarded=ub.badge.xp_reward,
            )
        )
    db.commit()
    return result


@router.get("/badges/student/{student_user_id}", response_model=List[UserBadgeResponse])
def get_student_badges(
    student_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN)),
):
    """Parent/teacher: view badges earned by a specific student."""
    from app.models.student import Student
    from app.models.student import parent_students

    # Verify parent has access to this student
    if current_user.role == UserRole.PARENT:
        student = (
            db.query(Student)
            .filter(Student.user_id == student_user_id)
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        link = (
            db.query(parent_students)
            .filter_by(parent_id=current_user.id, student_id=student.id)
            .first()
        )
        if not link:
            raise HTTPException(status_code=403, detail="Access denied")

    svc = GamificationService(db)
    return svc.get_user_badges(student_user_id)


# ---------------------------------------------------------------------------
# XP
# ---------------------------------------------------------------------------


@router.get("/xp/", response_model=UserXPResponse)
def get_my_xp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's XP and level."""
    svc = GamificationService(db)
    return _build_xp_response(svc, current_user.id)


@router.get("/xp/history", response_model=List[XPTransactionResponse])
def get_xp_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent XP transactions for the current user."""
    transactions = (
        db.query(XPTransaction)
        .filter(XPTransaction.user_id == current_user.id)
        .order_by(XPTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return transactions


@router.patch("/xp/leaderboard-opt-in", response_model=UserXPResponse)
def toggle_leaderboard_opt_in(
    body: LeaderboardOptInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle the user's opt-in status for the leaderboard."""
    svc = GamificationService(db)
    xp = svc.get_user_xp(current_user.id)
    xp.leaderboard_opt_in = body.opt_in
    db.commit()
    db.refresh(xp)
    return _build_xp_response(svc, current_user.id)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the top users by XP (opt-in only, anonymised display names)."""
    svc = GamificationService(db)
    entries = svc.get_leaderboard(limit=limit)
    return LeaderboardResponse(entries=entries, total=len(entries))
