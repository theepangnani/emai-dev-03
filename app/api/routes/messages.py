import logging
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import or_, and_, desc, func as sa_func

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
from app.services.email_service import send_email_sync, send_emails_batch, add_inspiration_to_email
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
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
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
            html = add_inspiration_to_email(html, db, recipient.role)
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


def _get_all_admins(db: Session, exclude_ids: set[int] | None = None) -> list[User]:
    """Get all active admin users, optionally excluding some IDs."""
    admins = (
        db.query(User)
        .filter(
            User.is_active == True,  # noqa: E712
            or_(
                User.roles.contains("admin"),
                User.role == UserRole.ADMIN,
            ),
        )
        .all()
    )
    if exclude_ids:
        admins = [a for a in admins if a.id not in exclude_ids]
    return admins


def _fan_out_to_admins(
    db: Session,
    sender: User,
    message_content: str,
    primary_admin_id: int,
    subject: str | None = None,
    student_id: int | None = None,
):
    """When a user messages an admin, fan out to ALL other admin users.

    Creates/reuses conversations and adds the message for each admin.
    Sends email notifications to all admins (including the primary recipient).
    """
    other_admins = _get_all_admins(db, exclude_ids={sender.id, primary_admin_id})
    if not other_admins:
        return

    for admin in other_admins:
        # Find or create conversation between sender and this admin
        conv = (
            db.query(Conversation)
            .filter(
                or_(
                    and_(
                        Conversation.participant_1_id == sender.id,
                        Conversation.participant_2_id == admin.id,
                    ),
                    and_(
                        Conversation.participant_1_id == admin.id,
                        Conversation.participant_2_id == sender.id,
                    ),
                )
            )
            .first()
        )
        if not conv:
            conv = Conversation(
                participant_1_id=sender.id,
                participant_2_id=admin.id,
                student_id=student_id,
                subject=subject,
            )
            db.add(conv)
            db.flush()

        db.add(Message(
            conversation_id=conv.id,
            sender_id=sender.id,
            content=message_content,
        ))
        _notify_message_recipient(db, admin, sender, message_content, conv.id)


def _get_other_participant(conv: Conversation, current_user_id: int) -> int:
    """Get the ID of the other participant in a conversation."""
    if conv.participant_1_id == current_user_id:
        return conv.participant_2_id
    return conv.participant_1_id


