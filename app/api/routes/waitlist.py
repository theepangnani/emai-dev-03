"""Public waitlist API endpoints (no auth required)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.waitlist import Waitlist
from app.models.user import User, UserRole
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse
from app.services.email_service import send_email_sync, wrap_branded_email
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.post("", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def join_waitlist(
    data: WaitlistCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Join the ClassBridge waitlist. Public endpoint, no auth required."""
    # Normalize email to lowercase
    email = data.email.lower()

    # Check if email is already registered as a user
    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered. Please log in instead.",
        )

    # Check for existing waitlist entry (case-insensitive)
    existing = db.query(Waitlist).filter(func.lower(Waitlist.email) == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already on the waitlist. We'll be in touch soon!",
        )

    # Create waitlist record
    entry = Waitlist(
        name=data.name,
        email=email,
        roles=data.roles,
        status="pending",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Send confirmation email to user (best-effort)
    _send_confirmation_email(entry)

    # Send admin notification (best-effort)
    _send_admin_notification(db, entry)

    return entry


@router.get("/verify/{token}", response_model=WaitlistResponse)
def verify_invite_token(
    token: str,
    db: Session = Depends(get_db),
):
    """Verify a waitlist invite token. Returns waitlist info for pre-filling registration.

    Public endpoint, no auth required.
    """
    entry = db.query(Waitlist).filter(Waitlist.invite_token == token).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite token. Please check your link or request a new one.",
        )

    # Must be approved to use the token
    if entry.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite is not currently active. It may have been revoked.",
        )

    # Check expiration
    if entry.invite_token_expires_at:
        now = datetime.now(timezone.utc)
        expires = entry.invite_token_expires_at
        # Handle both naive and aware datetimes (SQLite vs PostgreSQL)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite link has expired. Please contact us for a new one.",
            )

    return entry


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _send_confirmation_email(entry: Waitlist) -> None:
    """Send a confirmation email to the user who joined the waitlist."""
    try:
        roles_display = ", ".join(r.capitalize() for r in entry.roles)
        body = (
            f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">You\'re on the list!</h2>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">Hi {entry.name},</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">'
            f'Thanks for signing up for ClassBridge! We\'ve added you to our waitlist '
            f'as a <strong>{roles_display}</strong>.</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">'
            f'We\'re currently rolling out access in waves. You\'ll receive an email '
            f'with your invite link as soon as a spot opens up.</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 0 0;">Stay tuned!</p>'
        )
        html = wrap_branded_email(body)
        send_email_sync(
            to_email=entry.email,
            subject="ClassBridge — You're on the waitlist!",
            html_content=html,
        )
    except Exception as e:
        logger.warning("Failed to send waitlist confirmation email to %s: %s", entry.email, e)


def _send_admin_notification(db: Session, entry: Waitlist) -> None:
    """Notify all admin users about a new waitlist signup."""
    try:
        admins = db.query(User).filter(User.roles.contains("admin")).all()
        if not admins:
            logger.info("No admin users found to notify about waitlist signup")
            return

        roles_display = ", ".join(r.capitalize() for r in entry.roles)
        body = (
            f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">New Waitlist Signup</h2>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 8px 0;"><strong>Name:</strong> {entry.name}</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 8px 0;"><strong>Email:</strong> {entry.email}</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 8px 0;"><strong>Roles:</strong> {roles_display}</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;"><strong>Signed up:</strong> {entry.created_at}</p>'
            f'<p style="color:#999;font-size:13px;">Review and approve in the admin dashboard.</p>'
        )
        html = wrap_branded_email(body)

        for admin in admins:
            if admin.email:
                try:
                    send_email_sync(
                        to_email=admin.email,
                        subject=f"New waitlist signup: {entry.name}",
                        html_content=html,
                    )
                except Exception as e:
                    logger.warning("Failed to send admin notification to %s: %s", admin.email, e)
    except Exception as e:
        logger.warning("Failed to send admin waitlist notifications: %s", e)
