"""Centralized multi-channel notification service.

Sends notifications via up to 3 channels:
1. In-app notification bell (Notification table)
2. Email (SendGrid/SMTP)
3. ClassBridge message (Conversation + Message)

Respects user preferences and suppression rules.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.models.notification import Notification, NotificationType
from app.models.notification_suppression import NotificationSuppression
from app.models.message import Conversation, Message
from app.services.email_service import send_email_sync

logger = logging.getLogger(__name__)


# #3884: Detect whether notification email content already starts with a
# block-level HTML tag. If so, the caller has supplied pre-formatted HTML and
# wrapping it in <p>...</p> would produce invalid nested-block markup (e.g.
# <p><h3>...</h3></p>). We instead wrap in a <div> with matching styles.
_BLOCK_TAG_RE = re.compile(r"^\s*<(h[1-6]|p|ul|ol|div|section|article|hr)\b", re.IGNORECASE)


# Role-based deep link mappings: generic link → role-specific link
_ROLE_LINK_OVERRIDES: dict[str, dict[str, str]] = {
    "/messages": {
        UserRole.PARENT: "/messages",
        UserRole.STUDENT: "/messages",
        UserRole.TEACHER: "/messages",
        UserRole.ADMIN: "/messages",
    },
    "/dashboard": {
        UserRole.PARENT: "/dashboard",
        UserRole.STUDENT: "/dashboard",
        UserRole.TEACHER: "/teacher-communications",
        UserRole.ADMIN: "/admin/waitlist",
    },
    "/link-requests": {
        UserRole.PARENT: "/link-requests",
        UserRole.STUDENT: "/dashboard",
        UserRole.TEACHER: "/dashboard",
        UserRole.ADMIN: "/dashboard",
    },
}


def get_role_aware_link(link: str | None, role: str | None) -> str | None:
    """Return a role-appropriate deep link for email notifications.

    Falls back to the original link if no role-specific override exists.
    """
    if not link or not role:
        return link

    overrides = _ROLE_LINK_OVERRIDES.get(link)
    if overrides:
        return overrides.get(role, link)
    return link


def send_multi_channel_notification(
    db: Session,
    recipient: User,
    sender: User | None,
    title: str,
    content: str,
    notification_type: NotificationType,
    link: str | None = None,
    channels: list[str] | None = None,
    requires_ack: bool = False,
    source_type: str | None = None,
    source_id: int | None = None,
    student_id: int | None = None,
) -> dict | None:
    """Send notification via multiple channels.

    Args:
        db: Database session
        recipient: User who receives the notification
        sender: User who triggered the notification (None for system notifications)
        title: Notification title
        content: Notification body text
        notification_type: Type from NotificationType enum
        link: Frontend URL to navigate to on click
        channels: List of channels — "app_notification", "email", "classbridge_message"
        requires_ack: Whether recipient must acknowledge this notification
        source_type: Entity type for suppression/ACK tracking (e.g. "assignment")
        source_id: Entity ID for suppression/ACK tracking
        student_id: Student context for ClassBridge messages

    Returns:
        None if suppressed. Otherwise a dict with per-channel outcomes using a
        three-valued convention (#3887):
          - ``True``  — channel was requested and delivery succeeded
          - ``False`` — channel was requested and delivery actually failed
                        (exception raised, or underlying send helper returned
                        False)
          - ``None``  — not applicable: channel was not requested, or was
                        requested but intentionally skipped (recipient
                        preference off, no email on file, no valid sender for
                        the classbridge_message channel, etc.). Callers MUST
                        NOT treat ``None`` as a failure — it is a skip.

        Keys:
          - "notification": Notification | None — the in-app row, if any
          - "in_app": bool | None
          - "email": bool | None
          - "classbridge_message": bool | None

        Truthiness of the dict remains stable because a non-empty dict is always
        truthy, but legacy callers that check ``if notif:`` should migrate to
        ``if notif and notif.get("notification"):`` — see #3880.
    """
    if channels is None:
        channels = ["app_notification", "email", "classbridge_message"]

    # Check suppression
    if source_type and source_id:
        suppressed = db.query(NotificationSuppression).filter(
            NotificationSuppression.user_id == recipient.id,
            NotificationSuppression.source_type == source_type,
            NotificationSuppression.source_id == source_id,
        ).first()
        if suppressed:
            logger.debug(
                f"Notification suppressed for user {recipient.id}: "
                f"{source_type}:{source_id}"
            )
            return None

    notification: Notification | None = None
    in_app_status: bool | None = None
    email_status: bool | None = None
    cb_message_status: bool | None = None

    # Resolve notification type value for preference checks
    notif_type_value = notification_type.value if hasattr(notification_type, 'value') else str(notification_type)

    # Channel 1: In-app notification bell
    if "app_notification" in channels:
        if recipient.should_notify(notif_type_value, "in_app"):
            notification = Notification(
                user_id=recipient.id,
                type=notification_type,
                title=title,
                content=content[:500] if content else None,
                link=link,
                requires_ack=requires_ack,
                source_type=source_type,
                source_id=source_id,
                reminder_count=0,
            )
            if requires_ack:
                notification.next_reminder_at = datetime.now(timezone.utc) + timedelta(hours=24)
            db.add(notification)
            in_app_status = True
        else:
            # Preference-suppressed → not applicable, not a failure (#3887).
            in_app_status = None

    # Channel 2: Email
    if "email" in channels:
        if recipient.email and recipient.email_notifications and recipient.should_notify(notif_type_value, "email"):
            try:
                email_html = _build_notification_email(title, content, link, recipient.role)
                sent = send_email_sync(recipient.email, title, email_html)
                if sent:
                    email_status = True
                else:
                    logger.warning(
                        f"send_email_sync returned False for notification email to {recipient.email} (#3880)"
                    )
                    email_status = False
            except Exception as e:
                logger.warning(f"Failed to send notification email to {recipient.email}: {e}")
                email_status = False
        else:
            # No email on file / email_notifications=False / preference off → not
            # applicable, not a failure (#3887). The user never asked for this
            # channel to fire.
            email_status = None

    # Channel 3: ClassBridge message
    if "classbridge_message" in channels:
        if sender and sender.id != recipient.id:
            try:
                _send_as_classbridge_message(db, sender, recipient, content, student_id)
                cb_message_status = True
            except Exception as e:
                logger.warning(f"Failed to send ClassBridge message notification: {e}")
                cb_message_status = False
        else:
            # No valid sender (system notification or self-send) → not
            # applicable, not a failure (#3887).
            cb_message_status = None

    return {
        "notification": notification,
        "in_app": in_app_status,
        "email": email_status,
        "classbridge_message": cb_message_status,
    }


def notify_parents_of_student(
    db: Session,
    student_user: User,
    title: str,
    content: str,
    notification_type: NotificationType,
    link: str | None = None,
    requires_ack: bool = False,
    source_type: str | None = None,
    source_id: int | None = None,
) -> list[Notification]:
    """Find all parents linked to a student and send multi-channel notifications.

    Args:
        db: Database session
        student_user: The student User who triggered the action
        title: Notification title
        content: Notification body
        notification_type: Type from NotificationType enum
        link: Frontend URL
        requires_ack: Whether parents must acknowledge
        source_type: Entity type for tracking
        source_id: Entity ID for tracking

    Returns:
        List of created Notification records.
    """
    student = db.query(Student).filter(Student.user_id == student_user.id).first()
    if not student:
        logger.debug(f"No Student profile for user {student_user.id}, skipping parent notification")
        return []

    # Find all linked parents
    parent_rows = (
        db.query(User)
        .join(parent_students, parent_students.c.parent_id == User.id)
        .filter(parent_students.c.student_id == student.id)
        .all()
    )

    notifications = []
    for parent in parent_rows:
        result = send_multi_channel_notification(
            db=db,
            recipient=parent,
            sender=student_user,
            title=title,
            content=content,
            notification_type=notification_type,
            link=link,
            requires_ack=requires_ack,
            source_type=source_type,
            source_id=source_id,
            student_id=student.id,
        )
        # #3880: return is now dict | None. Only append if an in-app Notification row was created.
        notif = result.get("notification") if result else None
        if notif:
            notifications.append(notif)

    if notifications:
        logger.info(
            f"Sent {len(notifications)} parent notifications for student "
            f"{student_user.id}: {notification_type.value}"
        )

    return notifications


# #3956 — Sectioned 3x3 email renderer for parent digest. Kept as a separate
# helper (not wired into _build_notification_email) because the section
# headings / coloured accents / overflow CTA are specific to the digest and
# don't generalise to other notification types. The digest job computes the
# HTML up-front and passes it into the existing _build_notification_email
# path which already handles block-tag-starting content correctly (#3884).

_SECTIONED_SECTION_STYLES = {
    "urgent": {
        "heading": "Urgent",
        "emoji": "🔴",
        "color": "#dc2626",  # red-600
    },
    "announcements": {
        "heading": "Announcements",
        "emoji": "📢",
        "color": "#6b7280",  # grey-500
    },
    "action_items": {
        "heading": "Action Items",
        "emoji": "✅",
        "color": "#2563eb",  # blue-600
    },
}

def _html_escape(text: str) -> str:
    """Minimal HTML-escape for user-facing strings rendered into the digest."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_sectioned_digest_email_body(sectioned: dict) -> str:
    """Render the 3x3 sectioned digest as inline-styled email HTML (#3956).

    Takes a dict matching the ``SectionedDigest`` schema and produces HTML
    with:
      - Up to 3 sections (Urgent, Announcements, Action Items)
      - Coloured section headings (inline-styled for email-client compat)
      - Bullet list with up to 3 items per section
      - "And N more -> View full digest" CTA when overflow > 0
      - Empty sections are skipped entirely (no empty card)

    If ``sectioned["legacy_blob"]`` is set, returns the legacy HTML unchanged
    so the old full-format render path still works (back-compat for AI JSON
    parse failures).
    """
    legacy = sectioned.get("legacy_blob")
    if legacy:
        return legacy

    # #3965 — resolve digest URL from settings so dev/staging don't link to prod.
    from app.core.config import settings as app_settings
    full_digest_url = f"{app_settings.frontend_url.rstrip('/')}/email-digest"

    overflow = sectioned.get("overflow") or {}
    sections_html: list[str] = []

    for key in ("urgent", "announcements", "action_items"):
        items_raw = sectioned.get(key) or []
        items = items_raw[:3]
        if not items:
            # Empty section -> skip heading entirely (#3956).
            continue

        meta = _SECTIONED_SECTION_STYLES[key]
        heading = (
            f'<h3 style="color:{meta["color"]};margin:24px 0 8px 0;'
            f'font-size:16px;font-weight:700;">'
            f'{meta["emoji"]} {meta["heading"]}</h3>'
        )

        li_items = "".join(
            f'<li style="margin:4px 0;">{_html_escape(str(it))}</li>'
            for it in items
        )
        ul_html = (
            f'<ul style="margin:0 0 8px 20px;padding:0;color:#333;'
            f'line-height:1.5;">{li_items}</ul>'
        )

        try:
            more = int(overflow.get(key, 0) or 0)
        except (TypeError, ValueError):
            more = 0

        more_html = ""
        if more > 0:
            more_html = (
                f'<p style="margin:4px 0 0 0;font-size:14px;">'
                f'<a href="{full_digest_url}" '
                f'style="color:#4f46e5;text-decoration:none;">'
                f'And {more} more &rarr; View full digest</a></p>'
            )

        sections_html.append(heading + ul_html + more_html)

    if not sections_html:
        # Nothing at all — defensive fallback so the email still renders.
        return (
            '<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">'
            'No new school emails today.</p>'
        )

    return (
        '<div style="color:#333;line-height:1.6;margin:0 0 16px 0;">'
        + "".join(sections_html)
        + "</div>"
    )


def _build_notification_email(title: str, content: str, link: str | None, recipient_role: str | None = None) -> str:
    """Build a branded HTML email for notifications."""
    from app.core.config import settings
    from app.services.email_service import wrap_branded_email

    link_html = ""
    if link:
        role_link = get_role_aware_link(link, recipient_role)
        full_url = f"{settings.frontend_url}{role_link}"
        link_html = (
            f'<p style="margin:24px 0 0 0;"><a href="{full_url}" '
            f'style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;'
            f'padding:12px 24px;border-radius:8px;font-weight:600;">View in ClassBridge</a></p>'
        )

    # #3884: If content is already HTML (starts with a block-level tag), wrap in
    # <div> to avoid invalid nested-block markup like <p><h3>...</h3></p>.
    # Otherwise keep the <p> wrap so plain-text content renders identically.
    if _BLOCK_TAG_RE.match(content or ""):
        content_html = f'<div style="color:#333;line-height:1.6;margin:0 0 16px 0;">{content}</div>'
    else:
        content_html = f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">{content}</p>'

    body = (
        f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">{title}</h2>'
        f'{content_html}'
        f'{link_html}'
    )
    return wrap_branded_email(body)


def _send_as_classbridge_message(
    db: Session,
    sender: User,
    recipient: User,
    content: str,
    student_id: int | None = None,
) -> None:
    """Create or reuse a Conversation and send a system message."""
    # Find existing conversation between these users
    conversation = (
        db.query(Conversation)
        .filter(
            or_(
                and_(
                    Conversation.participant_1_id == sender.id,
                    Conversation.participant_2_id == recipient.id,
                ),
                and_(
                    Conversation.participant_1_id == recipient.id,
                    Conversation.participant_2_id == sender.id,
                ),
            )
        )
        .first()
    )

    if not conversation:
        conversation = Conversation(
            participant_1_id=sender.id,
            participant_2_id=recipient.id,
            student_id=student_id,
            subject="ClassBridge Notification",
        )
        db.add(conversation)
        db.flush()

    message = Message(
        conversation_id=conversation.id,
        sender_id=sender.id,
        content=content[:2000] if content else "",
    )
    db.add(message)
