import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.notification import Notification
from app.models.assignment import Assignment
from app.models.task import Task
from app.models.user import User
from app.services.notification_service import send_multi_channel_notification

logger = logging.getLogger(__name__)


def _source_due_date_passed(db: Session, source_type: str | None, source_id: int | None) -> bool:
    """Check if the source entity's due date has already passed."""
    if not source_type or not source_id:
        return False

    now = datetime.now(timezone.utc)

    if source_type == "assignment":
        assignment = db.query(Assignment).filter(Assignment.id == source_id).first()
        if assignment and assignment.due_date:
            due = assignment.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            return due < now

    elif source_type == "task":
        task = db.query(Task).filter(Task.id == source_id).first()
        if task and task.due_date:
            due = task.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            return due < now

    return False


async def check_notification_reminders():
    """Resend reminders for unacknowledged notifications.

    Runs every 6 hours. Queries notifications that:
    - require acknowledgement (requires_ack=True)
    - have not been acknowledged (acked_at IS NULL)
    - are due for a reminder (next_reminder_at <= now)
    - have not exceeded max reminders (reminder_count < 3)

    Skips if the source entity's due date has passed.
    After 3 reminders, stops by setting next_reminder_at = None.
    """
    logger.info("Running notification reminder check...")

    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Query unacked notifications due for reminder
        notifications = (
            db.query(Notification)
            .filter(
                Notification.requires_ack == True,
                Notification.acked_at.is_(None),
                Notification.next_reminder_at <= now,
                Notification.reminder_count < 3,
            )
            .all()
        )

        reminders_sent = 0
        for notif in notifications:
            # Skip if source entity's due date has passed
            if _source_due_date_passed(db, notif.source_type, notif.source_id):
                notif.next_reminder_at = None
                continue

            # Get recipient user
            recipient = db.query(User).filter(User.id == notif.user_id).first()
            if not recipient:
                continue

            # Resend via email and classbridge_message only (no new in-app notification)
            try:
                send_multi_channel_notification(
                    db=db,
                    recipient=recipient,
                    sender=None,
                    title=f"Reminder: {notif.title}",
                    content=notif.content or "",
                    notification_type=notif.type,
                    link=notif.link,
                    channels=["email", "classbridge_message"],
                    source_type=notif.source_type,
                    source_id=notif.source_id,
                )
            except Exception as e:
                logger.warning(f"Failed to send reminder for notification {notif.id}: {e}")

            # Update the existing notification row
            notif.reminder_count += 1
            if notif.reminder_count >= 3:
                notif.next_reminder_at = None
            else:
                notif.next_reminder_at = now + timedelta(hours=24)
            reminders_sent += 1

        db.commit()
        logger.info(
            f"Notification reminder check complete | "
            f"checked={len(notifications)} | reminders_sent={reminders_sent}"
        )

    except Exception as e:
        logger.error(f"Notification reminder job failed | error={e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
