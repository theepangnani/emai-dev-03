import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.models.course import Course, student_courses
from app.models.message import Conversation, Message
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

logger = logging.getLogger(__name__)

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
    db: Session, conv: Conversation, current_user: User
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

    messages = [_build_message_response(msg, db) for msg in conv.messages]

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

            result.append(
                RecipientOption(
                    user_id=user.id,
                    full_name=user.full_name,
                    role=user.role.value,
                    student_names=taught_children,
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
    if current_user.role not in [UserRole.PARENT, UserRole.TEACHER]:
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
    db.commit()
    db.refresh(conversation)

    logger.info(f"Created new conversation {conversation.id}")
    return _build_conversation_detail(db, conversation, current_user)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
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
    return result


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
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

    return _build_conversation_detail(db, conv, current_user)


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
