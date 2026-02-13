import logging
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.task import Task
from app.models.user import User
from app.models.notification import Notification, NotificationType
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _load_template(name: str) -> str:
    path = os.path.join(TEMPLATE_DIR, name)
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Email template not found: {path}")
        return ""


def _render(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


async def check_task_reminders():
    """Check for upcoming tasks and send reminders.

    Runs daily. For each user with tasks (creator or assignee), checks if any
    tasks are due within the user's configured reminder window. Creates in-app
    notifications and sends emails if enabled. Deduplicates by checking if a
    notification was already sent today for the same task.
    """
    logger.info("Running task reminder check...")

    db: Session = SessionLocal()
    try:
        template = _load_template("task_reminder.html")
        notifications_created = 0
        emails_sent = 0
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get all active users who might have tasks
        users = db.query(User).filter(User.is_active == True).all()

        for user in users:
            reminder_days_str = user.task_reminder_days or "1,3"
            try:
                reminder_days = [int(d.strip()) for d in reminder_days_str.split(",")]
            except ValueError:
                reminder_days = [1, 3]

            for days in reminder_days:
                target_start = now + timedelta(days=days)
                target_end = target_start + timedelta(days=1)

                # Tasks assigned to this user OR created by this user
                tasks = (
                    db.query(Task)
                    .filter(
                        Task.due_date >= target_start,
                        Task.due_date < target_end,
                        Task.is_completed == False,
                        Task.archived_at.is_(None),
                        (
                            (Task.assigned_to_user_id == user.id) |
                            (Task.created_by_user_id == user.id)
                        ),
                    )
                    .all()
                )

                for task in tasks:
                    # Dedup: skip if already notified today
                    existing = (
                        db.query(Notification)
                        .filter(
                            Notification.user_id == user.id,
                            Notification.type == NotificationType.TASK_DUE,
                            Notification.title.contains(task.title),
                            Notification.created_at >= today_start,
                        )
                        .first()
                    )
                    if existing:
                        continue

                    due_date_str = task.due_date.strftime("%B %d, %Y") if task.due_date else "Unknown"

                    notification = Notification(
                        user_id=user.id,
                        type=NotificationType.TASK_DUE,
                        title=f"{task.title} due in {days} day{'s' if days != 1 else ''}",
                        content=f"Your task is due on {due_date_str}.",
                        link=f"/tasks/{task.id}",
                    )
                    db.add(notification)
                    notifications_created += 1

                    # Send email if enabled
                    if user.email_notifications and template:
                        html = _render(
                            template,
                            user_name=user.full_name or "there",
                            task_title=task.title,
                            days_remaining=str(days),
                            due_date=due_date_str,
                            task_url=f"/tasks/{task.id}",
                        )
                        sent = await send_email(
                            to_email=user.email,
                            subject=f"Task Reminder: {task.title} due in {days} day{'s' if days != 1 else ''}",
                            html_content=html,
                        )
                        if sent:
                            emails_sent += 1

        db.commit()
        logger.info(
            f"Task reminder check complete | "
            f"notifications={notifications_created} | emails={emails_sent}"
        )

    except Exception as e:
        logger.error(f"Task reminder job failed | error={e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