def _build_message_response(msg: Message, sender_lookup: dict[int, User] | None = None) -> MessageResponse:
    """Build a MessageResponse from a Message model.

    Uses msg.sender relationship or an optional pre-fetched sender_lookup dict.
    """
    if sender_lookup and msg.sender_id in sender_lookup:
        sender = sender_lookup[msg.sender_id]
    else:
        sender = msg.sender
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
    """Build a ConversationDetail response.

    Uses conversation relationships (participant_1, participant_2, student)
    and batch-loads message senders to avoid N+1.
    """
    p1 = conv.participant_1
    p2 = conv.participant_2

    student_name = None
    if conv.student_id and conv.student:
        student_user = conv.student.user
        student_name = student_user.full_name if student_user else None

    total_messages = (
        db.query(sa_func.count(Message.id))
        .filter(Message.conversation_id == conv.id)
        .scalar()
    )
    message_rows = (
        db.query(Message)
        .options(selectinload(Message.sender))
        .filter(Message.conversation_id == conv.id)
        .order_by(desc(Message.created_at))
        .offset(message_offset)
        .limit(message_limit)
        .all()
    )
    messages = [_build_message_response(msg) for msg in reversed(message_rows)]

    return ConversationDetail(
        id=conv.id,
        participant_1_id=conv.participant_1_id,
        participant_1_name=p1.full_name if p1 else "Unknown",
        participant_2_id=conv.participant_2_id,
        participant_2_name=p2.full_name if p2 else "Unknown",
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
    """Get list of users this person can message based on student-teacher relationships.

    All users can always message admin users. Parents can message teachers,
    teachers can message parents, and admins can message everyone.
    """
    logger.info(f"Getting recipients for user {current_user.id} ({current_user.role})")

    result: list[RecipientOption] = []
    seen_user_ids: set[int] = set()

    if current_user.has_role(UserRole.PARENT):
        # Parent can message teachers of their children's courses
        children = (
            db.query(Student)
            .options(selectinload(Student.user))
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )

        if children:
            child_ids = [child.id for child in children]
            # Build child name lookup (using pre-loaded user relationship)
            child_name_map = {child.id: (child.user.full_name if child.user else "Unknown") for child in children}

            # Batch-fetch teacher-student-course relationships
            teacher_student_rows = (
                db.query(User, Teacher.id, student_courses.c.student_id)
                .join(Teacher, Teacher.user_id == User.id)
                .join(Course, Course.teacher_id == Teacher.id)
                .join(student_courses, student_courses.c.course_id == Course.id)
                .filter(student_courses.c.student_id.in_(child_ids))
                .all()
            )

            # Group: teacher_user -> list of child names they teach
            teacher_children_map: dict[int, tuple[User, list[str]]] = {}
            for user, _teacher_id, student_id in teacher_student_rows:
                if user.id not in teacher_children_map:
                    teacher_children_map[user.id] = (user, [])
                child_name = child_name_map.get(student_id, "Unknown")
                if child_name not in teacher_children_map[user.id][1]:
                    teacher_children_map[user.id][1].append(child_name)

            for uid, (user, taught_children) in teacher_children_map.items():
                seen_user_ids.add(uid)
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
            # Batch-fetch all teacher users for direct links
            direct_teacher_uids = {link.teacher_user_id for link in direct_links if link.teacher_user_id and link.teacher_user_id not in seen_user_ids}
            direct_teacher_users = {}
            if direct_teacher_uids:
                for u in db.query(User).filter(User.id.in_(direct_teacher_uids)).all():
                    direct_teacher_users[u.id] = u

            for link in direct_links:
                if link.teacher_user_id and link.teacher_user_id not in seen_user_ids:
                    teacher_user = direct_teacher_users.get(link.teacher_user_id)
                    if teacher_user:
                        child_name = child_name_map.get(link.student_id)
                        seen_user_ids.add(teacher_user.id)
                        result.append(
                            RecipientOption(
                                user_id=teacher_user.id,
                                full_name=teacher_user.full_name,
                                role=teacher_user.role.value,
                                student_names=[child_name] if child_name else [],
                            )
                        )

    if current_user.has_role(UserRole.TEACHER):
        # Teacher can message parents of students in their courses
        teacher = (
            db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        )

        if teacher:
            students_in_courses = (
                db.query(Student)
                .options(selectinload(Student.user))
                .join(student_courses, student_courses.c.student_id == Student.id)
                .join(Course, Course.id == student_courses.c.course_id)
                .filter(Course.teacher_id == teacher.id)
                .distinct()
                .all()
            )

            # Build student name lookup from pre-loaded relationships
            student_name_map = {s.id: (s.user.full_name if s.user else "Unknown") for s in students_in_courses}
            student_ids = [s.id for s in students_in_courses]

            # Batch-fetch all parent links for these students
            parent_student_map: dict[int, list[str]] = {}
            if student_ids:
                parent_links = (
                    db.query(parent_students.c.parent_id, parent_students.c.student_id)
                    .filter(parent_students.c.student_id.in_(student_ids))
                    .all()
                )
                for pid, sid in parent_links:
                    if pid not in parent_student_map:
                        parent_student_map[pid] = []
                    parent_student_map[pid].append(student_name_map.get(sid, "Unknown"))

            parents = db.query(User).filter(User.id.in_(parent_student_map.keys())).all() if parent_student_map else []

            for p in parents:
                if p.id not in seen_user_ids:
                    seen_user_ids.add(p.id)
                    result.append(
                        RecipientOption(
                            user_id=p.id,
                            full_name=p.full_name,
                            role=p.role.value,
                            student_names=parent_student_map[p.id],
                        )
                    )

            # Also include parents who directly linked this teacher via student_teachers
            direct_links = (
                db.query(student_teachers)
                .filter(student_teachers.c.teacher_user_id == current_user.id)
                .all()
            )
            if direct_links:
                # Batch-fetch all students and parent users referenced by direct links
                dl_student_ids = {link.student_id for link in direct_links}
                dl_parent_ids = {link.added_by_user_id for link in direct_links if link.added_by_user_id}
                all_user_ids = dl_parent_ids | set()

                dl_students = {s.id: s for s in db.query(Student).options(selectinload(Student.user)).filter(Student.id.in_(dl_student_ids)).all()} if dl_student_ids else {}
                dl_users = {u.id: u for u in db.query(User).filter(User.id.in_(all_user_ids)).all()} if all_user_ids else {}

                for link in direct_links:
                    student = dl_students.get(link.student_id)
                    if not student:
                        continue
                    student_name = student.user.full_name if student.user else "Unknown"

                    parent_id = link.added_by_user_id
                    if parent_id not in seen_user_ids:
                        parent_user = dl_users.get(parent_id)
                        if parent_user:
                            seen_user_ids.add(parent_id)
                            result.append(
                                RecipientOption(
                                    user_id=parent_user.id,
                                    full_name=parent_user.full_name,
                                    role=parent_user.role.value,
                                    student_names=[student_name],
                                )
                            )
                    else:
                        for r in result:
                            if r.user_id == parent_id and student_name not in r.student_names:
                                r.student_names.append(student_name)

    # ── Always include admin users as valid recipients for everyone ──
    admin_users = (
        db.query(User)
        .filter(
            User.is_active == True,  # noqa: E712
            or_(
                User.roles.contains("admin"),
                User.role == UserRole.ADMIN,
            ),
        )
        .all()
    )
    for admin in admin_users:
        if admin.id != current_user.id and admin.id not in seen_user_ids:
            seen_user_ids.add(admin.id)
            result.append(
                RecipientOption(
                    user_id=admin.id,
                    full_name=admin.full_name,
                    role="admin",
                    student_names=[],
                )
            )

    logger.info(f"Found {len(result)} valid recipients for user {current_user.id}")
    return result


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
            detail="You cannot message this user",
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

        # Fan out to all admins if recipient is an admin
        if recipient.has_role(UserRole.ADMIN):
            _fan_out_to_admins(
                db, current_user, data.initial_message,
                primary_admin_id=recipient.id,
                subject=data.subject,
                student_id=data.student_id,
            )

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

    # Fan out to all admins if recipient is an admin
    if recipient.has_role(UserRole.ADMIN):
        _fan_out_to_admins(
            db, current_user, data.initial_message,
            primary_admin_id=recipient.id,
            subject=data.subject,
            student_id=data.student_id,
        )

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
        .options(
            selectinload(Conversation.participant_1),
            selectinload(Conversation.participant_2),
            selectinload(Conversation.student).selectinload(Student.user),
        )
        .filter(
            or_(
                Conversation.participant_1_id == current_user.id,
                Conversation.participant_2_id == current_user.id,
            )
        )
        .all()
    )

    if not conversations:
        return []

    conv_ids = [c.id for c in conversations]

    # Batch-fetch last message per conversation using a subquery
    last_msg_subq = (
        db.query(
            Message.conversation_id,
            sa_func.max(Message.id).label("max_id"),
        )
        .filter(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .subquery()
    )
    last_messages = (
        db.query(Message)
        .join(last_msg_subq, Message.id == last_msg_subq.c.max_id)
        .all()
    )
    last_msg_map = {m.conversation_id: m for m in last_messages}

    # Batch-fetch unread counts per conversation
    unread_rows = (
        db.query(Message.conversation_id, sa_func.count(Message.id))
        .filter(
            Message.conversation_id.in_(conv_ids),
            Message.sender_id != current_user.id,
            Message.is_read == False,  # noqa: E712
        )
        .group_by(Message.conversation_id)
        .all()
    )
    unread_map = {cid: cnt for cid, cnt in unread_rows}

    result = []
    for conv in conversations:
        other_id = _get_other_participant(conv, current_user.id)
        other_user = conv.participant_1 if conv.participant_2_id == current_user.id else conv.participant_2

        student_name = None
        if conv.student_id and conv.student and conv.student.user:
            student_name = conv.student.user.full_name

        last_msg = last_msg_map.get(conv.id)
        result.append(
            ConversationSummary(
                id=conv.id,
                other_participant_id=other_id,
                other_participant_name=other_user.full_name if other_user else "Unknown",
                other_participant_role=other_user.role.value if other_user else None,
                student_id=conv.student_id,
                student_name=student_name,
                subject=conv.subject,
                last_message_preview=last_msg.content[:100] if last_msg else None,
                last_message_at=last_msg.created_at if last_msg else None,
                unread_count=unread_map.get(conv.id, 0),
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
    conv = (
        db.query(Conversation)
        .options(
            selectinload(Conversation.participant_1),
            selectinload(Conversation.participant_2),
            selectinload(Conversation.student).selectinload(Student.user),
        )
        .filter(Conversation.id == conversation_id)
        .first()
    )

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

        # Fan out to all admins if recipient is an admin
        if recipient.has_role(UserRole.ADMIN):
            _fan_out_to_admins(
                db, current_user, data.content,
                primary_admin_id=recipient.id,
                subject=conv.subject,
            )

    db.commit()
    db.refresh(message)

    logger.info(
        f"Message sent in conversation {conversation_id} by user {current_user.id}"
    )

    return _build_message_response(message)


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
        .update({"is_read": True, "read_at": datetime.now(timezone.utc)})
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
