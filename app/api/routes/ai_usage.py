import logging
from datetime import datetime, timezone

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.notification import Notification, NotificationType
from app.models.ai_limit_request import AILimitRequest
from app.models.ai_usage_history import AIUsageHistory
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.utils import escape_like
from app.api.deps import get_current_user, require_role
from app.schemas.ai_usage import (
    AIUsageResponse,
    AILimitRequestCreate,
    AILimitRequestResponse,
    AILimitAdminAction,
    AILimitSetRequest,
    AIBulkSetLimitRequest,
    AIBulkSetLimitResponse,
    AIUsageUserResponse,
    AIUsageUserList,
    AILimitRequestList,
    AIUsageHistoryResponse,
    AIUsageHistoryList,
    AIUsageSummaryResponse,
)

logger = logging.getLogger(__name__)

# ── User-facing endpoints ─────────────────────────────────────────────

router = APIRouter(prefix="/ai-usage", tags=["AI Usage"])

AI_WARNING_THRESHOLD = 0.8  # Warn when usage >= 80% of limit


@router.get("", response_model=AIUsageResponse)
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


@router.get("/history", response_model=AIUsageHistoryList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_user_history(
    request: Request,
    generation_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's AI usage history (paginated)."""
    query = db.query(AIUsageHistory).filter(AIUsageHistory.user_id == current_user.id)

    if generation_type:
        query = query.filter(AIUsageHistory.generation_type == generation_type)

    total = query.count()
    records = query.order_by(desc(AIUsageHistory.created_at)).offset(skip).limit(limit).all()

    items = []
    for rec in records:
        resp = AIUsageHistoryResponse.model_validate(rec)
        resp.user_name = current_user.full_name
        resp.user_email = current_user.email
        if rec.course_material:
            resp.course_material_title = rec.course_material.title
        items.append(resp)

    return AIUsageHistoryList(items=items, total=total)


# ── Admin endpoints ───────────────────────────────────────────────────

admin_router = APIRouter(prefix="/admin/ai-usage", tags=["Admin AI Usage"])


@admin_router.get("", response_model=AIUsageUserList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_users_usage(
    request: Request,
    search: str | None = Query(None),
    sort_by: Literal["ai_usage_count", "ai_usage_limit", "name", "usage", "limit"] = Query("name"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
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

    if sort_by in ("usage", "ai_usage_count"):
        col = User.ai_usage_count
    elif sort_by in ("limit", "ai_usage_limit"):
        col = User.ai_usage_limit
    else:
        col = User.full_name

    query = query.order_by(desc(col) if sort_dir == "desc" else col.asc())

    total = query.count()
    users = query.offset(skip).limit(limit).all()
    return AIUsageUserList(items=users, total=total)


@admin_router.get("/summary", response_model=AIUsageSummaryResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_usage_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get AI usage summary: total calls and top users."""
    total_calls = db.query(func.coalesce(func.sum(User.ai_usage_count), 0)).scalar()

    top_users = (
        db.query(User.id, User.full_name, User.ai_usage_count)
        .filter(User.ai_usage_count > 0)
        .order_by(desc(User.ai_usage_count))
        .limit(5)
        .all()
    )

    return AIUsageSummaryResponse(
        total_ai_calls=total_calls,
        top_users=[
            {"id": u.id, "full_name": u.full_name, "ai_usage_count": u.ai_usage_count}
            for u in top_users
        ],
    )


@admin_router.get("/requests", response_model=AILimitRequestList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_limit_requests(
    request: Request,
    request_status: str = Query("all", alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List AI limit increase requests, optionally filtered by status."""
    query = db.query(AILimitRequest)

    if request_status != "all":
        query = query.filter(AILimitRequest.status == request_status)

    total = query.count()
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
    return AILimitRequestList(items=results, total=total)


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


@admin_router.post("/bulk-set-limit", response_model=AIBulkSetLimitResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def bulk_set_limit(
    request: Request,
    body: AIBulkSetLimitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Set AI usage limit for all users at once. Optionally reset counts."""
    updated = db.query(User).update({User.ai_usage_limit: body.ai_usage_limit})
    if body.reset_counts:
        db.query(User).update({User.ai_usage_count: 0})
    db.commit()
    logger.info(
        "Admin %s bulk-set AI limit to %d for %d users (reset_counts=%s)",
        current_user.id, body.ai_usage_limit, updated, body.reset_counts,
    )
    return AIBulkSetLimitResponse(updated_count=updated, new_limit=body.ai_usage_limit)


@admin_router.get("/history", response_model=AIUsageHistoryList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def admin_list_usage_history(
    request: Request,
    user_id: int | None = Query(None),
    generation_type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all users' AI usage history with filters. Admin only."""
    query = db.query(AIUsageHistory)

    if user_id is not None:
        query = query.filter(AIUsageHistory.user_id == user_id)
    if generation_type:
        query = query.filter(AIUsageHistory.generation_type == generation_type)
    if date_from:
        query = query.filter(AIUsageHistory.created_at >= date_from)
    if date_to:
        query = query.filter(AIUsageHistory.created_at <= date_to)
    if search:
        search_term = f"%{escape_like(search)}%"
        # Join to User table to search by name/email
        query = query.join(User, AIUsageHistory.user_id == User.id).filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    total = query.count()
    records = query.order_by(desc(AIUsageHistory.created_at)).offset(skip).limit(limit).all()

    # Resolve user names in bulk
    user_ids = {rec.user_id for rec in records}
    user_map = {}
    if user_ids:
        users = db.query(User.id, User.full_name, User.email).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: (u.full_name, u.email) for u in users}

    items = []
    for rec in records:
        resp = AIUsageHistoryResponse.model_validate(rec)
        if rec.user_id in user_map:
            resp.user_name, resp.user_email = user_map[rec.user_id]
        if rec.course_material:
            resp.course_material_title = rec.course_material.title
        items.append(resp)

    return AIUsageHistoryList(items=items, total=total)
