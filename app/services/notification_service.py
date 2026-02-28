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

    notification = None

    # Channel 1: In-app notification bell
    if "app_notification" in channels:
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

    # Channel 2: Email
    if "email" in channels and recipient.email and recipient.email_notifications:
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
    """Build a simple HTML email for notifications."""
    from app.core.config import settings

    link_html = ""
    if link:
        full_url = f"{settings.frontend_url}{link}"
        link_html = f'<p><a href="{full_url}" style="color: #4F46E5;">View in ClassBridge</a></p>'

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #4F46E5; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">ClassBridge</h1>
        </div>
        <div style="padding: 30px; background: #ffffff;">
            <h2 style="color: #1F2937; margin-top: 0;">{title}</h2>
            <p style="color: #4B5563; line-height: 1.6;">{content}</p>
            {link_html}
        </div>
        <div style="padding: 15px; text-align: center; color: #9CA3AF; font-size: 12px;">
            ClassBridge — Stay connected with your child's education
        </div>
    </div>
    """


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
