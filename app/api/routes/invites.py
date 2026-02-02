import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.invite import Invite, InviteType
from app.api.deps import get_current_user
from app.schemas.invite import InviteCreate, InviteResponse
from app.services.email_service import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invites", tags=["Invites"])

EXPIRY_DAYS = {
    InviteType.STUDENT: 7,
    InviteType.TEACHER: 30,
}


@router.post("/", response_model=InviteResponse)
def create_invite(
    data: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an invite. Parents can invite students; teachers and admins can invite teachers."""
    invite_type = InviteType(data.invite_type)

    # Authorization checks
    if invite_type == InviteType.STUDENT and current_user.role != UserRole.PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can invite students",
        )
    if invite_type == InviteType.TEACHER and current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can invite teachers",
        )

    # Check if email already registered
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # Check for existing pending invite
    existing_invite = (
        db.query(Invite)
        .filter(
            Invite.email == data.email,
            Invite.invite_type == invite_type,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.utcnow(),
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
        expires_at=datetime.utcnow() + timedelta(days=expiry_days),
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

    # Fire-and-forget email (don't block on failure)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(
                send_email(
                    to_email=data.email,
                    subject=f"{current_user.full_name} invited you to EMAI",
                    html_content=html_content,
                )
            )
        else:
            loop.run_until_complete(
                send_email(
                    to_email=data.email,
                    subject=f"{current_user.full_name} invited you to EMAI",
                    html_content=html_content,
                )
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
