"""Family Report Card preview endpoint (#2228).

Thin wrapper around the weekly digest service -- provides a dedicated
``/api/family-report/preview`` URL that parents can bookmark or share.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.weekly_digest import WeeklyDigestResponse
from app.services.weekly_digest_service import generate_weekly_digest

router = APIRouter(prefix="/family-report", tags=["Family Report"])


@router.get("/preview", response_model=WeeklyDigestResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def family_report_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Preview this week's family report card as JSON."""
    return generate_weekly_digest(db, current_user.id)
