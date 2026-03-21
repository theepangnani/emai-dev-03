"""
XP / Streak API routes (#2002, #2003).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.logging_config import get_logger
from app.models.user import User, UserRole
from app.services.streak_service import StreakService

logger = get_logger(__name__)

router = APIRouter(prefix="/xp", tags=["XP & Streaks"])


@router.get("/streak")
def get_streak(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Returns streak info for the current student."""
    return StreakService.get_streak_info(db, current_user.id)


@router.post("/streak/recover")
def recover_streak(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Attempt streak recovery (if eligible)."""
    # Check eligibility first
    recovery_info = StreakService.check_streak_recovery(db, current_user.id)
    if not recovery_info:
        raise HTTPException(
            status_code=400,
            detail="Not eligible for streak recovery",
        )

    result = StreakService.recover_streak(db, current_user.id)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Streak recovery failed",
        )

    return result
