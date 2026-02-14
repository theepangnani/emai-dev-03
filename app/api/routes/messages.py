import logging
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students, student_teachers
from app.models.teacher import Teacher
from app.models.course import Course, student_courses
from app.models.message import Conversation, Message
from app.models.notification import Notification, NotificationType
from app.schemas.message import (
    ConversationCreate,
    ConversationSummary,
    ConversationDetail,
    MessageCreate,
    MessageResponse,
    RecipientOption,
    UnreadCountResponse,
)
from app.api.deps import get_current_user
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync
from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


def _load_template(name: str) -> str:
    path = os.path.join(TEMPLATE_DIR, name)
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Email template not found: {path}")
        return ""


def _render_template(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def _notify_message_recipient(
    db: Session,
    recipient: User,
    sender: User,
    message_content: str,
    conversation_id: int,
):
    """Create in-app notification and send email for a new message.

    Dedup: skips if there's already an unread MESSAGE notification for this
    conversation created within the last 5 minutes (avoids spam on rapid messages).
    """
    # Dedup check: recent unread notification for this conversation
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == recipient.id,
            Notification.type == NotificationType.MESSAGE,
            Notification.read == False,
            Notification.link == "/messages",
            Notification.title.contains(sender.full_name),
            Notification.created_at >= cutoff,
        )
        .first()
    )
    if existing:
        logger.debug(
            f"Skipping duplicate message notification for user {recipient.id} "
            f"(existing notification {existing.id} within 5-min window)"
        )
        return

    # Truncate preview
    preview = message_content[:100] + ("..." if len(message_content) > 100 else "")

    # Create in-app notification
    notification = Notification(
        user_id=recipient.id,
        type=NotificationType.MESSAGE,
        title=f"New message from {sender.full_name}",
        content=preview,
        link="/messages",
    )
    db.add(notification)

    # Send email if recipient has email notifications enabled
    if recipient.email_notifications:
        template = _load_template("message_notification.html")
        if template:
            html = _render_template(
                template,
                recipient_name=recipient.full_name,
                sender_name=sender.full_name,
                message_preview=preview,
                app_url=settings.frontend_url,
            )
            sent = send_email_sync(
                to_email=recipient.email,
                subject=f"New message from {sender.full_name} — ClassBridge",
                html_content=html,
            )
            if sent:
                logger.info(f"Message notification email sent to {recipient.email}")
        else:
            logger.warning("Message notification email template not found, skipping email")

router = APIRouter(prefix="/messages", tags=["Messages"])


def _get_other_participant(conv: Conversation, current_user_id: int) -> int:
    """Get the ID of the other participant in a conversation."""
    if conv.participant_1_id == current_user_id:
        return conv.participant_2_id
    return conv.participant_1_id


def _build_message_response(msg: Message, db: Session) -> MessageResponse:
    """Build a MessageResponse from a Message model."""
    sender = db.query(User).filter(User.id == msg.sender_id).first()
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        sender_name=sender.full_name if sender else "Unknown",
        content=msg.content,
        is_read=msg.is_read,
        read_at=msg.read_at,
        created_at=msg.created_at,
    )


def _build_conversation_detail(
    db: Session,
    conv: Conversation,
    current_user: User,
    message_offset: int = 0,
    message_limit: int = 50,
) -> ConversationDetail:
    """Build a ConversationDetail response."""
    participant_1 = db.query(User).filter(User.id == conv.participant_1_id).first()
    participant_2 = db.query(User).filter(User.id == conv.participant_2_id).first()

    student_name = None
    if conv.student_id:
        student = db.query(Student).filter(Student.id == conv.student_id).first()
        if student:
            student_user = db.query(User).filter(User.id == student.user_id).first()
            student_name = student_user.full_name if student_user else None

    total_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .count()
    )
    message_rows = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(desc(Message.created_at))
        .offset(message_offset)
        .limit(message_limit)
        .all()
    )
    messages = [_build_message_response(msg, db) for msg in reversed(message_rows)]

    return ConversationDetail(
        id=conv.id,
        participant_1_id=conv.participant_1_id,
        participant_1_name=participant_1.full_name if participant_1 else "Unknown",
        participant_2_id=conv.participant_2_id,
        participant_2_name=participant_2.full_name if participant_2 else "Unknown",
        student_id=conv.student_id,
        student_name=student_name,
        subject=conv.subject,
        messages=messages,
        messages_total=total_messages,
        messages_offset=message_offset,
        messages_limit=message_limit,
        created_at=conv.created_at,
    )


