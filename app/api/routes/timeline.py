"""Study Timeline API route (#2017)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User
from app.schemas.timeline import TimelineResponse

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/timeline", response_model=TimelineResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_study_timeline(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    type: Optional[str] = Query(default=None, alias="type"),
    course_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a chronological timeline of all study activity for the current user."""
    from app.services.timeline_service import get_timeline

    return get_timeline(
        db,
        current_user.id,
        days=days,
        activity_type=type,
        course_id=course_id,
        limit=limit,
        offset=offset,
    )
