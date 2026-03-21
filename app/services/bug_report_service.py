import base64
import logging
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


def _create_github_issue(
    description: Optional[str],
    screenshot_bytes: Optional[bytes],
    screenshot_content_type: Optional[str],
    page_url: Optional[str],
    user_agent: Optional[str],
    user_role: str,
    user_name: str,
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

    if screenshot_bytes and screenshot_content_type:
        b64 = base64.b64encode(screenshot_bytes).decode("ascii")
        body_parts.append(
            f"\n**Screenshot:**\n\n![screenshot](data:{screenshot_content_type};base64,{b64})"
        )

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


def create_bug_report(
    db: Session,
    user: User,
    description: Optional[str],
    screenshot_bytes: Optional[bytes] = None,
    screenshot_content_type: Optional[str] = None,
    page_url: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BugReport:
    """Create a bug report, optionally create a GitHub issue, and notify admins."""

    # Create GitHub issue
    issue_number, issue_url = _create_github_issue(
        description=description,
        screenshot_bytes=screenshot_bytes,
        screenshot_content_type=screenshot_content_type,
        page_url=page_url,
        user_agent=user_agent,
        user_role=user.role,
        user_name=user.full_name or user.email,
    )

    # Build screenshot data URL for DB storage (if screenshot provided)
    screenshot_url = None
    if screenshot_bytes and screenshot_content_type:
        b64 = base64.b64encode(screenshot_bytes).decode("ascii")
        screenshot_url = f"data:{screenshot_content_type};base64,{b64}"

    # Save bug report
    report = BugReport(
        user_id=user.id,
        description=description,
        screenshot_url=screenshot_url,
        page_url=page_url,
        user_agent=user_agent,
        github_issue_number=issue_number,
        github_issue_url=issue_url,
    )
    db.add(report)
    db.flush()

    # Notify all admins
    admins = db.query(User).filter(
        or_(User.role == UserRole.ADMIN, User.roles.contains("admin"))
    ).all()

    short_desc = (description or "No description")[:80]
    notif_title = "New Bug Report"
    notif_content = f"{user.full_name or user.email} reported a bug: {short_desc}"
    notif_link = issue_url

    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            type=NotificationType.SYSTEM,
            title=notif_title,
            content=notif_content,
            link=notif_link,
        ))

    db.commit()
    db.refresh(report)

    # Send email to admins (best-effort, don't fail the request)
    subject = f"[ClassBridge] Bug Report from {user.full_name or user.email}"
    body_html = f"""
    <h2>New Bug Report</h2>
    <p><strong>From:</strong> {user.full_name or user.email} ({user.role})</p>
    <p><strong>Description:</strong> {description or 'No description'}</p>
    {f'<p><strong>Page:</strong> {page_url}</p>' if page_url else ''}
    {f'<p><strong>GitHub Issue:</strong> <a href="{issue_url}">#{issue_number}</a></p>' if issue_url else ''}
    """
    for admin in admins:
        try:
            send_email_sync(admin.email, subject, wrap_branded_email(body_html))
        except Exception as e:
            logger.warning(f"Failed to email admin {admin.email} about bug report: {e}")

    return report
