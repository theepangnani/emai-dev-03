import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel as PydanticBaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.invite import Invite, InviteType
from app.models.message import Conversation, Message
from app.models.notification import Notification, NotificationType
from app.api.deps import get_current_user, require_role
from app.schemas.invite import InviteCreate, InviteResponse
from app.services.email_service import send_email_sync, add_inspiration_to_email
from app.core.config import settings

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")

router = APIRouter(prefix="/invites", tags=["Invites"])

EXPIRY_DAYS = {
    InviteType.STUDENT: 7,
    InviteType.TEACHER: 30,
    InviteType.PARENT: 30,
}


def _send_message_to_existing_user(
    db: Session,
    sender: User,
    recipient: User,
    message_content: str,
) -> dict:
    """Send a message + notification to an existing user instead of creating an invite.

    Creates or reuses a conversation, adds the message, creates an in-app
    notification, and sends an email notification.
    Returns a dict summarising the action.
    """
    # Find or create conversation
    conv = (
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
    if not conv:
        conv = Conversation(
            participant_1_id=sender.id,
            participant_2_id=recipient.id,
        )
        db.add(conv)
        db.flush()

    msg = Message(
        conversation_id=conv.id,
        sender_id=sender.id,
        content=message_content,
    )
    db.add(msg)

    # In-app notification
    preview = message_content[:100] + ("..." if len(message_content) > 100 else "")
    db.add(Notification(
        user_id=recipient.id,
        type=NotificationType.MESSAGE,
        title=f"New message from {sender.full_name}",
        content=preview,
        link="/messages",
    ))

    db.commit()

    # Email notification
    if recipient.email and recipient.email_notifications:
        try:
            tpl_path = os.path.join(_TEMPLATE_DIR, "message_notification.html")
            with open(tpl_path, "r") as f:
                html = f.read()
            html = (html
                .replace("{{recipient_name}}", recipient.full_name)
                .replace("{{sender_name}}", sender.full_name)
                .replace("{{message_preview}}", preview)
                .replace("{{app_url}}", settings.frontend_url))
            html = add_inspiration_to_email(html, db, recipient.role)
            send_email_sync(
                to_email=recipient.email,
                subject=f"New message from {sender.full_name} — ClassBridge",
                html_content=html,
            )
        except Exception as e:
            logger.warning(f"Failed to send message notification email to {recipient.email}: {e}")

    logger.info(f"Message sent to existing user {recipient.id} ({recipient.email}) by {sender.id}")
    return {
        "action": "message_sent",
        "recipient_name": recipient.full_name,
        "message": f"Message sent to {recipient.full_name} (already on ClassBridge)",
    }


@router.post("/")
def create_invite(
    data: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an invite. Parents can invite students; teachers and admins can invite teachers."""
    invite_type = InviteType(data.invite_type)

    # Authorization checks
    if invite_type == InviteType.STUDENT and not current_user.has_role(UserRole.PARENT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can invite students",
        )
    if invite_type == InviteType.TEACHER and not (current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can invite teachers",
        )
    if invite_type == InviteType.PARENT and not (current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can invite parents",
        )

    # If email is already registered, send a message instead of creating an invite
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        role_label = invite_type.value
        return _send_message_to_existing_user(
            db,
            sender=current_user,
            recipient=existing_user,
            message_content=(
                f"Hi {existing_user.full_name}! {current_user.full_name} "
                f"would like to connect with you on ClassBridge."
            ),
        )

    # Check for existing pending invite
    existing_invite = (
        db.query(Invite)
        .filter(
            Invite.email == data.email,
            Invite.invite_type == invite_type,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invite already exists for this email",
        )

    token = secrets.token_urlsafe(32)
    expiry_days = EXPIRY_DAYS[invite_type]

    invite = Invite(
        email=data.email,
        invite_type=invite_type,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expiry_days),
        invited_by_user_id=current_user.id,
        metadata_json=data.metadata,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # Send invite email
    frontend_url = settings.frontend_url
    invite_link = f"{frontend_url}/accept-invite?token={token}"
    role_label = "student" if invite_type == InviteType.STUDENT else "teacher"

    if invite_type == InviteType.STUDENT:
        html_content = f"""
    <h2>You've been invited to EMAI</h2>
    <p><strong>{current_user.full_name}</strong> has invited you to join EMAI as a student.</p>
    <p>Getting started is easy &mdash; just two steps:</p>
    <ol>
      <li><strong>Create your account</strong> by clicking the link below</li>
      <li><strong>Connect your Google Classroom</strong> from your dashboard so your parent can see your courses and teachers</li>
    </ol>
    <p><a href="{invite_link}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">Create My Account</a></p>
    <p style="color:#666;font-size:14px;">This invite expires in {expiry_days} days. Your parent is waiting to see your progress!</p>
    """
    else:
        html_content = f"""
    <h2>You've been invited to EMAI</h2>
    <p>{current_user.full_name} has invited you to join EMAI as a {role_label}.</p>
    <p>Click the link below to create your account:</p>
    <p><a href="{invite_link}">{invite_link}</a></p>
    <p>This invite expires in {expiry_days} days.</p>
    """

    # Send invite email (sync call — SendGrid SDK is synchronous)
    try:
        html_content = add_inspiration_to_email(html_content, db, invite_type.value)
        send_email_sync(
            to_email=data.email,
            subject=f"{current_user.full_name} invited you to EMAI",
            html_content=html_content,
        )
    except Exception as e:
        logger.warning(f"Failed to send invite email to {data.email}: {e}")

    logger.info(f"Invite created: {invite_type.value} invite to {data.email} by user {current_user.id}")
    return invite


@router.get("/sent", response_model=list[InviteResponse])
def list_sent_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all invites sent by the current user."""
    invites = (
        db.query(Invite)
        .filter(Invite.invited_by_user_id == current_user.id)
        .order_by(Invite.created_at.desc())
        .all()
    )
    return invites


@router.post("/{invite_id}/resend", response_model=InviteResponse)
def resend_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend a pending invite: refresh token + expiry, re-send email.

    Rate-limited to 1 resend per hour.
    """
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.invited_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your invite")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Invite already accepted")

    # Rate limit: max 1 resend per hour
    now = datetime.now(timezone.utc)
    if invite.last_resent_at:
        elapsed = now - invite.last_resent_at
        if elapsed < timedelta(hours=1):
            remaining_minutes = int((timedelta(hours=1) - elapsed).total_seconds() // 60) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining_minutes} minute(s) before resending this invite",
            )

    # Refresh token and expiry
    invite.token = secrets.token_urlsafe(32)
    expiry_days = EXPIRY_DAYS.get(invite.invite_type, 30)
    invite.expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
    invite.last_resent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invite)

    # Re-send email
    invite_link = f"{settings.frontend_url}/accept-invite?token={invite.token}"
    role_label = invite.invite_type.value if hasattr(invite.invite_type, 'value') else str(invite.invite_type)
    try:
        html = f"""
        <h2>Reminder: You've been invited to ClassBridge</h2>
        <p><strong>{current_user.full_name}</strong> invited you to join ClassBridge as a {role_label}.</p>
        <p>Click the link below to create your account:</p>
        <p><a href="{invite_link}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">Create My Account</a></p>
        <p style="color:#666;font-size:14px;">This invite expires in {expiry_days} days.</p>
        """
        html = add_inspiration_to_email(html, db, role_label)
        send_email_sync(
            to_email=invite.email,
            subject=f"Reminder: {current_user.full_name} invited you to ClassBridge",
            html_content=html,
        )
    except Exception as e:
        logger.warning(f"Failed to resend invite email to {invite.email}: {e}")

    logger.info(f"Invite {invite.id} resent to {invite.email} by user {current_user.id}")
    return invite


class _InviteTeacherRequest(PydanticBaseModel):
    teacher_email: EmailStr


@router.post("/invite-teacher")
def invite_teacher(
    data: _InviteTeacherRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Student invites a private teacher to ClassBridge.

    If the teacher already has an account, sends them a welcome message instead.
    Also notifies the student's parents.
    """
    from app.services.notification_service import notify_parents_of_student

    # Check if teacher email already registered
    existing_user = db.query(User).filter(User.email == data.teacher_email).first()
    if existing_user:
        result = _send_message_to_existing_user(
            db,
            sender=current_user,
            recipient=existing_user,
            message_content=(
                f"Hi {existing_user.full_name}! I'm {current_user.full_name}, "
                f"one of your students. I'd like to connect with you on ClassBridge "
                f"for study tools and communication with my parents."
            ),
        )
        # Notify parents
        notify_parents_of_student(
            db,
            student_user=current_user,
            title=f"{current_user.full_name} invited a teacher",
            content=f"{current_user.full_name} connected with {existing_user.full_name} on ClassBridge.",
            notification_type=NotificationType.SYSTEM,
            link="/messages",
        )
        db.commit()
        return result

    # Check for existing pending teacher invite
    existing_invite = (
        db.query(Invite)
        .filter(
            Invite.email == data.teacher_email,
            Invite.invite_type == InviteType.TEACHER,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invite already exists for this email",
        )

    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=data.teacher_email,
        invite_type=InviteType.TEACHER,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        invited_by_user_id=current_user.id,
        metadata_json={"source": "student_invite"},
    )
    db.add(invite)
    db.flush()

    # Send email
    invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
    try:
        html = f"""
        <h2>You've Been Invited to ClassBridge</h2>
        <p>Hi there,</p>
        <p><strong>{current_user.full_name}</strong>, one of your students, invited you to join ClassBridge.
        Connect with parents, share announcements, and track student progress.</p>
        <p><a href="{invite_link}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">Create Your Account</a></p>
        <p style="color:#666;font-size:14px;">This invite expires in 30 days.</p>
        """
        html = add_inspiration_to_email(html, db, "teacher")
        send_email_sync(
            to_email=data.teacher_email,
            subject=f"{current_user.full_name} invited you to ClassBridge",
            html_content=html,
        )
    except Exception as e:
        logger.warning(f"Failed to send teacher invite email to {data.teacher_email}: {e}")

    # Notify parents
    notify_parents_of_student(
        db,
        student_user=current_user,
        title=f"{current_user.full_name} invited a teacher",
        content=f"{current_user.full_name} invited {data.teacher_email} to join ClassBridge as a teacher.",
        notification_type=NotificationType.SYSTEM,
    )

    db.commit()
    db.refresh(invite)

    logger.info(f"Student {current_user.id} invited teacher {data.teacher_email}")
    return invite


class _InviteParentRequest(PydanticBaseModel):
    parent_email: EmailStr
    student_id: int | None = None


@router.post("/invite-parent")
def invite_parent(
    data: _InviteParentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Teacher invites a parent to ClassBridge.

    If the parent already has an account, sends them a welcome message instead
    (which also triggers an email notification).
    """
    # Resolve student name for context
    student_name = None
    if data.student_id:
        from app.models.student import Student
        student = db.query(Student).filter(Student.id == data.student_id).first()
        if student and student.user:
            student_name = student.user.full_name

    # Check if parent email already registered
    existing_user = db.query(User).filter(User.email == data.parent_email).first()
    if existing_user:
        student_context = f" regarding {student_name}'s education" if student_name else " regarding your child's education"
        return _send_message_to_existing_user(
            db,
            sender=current_user,
            recipient=existing_user,
            message_content=(
                f"Hi {existing_user.full_name}! I'm {current_user.full_name}, "
                f"a teacher on ClassBridge. I'd like to connect with you"
                f"{student_context}. Feel free to message me anytime!"
            ),
        )

    # Check for existing pending parent invite
    existing_invite = (
        db.query(Invite)
        .filter(
            Invite.email == data.parent_email,
            Invite.invite_type == InviteType.PARENT,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invite already exists for this email",
        )

    token = secrets.token_urlsafe(32)
    metadata = {}
    if data.student_id:
        metadata["student_id"] = data.student_id
        if student_name:
            metadata["student_name"] = student_name
    invite = Invite(
        email=data.parent_email,
        invite_type=InviteType.PARENT,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        invited_by_user_id=current_user.id,
        metadata_json=metadata or None,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # Send email
    invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
    try:
        tpl_path = os.path.join(_TEMPLATE_DIR, "parent_invite.html")
        with open(tpl_path, "r") as f:
            html = f.read()
        html = (html
            .replace("{{teacher_name}}", current_user.full_name)
            .replace("{{invite_link}}", invite_link))
        html = add_inspiration_to_email(html, db, "parent")
        send_email_sync(
            to_email=data.parent_email,
            subject=f"{current_user.full_name} invited you to ClassBridge",
            html_content=html,
        )
        logger.info(f"Parent invite email sent to {data.parent_email}")
    except Exception as e:
        logger.warning(f"Failed to send parent invite email: {e}")

    return invite
