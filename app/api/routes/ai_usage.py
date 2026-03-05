import logging
from datetime import datetime, timezone

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.notification import Notification, NotificationType
from app.models.ai_limit_request import AILimitRequest
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.utils import escape_like
from app.api.deps import get_current_user, require_role
from app.schemas.ai_usage import (
    AIUsageResponse,
    AILimitRequestCreate,
    AILimitRequestResponse,
    AILimitAdminAction,
    AILimitSetRequest,
    AIUsageUserResponse,
)

logger = logging.getLogger(__name__)

# ── User-facing endpoints ─────────────────────────────────────────────

router = APIRouter(prefix="/ai-usage", tags=["AI Usage"])

AI_WARNING_THRESHOLD = 0.8  # Warn when usage >= 80% of limit


@router.get("/", response_model=AIUsageResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_current_usage(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get the current user's AI usage stats."""
    count = current_user.ai_usage_count or 0
    limit = current_user.ai_usage_limit or 10
    remaining = max(0, limit - count)
    return AIUsageResponse(
        count=count,
        limit=limit,
        remaining=remaining,
        warning_threshold=AI_WARNING_THRESHOLD,
        at_limit=count >= limit,
    )


@router.post("/request", response_model=AILimitRequestResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def request_more_credits(
    request: Request,
    body: AILimitRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request additional AI usage credits. Creates a pending request for admin review."""
    ai_request = AILimitRequest(
        user_id=current_user.id,
        requested_amount=body.requested_amount,
        reason=body.reason,
        status="pending",
    )
    db.add(ai_request)
    db.flush()

    # Notify all admins
    admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
    for admin_user in admins:
        notification = Notification(
            user_id=admin_user.id,
            type=NotificationType.SYSTEM,
            title="AI Credit Request",
            content=f"{current_user.full_name} requested {body.requested_amount} additional AI credits.",
            link="/admin/ai-usage",
        )
        db.add(notification)

    db.commit()
    db.refresh(ai_request)
    logger.info("User %s requested %d AI credits (request #%d)", current_user.id, body.requested_amount, ai_request.id)
    return ai_request


# ── Admin endpoints ───────────────────────────────────────────────────

admin_router = APIRouter(prefix="/admin/ai-usage", tags=["Admin AI Usage"])


@admin_router.get("/", response_model=list[AIUsageUserResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_users_usage(
    request: Request,
    search: str | None = Query(None),
    sort_by: Literal["usage", "limit", "name"] = Query("name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all users with their AI usage stats."""
    query = db.query(User)

    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    if sort_by == "usage":
        query = query.order_by(desc(User.ai_usage_count))
    elif sort_by == "limit":
        query = query.order_by(desc(User.ai_usage_limit))
    else:
        query = query.order_by(User.full_name)

    users = query.offset(skip).limit(limit).all()
    return users


@admin_router.get("/requests", response_model=list[AILimitRequestResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_limit_requests(
    request: Request,
    request_status: str = Query("pending", alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List AI limit increase requests, optionally filtered by status."""
    query = db.query(AILimitRequest)

    if request_status != "all":
        query = query.filter(AILimitRequest.status == request_status)

    records = query.order_by(desc(AILimitRequest.created_at)).offset(skip).limit(limit).all()

    # Enrich with user info
    results = []
    for rec in records:
        resp = AILimitRequestResponse.model_validate(rec)
        if rec.user:
            resp.user_name = rec.user.full_name
            resp.user_email = rec.user.email
            resp.user_role = rec.user.role.value if rec.user.role else None
        results.append(resp)
    return results


@admin_router.patch("/requests/{request_id}/approve", response_model=AILimitRequestResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def approve_request(
    request: Request,
    request_id: int,
    body: AILimitAdminAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Approve an AI credit request and increase the user's limit."""
    ai_request = db.query(AILimitRequest).filter(AILimitRequest.id == request_id).first()
    if not ai_request:
        raise HTTPException(status_code=404, detail="Request not found")
    if ai_request.status != "pending":
        raise HTTPException(status_code=400, detail="Request has already been resolved")

    ai_request.status = "approved"
    ai_request.approved_amount = body.approved_amount
    ai_request.admin_user_id = current_user.id
    ai_request.resolved_at = datetime.now(timezone.utc)

    # Increase user's limit
    target_user = db.query(User).filter(User.id == ai_request.user_id).first()
    if target_user:
        target_user.ai_usage_limit = (target_user.ai_usage_limit or 10) + body.approved_amount

        # Notify the user
        notification = Notification(
            user_id=target_user.id,
            type=NotificationType.SYSTEM,
            title="AI Credit Request Approved",
            content=f"Your request for additional AI credits has been approved. {body.approved_amount} credits added to your account.",
            link="/study-guides",
        )
        db.add(notification)

    db.commit()
    db.refresh(ai_request)
    logger.info("Admin %s approved AI request #%d (+%d credits for user %s)", current_user.id, request_id, body.approved_amount, ai_request.user_id)
    return ai_request


@admin_router.patch("/requests/{request_id}/decline", response_model=AILimitRequestResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def decline_request(
    request: Request,
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Decline an AI credit request."""
    ai_request = db.query(AILimitRequest).filter(AILimitRequest.id == request_id).first()
    if not ai_request:
        raise HTTPException(status_code=404, detail="Request not found")
    if ai_request.status != "pending":
        raise HTTPException(status_code=400, detail="Request has already been resolved")

    ai_request.status = "declined"
    ai_request.admin_user_id = current_user.id
    ai_request.resolved_at = datetime.now(timezone.utc)

    # Notify the user
    target_user = db.query(User).filter(User.id == ai_request.user_id).first()
    if target_user:
        notification = Notification(
            user_id=target_user.id,
            type=NotificationType.SYSTEM,
            title="AI Credit Request Declined",
            content="Your request for additional AI credits has been declined. Contact your administrator for more information.",
            link="/study-guides",
        )
        db.add(notification)

    db.commit()
    db.refresh(ai_request)
    logger.info("Admin %s declined AI request #%d (user %s)", current_user.id, request_id, ai_request.user_id)
    return ai_request


@admin_router.patch("/users/{user_id}/limit", response_model=AIUsageUserResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def set_user_limit(
    request: Request,
    user_id: int,
    body: AILimitSetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Directly set a user's AI usage limit."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.ai_usage_limit = body.ai_usage_limit
    db.commit()
    db.refresh(target_user)
    logger.info("Admin %s set AI limit for user %s to %d", current_user.id, user_id, body.ai_usage_limit)
    return target_user


@admin_router.post("/users/{user_id}/reset", response_model=AIUsageUserResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def reset_user_usage(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Reset a user's AI usage count to zero."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.ai_usage_count = 0
    db.commit()
    db.refresh(target_user)
    logger.info("Admin %s reset AI usage count for user %s", current_user.id, user_id)
    return target_user
