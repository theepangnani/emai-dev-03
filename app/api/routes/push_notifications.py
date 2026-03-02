"""Push notification API — device token registration and admin send endpoints."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.push_token import PushToken, DevicePlatform
from app.models.user import User, UserRole
from app.services.push_notifications import push_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/push", tags=["push-notifications"])
admin_router = APIRouter(prefix="/admin/push", tags=["admin-push-notifications"])

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RegisterTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=512, description="FCM registration token")
    platform: DevicePlatform = DevicePlatform.WEB
    device_name: str | None = Field(None, max_length=255, description="e.g. 'iPhone 15', 'Chrome on Windows'")
    app_version: str | None = Field(None, max_length=50)


class UnregisterTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=512)


class PushTokenResponse(BaseModel):
    id: int
    user_id: int
    token: str
    platform: DevicePlatform
    device_name: str | None
    app_version: str | None
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class AdminSendRequest(BaseModel):
    user_ids: list[int] = Field(..., min_length=1, description="Target user IDs")
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=1000)
    data: dict | None = None


class AdminSendResponse(BaseModel):
    sent: int
    failed: int
    users_reached: int | None = None
    skipped: bool | None = None
    reason: str | None = None


class AdminPushStatsResponse(BaseModel):
    total_tokens: int
    active_tokens: int
    by_platform: dict[str, int]
    unique_users_with_tokens: int


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=PushTokenResponse)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def register_push_token(
    request: Request,
    body: RegisterTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register (or update) a device FCM push token for the current user.

    If the token already exists (for any user), it is reassigned to the
    current user and its metadata is updated (upsert semantics).
    """
    existing = db.query(PushToken).filter(PushToken.token == body.token).first()

    if existing:
        # Reassign token if it belonged to another user (e.g. shared device)
        existing.user_id = current_user.id
        existing.platform = body.platform
        existing.device_name = body.device_name
        existing.app_version = body.app_version
        existing.is_active = True
        existing.last_used_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        logger.info(
            "Updated FCM token for user %s (platform=%s)",
            current_user.id,
            body.platform.value,
        )
        return existing

    push_token = PushToken(
        user_id=current_user.id,
        token=body.token,
        platform=body.platform,
        device_name=body.device_name,
        app_version=body.app_version,
        is_active=True,
        last_used_at=datetime.now(timezone.utc),
    )
    db.add(push_token)
    db.commit()
    db.refresh(push_token)

    logger.info(
        "Registered new FCM token for user %s (platform=%s, device=%s)",
        current_user.id,
        body.platform.value,
        body.device_name or "unknown",
    )
    return push_token


@router.delete("/unregister")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def unregister_push_token(
    request: Request,
    body: UnregisterTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a push token.  The token must belong to the current user."""
    push_token = (
        db.query(PushToken)
        .filter(
            PushToken.token == body.token,
            PushToken.user_id == current_user.id,
        )
        .first()
    )
    if not push_token:
        raise HTTPException(status_code=404, detail="Push token not found")

    push_token.is_active = False
    db.commit()
    logger.info("Deactivated FCM token for user %s", current_user.id)
    return {"status": "ok", "message": "Token deactivated"}


@router.get("/tokens", response_model=list[PushTokenResponse])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def list_push_tokens(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active push tokens registered for the current user."""
    tokens = (
        db.query(PushToken)
        .filter(
            PushToken.user_id == current_user.id,
            PushToken.is_active.is_(True),
        )
        .order_by(PushToken.last_used_at.desc())
        .all()
    )
    return tokens


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@admin_router.post("/send", response_model=AdminSendResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def admin_send_push(
    request: Request,
    body: AdminSendRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Admin: send a push notification to one or more specific users."""
    result = await push_service.send_to_users(
        user_ids=body.user_ids,
        title=body.title,
        body=body.body,
        data=body.data,
        db=db,
    )
    logger.info(
        "Admin push sent to %d users: sent=%s failed=%s",
        len(body.user_ids),
        result.get("sent", 0),
        result.get("failed", 0),
    )
    return result


@admin_router.get("/stats", response_model=AdminPushStatsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def admin_push_stats(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Admin: aggregate statistics about registered push tokens."""
    total = db.query(func.count(PushToken.id)).scalar() or 0
    active = (
        db.query(func.count(PushToken.id))
        .filter(PushToken.is_active.is_(True))
        .scalar()
        or 0
    )
    unique_users = (
        db.query(func.count(func.distinct(PushToken.user_id)))
        .filter(PushToken.is_active.is_(True))
        .scalar()
        or 0
    )

    # Counts by platform
    platform_rows = (
        db.query(PushToken.platform, func.count(PushToken.id))
        .filter(PushToken.is_active.is_(True))
        .group_by(PushToken.platform)
        .all()
    )
    by_platform = {row[0].value: row[1] for row in platform_rows}

    return AdminPushStatsResponse(
        total_tokens=total,
        active_tokens=active,
        by_platform=by_platform,
        unique_users_with_tokens=unique_users,
    )
