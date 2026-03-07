"""Service that builds a unified recent-activity feed for parents."""

from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.models.message import Conversation, Message
from app.models.notification import Notification
from app.models.student import Student, parent_students
from app.models.task import Task
from app.models.user import User
from app.schemas.activity import ActivityItem, ActivityType


def _get_children(db: Session, parent_user_id: int, student_id: int | None = None):
    """Return list of (Student, User) tuples for a parent's linked children."""
    query = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(parent_students.c.parent_id == parent_user_id)
    )
    if student_id is not None:
        query = query.filter(Student.id == student_id)
    return query.all()


def get_recent_activity(
    db: Session,
    user_id: int,
    student_id: int | None = None,
    limit: int = 10,
) -> list[ActivityItem]:
    """Build a merged, time-sorted activity feed for a parent."""

    children = _get_children(db, user_id, student_id)
    if not children:
        return []

    # Maps for quick lookups
    student_user_ids = [user.id for _, user in children]
    student_ids = [s.id for s, _ in children]
    student_name_by_user_id: dict[int, str] = {user.id: user.full_name for _, user in children}
    student_id_by_user_id: dict[int, int] = {user.id: s.id for s, user in children}
    student_name_by_student_id: dict[int, str] = {s.id: user.full_name for s, user in children}

    items: list[ActivityItem] = []

    # ── 1. Courses created (linked to children via student_courses) ──
    course_rows = (
        db.query(Course, student_courses.c.student_id)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(student_courses.c.student_id.in_(student_ids))
        .order_by(Course.created_at.desc())
        .limit(limit)
        .all()
    )
    for course, sid in course_rows:
        items.append(ActivityItem(
            activity_type=ActivityType.COURSE_CREATED,
            title=course.name,
            description=f"Course added for {student_name_by_student_id.get(sid, 'student')}",
            resource_type="course",
            resource_id=course.id,
            student_id=sid,
            student_name=student_name_by_student_id.get(sid),
            created_at=course.created_at or datetime.now(timezone.utc),
            icon_type=ActivityType.COURSE_CREATED.value,
        ))

    # ── 2. Tasks created (by parent OR assigned to child) ──
    task_created_rows = (
        db.query(Task)
        .filter(
            Task.archived_at.is_(None),
            or_(
                Task.created_by_user_id == user_id,
                Task.assigned_to_user_id.in_(student_user_ids),
            ),
        )
        .order_by(Task.created_at.desc())
        .limit(limit)
        .all()
    )
    for task in task_created_rows:
        # Determine which child this relates to
        child_user_id = task.assigned_to_user_id if task.assigned_to_user_id in student_user_ids else None
        sid = student_id_by_user_id.get(child_user_id) if child_user_id else None
        sname = student_name_by_user_id.get(child_user_id) if child_user_id else None

        if task.is_completed and task.completed_at:
            items.append(ActivityItem(
                activity_type=ActivityType.TASK_COMPLETED,
                title=task.title,
                description=f"Task completed{(' by ' + sname) if sname else ''}",
                resource_type="task",
                resource_id=task.id,
                student_id=sid,
                student_name=sname,
                created_at=task.completed_at,
                icon_type=ActivityType.TASK_COMPLETED.value,
            ))
        else:
            items.append(ActivityItem(
                activity_type=ActivityType.TASK_CREATED,
                title=task.title,
                description=f"Task created{(' for ' + sname) if sname else ''}",
                resource_type="task",
                resource_id=task.id,
                student_id=sid,
                student_name=sname,
                created_at=task.created_at or datetime.now(timezone.utc),
                icon_type=ActivityType.TASK_CREATED.value,
            ))

    # ── 3. Course materials uploaded ──
    material_rows = (
        db.query(CourseContent, student_courses.c.student_id)
        .join(student_courses, student_courses.c.course_id == CourseContent.course_id)
        .filter(
            student_courses.c.student_id.in_(student_ids),
            CourseContent.archived_at.is_(None),
        )
        .order_by(CourseContent.created_at.desc())
        .limit(limit)
        .all()
    )
    for cc, sid in material_rows:
        items.append(ActivityItem(
            activity_type=ActivityType.MATERIAL_UPLOADED,
            title=cc.title,
            description=f"Material uploaded for {student_name_by_student_id.get(sid, 'student')}",
            resource_type="course_content",
            resource_id=cc.id,
            student_id=sid,
            student_name=student_name_by_student_id.get(sid),
            created_at=cc.created_at or datetime.now(timezone.utc),
            icon_type=ActivityType.MATERIAL_UPLOADED.value,
        ))

    # ── 4. Messages received ──
    message_rows = (
        db.query(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            or_(
                Conversation.participant_1_id == user_id,
                Conversation.participant_2_id == user_id,
            ),
            Message.sender_id != user_id,
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    for msg in message_rows:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        sender_name = sender.full_name if sender else "Someone"
        items.append(ActivityItem(
            activity_type=ActivityType.MESSAGE_RECEIVED,
            title=f"Message from {sender_name}",
            description=msg.content[:100] if msg.content else "",
            resource_type="message",
            resource_id=msg.id,
            student_id=None,
            student_name=None,
            created_at=msg.created_at or datetime.now(timezone.utc),
            icon_type=ActivityType.MESSAGE_RECEIVED.value,
        ))

    # ── 5. Notifications received ──
    notif_rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    for notif in notif_rows:
        items.append(ActivityItem(
            activity_type=ActivityType.NOTIFICATION_RECEIVED,
            title=notif.title,
            description=notif.content or "",
            resource_type="notification",
            resource_id=notif.id,
            student_id=None,
            student_name=None,
            created_at=notif.created_at or datetime.now(timezone.utc),
            icon_type=ActivityType.NOTIFICATION_RECEIVED.value,
        ))

    # Sort all items by created_at descending and take the top `limit`
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:limit]
