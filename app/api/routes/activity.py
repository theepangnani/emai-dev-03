"""Recent Activity feed endpoint for parents."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import require_role
from app.schemas.activity import ActivityItem
from app.services.activity_service import get_recent_activity

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/recent", response_model=list[ActivityItem])
def recent_activity(
    student_id: int | None = None,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Return a unified recent-activity feed for the authenticated parent."""
    return get_recent_activity(db, current_user.id, student_id=student_id, limit=limit)
