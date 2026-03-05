import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.utils import escape_like
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.api.deps import require_role
from app.schemas.waitlist import (
    WaitlistAdminUpdate,
    WaitlistListResponse,
    WaitlistResponse,
    WaitlistStats,
)
from app.services.email_service import send_email_sync, wrap_branded_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/waitlist", tags=["Admin Waitlist"])

INVITE_EXPIRY_DAYS = 7


def _build_approval_email(name: str, invite_token: str) -> str:
    """Build HTML email for waitlist approval with registration link."""
    reg_url = f"{settings.frontend_url}/register?token={invite_token}"
    body = f"""
    <h2 style="color:#1e293b;margin:0 0 16px 0;">Welcome to ClassBridge!</h2>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        Hi {name},
    </p>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        Great news! Your request to join ClassBridge has been <strong>approved</strong>.
        Click the button below to create your account:
    </p>
    <div style="text-align:center;margin:32px 0;">
        <a href="{reg_url}"
           style="display:inline-block;padding:14px 32px;background:#4f46e5;color:#ffffff;
                  text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;">
            Create Your Account
        </a>
    </div>
    <p style="color:#64748b;font-size:13px;">
        This link expires in {INVITE_EXPIRY_DAYS} days. If you can't click the button,
        copy and paste this URL into your browser:<br>
        <a href="{reg_url}" style="color:#4f46e5;">{reg_url}</a>
    </p>
    """
    return wrap_branded_email(body)


def _build_decline_email(name: str) -> str:
    """Build HTML email for waitlist decline."""
    body = f"""
    <h2 style="color:#1e293b;margin:0 0 16px 0;">ClassBridge Waitlist Update</h2>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        Hi {name},
    </p>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        Thank you for your interest in ClassBridge. Unfortunately, we are unable to
        approve your request at this time.
    </p>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        If you believe this was a mistake, please contact us and we'll be happy to
        review your application again.
    </p>
    """
    return wrap_branded_email(body)


def _build_reminder_email(name: str, invite_token: str) -> str:
    """Build HTML email for waitlist reminder with registration link."""
    reg_url = f"{settings.frontend_url}/register?token={invite_token}"
    body = f"""
    <h2 style="color:#1e293b;margin:0 0 16px 0;">Reminder: Complete Your ClassBridge Registration</h2>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        Hi {name},
    </p>
    <p style="color:#334155;font-size:15px;line-height:1.6;">
        You were approved to join ClassBridge but haven't created your account yet.
        Click below to get started:
    </p>
    <div style="text-align:center;margin:32px 0;">
        <a href="{reg_url}"
           style="display:inline-block;padding:14px 32px;background:#4f46e5;color:#ffffff;
                  text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;">
            Create Your Account
        </a>
    </div>
    <p style="color:#64748b;font-size:13px;">
        This link expires in {INVITE_EXPIRY_DAYS} days. If you can't click the button,
        copy and paste this URL into your browser:<br>
        <a href="{reg_url}" style="color:#4f46e5;">{reg_url}</a>
    </p>
    """
    return wrap_branded_email(body)


# ── GET /api/admin/waitlist ──────────────────────────────────────────


@router.get("", response_model=WaitlistListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_waitlist(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List waitlist entries with optional status filter and search."""
    query = db.query(WaitlistEntry)

    if status_filter:
        query = query.filter(WaitlistEntry.status == status_filter)

    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                WaitlistEntry.name.ilike(search_term),
                WaitlistEntry.email.ilike(search_term),
            )
        )

    total = query.count()
    items = (
        query.order_by(WaitlistEntry.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return WaitlistListResponse(items=items, total=total)


# ── GET /api/admin/waitlist/stats ────────────────────────────────────


@router.get("/stats", response_model=WaitlistStats)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def waitlist_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get waitlist statistics by status."""
    total = db.query(WaitlistEntry).count()
    pending = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.status == WaitlistStatus.PENDING.value)
        .count()
    )
    approved = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.status == WaitlistStatus.APPROVED.value)
        .count()
    )
    registered = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.status == WaitlistStatus.REGISTERED.value)
        .count()
    )
    declined = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.status == WaitlistStatus.DECLINED.value)
        .count()
    )

    return WaitlistStats(
        total=total,
        pending=pending,
        approved=approved,
        registered=registered,
        declined=declined,
    )


