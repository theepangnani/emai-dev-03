"""Weekly Family Report Card endpoints for parents (#2228)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.weekly_report import WeeklyFamilyReportResponse, WeeklyReportSendResponse
from app.services.weekly_report_service import (
    generate_weekly_report,
    send_weekly_report_email,
)

router = APIRouter(prefix="/parent", tags=["Parent"])


@router.get("/weekly-report", response_model=WeeklyFamilyReportResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def weekly_report_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Preview the weekly family report card data as JSON."""
    return generate_weekly_report(db, current_user.id)


@router.post("/weekly-report/send", response_model=WeeklyReportSendResponse)
@limiter.limit("3/hour", key_func=get_user_id_or_ip)
async def weekly_report_send(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Send the weekly family report card email to the parent immediately."""
    success = await send_weekly_report_email(db, current_user.id)
    if success:
        return WeeklyReportSendResponse(success=True, message="Weekly report card sent to your email!")
    return WeeklyReportSendResponse(success=False, message="Failed to send email. Please try again later.")
