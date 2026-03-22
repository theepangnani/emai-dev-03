import base64
import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bug_report import BugReport
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.services.email_service import send_email_sync, wrap_branded_email

logger = logging.getLogger(__name__)


def _upload_screenshot_to_gcs(
    screenshot_bytes: bytes, screenshot_content_type: str
) -> str | None:
    """Upload screenshot to GCS and return the gcs_path, or None if GCS not configured."""
    if not settings.use_gcs or not settings.gcs_bucket_name:
        return None

    try:
        from app.services.gcs_service import get_bucket

        ext_map = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp"}
        ext = ext_map.get(screenshot_content_type, "png")

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        gcs_path = f"bug-reports/{timestamp}-{unique_id}.{ext}"

        bucket = get_bucket()
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(screenshot_bytes, content_type=screenshot_content_type)

        return gcs_path
    except Exception as e:
        logger.error(f"Failed to upload screenshot to GCS: {e}")
        return None


def _generate_thumbnail(screenshot_bytes: bytes, max_size: int = 400, max_bytes: int = 50000) -> str | None:
    """Generate a low-res JPEG thumbnail as a base64 string for embedding in GitHub issues."""
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(screenshot_bytes))
        img.thumbnail((max_size, max_size))

        # Convert to RGB if necessary (PNG with alpha)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Try quality levels until under max_bytes
        for quality in (60, 40, 25, 15):
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=quality)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            if len(b64) <= max_bytes:
                return b64

        # Still too large — resize smaller
        img.thumbnail((200, 200))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=30)
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        logger.warning(f"Failed to generate thumbnail: {e}")
        return None


