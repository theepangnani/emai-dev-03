"""Centralized multi-channel notification service.

Sends notifications via up to 3 channels:
1. In-app notification bell (Notification table)
2. Email (SendGrid/SMTP)
3. ClassBridge message (Conversation + Message)

Respects user preferences and suppression rules.
"""
import logging
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


# Lazy import to avoid circular imports
def _get_or_create_notif_prefs(db: Session, user_id: int):
    """Load (or create) NotificationPreference for a user. Returns None on error."""
    try:
        from app.models.notification_preference import NotificationPreference
        prefs = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        if prefs is None:
            prefs = NotificationPreference(user_id=user_id)
            db.add(prefs)
            db.flush()  # get ID without full commit — caller owns the transaction
        return prefs
    except Exception as e:
        logger.warning(f"Could not load/create notification preferences for user {user_id}: {e}")
        return None


def _type_to_pref_key(notification_type: NotificationType) -> str:
    """Map a NotificationType to the preference key prefix (assignments/messages/tasks/system/reminders)."""
    _map = {
        NotificationType.ASSIGNMENT_DUE: "assignments",
        NotificationType.GRADE_POSTED: "assignments",
        NotificationType.PROJECT_DUE: "assignments",
        NotificationType.ASSESSMENT_UPCOMING: "assignments",
        NotificationType.MATERIAL_UPLOADED: "assignments",
        NotificationType.STUDY_GUIDE_CREATED: "assignments",
        NotificationType.MESSAGE: "messages",
        NotificationType.TASK_DUE: "tasks",
        NotificationType.SYSTEM: "system",
        NotificationType.LINK_REQUEST: "system",
        NotificationType.PARENT_REQUEST: "system",
    }
    return _map.get(notification_type, "system")


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
) -> Notification | None:
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
        The created Notification record, or None if suppressed.
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

    # Load advanced notification preferences — fall back gracefully on any error
    try:
        adv_prefs = _get_or_create_notif_prefs(db, recipient.id)
        pref_key = _type_to_pref_key(notification_type)
        in_app_enabled = getattr(adv_prefs, f"in_app_{pref_key}", True) if adv_prefs else True
        email_enabled = getattr(adv_prefs, f"email_{pref_key}", True) if adv_prefs else True
        digest_mode = adv_prefs.digest_mode if adv_prefs else False
    except Exception as _e:
        logger.warning(f"Error reading advanced prefs for user {recipient.id}: {_e}")
        in_app_enabled = True
        email_enabled = True
        digest_mode = False

    notification = None

    # Channel 1: In-app notification bell (skip if per-type in-app is disabled)
    if "app_notification" in channels and in_app_enabled:
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

    # Channel 2: Email — skip if per-type email disabled or digest mode is on
    if "email" in channels and recipient.email and recipient.email_notifications and email_enabled and not digest_mode:
        try:
            email_html = _build_notification_email(title, content, link)
            send_email_sync(recipient.email, title, email_html)
        except Exception as e:
            logger.warning(f"Failed to send notification email to {recipient.email}: {e}")

    # Channel 3: ClassBridge message
    if "classbridge_message" in channels and sender and sender.id != recipient.id:
        try:
            _send_as_classbridge_message(db, sender, recipient, content, student_id)
        except Exception as e:
            logger.warning(f"Failed to send ClassBridge message notification: {e}")

    return notification


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
        notif = send_multi_channel_notification(
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
        if notif:
            notifications.append(notif)

    if notifications:
        logger.info(
            f"Sent {len(notifications)} parent notifications for student "
            f"{student_user.id}: {notification_type.value}"
        )

    return notifications


def _build_notification_email(title: str, content: str, link: str | None) -> str:
    """Build a branded HTML email for notifications."""
    from app.core.config import settings
    from app.services.email_service import wrap_branded_email

    link_html = ""
    if link:
        full_url = f"{settings.frontend_url}{link}"
        link_html = (
            f'<p style="margin:24px 0 0 0;"><a href="{full_url}" '
            f'style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;'
            f'padding:12px 24px;border-radius:8px;font-weight:600;">View in ClassBridge</a></p>'
        )

    body = (
        f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">{title}</h2>'
        f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">{content}</p>'
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
