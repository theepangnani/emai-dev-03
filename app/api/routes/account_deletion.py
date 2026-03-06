"""Account deletion and data anonymization routes (#964).

Endpoints:
  DELETE /api/users/me           — Request account deletion (30-day grace period)
  POST   /api/users/me/cancel-deletion — Cancel pending deletion
  GET    /api/admin/deletion-requests   — List pending deletions (admin)
  POST   /api/admin/deletion-requests/{user_id}/process — Force-process deletion (admin)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role
from app.services.audit_service import log_action
from app.services.deletion_service import (
    request_deletion,
    cancel_deletion,
    is_deletion_pending,
    get_grace_period_end,
    get_pending_deletions,
    admin_process_deletion,
    GRACE_PERIOD_DAYS,
)

logger = logging.getLogger(__name__)

# User-facing routes (mounted under /api/users)
router = APIRouter(prefix="/users", tags=["Account Deletion"])

# Admin routes (mounted under /api/admin)
admin_router = APIRouter(prefix="/admin", tags=["Admin - Account Deletion"])


# ── Response schemas ──────────────────────────────────────────

class DeletionStatusResponse(BaseModel):
    message: str
    deletion_requested_at: datetime | None = None
    grace_period_ends_at: datetime | None = None
    grace_period_days: int = GRACE_PERIOD_DAYS


class DeletionRequestItem(BaseModel):
    user_id: int
    email: str | None
    full_name: str
    role: str | None
    deletion_requested_at: datetime | None
    grace_period_ends_at: datetime | None

    class Config:
        from_attributes = True


class DeletionRequestList(BaseModel):
    items: list[DeletionRequestItem]
    total: int


class AdminProcessResponse(BaseModel):
    message: str
    user_id: int


# ── User endpoints ────────────────────────────────────────────

@router.delete("/me", response_model=DeletionStatusResponse)
@limiter.limit("3/minute", key_func=get_user_id_or_ip)
def delete_my_account(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request account deletion. Starts a 30-day grace period.

    After the grace period, all PII is anonymized and the account is deactivated.
    A confirmation email is sent to the user.
    """
    if current_user.is_deleted:
        raise HTTPException(status_code=400, detail="Account is already deleted")

    if is_deletion_pending(current_user):
        grace_end = get_grace_period_end(current_user)
        return DeletionStatusResponse(
            message="Account deletion is already pending",
            deletion_requested_at=current_user.deletion_requested_at,
            grace_period_ends_at=grace_end,
        )

    # Mark for deletion
    request_deletion(db, current_user)

    # Send confirmation email (best-effort)
    _send_deletion_confirmation_email(current_user, db)

    log_action(
        db, user_id=current_user.id, action="deletion_requested",
        resource_type="user", resource_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    grace_end = get_grace_period_end(current_user)
    return DeletionStatusResponse(
        message=f"Account marked for deletion. You have {GRACE_PERIOD_DAYS} days to cancel.",
        deletion_requested_at=current_user.deletion_requested_at,
        grace_period_ends_at=grace_end,
    )


@router.get("/me/deletion-status", response_model=DeletionStatusResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_deletion_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Check current account deletion status."""
    if current_user.is_deleted:
        return DeletionStatusResponse(message="Account has been deleted and anonymized")

    if is_deletion_pending(current_user):
        grace_end = get_grace_period_end(current_user)
        return DeletionStatusResponse(
            message="Account deletion is pending",
            deletion_requested_at=current_user.deletion_requested_at,
            grace_period_ends_at=grace_end,
        )

    return DeletionStatusResponse(message="No deletion request pending")


@router.post("/me/cancel-deletion", response_model=DeletionStatusResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def cancel_my_deletion(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending account deletion during the grace period."""
    if current_user.is_deleted:
        raise HTTPException(status_code=400, detail="Account is already deleted and cannot be restored")

    if not is_deletion_pending(current_user):
        raise HTTPException(status_code=400, detail="No pending deletion request to cancel")

    cancel_deletion(db, current_user)

    log_action(
        db, user_id=current_user.id, action="deletion_cancelled",
        resource_type="user", resource_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return DeletionStatusResponse(message="Account deletion has been cancelled")


# ── Admin endpoints ───────────────────────────────────────────

@admin_router.get("/deletion-requests", response_model=DeletionRequestList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_deletion_requests(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all pending account deletion requests."""
    users, total = get_pending_deletions(db, skip=skip, limit=limit)

    items = []
    for u in users:
        items.append(DeletionRequestItem(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.value if u.role else None,
            deletion_requested_at=u.deletion_requested_at,
            grace_period_ends_at=get_grace_period_end(u),
        ))

    return DeletionRequestList(items=items, total=total)


@admin_router.post("/deletion-requests/{user_id}/process", response_model=AdminProcessResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def admin_force_process_deletion(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Force-process a deletion request immediately, bypassing the grace period."""
    try:
        user = admin_process_deletion(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(
        db, user_id=current_user.id, action="admin_force_deletion",
        resource_type="user", resource_id=user_id,
        details={"processed_by": current_user.id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return AdminProcessResponse(message="Account deleted and anonymized", user_id=user_id)


# ── Email helper ──────────────────────────────────────────────

def _send_deletion_confirmation_email(user: User, db: Session) -> None:
    """Send a deletion confirmation email (best-effort, never raises)."""
    if not user.email:
        return
    try:
        from app.services.email_service import send_email_sync, wrap_branded_email
        from app.core.config import settings

        cancel_url = f"{settings.frontend_url}/settings/account"
        body = (
            f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">Account Deletion Requested</h2>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">Hi {user.full_name or "there"},</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">We received a request to delete your ClassBridge account. '
            f'Your account will be permanently deleted and all personal data anonymized after <strong>{GRACE_PERIOD_DAYS} days</strong>.</p>'
            f'<p style="color:#333;line-height:1.6;margin:0 0 24px 0;">If you did not request this, or if you change your mind, you can cancel the deletion:</p>'
            f'<a href="{cancel_url}" style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;padding:14px 28px;border-radius:8px;font-weight:600;font-size:16px;">Cancel Deletion</a>'
            f'<p style="color:#999;font-size:13px;margin:24px 0 0 0;">If you take no action, your account will be permanently deleted after the grace period.</p>'
        )
        html = wrap_branded_email(body)
        send_email_sync(
            to_email=user.email,
            subject="ClassBridge - Account Deletion Requested",
            html_content=html,
        )
    except Exception as e:
        logger.warning("Failed to send deletion confirmation email to %s: %s", user.email, e)
