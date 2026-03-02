from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role, get_db
from app.models.user import User, UserRole
from app.models.study_timer import StudySession
from app.schemas.study_timer import (
    StudySessionCreate,
    StudySessionResponse,
    StudyStreakResponse,
    StudyStatsResponse,
)
from app.services.study_timer import StudyTimerService

router = APIRouter(tags=["study-timer"])

_service = StudyTimerService()


# ---------------------------------------------------------------------------
# Start a new session
# ---------------------------------------------------------------------------


@router.post(
    "/study-timer/sessions/start",
    response_model=StudySessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_session(
    payload: StudySessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new Pomodoro session (work, short_break, or long_break)."""
    session = _service.start_session(
        user_id=current_user.id,
        session_type=payload.session_type,
        db=db,
        course_id=payload.course_id,
    )
    return session


# ---------------------------------------------------------------------------
# End a session
# ---------------------------------------------------------------------------


@router.post(
    "/study-timer/sessions/{session_id}/end",
    response_model=StudySessionResponse,
)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a session as ended and calculate duration."""
    session = _service.end_session(
        session_id=session_id,
        user_id=current_user.id,
        db=db,
    )
    return session


# ---------------------------------------------------------------------------
# List recent sessions (last 30)
# ---------------------------------------------------------------------------


@router.get(
    "/study-timer/sessions",
    response_model=List[StudySessionResponse],
)
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the 30 most recent study sessions for the authenticated user."""
    sessions = (
        db.query(StudySession)
        .filter(StudySession.user_id == current_user.id)
        .order_by(StudySession.started_at.desc())
        .limit(30)
        .all()
    )
    return sessions


# ---------------------------------------------------------------------------
# Get current streak
# ---------------------------------------------------------------------------


@router.get(
    "/study-timer/streak",
    response_model=StudyStreakResponse,
)
def get_streak(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current streak record for the authenticated user."""
    streak = _service.get_streak(user_id=current_user.id, db=db)
    return streak


# ---------------------------------------------------------------------------
# Get stats summary
# ---------------------------------------------------------------------------


@router.get(
    "/study-timer/stats",
    response_model=StudyStatsResponse,
)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated study statistics for the authenticated user."""
    return _service.get_stats(user_id=current_user.id, db=db)


# ---------------------------------------------------------------------------
# Parent: child stats
# ---------------------------------------------------------------------------


@router.get(
    "/study-timer/stats/{student_id}",
    response_model=StudyStatsResponse,
)
def get_child_stats(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """Parent/admin endpoint — return a specific student's study stats."""
    return _service.get_parent_child_stats(
        parent_id=current_user.id,
        student_user_id=student_id,
        db=db,
    )
