"""Weekly Progress Pulse digest endpoints for parents."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.weekly_digest import WeeklyDigestResponse, WeeklyDigestSendResponse
from app.services.weekly_digest_service import (
    generate_weekly_digest,
    send_weekly_digest_email,
)

router = APIRouter(prefix="/digest", tags=["Digest"])


@router.get("/weekly/preview", response_model=WeeklyDigestResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def weekly_digest_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Preview the weekly digest data as JSON."""
    return generate_weekly_digest(db, current_user.id)


@router.post("/weekly/send", response_model=WeeklyDigestSendResponse)
@limiter.limit("3/hour", key_func=get_user_id_or_ip)
async def weekly_digest_send(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Send the weekly digest email to the parent immediately."""
    success = await send_weekly_digest_email(db, current_user.id)
    if success:
        return WeeklyDigestSendResponse(success=True, message="Weekly digest sent to your email!")
    return WeeklyDigestSendResponse(success=False, message="Failed to send email. Please try again later.")