def _create_github_issue(
    description: Optional[str],
    page_url: Optional[str],
    user_agent: Optional[str],
    user_role: str,
    user_name: str,
    screenshot_link: str | None = None,
    screenshot_bytes: bytes | None = None,
) -> tuple[Optional[int], Optional[str]]:
    """Create a GitHub issue and return (issue_number, issue_url) or (None, None) on failure."""
    if not settings.github_token:
        logger.info("GITHUB_TOKEN not configured, skipping GitHub issue creation")
        return None, None

    title_desc = (description or "No description")[:60]
    title = f"User Bug Report: {title_desc}"

    body_parts = []
    body_parts.append(f"**Reported by:** {user_name} ({user_role})")
    if description:
        body_parts.append(f"\n**Description:**\n{description}")
    if page_url:
        body_parts.append(f"\n**Page URL:** {page_url}")
    if user_agent:
        body_parts.append(f"\n**Browser:** {user_agent}")

    if screenshot_link:
        body_parts.append(f"\n**Screenshot:** [View Full Screenshot]({screenshot_link})")
        # Embed thumbnail if available
        if screenshot_bytes:
            thumbnail_b64 = _generate_thumbnail(screenshot_bytes)
            if thumbnail_b64:
                body_parts.append(f"\n![screenshot preview](data:image/jpeg;base64,{thumbnail_b64})")

    body = "\n".join(body_parts)

    try:
        resp = httpx.post(
            "https://api.github.com/repos/theepangnani/emai-dev-03/issues",
            headers={
                "Authorization": f"token {settings.github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "title": title,
                "body": body,
                "labels": ["bug", "user-reported"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("number"), data.get("html_url")
    except Exception as e:
        logger.error(f"Failed to create GitHub issue: {e}")
        return None, None


def _process_bug_report_background(
    report_id: int,
    user_id: int,
    user_role: str,
    user_name: str,
    user_email: str,
    description: str | None,
    screenshot_bytes: bytes | None,
    screenshot_content_type: str | None,
    page_url: str | None,
    user_agent: str | None,
    admin_emails: list[str],
) -> None:
    """Background task: upload to GCS, create GitHub issue, send admin emails."""
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        report = db.query(BugReport).filter(BugReport.id == report_id).first()
        if not report:
            logger.error(f"Bug report {report_id} not found for background processing")
            return

        # 1. Upload screenshot to GCS
        screenshot_link = None
        if screenshot_bytes and screenshot_content_type:
            gcs_path = _upload_screenshot_to_gcs(screenshot_bytes, screenshot_content_type)
            if gcs_path:
                report.screenshot_url = gcs_path
                screenshot_link = f"{settings.frontend_url}/api/bug-reports/{report_id}/screenshot"

        # 2. Create GitHub issue with thumbnail
        issue_number, issue_url = _create_github_issue(
            description=description,
            page_url=page_url,
            user_agent=user_agent,
            user_role=user_role,
            user_name=user_name,
            screenshot_link=screenshot_link,
            screenshot_bytes=screenshot_bytes if screenshot_link else None,
        )

        # 3. Update report with GitHub issue info
        if issue_number:
            report.github_issue_number = issue_number
            report.github_issue_url = issue_url

        db.commit()

        # 4. Send admin emails (best-effort)
        subject = f"[ClassBridge] Bug Report from {user_name}"
        body_html = f"""
        <h2>New Bug Report</h2>
        <p><strong>From:</strong> {user_name} ({user_role})</p>
        <p><strong>Description:</strong> {description or 'No description'}</p>
        {f'<p><strong>Page:</strong> {page_url}</p>' if page_url else ''}
        {f'<p><strong>GitHub Issue:</strong> <a href="{issue_url}">#{issue_number}</a></p>' if issue_url else ''}
        """
        for email in admin_emails:
            try:
                send_email_sync(email, subject, wrap_branded_email(body_html))
            except Exception as e:
                logger.warning(f"Failed to email admin {email} about bug report: {e}")

    except Exception as e:
        logger.error(f"Background bug report processing failed for report {report_id}: {e}")
        db.rollback()
    finally:
        db.close()


def create_bug_report(
    db: Session,
    user: User,
    description: Optional[str],
    screenshot_bytes: Optional[bytes] = None,
    screenshot_content_type: Optional[str] = None,
    page_url: Optional[str] = None,
    user_agent: Optional[str] = None,
    background_tasks=None,
) -> BugReport:
    """Create a bug report (fast) and schedule heavy processing in background."""

    # 1. Build fallback screenshot URL (base64 for immediate DB storage)
    screenshot_url = None
    if screenshot_bytes and screenshot_content_type:
        b64 = base64.b64encode(screenshot_bytes).decode("ascii")
        screenshot_url = f"data:{screenshot_content_type};base64,{b64}"

    # 2. Save report to DB immediately
    report = BugReport(
        user_id=user.id,
        description=description,
        screenshot_url=screenshot_url,
        page_url=page_url,
        user_agent=user_agent,
    )
    db.add(report)
    db.flush()

    # 3. Create in-app notifications for admins (fast DB inserts)
    admins = db.query(User).filter(
        or_(User.role == UserRole.ADMIN, User.roles.contains("admin"))
    ).all()

    short_desc = (description or "No description")[:80]
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            type=NotificationType.SYSTEM,
            title="New Bug Report",
            content=f"{user.full_name or user.email} reported a bug: {short_desc}",
        ))

    db.commit()
    db.refresh(report)

    # 4. Schedule heavy work in background
    admin_emails = [a.email for a in admins if a.email]
    if background_tasks:
        background_tasks.add_task(
            _process_bug_report_background,
            report_id=report.id,
            user_id=user.id,
            user_role=user.role,
            user_name=user.full_name or user.email,
            user_email=user.email,
            description=description,
            screenshot_bytes=screenshot_bytes,
            screenshot_content_type=screenshot_content_type,
            page_url=page_url,
            user_agent=user_agent,
            admin_emails=admin_emails,
        )
    else:
        # Fallback: run synchronously (e.g., in tests)
        _process_bug_report_background(
            report_id=report.id,
            user_id=user.id,
            user_role=user.role,
            user_name=user.full_name or user.email,
            user_email=user.email,
            description=description,
            screenshot_bytes=screenshot_bytes,
            screenshot_content_type=screenshot_content_type,
            page_url=page_url,
            user_agent=user_agent,
            admin_emails=admin_emails,
        )

    return report
