import logging
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session, aliased, selectinload, joinedload
from sqlalchemy import or_, and_, desc, func as sa_func

from app.db.database import get_db
from app.models.user import User, UserRole
from app.core.rate_limit import limiter, get_user_id_or_ip
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
    MessageSearchResult,
    MessageSearchResponse,
    RecipientOption,
    UnreadCountResponse,
)
from app.core.utils import escape_like
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


@router.get("/search", response_model=MessageSearchResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def search_messages(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    conversation_id: int | None = Query(None, description="Filter by conversation"),
    date_from: datetime | None = Query(None, description="Filter messages from this date (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Filter messages up to this date (ISO 8601)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=50, description="Pagination limit"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search messages across conversations the current user participates in.

    Searches Message.content, Conversation.subject, and participant names using
    case-insensitive LIKE matching. Supports filtering by conversation_id and
    date range. Returns paginated results ordered by most recent first.
    """
    escaped_q = escape_like(q)
    like_pattern = f"%{escaped_q}%"

    # Get conversations the current user participates in
    user_conv_filter = or_(
        Conversation.participant_1_id == current_user.id,
        Conversation.participant_2_id == current_user.id,
    )
    user_conversations = (
        db.query(Conversation.id)
        .filter(user_conv_filter)
    )
    # If conversation_id is specified, also verify user has access
    if conversation_id is not None:
        user_conversations = user_conversations.filter(Conversation.id == conversation_id)
    user_conversations = user_conversations.subquery()

    # Build base date filters for messages
    date_filters = []
    if date_from is not None:
        date_filters.append(Message.created_at >= date_from)
    if date_to is not None:
        date_filters.append(Message.created_at <= date_to)

    # Search messages by content match
    content_query = (
        db.query(Message, Conversation.subject, User.full_name)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Message.sender_id == User.id)
        .filter(
            Message.conversation_id.in_(db.query(user_conversations.c.id)),
            sa_func.lower(Message.content).like(sa_func.lower(like_pattern)),
            *date_filters,
        )
        .order_by(desc(Message.created_at))
    )
    content_results = content_query.all()

    # Search conversations by subject match (return the latest message from each)
    subject_match_convs = (
        db.query(Conversation.id)
        .filter(
            Conversation.id.in_(db.query(user_conversations.c.id)),
            Conversation.subject.isnot(None),
            sa_func.lower(Conversation.subject).like(sa_func.lower(like_pattern)),
        )
        .all()
    )
    subject_conv_ids = {row[0] for row in subject_match_convs}

    # Search conversations by participant name (To/From)
    P1 = aliased(User)
    P2 = aliased(User)
    participant_match_convs = (
        db.query(Conversation.id)
        .join(P1, Conversation.participant_1_id == P1.id)
        .join(P2, Conversation.participant_2_id == P2.id)
        .filter(
            Conversation.id.in_(db.query(user_conversations.c.id)),
            or_(
                sa_func.lower(P1.full_name).like(sa_func.lower(like_pattern)),
                sa_func.lower(P2.full_name).like(sa_func.lower(like_pattern)),
            ),
        )
        .all()
    )
    subject_conv_ids |= {row[0] for row in participant_match_convs}

    # For subject/participant matches, get the latest message from each matching
    # conversation that wasn't already found by content search
    content_msg_ids = {msg.id for msg, _, _ in content_results}
    subject_results = []
    if subject_conv_ids:
        for conv_id in subject_conv_ids:
            latest_query = (
                db.query(Message, Conversation.subject, User.full_name)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .join(User, Message.sender_id == User.id)
                .filter(Message.conversation_id == conv_id, *date_filters)
                .order_by(desc(Message.created_at))
            )
            latest_msg = latest_query.first()
            if latest_msg and latest_msg[0].id not in content_msg_ids:
                subject_results.append(latest_msg)

    # Combine and deduplicate results, sort by most recent
    all_results = content_results + subject_results
    seen_ids: set[int] = set()
    unique_results = []
    for msg, conv_subject, sender_name in all_results:
        if msg.id not in seen_ids:
            seen_ids.add(msg.id)
            unique_results.append((msg, conv_subject, sender_name))

    # Sort by sent_at descending
    unique_results.sort(key=lambda r: r[0].created_at, reverse=True)
    total = len(unique_results)

    # Apply pagination
    paginated = unique_results[offset: offset + limit]

    return MessageSearchResponse(
        results=[
            MessageSearchResult(
                conversation_id=msg.conversation_id,
                conversation_subject=conv_subject,
                message_id=msg.id,
                message_content=msg.content,
                sender_name=sender_name,
                sent_at=msg.created_at,
            )
            for msg, conv_subject, sender_name in paginated
        ],
        total=total,
        offset=offset,
        limit=limit,
        query=q,
    )


@router.get("/recipients", response_model=list[RecipientOption])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_valid_recipients(
    request: Request,
    q: str | None = Query(None, min_length=2, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of users this person can message.

    When `q` is provided, searches ALL active users by name (any role).
    When `q` is absent, returns linked users + admins (existing behavior).
    """
    logger.info(f"Getting recipients for user {current_user.id} ({current_user.role})")

    # ── Global user search mode ─────────────────────────────────
    if q:
        escaped_q = escape_like(q)
        like_pattern = f"%{escaped_q}%"
        users = (
            db.query(User)
            .filter(
                User.is_active == True,  # noqa: E712
                User.id != current_user.id,
                sa_func.lower(User.full_name).like(sa_func.lower(like_pattern)),
            )
            .limit(20)
            .all()
        )
        return [
            RecipientOption(
                user_id=u.id,
                full_name=u.full_name,
                role=u.role.value if u.role else "unknown",
                student_names=[],
            )
            for u in users
        ]

    # ── Default: linked users + admins ──────────────────────────
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

        # Include the parent's own children as recipients
        for child in children:
            if child.user and child.user_id not in seen_user_ids:
                seen_user_ids.add(child.user_id)
                result.append(
                    RecipientOption(
                        user_id=child.user_id,
                        full_name=child.user.full_name,
                        role=child.user.role.value if child.user.role else "student",
                        student_names=[],
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
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def create_conversation(
    request: Request,
    data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new conversation with a valid recipient."""
    logger.info(
        f"User {current_user.id} creating conversation with recipient {data.recipient_id}"
    )

    # Validate recipient exists and is active
    recipient = db.query(User).filter(
        User.id == data.recipient_id,
        User.is_active == True,  # noqa: E712
    ).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    # Prevent messaging yourself
    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot message yourself",
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
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_conversations(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, min_length=2, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all conversations for the current user with unread counts.

    When `q` is provided, filters to conversations matching by message content,
    subject, or other participant name.
    """
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

    # ── Optional search filter ──────────────────────────────────
    if q:
        escaped_q = escape_like(q)
        like_pattern = f"%{escaped_q}%"

        msg_match_ids = set(
            row[0] for row in db.query(Message.conversation_id)
            .filter(
                Message.conversation_id.in_(conv_ids),
                sa_func.lower(Message.content).like(sa_func.lower(like_pattern)),
            )
            .distinct()
            .all()
        )

        subject_match_ids = {
            c.id for c in conversations
            if c.subject and q.lower() in c.subject.lower()
        }

        participant_match_ids = set()
        for conv in conversations:
            other = conv.participant_1 if conv.participant_2_id == current_user.id else conv.participant_2
            if other and q.lower() in other.full_name.lower():
                participant_match_ids.add(conv.id)

        matching_ids = msg_match_ids | subject_match_ids | participant_match_ids
        conversations = [c for c in conversations if c.id in matching_ids]
        conv_ids = [c.id for c in conversations]

        if not conversations:
            return []

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
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_conversation(
    request: Request,
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
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def send_message(
    request: Request,
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def mark_conversation_read(
    request: Request,
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
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_unread_count(
    request: Request,
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