# ── PATCH /api/admin/waitlist/{id}/approve ───────────────────────────


@router.patch("/{entry_id}/approve", response_model=WaitlistResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def approve_waitlist_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Approve a waitlist entry and send approval email with registration link."""
    entry = db.query(WaitlistEntry).filter(WaitlistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    if entry.status == WaitlistStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entry is already approved",
        )

    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    entry.status = WaitlistStatus.APPROVED.value
    entry.invite_token = invite_token
    entry.invite_token_expires_at = now + timedelta(days=INVITE_EXPIRY_DAYS)
    entry.approved_by_user_id = current_user.id
    entry.approved_at = now

    db.commit()
    db.refresh(entry)

    # Send approval email
    try:
        html = _build_approval_email(entry.name, invite_token)
        send_email_sync(entry.email, "ClassBridge: You're Approved!", html)
    except Exception:
        logger.warning("Failed to send approval email to %s", entry.email)

    logger.info(
        "Admin %s approved waitlist entry %s (%s)",
        current_user.id,
        entry.id,
        entry.email,
    )
    return entry


# ── PATCH /api/admin/waitlist/{id}/decline ───────────────────────────


@router.patch("/{entry_id}/decline", response_model=WaitlistResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def decline_waitlist_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Decline a waitlist entry and send decline email."""
    entry = db.query(WaitlistEntry).filter(WaitlistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    if entry.status == WaitlistStatus.DECLINED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entry is already declined",
        )

    entry.status = WaitlistStatus.DECLINED.value

    db.commit()
    db.refresh(entry)

    # Send decline email
    try:
        html = _build_decline_email(entry.name)
        send_email_sync(entry.email, "ClassBridge: Waitlist Update", html)
    except Exception:
        logger.warning("Failed to send decline email to %s", entry.email)

    logger.info(
        "Admin %s declined waitlist entry %s (%s)",
        current_user.id,
        entry.id,
        entry.email,
    )
    return entry


# ── POST /api/admin/waitlist/{id}/remind ─────────────────────────────


@router.post("/{entry_id}/remind", response_model=WaitlistResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def send_waitlist_reminder(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Send a reminder email to an approved but unregistered waitlist entry."""
    entry = db.query(WaitlistEntry).filter(WaitlistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    if entry.status != WaitlistStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only send reminders for approved entries",
        )

    if entry.registered_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has already registered",
        )

    now = datetime.now(timezone.utc)

    # If token is expired, generate a new one
    expires = entry.invite_token_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if (
        not entry.invite_token
        or not expires
        or expires < now
    ):
        entry.invite_token = secrets.token_urlsafe(32)
        entry.invite_token_expires_at = now + timedelta(days=INVITE_EXPIRY_DAYS)

    entry.reminder_sent_at = now

    db.commit()
    db.refresh(entry)

    # Send reminder email
    try:
        html = _build_reminder_email(entry.name, entry.invite_token)
        send_email_sync(
            entry.email, "ClassBridge: Complete Your Registration", html
        )
    except Exception:
        logger.warning("Failed to send reminder email to %s", entry.email)

    logger.info(
        "Admin %s sent reminder to waitlist entry %s (%s)",
        current_user.id,
        entry.id,
        entry.email,
    )
    return entry


# ── PATCH /api/admin/waitlist/{id}/notes ─────────────────────────────


@router.patch("/{entry_id}/notes", response_model=WaitlistResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_waitlist_notes(
    entry_id: int,
    data: WaitlistAdminUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update admin notes on a waitlist entry."""
    entry = db.query(WaitlistEntry).filter(WaitlistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    entry.admin_notes = data.admin_notes

    db.commit()
    db.refresh(entry)

    logger.info(
        "Admin %s updated notes on waitlist entry %s", current_user.id, entry.id
    )
    return entry


# ── DELETE /api/admin/waitlist/{id} ──────────────────────────────────


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_waitlist_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Hard delete a waitlist entry."""
    entry = db.query(WaitlistEntry).filter(WaitlistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    logger.info(
        "Admin %s deleted waitlist entry %s (%s)",
        current_user.id,
        entry.id,
        entry.email,
    )

    db.delete(entry)
    db.commit()
