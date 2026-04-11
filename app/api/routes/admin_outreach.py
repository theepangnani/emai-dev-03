import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.parent_contact import ParentContact, OutreachLog, OutreachTemplate
from app.models.user import User, UserRole
from app.schemas.outreach import (
    SendOutreachRequest,
    SendOutreachResponse,
    OutreachLogResponse,
    OutreachLogListResponse,
    OutreachStatsResponse,
)
from app.services.outreach_service import send_outreach

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/outreach", tags=["Admin Outreach"])


@router.post("/send", response_model=SendOutreachResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def send_outreach_endpoint(
    request: Request,
    body: SendOutreachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Send outreach messages to contacts via email, WhatsApp, or SMS."""
    try:
        result = send_outreach(
            db=db,
            contact_ids=body.parent_contact_ids,
            channel=body.channel,
            sent_by_user_id=current_user.id,
            template_id=body.template_id,
            custom_subject=body.custom_subject,
            custom_body=body.custom_body,
        )
    except ValueError as e:
        error_msg = str(e)
        # Channel not configured -> 503
        if "not configured" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_msg
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    return SendOutreachResponse(
        sent_count=result["sent_count"],
        failed_count=result["failed_count"],
        errors=result["errors"],
    )


@router.get("/log", response_model=OutreachLogListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_outreach_logs(
    request: Request,
    contact_id: int | None = Query(None),
    channel: str | None = Query(None),
    log_status: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List outreach log entries with optional filters."""
    query = db.query(OutreachLog)

    if contact_id is not None:
        query = query.filter(OutreachLog.parent_contact_id == contact_id)
    if channel is not None:
        query = query.filter(OutreachLog.channel == channel)
    if log_status is not None:
        query = query.filter(OutreachLog.status == log_status)

    total = query.count()
    logs = query.order_by(OutreachLog.created_at.desc()).offset(skip).limit(limit).all()

    # Build response with joined names
    items = []
    for log in logs:
        contact = (
            db.query(ParentContact).filter(ParentContact.id == log.parent_contact_id).first()
            if log.parent_contact_id
            else None
        )
        template = (
            db.query(OutreachTemplate).filter(OutreachTemplate.id == log.template_id).first()
            if log.template_id
            else None
        )
        items.append(
            OutreachLogResponse(
                id=log.id,
                parent_contact_id=log.parent_contact_id,
                contact_name=contact.full_name if contact else None,
                template_id=log.template_id,
                template_name=template.name if template else None,
                channel=log.channel,
                status=log.status,
                recipient_detail=log.recipient_detail,
                body_snapshot=None,  # Omit from list for brevity
                sent_by_user_id=log.sent_by_user_id,
                error_message=log.error_message,
                created_at=log.created_at,
            )
        )

    return OutreachLogListResponse(items=items, total=total)


@router.get("/log/{log_id}", response_model=OutreachLogResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_outreach_log(
    request: Request,
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get a single outreach log entry with full body snapshot."""
    log = db.query(OutreachLog).filter(OutreachLog.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found"
        )

    contact = (
        db.query(ParentContact).filter(ParentContact.id == log.parent_contact_id).first()
        if log.parent_contact_id
        else None
    )
    template = (
        db.query(OutreachTemplate).filter(OutreachTemplate.id == log.template_id).first()
        if log.template_id
        else None
    )

    return OutreachLogResponse(
        id=log.id,
        parent_contact_id=log.parent_contact_id,
        contact_name=contact.full_name if contact else None,
        template_id=log.template_id,
        template_name=template.name if template else None,
        channel=log.channel,
        status=log.status,
        recipient_detail=log.recipient_detail,
        body_snapshot=log.body_snapshot,
        sent_by_user_id=log.sent_by_user_id,
        error_message=log.error_message,
        created_at=log.created_at,
    )


@router.get("/stats", response_model=OutreachStatsResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_outreach_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get outreach summary statistics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    total_sent = (
        db.query(func.count(OutreachLog.id))
        .filter(OutreachLog.status == "sent")
        .scalar()
        or 0
    )
    sent_today = (
        db.query(func.count(OutreachLog.id))
        .filter(OutreachLog.status == "sent", OutreachLog.created_at >= today_start)
        .scalar()
        or 0
    )
    sent_this_week = (
        db.query(func.count(OutreachLog.id))
        .filter(OutreachLog.status == "sent", OutreachLog.created_at >= week_start)
        .scalar()
        or 0
    )

    # By channel
    channel_rows = (
        db.query(OutreachLog.channel, func.count(OutreachLog.id))
        .group_by(OutreachLog.channel)
        .all()
    )
    by_channel = {row[0]: row[1] for row in channel_rows}

    # By status
    status_rows = (
        db.query(OutreachLog.status, func.count(OutreachLog.id))
        .group_by(OutreachLog.status)
        .all()
    )
    by_status = {row[0]: row[1] for row in status_rows}

    return OutreachStatsResponse(
        total_sent=total_sent,
        sent_today=sent_today,
        sent_this_week=sent_this_week,
        by_channel=by_channel,
        by_status=by_status,
    )
