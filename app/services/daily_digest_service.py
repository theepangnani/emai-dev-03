"""Service that builds and sends the Daily Morning Email Digest for parents."""

import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.briefing import DailyBriefingResponse
from app.services.briefing_service import get_daily_briefing
from app.services.email_service import send_email, wrap_branded_email
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


def _render_digest_email_html(
    briefing: DailyBriefingResponse, unsubscribe_url: str | None = None
) -> str:
    """Render the daily briefing data as branded HTML email."""

    children_html = ""
    for child in briefing.children:
        # Overdue tasks
        overdue_html = ""
        if child.overdue_tasks:
            items = "".join(
                f'<li style="color:#dc2626;margin:4px 0;">'
                f'{t.title}'
                f'{" (" + t.course_name + ")" if t.course_name else ""}'
                f' &mdash; due {t.due_date.strftime("%b %d") if t.due_date else "N/A"}'
                f'</li>'
                for t in child.overdue_tasks
            )
            overdue_html = (
                f'<div style="margin-top:12px;">'
                f'<strong style="color:#dc2626;">Overdue ({len(child.overdue_tasks)}):</strong>'
                f'<ul style="margin:4px 0 0 16px;padding:0;">{items}</ul>'
                f'</div>'
            )

        # Due today
        due_today_html = ""
        if child.due_today_tasks:
            items = "".join(
                f'<li style="color:#d97706;margin:4px 0;">'
                f'{t.title}'
                f'{" (" + t.course_name + ")" if t.course_name else ""}'
                f'</li>'
                for t in child.due_today_tasks
            )
            due_today_html = (
                f'<div style="margin-top:12px;">'
                f'<strong style="color:#d97706;">Due Today ({len(child.due_today_tasks)}):</strong>'
                f'<ul style="margin:4px 0 0 16px;padding:0;">{items}</ul>'
                f'</div>'
            )

        # Upcoming assignments
        upcoming_html = ""
        if child.upcoming_assignments:
            items = "".join(
                f'<li style="color:#4b5563;margin:4px 0;">'
                f'{a.title} ({a.course_name})'
                f' &mdash; due {a.due_date.strftime("%b %d") if a.due_date else "N/A"}'
                f'</li>'
                for a in child.upcoming_assignments
            )
            upcoming_html = (
                f'<div style="margin-top:12px;">'
                f'<strong style="color:#4338ca;">Upcoming This Week ({len(child.upcoming_assignments)}):</strong>'
                f'<ul style="margin:4px 0 0 16px;padding:0;">{items}</ul>'
                f'</div>'
            )

        # Attention badge
        attention_badge = ""
        if child.needs_attention:
            attention_badge = (
                '<span style="display:inline-block;background:#fef2f2;color:#dc2626;'
                'font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">'
                'Needs attention</span>'
            )

        grade_label = f" (Grade {child.grade_level})" if child.grade_level else ""

        children_html += f"""
        <div style="margin-bottom:24px;padding:16px;background:#f9fafb;border-radius:12px;border-left:4px solid #4f46e5;">
          <h3 style="margin:0 0 8px 0;color:#1f2937;">{child.full_name}{grade_label}{attention_badge}</h3>
          {overdue_html}
          {due_today_html}
          {upcoming_html}
          {f'<div style="margin-top:8px;color:#6b7280;font-size:13px;">{child.recent_study_count} study guide{"s" if child.recent_study_count != 1 else ""} created this week</div>' if child.recent_study_count > 0 else ""}
        </div>
        """

    # Summary banner
    summary_parts = []
    if briefing.total_overdue > 0:
        summary_parts.append(f"{briefing.total_overdue} overdue")
    if briefing.total_due_today > 0:
        summary_parts.append(f"{briefing.total_due_today} due today")
    if briefing.total_upcoming > 0:
        summary_parts.append(f"{briefing.total_upcoming} upcoming this week")
    summary_text = " &bull; ".join(summary_parts) if summary_parts else "All clear for today!"

    body_html = f"""
    <h2 style="color:#1f2937;margin:0 0 4px 0;">Daily Morning Digest</h2>
    <p style="color:#6b7280;margin:0 0 24px 0;font-size:14px;">{briefing.date}</p>
    <p style="color:#4b5563;margin:0 0 24px 0;">{briefing.greeting} &mdash; here's what's happening today.</p>
    <div style="margin-bottom:24px;padding:12px 16px;background:#eef2ff;border-radius:8px;color:#4338ca;font-size:14px;">
      {summary_text}
    </div>
    {children_html}
    <p style="margin-top:24px;text-align:center;">
      <a href="https://www.classbridge.ca/dashboard" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">View Dashboard</a>
    </p>
    """

    if unsubscribe_url:
        body_html += f"""
    <p style="text-align:center;font-size:12px;color:#999;margin-top:24px;">
      <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe from these emails</a>
    </p>
    """

    return wrap_branded_email(body_html)


def generate_daily_digest(db: Session, parent_user_id: int) -> DailyBriefingResponse:
    """Generate daily digest data (reuses the briefing service)."""
    return get_daily_briefing(db, parent_user_id)


def has_content(briefing: DailyBriefingResponse) -> bool:
    """Check if the briefing has anything worth reporting."""
    return (
        briefing.total_overdue > 0
        or briefing.total_due_today > 0
        or briefing.total_upcoming > 0
    )


def _translate_safe(text: str, target_language: str) -> str:
    """Translate text, falling back to original on any error."""
    try:
        return TranslationService.translate(text, target_language)
    except Exception:
        logger.warning("Translation failed, using English fallback")
        return text


def _translate_briefing(briefing: DailyBriefingResponse, target_language: str) -> DailyBriefingResponse:
    """Translate key briefing text fields in-place and return the briefing."""
    if not target_language or target_language == "en":
        return briefing

    briefing.greeting = _translate_safe(briefing.greeting, target_language)

    return briefing


async def send_daily_digest_email(db: Session, parent_user_id: int, force: bool = False) -> bool:
    """Generate and send the daily digest email to a parent.

    Args:
        db: Database session.
        parent_user_id: The parent user's ID.
        force: If True, send even if there's nothing to report.

    Returns:
        True if email was sent successfully.
    """
    parent = db.query(User).filter(User.id == parent_user_id).first()
    if not parent or not parent.email:
        return False

    from app.core.security import get_unsubscribe_url

    briefing = generate_daily_digest(db, parent_user_id)

    # Skip if nothing to report (unless forced, e.g. test send)
    if not force and not has_content(briefing):
        return False

    lang = getattr(parent, "preferred_language", "en") or "en"
    if lang != "en":
        briefing = _translate_briefing(briefing, lang)

    unsub_url = get_unsubscribe_url(parent_user_id)
    html = _render_digest_email_html(briefing, unsubscribe_url=unsub_url)
    subject = f"Daily Digest - {briefing.date}"

    if lang != "en":
        subject = _translate_safe(subject, lang)

    return await send_email(parent.email, subject, html)
