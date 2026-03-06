"""Account deletion endpoints.

DELETE /users/me/account          — request deletion (sends confirmation email)
POST   /users/me/confirm-deletion — confirm with token (starts 30-day grace)
POST   /users/me/cancel-deletion  — cancel pending deletion
GET    /admin/deletion-requests   — list pending deletions (admin)
POST   /admin/deletion-requests/{user_id}/process — immediate anonymize (admin)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.security import (
    create_deletion_confirmation_token,
    decode_deletion_confirmation_token,
)
from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role
from app.services.account_deletion_service import (
    request_deletion,
    confirm_deletion,
    cancel_deletion,
    anonymize_user,
)
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, wrap_branded_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Account Deletion"])
admin_router = APIRouter(prefix="/admin", tags=["Admin - Deletion Requests"])


# ── Schemas ──────────────────────────────────────────────────

class ConfirmDeletionRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2000)


class DeletionStatusResponse(BaseModel):
    deletion_requested: bool
    deletion_confirmed: bool
    deletion_requested_at: str | None = None
    deletion_confirmed_at: str | None = None
    is_deleted: bool = False
    message: str


class DeletionRequestItem(BaseModel):
    user_id: int
    email: str | None
    full_name: str
    role: str | None
    deletion_requested_at: str | None
    deletion_confirmed_at: str | None
    is_deleted: bool


class DeletionRequestList(BaseModel):
    items: list[DeletionRequestItem]
    total: int


# ── User endpoints ───────────────────────────────────────────

@router.delete("/me/account", response_model=DeletionStatusResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def request_account_deletion(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request account deletion. Sends a confirmation email with a token."""
    if current_user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already deleted",
        )

    if current_user.deletion_confirmed_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion is already confirmed and pending. Use cancel-deletion to undo.",
        )

    # Mark as requested
    request_deletion(db, current_user)

    # Generate confirmation token
    token = create_deletion_confirmation_token(current_user.id)
    confirm_url = f"{settings.frontend_url}/confirm-deletion?token={token}"

    # Send confirmation email
    html = wrap_branded_email(f"""
        <h2 style="color:#1f2937;margin:0 0 16px 0;">Account Deletion Request</h2>
        <p style="color:#4b5563;">Hi {current_user.full_name},</p>
        <p style="color:#4b5563;">
          We received a request to delete your ClassBridge account. This action is
          <strong>irreversible</strong> after the 30-day grace period.
        </p>
        <p style="color:#4b5563;">
          If you did not make this request, you can safely ignore this email.
        </p>
        <div style="text-align:center;margin:24px 0;">
          <a href="{confirm_url}"
             style="background:#dc2626;color:white;padding:12px 32px;border-radius:8px;
                    text-decoration:none;font-weight:600;display:inline-block;">
            Confirm Account Deletion
          </a>
        </div>
        <p style="color:#9ca3af;font-size:13px;">
          This link expires in 24 hours. After confirming, your account will be
          deactivated immediately and permanently anonymized after 30 days.
        </p>
    """)

    if current_user.email:
        send_email_sync(current_user.email, "ClassBridge: Account Deletion Request", html)

    log_action(
        db,
        user_id=current_user.id,
        action="account_deletion_requested",
        resource_type="user",
        resource_id=current_user.id,
        details={"email": current_user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return DeletionStatusResponse(
        deletion_requested=True,
        deletion_confirmed=False,
        deletion_requested_at=current_user.deletion_requested_at.isoformat() if current_user.deletion_requested_at else None,
        message="Deletion requested. Check your email for a confirmation link.",
    )


@router.post("/me/confirm-deletion", response_model=DeletionStatusResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def confirm_account_deletion(
    request: Request,
    body: ConfirmDeletionRequest,
    db: Session = Depends(get_db),
):
    """Confirm account deletion using the emailed token.

    This endpoint does NOT require auth (user may have logged out).
    The token itself authenticates the request.
    """
    user_id = decode_deletion_confirmation_token(body.token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired deletion token",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already deleted",
        )

    if not user.deletion_requested_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No deletion request found. Please request deletion first.",
        )

    if user.deletion_confirmed_at:
        return DeletionStatusResponse(
            deletion_requested=True,
            deletion_confirmed=True,
            deletion_requested_at=user.deletion_requested_at.isoformat() if user.deletion_requested_at else None,
            deletion_confirmed_at=user.deletion_confirmed_at.isoformat() if user.deletion_confirmed_at else None,
            message="Deletion was already confirmed.",
        )

    confirm_deletion(db, user)

    log_action(
        db,
        user_id=user.id,
        action="account_deletion_confirmed",
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return DeletionStatusResponse(
        deletion_requested=True,
        deletion_confirmed=True,
        deletion_requested_at=user.deletion_requested_at.isoformat() if user.deletion_requested_at else None,
        deletion_confirmed_at=user.deletion_confirmed_at.isoformat() if user.deletion_confirmed_at else None,
        message="Account deletion confirmed. Your account will be permanently anonymized after 30 days.",
    )


@router.post("/me/cancel-deletion", response_model=DeletionStatusResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def cancel_account_deletion(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending account deletion and reactivate the account."""
    if current_user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already permanently deleted and cannot be recovered",
        )

    if not current_user.deletion_requested_at and not current_user.deletion_confirmed_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending deletion request to cancel",
        )

    cancel_deletion(db, current_user)

    log_action(
        db,
        user_id=current_user.id,
        action="account_deletion_cancelled",
        resource_type="user",
        resource_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return DeletionStatusResponse(
        deletion_requested=False,
        deletion_confirmed=False,
        message="Deletion request cancelled. Your account has been reactivated.",
    )


@router.get("/me/deletion-status", response_model=DeletionStatusResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_deletion_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get current account deletion status."""
    return DeletionStatusResponse(
        deletion_requested=current_user.deletion_requested_at is not None,
        deletion_confirmed=current_user.deletion_confirmed_at is not None,
        deletion_requested_at=current_user.deletion_requested_at.isoformat() if current_user.deletion_requested_at else None,
        deletion_confirmed_at=current_user.deletion_confirmed_at.isoformat() if current_user.deletion_confirmed_at else None,
        is_deleted=current_user.is_deleted,
        message="No deletion request" if not current_user.deletion_requested_at else (
            "Deletion confirmed, awaiting anonymization" if current_user.deletion_confirmed_at else "Deletion requested, awaiting confirmation"
        ),
    )


# ── Admin endpoints ──────────────────────────────────────────

@admin_router.get("/deletion-requests", response_model=DeletionRequestList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_deletion_requests(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List pending and processed deletion requests. Admin only."""
    query = db.query(User).filter(User.deletion_requested_at.isnot(None))

    if status_filter == "pending":
        query = query.filter(User.is_deleted == False)  # noqa: E712
    elif status_filter == "processed":
        query = query.filter(User.is_deleted == True)  # noqa: E712

    total = query.count()
    users = query.order_by(User.deletion_requested_at.desc()).offset(skip).limit(limit).all()

    items = [
        DeletionRequestItem(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.value if u.role else None,
            deletion_requested_at=u.deletion_requested_at.isoformat() if u.deletion_requested_at else None,
            deletion_confirmed_at=u.deletion_confirmed_at.isoformat() if u.deletion_confirmed_at else None,
            is_deleted=u.is_deleted or False,
        )
        for u in users
    ]

    return DeletionRequestList(items=items, total=total)


@admin_router.post("/deletion-requests/{user_id}/process")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def process_deletion_request(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Immediately anonymize a user's account. Admin only.

    Bypasses the 30-day grace period.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already anonymized",
        )

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account via admin panel",
        )

    anonymize_user(db, user)

    log_action(
        db,
        user_id=current_user.id,
        action="account_deletion_admin_processed",
        resource_type="user",
        resource_id=user.id,
        details={"target_user_id": user.id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    logger.info("Admin %s processed deletion for user %s", current_user.id, user.id)
    return {"message": f"User {user_id} has been anonymized."}