@router.get("/recipients", response_model=list[RecipientOption])
def get_valid_recipients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of users this person can message based on student-teacher relationships."""
    logger.info(f"Getting recipients for user {current_user.id} ({current_user.role})")

    if current_user.role == UserRole.PARENT:
        # Parent can message teachers of their children's courses
        children = (
            db.query(Student)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )

        if not children:
            logger.debug(f"Parent {current_user.id} has no linked children")
            return []

        child_ids = [child.id for child in children]

        # Get teachers of courses these children are enrolled in
        teacher_query = (
            db.query(User, Teacher)
            .join(Teacher, Teacher.user_id == User.id)
            .join(Course, Course.teacher_id == Teacher.id)
            .join(student_courses, student_courses.c.course_id == Course.id)
            .filter(student_courses.c.student_id.in_(child_ids))
            .distinct()
        )

        teachers = teacher_query.all()

        result = []
        seen_user_ids = set()
        for user, teacher in teachers:
            # Find which children this teacher teaches
            taught_children = []
            for child in children:
                child_courses = (
                    db.query(Course)
                    .join(student_courses, student_courses.c.course_id == Course.id)
                    .filter(student_courses.c.student_id == child.id)
                    .filter(Course.teacher_id == teacher.id)
                    .first()
                )
                if child_courses:
                    child_user = (
                        db.query(User).filter(User.id == child.user_id).first()
                    )
                    if child_user:
                        taught_children.append(child_user.full_name)

            seen_user_ids.add(user.id)
            result.append(
                RecipientOption(
                    user_id=user.id,
                    full_name=user.full_name,
                    role=user.role.value,
                    student_names=taught_children,
                )
            )

        # Also include directly-linked teachers (from student_teachers table)
        direct_links = (
            db.query(student_teachers)
            .filter(student_teachers.c.student_id.in_(child_ids))
            .all()
        )
        for link in direct_links:
            if link.teacher_user_id and link.teacher_user_id not in seen_user_ids:
                teacher_user = db.query(User).filter(User.id == link.teacher_user_id).first()
                if teacher_user:
                    # Find child name for this link
                    child = next((c for c in children if c.id == link.student_id), None)
                    child_name = None
                    if child:
                        child_user = db.query(User).filter(User.id == child.user_id).first()
                        child_name = child_user.full_name if child_user else None

                    seen_user_ids.add(teacher_user.id)
                    result.append(
                        RecipientOption(
                            user_id=teacher_user.id,
                            full_name=teacher_user.full_name,
                            role=teacher_user.role.value,
                            student_names=[child_name] if child_name else [],
                        )
                    )

        logger.info(f"Found {len(result)} valid recipients for parent {current_user.id}")
        return result

    elif current_user.role == UserRole.TEACHER:
        # Teacher can message parents of students in their courses
        teacher = (
            db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        )

        if not teacher:
            logger.warning(f"No teacher profile for user {current_user.id}")
            return []

        # Get students in teacher's courses who have parents linked via join table
        students_in_courses = (
            db.query(Student)
            .join(student_courses, student_courses.c.student_id == Student.id)
            .join(Course, Course.id == student_courses.c.course_id)
            .filter(Course.teacher_id == teacher.id)
            .distinct()
            .all()
        )

        # Group students by parent using parent_students join table
        parent_student_map: dict[int, list[str]] = {}
        for student in students_in_courses:
            student_user = db.query(User).filter(User.id == student.user_id).first()
            student_name = student_user.full_name if student_user else "Unknown"

            # Find all parents for this student
            links = (
                db.query(parent_students.c.parent_id)
                .filter(parent_students.c.student_id == student.id)
                .all()
            )
            for (pid,) in links:
                if pid not in parent_student_map:
                    parent_student_map[pid] = []
                parent_student_map[pid].append(student_name)

        # Get parent users
        parents = db.query(User).filter(User.id.in_(parent_student_map.keys())).all()

        result = [
            RecipientOption(
                user_id=p.id,
                full_name=p.full_name,
                role=p.role.value,
                student_names=parent_student_map[p.id],
            )
            for p in parents
        ]

        # Also include parents who directly linked this teacher via student_teachers
        seen_parent_ids = set(parent_student_map.keys())
        direct_links = (
            db.query(student_teachers)
            .filter(student_teachers.c.teacher_user_id == current_user.id)
            .all()
        )
        for link in direct_links:
            student = db.query(Student).filter(Student.id == link.student_id).first()
            if not student:
                continue
            student_user = db.query(User).filter(User.id == student.user_id).first()
            student_name = student_user.full_name if student_user else "Unknown"

            # Find the parent who added this link
            parent_id = link.added_by_user_id
            if parent_id not in seen_parent_ids:
                parent_user = db.query(User).filter(User.id == parent_id).first()
                if parent_user:
                    seen_parent_ids.add(parent_id)
                    result.append(
                        RecipientOption(
                            user_id=parent_user.id,
                            full_name=parent_user.full_name,
                            role=parent_user.role.value,
                            student_names=[student_name],
                        )
                    )
            else:
                # Add the student name to existing entry if not already there
                for r in result:
                    if r.user_id == parent_id and student_name not in r.student_names:
                        r.student_names.append(student_name)

        logger.info(f"Found {len(result)} valid recipients for teacher {current_user.id}")
        return result

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only parents and teachers can use messaging",
    )


@router.post("/conversations", response_model=ConversationDetail)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new conversation with a valid recipient."""
    logger.info(
        f"User {current_user.id} creating conversation with recipient {data.recipient_id}"
    )

    # Validate sender is parent or teacher
    if not (current_user.has_role(UserRole.PARENT) or current_user.has_role(UserRole.TEACHER)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents and teachers can start conversations",
        )

    # Validate recipient exists
    recipient = db.query(User).filter(User.id == data.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    # Verify this is a valid recipient
    valid_recipients = get_valid_recipients(db=db, current_user=current_user)
    valid_ids = [r.user_id for r in valid_recipients]

    if data.recipient_id not in valid_ids:
        logger.warning(
            f"User {current_user.id} attempted to message invalid recipient {data.recipient_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only message teachers of your children or parents of your students",
        )

    # Check if conversation already exists between these two
    existing = (
        db.query(Conversation)
        .filter(
            or_(
                and_(
                    Conversation.participant_1_id == current_user.id,
                    Conversation.participant_2_id == data.recipient_id,
                ),
                and_(
                    Conversation.participant_1_id == data.recipient_id,
                    Conversation.participant_2_id == current_user.id,
                ),
            )
        )
        .first()
    )

    if existing:
        # Add message to existing conversation
        logger.info(f"Adding to existing conversation {existing.id}")
        message = Message(
            conversation_id=existing.id,
            sender_id=current_user.id,
            content=data.initial_message,
        )
        db.add(message)
        _notify_message_recipient(db, recipient, current_user, data.initial_message, existing.id)
        db.commit()
        db.refresh(existing)
        return _build_conversation_detail(db, existing, current_user)

    # Create new conversation
    conversation = Conversation(
        participant_1_id=current_user.id,
        participant_2_id=data.recipient_id,
        student_id=data.student_id,
        subject=data.subject,
    )
    db.add(conversation)
    db.flush()

    # Add initial message
    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=data.initial_message,
    )
    db.add(message)
    _notify_message_recipient(db, recipient, current_user, data.initial_message, conversation.id)
    db.commit()
    db.refresh(conversation)

    logger.info(f"Created new conversation {conversation.id}")
    return _build_conversation_detail(db, conversation, current_user)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all conversations for the current user with unread counts."""
    conversations = (
        db.query(Conversation)
        .filter(
            or_(
                Conversation.participant_1_id == current_user.id,
                Conversation.participant_2_id == current_user.id,
            )
        )
        .all()
    )

    result = []
    for conv in conversations:
        other_id = _get_other_participant(conv, current_user.id)
        other_user = db.query(User).filter(User.id == other_id).first()

        # Get last message
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .first()
        )

        # Count unread messages (from other person, not read)
        unread_count = (
            db.query(Message)
            .filter(
                Message.conversation_id == conv.id,
                Message.sender_id != current_user.id,
                Message.is_read == False,
            )
            .count()
        )

        # Get student name if set
        student_name = None
        if conv.student_id:
            student = db.query(Student).filter(Student.id == conv.student_id).first()
            if student:
                student_user = db.query(User).filter(User.id == student.user_id).first()
                student_name = student_user.full_name if student_user else None

        result.append(
            ConversationSummary(
                id=conv.id,
                other_participant_id=other_id,
                other_participant_name=other_user.full_name if other_user else "Unknown",
                student_id=conv.student_id,
                student_name=student_name,
                subject=conv.subject,
                last_message_preview=last_msg.content[:100] if last_msg else None,
                last_message_at=last_msg.created_at if last_msg else None,
                unread_count=unread_count,
                created_at=conv.created_at,
            )
        )

    # Sort by last message time, most recent first
    result.sort(key=lambda x: x.last_message_at or x.created_at, reverse=True)
    return result[skip: skip + limit]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a conversation with all its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify current user is a participant
    if current_user.id not in [conv.participant_1_id, conv.participant_2_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation",
        )

    return _build_conversation_detail(
        db,
        conv,
        current_user,
        message_offset=offset,
        message_limit=limit,
    )


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse
)
def send_message(
    conversation_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message in an existing conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify current user is a participant
    if current_user.id not in [conv.participant_1_id, conv.participant_2_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation",
        )

    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=data.content,
    )
    db.add(message)
    db.flush()
    log_action(db, user_id=current_user.id, action="create", resource_type="message", resource_id=message.id)

    # Notify the other participant
    recipient_id = _get_other_participant(conv, current_user.id)
    recipient = db.query(User).filter(User.id == recipient_id).first()
    if recipient:
        _notify_message_recipient(db, recipient, current_user, data.content, conversation_id)

    db.commit()
    db.refresh(message)

    logger.info(
        f"Message sent in conversation {conversation_id} by user {current_user.id}"
    )

    return _build_message_response(message, db)


@router.patch("/conversations/{conversation_id}/read")
def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all messages in a conversation as read."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify current user is a participant
    if current_user.id not in [conv.participant_1_id, conv.participant_2_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation",
        )

    # Mark unread messages from other person as read
    updated = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.is_read == False,
        )
        .update({"is_read": True, "read_at": datetime.utcnow()})
    )
    db.commit()

    logger.debug(f"Marked {updated} messages as read in conversation {conversation_id}")

    return {"status": "ok", "messages_marked_read": updated}


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total unread message count for the current user."""
    # Get all conversations user is part of
    conversations = (
        db.query(Conversation)
        .filter(
            or_(
                Conversation.participant_1_id == current_user.id,
                Conversation.participant_2_id == current_user.id,
            )
        )
        .all()
    )

    conv_ids = [c.id for c in conversations]

    if not conv_ids:
        return UnreadCountResponse(total_unread=0)

    # Count unread messages across all conversations
    total_unread = (
        db.query(Message)
        .filter(
            Message.conversation_id.in_(conv_ids),
            Message.sender_id != current_user.id,
            Message.is_read == False,
        )
        .count()
    )

    return UnreadCountResponse(total_unread=total_unread)
