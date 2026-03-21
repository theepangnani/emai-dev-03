import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.bug_report import BugReport
from app.models.user import User
from app.schemas.bug_report import BugReportResponse
from app.services.bug_report_service import create_bug_report

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bug-reports"])

MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
RATE_LIMIT_PER_HOUR = 20


@router.post("/bug-reports", response_model=BugReportResponse)
@limiter.limit("20/hour")
async def submit_bug_report(
    request: Request,
    description: Optional[str] = Form(None),
    page_url: Optional[str] = Form(None),
    user_agent: Optional[str] = Form(None),
    website: Optional[str] = Form(None),  # honeypot field
    screenshot: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a bug report with optional screenshot."""
    # Honeypot check — bots auto-fill this hidden field
    if website:
        logger.warning(f"Honeypot triggered for user {current_user.id}")
        return BugReportResponse(
            id=0,
            user_id=current_user.id,
            description=description,
            screenshot_url=None,
            page_url=page_url,
            user_agent=user_agent,
            github_issue_number=None,
            github_issue_url=None,
            created_at=datetime.now(timezone.utc),
        )

    # Additional rate limiting check via DB (defense-in-depth)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count = db.query(BugReport).filter(
        BugReport.user_id == current_user.id,
        BugReport.created_at >= one_hour_ago,
    ).count()
    if recent_count >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many bug reports. Please try again later.",
        )

    # Process screenshot if provided
    screenshot_bytes = None
    screenshot_content_type = None
    if screenshot and screenshot.filename:
        if screenshot.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Screenshot must be PNG, JPG, or WebP image.",
            )
        screenshot_bytes = await screenshot.read()
        if len(screenshot_bytes) > MAX_SCREENSHOT_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Screenshot must be under 5 MB.",
            )
        screenshot_content_type = screenshot.content_type

    report = create_bug_report(
        db=db,
        user=current_user,
        description=description,
        screenshot_bytes=screenshot_bytes,
        screenshot_content_type=screenshot_content_type,
        page_url=page_url,
        user_agent=user_agent,
    )

    return report
