import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.bug_report import BugReport
from app.models.user import User, UserRole
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
    background_tasks: BackgroundTasks,
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
        background_tasks=background_tasks,
    )

    return report


@router.get("/bug-reports/{report_id}/screenshot")
async def get_bug_report_screenshot(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve bug report screenshot. Accessible by admins and the report submitter."""
    report = db.query(BugReport).filter(BugReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Bug report not found")

    # Access control: admin or the user who submitted the report
    is_admin = current_user.role == UserRole.ADMIN or (
        current_user.roles and "admin" in current_user.roles
    )
    if not is_admin and current_user.id != report.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not report.screenshot_url:
        raise HTTPException(status_code=404, detail="No screenshot attached")

    # If screenshot is a GCS path (not a data URL), download from GCS
    if report.screenshot_url.startswith("bug-reports/"):
        try:
            from app.services.gcs_service import download_file

            image_bytes = download_file(report.screenshot_url)
            # Determine content type from extension
            if report.screenshot_url.endswith(".png"):
                content_type = "image/png"
            elif report.screenshot_url.endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            elif report.screenshot_url.endswith(".webp"):
                content_type = "image/webp"
            else:
                content_type = "image/png"
            return Response(content=image_bytes, media_type=content_type)
        except Exception:
            raise HTTPException(
                status_code=404, detail="Screenshot not found in storage"
            )

    # If screenshot is a base64 data URL, decode and serve
    if report.screenshot_url.startswith("data:"):
        import base64

        # Parse data URL: data:image/png;base64,xxxx
        header, b64_data = report.screenshot_url.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
        image_bytes = base64.b64decode(b64_data)
        return Response(content=image_bytes, media_type=content_type)

    raise HTTPException(status_code=404, detail="Screenshot format not recognized")
