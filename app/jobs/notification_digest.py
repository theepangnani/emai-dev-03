"""Daily notification digest job (#966).

Sends a batched HTML email digest to users who have opted into digest mode.
Runs every hour via APScheduler; only sends digests at the user's configured hour.
"""
import logging
from datetime import datetime, timezone, date, timedelta

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.notification import Notification, NotificationType
from app.models.notification_preference import NotificationPreference
from app.models.user import User
from app.services.email_service import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)

# Human-readable labels for each notification type
_TYPE_LABELS = {
    NotificationType.ASSIGNMENT_DUE: "Assignments",
    NotificationType.GRADE_POSTED: "Grades",
    NotificationType.PROJECT_DUE: "Projects",
    NotificationType.ASSESSMENT_UPCOMING: "Assessments",
    NotificationType.MATERIAL_UPLOADED: "New Materials",
    NotificationType.STUDY_GUIDE_CREATED: "Study Guides",
    NotificationType.MESSAGE: "Messages",
    NotificationType.TASK_DUE: "Tasks",
    NotificationType.SYSTEM: "System",
    NotificationType.LINK_REQUEST: "Link Requests",
    NotificationType.PARENT_REQUEST: "Requests",
}


def _build_digest_html(user: User, notifications: list[Notification]) -> str:
    """Build a plain but clearly structured HTML digest email."""
    today_str = date.today().strftime("%B %-d, %Y") if hasattr(date, "strftime") else str(date.today())
    # Fallback for Windows where %-d is not supported
    try:
        today_str = date.today().strftime("%B %-d, %Y")
    except ValueError:
        today_str = date.today().strftime("%B %d, %Y")

    # Group notifications by type label
    grouped: dict[str, list[Notification]] = {}
    for n in notifications:
        label = _TYPE_LABELS.get(n.type, "Other")
        grouped.setdefault(label, []).append(n)

    sections_html = ""
    for label, items in grouped.items():
        items_html = "".join(
            f"<li style='margin:4px 0;color:#333;'>"
            f"<strong>{n.title}</strong>"
            f"{': ' + n.content if n.content else ''}"
            f"</li>"
            for n in items
        )
        sections_html += (
            f"<div style='margin:20px 0;'>"
            f"<h3 style='color:#4f46e5;margin:0 0 8px 0;font-size:16px;border-bottom:1px solid #e5e7eb;padding-bottom:4px;'>{label}</h3>"
            f"<ul style='margin:0;padding-left:20px;'>{items_html}</ul>"
            f"</div>"
        )

    dashboard_url = f"{settings.frontend_url}/dashboard"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8" /></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f9fafb;margin:0;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
    <!-- Header -->
    <div style="background:#4f46e5;padding:24px 32px;">
      <h1 style="color:white;margin:0;font-size:20px;font-weight:700;">ClassBridge</h1>
      <p style="color:#c7d2fe;margin:4px 0 0 0;font-size:14px;">Your Daily Digest &mdash; {today_str}</p>
    </div>
    <!-- Body -->
    <div style="padding:24px 32px;">
      <p style="color:#374151;margin:0 0 16px 0;">Hi {user.full_name},</p>
      <p style="color:#6b7280;margin:0 0 24px 0;font-size:14px;">
        Here is a summary of your unread notifications since your last digest.
        You have <strong>{len(notifications)}</strong> unread notification{'s' if len(notifications) != 1 else ''}.
      </p>
      {sections_html}
      <div style="margin-top:28px;text-align:center;">
        <a href="{dashboard_url}"
           style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;
                  padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px;">
          Go to Dashboard
        </a>
      </div>
    </div>
    <!-- Footer -->
    <div style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;">
      <p style="color:#9ca3af;font-size:12px;margin:0;text-align:center;">
        You're receiving this because you enabled daily digest in your
        <a href="{settings.frontend_url}/notifications/preferences" style="color:#6b7280;">notification settings</a>.
      </p>
    </div>
  </div>
</body>
</html>"""
    return html


async def send_daily_digests():
    """Send digest emails to all users with digest_mode=True whose digest hour has arrived.

    Called by APScheduler every hour at :00 minutes.
    Each user has a configurable digest_hour (0-23); we send when current UTC hour matches.
    We skip users who already received a digest today.
    """
    logger.info("Running daily notification digest job...")

    db: Session = SessionLocal()
    try:
        current_hour_utc = datetime.now(timezone.utc).hour
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

        # Find all preferences with digest enabled at the current hour that haven't been sent today
        candidates = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.digest_mode == True,  # noqa: E712
                NotificationPreference.digest_hour == current_hour_utc,
            )
            .all()
        )

        sent_count = 0
        skipped_count = 0

        for prefs in candidates:
            try:
                # Skip if already sent today
                if prefs.last_digest_sent_at is not None:
                    last_sent = prefs.last_digest_sent_at
                    if last_sent.tzinfo is None:
                        last_sent = last_sent.replace(tzinfo=timezone.utc)
                    if last_sent >= today_start:
                        skipped_count += 1
                        continue

                user = db.query(User).filter(
                    User.id == prefs.user_id,
                    User.is_active == True,  # noqa: E712
                ).first()
                if not user or not user.email or not user.email_notifications:
                    skipped_count += 1
                    continue

                # Collect unread notifications since last digest (or start of today)
                cutoff = prefs.last_digest_sent_at or today_start
                if hasattr(cutoff, 'tzinfo') and cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=timezone.utc)

                unread = (
                    db.query(Notification)
                    .filter(
                        Notification.user_id == user.id,
                        Notification.read == False,  # noqa: E712
                        Notification.created_at >= cutoff,
                    )
                    .order_by(Notification.type, Notification.created_at)
                    .all()
                )

                if not unread:
                    # No notifications to digest — still update timestamp to avoid re-check
                    prefs.last_digest_sent_at = datetime.now(timezone.utc)
                    db.commit()
                    skipped_count += 1
                    continue

                html = _build_digest_html(user, unread)
                today_label = date.today().strftime("%B %d, %Y")
                subject = f"Your ClassBridge Digest for {today_label}"

                sent = await send_email(
                    to_email=user.email,
                    subject=subject,
                    html_content=html,
                )
                if sent:
                    prefs.last_digest_sent_at = datetime.now(timezone.utc)
                    db.commit()
                    sent_count += 1
                    logger.info(
                        f"Digest sent to user {user.id} ({user.email}) | "
                        f"notifications={len(unread)}"
                    )
                else:
                    logger.warning(f"Digest email failed for user {user.id} ({user.email})")

            except Exception as e:
                logger.error(f"Digest job failed for prefs.user_id={prefs.user_id}: {e}", exc_info=True)
                db.rollback()

        logger.info(
            f"Daily digest job complete | sent={sent_count} | skipped/empty={skipped_count}"
        )

    except Exception as e:
        logger.error(f"Daily digest job failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
