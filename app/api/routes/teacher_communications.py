import logging
from pydantic import BaseModel as PydanticBaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.utils import escape_like

from app.db.database import get_db
from app.models.user import User
from app.models.teacher_communication import TeacherCommunication, CommunicationType
from app.schemas.teacher_communication import (
    TeacherCommunicationResponse,
    TeacherCommunicationList,
    EmailMonitoringStatus,
)
from app.api.deps import get_current_user
from app.services.google_classroom import get_email_monitoring_auth_url, GMAIL_READONLY_SCOPE
from app.services.email_service import send_email_sync, add_inspiration_to_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher-communications", tags=["Teacher Communications"])


@router.get("/", response_model=TeacherCommunicationList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_communications(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: CommunicationType | None = None,
    search: str | None = None,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List teacher communications with search and filtering."""
    query = db.query(TeacherCommunication).filter(
        TeacherCommunication.user_id == current_user.id
    )

    if type:
        query = query.filter(TeacherCommunication.type == type)

    if unread_only:
        query = query.filter(TeacherCommunication.is_read == False)

    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                TeacherCommunication.subject.ilike(search_term),
                TeacherCommunication.body.ilike(search_term),
                TeacherCommunication.sender_name.ilike(search_term),
                TeacherCommunication.ai_summary.ilike(search_term),
            )
        )

    total = query.count()
    items = (
        query.order_by(desc(TeacherCommunication.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return TeacherCommunicationList(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/status", response_model=EmailMonitoringStatus)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_monitoring_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get email monitoring status and stats."""
    total = db.query(TeacherCommunication).filter(
        TeacherCommunication.user_id == current_user.id
    ).count()

    unread = db.query(TeacherCommunication).filter(
        TeacherCommunication.user_id == current_user.id,
        TeacherCommunication.is_read == False,
    ).count()

    has_gmail_scope = current_user.has_google_scope(GMAIL_READONLY_SCOPE)
    return EmailMonitoringStatus(
        gmail_enabled=bool(current_user.google_access_token) and has_gmail_scope,
        classroom_enabled=bool(current_user.google_access_token),
        gmail_scope_granted=has_gmail_scope,
        last_gmail_sync=getattr(current_user, "gmail_last_sync", None),
        last_classroom_sync=getattr(current_user, "classroom_last_sync", None),
        total_communications=total,
        unread_count=unread,
    )


@router.get("/auth/email-monitoring")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_email_monitoring_auth(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get OAuth URL for granting email monitoring permissions."""
    state = f"email_monitor:{current_user.id}"
    auth_url, _ = get_email_monitoring_auth_url(state)
    return {"authorization_url": auth_url}


@router.get("/{comm_id}", response_model=TeacherCommunicationResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_communication(
    request: Request,
    comm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single communication with full details."""
    comm = db.query(TeacherCommunication).filter(
        TeacherCommunication.id == comm_id,
        TeacherCommunication.user_id == current_user.id,
    ).first()

    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")

    if not comm.is_read:
        comm.is_read = True
        db.commit()
        db.refresh(comm)

    return comm


@router.put("/{comm_id}/read")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def mark_as_read(
    request: Request,
    comm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a communication as read."""
    comm = db.query(TeacherCommunication).filter(
        TeacherCommunication.id == comm_id,
        TeacherCommunication.user_id == current_user.id,
    ).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    comm.is_read = True
    db.commit()
    return {"status": "ok"}


@router.post("/sync")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def trigger_sync(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a sync for the current user."""
    if not current_user.google_access_token:
        raise HTTPException(status_code=400, detail="Google not connected")

    from app.jobs.teacher_comm_sync import sync_user_communications
    result = await sync_user_communications(current_user.id, db)
    return result


class ReplyRequest(PydanticBaseModel):
    body: str


@router.post("/{comm_id}/reply")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def reply_to_communication(
    request: Request,
    comm_id: int,
    data: ReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reply to a teacher communication via ClassBridge email."""
    comm = db.query(TeacherCommunication).filter(
        TeacherCommunication.id == comm_id,
        TeacherCommunication.user_id == current_user.id,
    ).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    if not comm.sender_email:
        raise HTTPException(status_code=400, detail="No sender email to reply to")
    if not data.body.strip():
        raise HTTPException(status_code=400, detail="Reply body cannot be empty")

    subject = f"Re: {comm.subject}" if comm.subject else "Reply from ClassBridge"
    reply_html = f"""
        <p>{data.body.replace(chr(10), '<br>')}</p>
        <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;" />
        <p style="color:#888;font-size:13px;">
            Sent by <strong>{current_user.full_name}</strong> via ClassBridge
        </p>
        <blockquote style="border-left:3px solid #ddd;padding-left:12px;color:#666;margin-top:16px;">
            <p style="font-size:13px;"><strong>Original message from {comm.sender_name or 'Unknown'}:</strong></p>
            <p style="font-size:13px;">{(comm.body or '(No content)')[:500]}</p>
        </blockquote>
    """

    try:
        reply_html = add_inspiration_to_email(reply_html, db, current_user.role)
        send_email_sync(
            to_email=comm.sender_email,
            subject=subject,
            html_content=reply_html,
        )
    except Exception as e:
        logger.error(f"Failed to send reply to {comm.sender_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send reply email")

    return {"status": "sent", "to": comm.sender_email}
