"""Study Sessions (Pomodoro) API routes (#2021)."""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.study_session import StudySession
from app.models.user import User, UserRole
from app.schemas.study_session import (
    StudySessionStart,
    StudySessionComplete,
    StudySessionResponse,
    StudySessionListResponse,
    StudySessionStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study-sessions", tags=["study-sessions"])

MIN_DURATION_FOR_XP = 1200  # 20 minutes in seconds


def _generate_ai_recap(subject: str, duration_minutes: int) -> str | None:
    """Generate an AI recap using OpenAI. Returns None on failure."""
    try:
        from openai import OpenAI
        from app.core.config import settings

        if not settings.openai_api_key:
            return None

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an encouraging study coach for students.",
                },
                {
                    "role": "user",
                    "content": (
                        f"The student just completed a {duration_minutes} minute study session "
                        f"on {subject}. Generate a brief, encouraging recap with 3 key things "
                        f"to remember. Keep it warm and motivating."
                    ),
                },
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception:
        logger.exception("AI recap generation failed")
        return None


@router.post("/start", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def start_session(
    request: Request,
    body: StudySessionStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Start a new study session."""
    session = StudySession(
        student_id=current_user.id,
        course_id=body.course_id,
        subject=body.subject,
        duration_seconds=0,
        target_duration=body.target_duration,
        completed=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/complete", response_model=StudySessionResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def complete_session(
    request: Request,
    session_id: int,
    body: StudySessionComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Complete a study session with actual duration."""
    session = (
        db.query(StudySession)
        .filter(StudySession.id == session_id, StudySession.student_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")

    if session.completed:
        raise HTTPException(status_code=400, detail="Session already completed")

    session.duration_seconds = body.duration_seconds
    completed = body.duration_seconds >= MIN_DURATION_FOR_XP
    session.completed = completed

    # Award XP if >= 20 min
    if completed:
        from app.services.xp_service import award_xp
        entry = award_xp(db, current_user.id, "pomodoro")
        if entry:
            session.xp_awarded = entry.xp_awarded

        # Generate AI recap (non-blocking — don't fail completion)
        subject = session.subject or "their studies"
        duration_minutes = body.duration_seconds // 60
        recap = _generate_ai_recap(subject, duration_minutes)
        if recap:
            session.ai_recap = recap

    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=StudySessionListResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def list_sessions(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """List past study sessions (paginated)."""
    total = (
        db.query(func.count(StudySession.id))
        .filter(StudySession.student_id == current_user.id)
        .scalar()
    ) or 0

    sessions = (
        db.query(StudySession)
        .filter(StudySession.student_id == current_user.id)
        .order_by(StudySession.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return StudySessionListResponse(
        items=[StudySessionResponse.model_validate(s) for s in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=StudySessionStats)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Get weekly study session stats."""
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    sessions = (
        db.query(StudySession)
        .filter(
            StudySession.student_id == current_user.id,
            StudySession.created_at >= week_ago,
        )
        .all()
    )

    total_sessions = len(sessions)
    total_seconds = sum(s.duration_seconds for s in sessions)
    total_minutes = total_seconds // 60
    xp_earned = sum(s.xp_awarded or 0 for s in sessions)

    return StudySessionStats(
        total_sessions=total_sessions,
        total_minutes=total_minutes,
        xp_earned=xp_earned,
    )
