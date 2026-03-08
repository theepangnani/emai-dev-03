"""Daily Briefing endpoint for parents."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.briefing import DailyBriefingResponse
from app.services.briefing_service import get_daily_briefing

router = APIRouter(prefix="/briefing", tags=["Briefing"])


@router.get("/daily", response_model=DailyBriefingResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def daily_briefing(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get the daily briefing for a parent — overdue tasks, due today, upcoming assignments per child."""
    return get_daily_briefing(db, current_user.id)
