import logging
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.user import User
from app.models.notification import Notification, NotificationType
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _load_template(name: str) -> str:
    """Load an HTML email template."""
    path = os.path.join(TEMPLATE_DIR, name)
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Email template not found: {path}")
        return ""


def _render_template(template: str, **kwargs) -> str:
    """Simple template rendering with {{key}} placeholders."""
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


async def check_assignment_reminders():
    """Check for upcoming assignments and send reminders.

    Runs daily. For each student-parent pair (via parent_students join table),
    checks if any assignments are due in the user's configured reminder days
    (default: 1, 3 days). Creates in-app notifications and sends emails if enabled.
    """
    logger.info("Running assignment reminder check...")

    db: Session = SessionLocal()
    try:
        # Get all parent-student links
        links = db.query(parent_students).all()

        template = _load_template("assignment_reminder.html")
        notifications_created = 0
        emails_sent = 0

        for link in links:
            parent_id = link.parent_id
            student_id = link.student_id

            parent = db.query(User).filter(User.id == parent_id).first()
            if not parent or not parent.is_active:
                continue

            student = db.query(Student).filter(Student.id == student_id).first()
            if not student:
                continue

            reminder_days_str = parent.assignment_reminder_days or "1,3"
            try:
                reminder_days = [int(d.strip()) for d in reminder_days_str.split(",")]
            except ValueError:
                reminder_days = [1, 3]

            # Get student's user record for name
            student_user = db.query(User).filter(User.id == student.user_id).first()
            if not student_user:
                continue

            # Get student's courses
            student_course_ids = (
                db.query(student_courses.c.course_id)
                .filter(student_courses.c.student_id == student.id)
                .all()
            )
            course_ids = [c[0] for c in student_course_ids]

            if not course_ids:
                continue

            # Check assignments due in reminder_days
            now = datetime.utcnow()

            for days in reminder_days:
                target_start = now + timedelta(days=days)
                target_end = target_start + timedelta(days=1)

                assignments = (
                    db.query(Assignment)
                    .filter(
                        Assignment.course_id.in_(course_ids),
                        Assignment.due_date >= target_start,
                        Assignment.due_date < target_end,
                    )
                    .all()
                )

                for assignment in assignments:
                    # Check if we already sent this notification today
                    existing = (
                        db.query(Notification)
                        .filter(
                            Notification.user_id == parent.id,
                            Notification.type == NotificationType.ASSIGNMENT_DUE,
                            Notification.title.contains(assignment.title),
                            Notification.created_at >= now.replace(hour=0, minute=0, second=0),
                        )
                        .first()
                    )

                    if existing:
                        continue

                    # Get course name
                    course = db.query(Course).filter(Course.id == assignment.course_id).first()
                    course_name = course.name if course else "Unknown Course"

                    due_date_str = assignment.due_date.strftime("%B %d, %Y") if assignment.due_date else "Unknown"

                    # Create in-app notification for parent
                    notification = Notification(
                        user_id=parent.id,
                        type=NotificationType.ASSIGNMENT_DUE,
                        title=f"{assignment.title} due in {days} day{'s' if days != 1 else ''}",
                        content=f"{student_user.full_name}'s assignment for {course_name} is due on {due_date_str}.",
                        link="/dashboard",
                    )
                    db.add(notification)
                    notifications_created += 1

                    # Also notify the student
                    student_notification = Notification(
                        user_id=student.user_id,
                        type=NotificationType.ASSIGNMENT_DUE,
                        title=f"{assignment.title} due in {days} day{'s' if days != 1 else ''}",
                        content=f"Your {course_name} assignment is due on {due_date_str}.",
                        link="/dashboard",
                    )
                    db.add(student_notification)
                    notifications_created += 1

                    # Send email to parent if enabled
                    if parent.email_notifications and template:
                        html = _render_template(
                            template,
                            user_name=parent.full_name,
                            student_name=student_user.full_name,
                            assignment_title=assignment.title,
                            course_name=course_name,
                            days_remaining=str(days),
                            due_date=due_date_str,
                            app_url="http://localhost:5173",
                        )
                        sent = await send_email(
                            to_email=parent.email,
                            subject=f"Assignment Reminder: {assignment.title} due in {days} day{'s' if days != 1 else ''}",
                            html_content=html,
                        )
                        if sent:
                            emails_sent += 1

        db.commit()
        logger.info(
            f"Assignment reminder check complete | "
            f"notifications={notifications_created} | emails={emails_sent}"
        )

    except Exception as e:
        logger.error(f"Assignment reminder job failed | error={e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
