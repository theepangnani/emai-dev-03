import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.db.database import get_db
from app.models.user import User
from app.models.teacher_communication import TeacherCommunication, CommunicationType
from app.schemas.teacher_communication import (
    TeacherCommunicationResponse,
    TeacherCommunicationList,
    EmailMonitoringStatus,
)
from app.api.deps import get_current_user
from app.services.google_classroom import get_email_monitoring_auth_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher-communications", tags=["Teacher Communications"])


@router.get("/", response_model=TeacherCommunicationList)
def list_communications(
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
        search_term = f"%{search}%"
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
def get_monitoring_status(
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

    return EmailMonitoringStatus(
        gmail_enabled=bool(current_user.google_access_token),
        classroom_enabled=bool(current_user.google_access_token),
        last_gmail_sync=getattr(current_user, "gmail_last_sync", None),
        last_classroom_sync=getattr(current_user, "classroom_last_sync", None),
        total_communications=total,
        unread_count=unread,
    )


@router.get("/auth/email-monitoring")
def get_email_monitoring_auth(
    current_user: User = Depends(get_current_user),
):
    """Get OAuth URL for granting email monitoring permissions."""
    state = f"email_monitor:{current_user.id}"
    auth_url, _ = get_email_monitoring_auth_url(state)
    return {"authorization_url": auth_url}


@router.get("/{comm_id}", response_model=TeacherCommunicationResponse)
def get_communication(
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
def mark_as_read(
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
async def trigger_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a sync for the current user."""
    if not current_user.google_access_token:
        raise HTTPException(status_code=400, detail="Google not connected")

    from app.jobs.teacher_comm_sync import sync_user_communications
    result = await sync_user_communications(current_user.id, db)
    return result
