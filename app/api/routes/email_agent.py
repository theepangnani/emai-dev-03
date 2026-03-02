"""
AI Email Agent API — Phase 5.

Endpoints:
  Threads:
    GET    /api/email-agent/threads                   list (paginated, filter tab/tag/archived)
    GET    /api/email-agent/threads/{id}              detail with all messages
    DELETE /api/email-agent/threads/{id}              archive thread

  Messages:
    POST   /api/email-agent/messages                  send email (creates/updates thread)
    GET    /api/email-agent/messages/{id}             single message

  AI Assistance:
    POST   /api/email-agent/ai/draft                  draft new email
    POST   /api/email-agent/ai/improve                improve draft
    POST   /api/email-agent/threads/{id}/summarize    generate AI thread summary
    POST   /api/email-agent/threads/{id}/suggest-reply suggest reply
    POST   /api/email-agent/threads/{id}/action-items extract action items

  Search:
    GET    /api/email-agent/search                    full-text search

  Inbound Webhook (no auth):
    POST   /api/email-agent/inbound                   SendGrid Inbound Parse

  Stats:
    GET    /api/email-agent/stats                     aggregate counts
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func as sa_func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature
from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.email_thread import EmailDirection, EmailMessage, EmailStatus, EmailThread
from app.models.user import User
from app.services.ai_email_service import AIEmailService
from app.services.sendgrid_inbound import (
    find_thread_by_reply,
    find_thread_by_subject,
    parse_sendgrid_inbound,
    verify_sendgrid_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email-agent", tags=["email-agent"])


# ---------------------------------------------------------------------------
# Pydantic schemas (local — no separate schemas file needed for this module)
# ---------------------------------------------------------------------------

class ThreadSummaryResponse(BaseModel):
    id: int
    subject: str
    recipient_emails: list[str]
    recipient_names: list[str]
    message_count: int
    last_message_at: Optional[datetime]
    ai_summary: Optional[str]
    tags: list[str]
    is_archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    thread_id: int
    direction: str
    from_email: str
    from_name: Optional[str]
    to_emails: list[str]
    subject: str
    body_text: str
    body_html: Optional[str]
    ai_draft: bool
    ai_tone: Optional[str]
    status: str
    sent_at: Optional[datetime]
    received_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadDetailResponse(BaseModel):
    id: int
    subject: str
    recipient_emails: list[str]
    recipient_names: list[str]
    message_count: int
    last_message_at: Optional[datetime]
    ai_summary: Optional[str]
    ai_summary_generated_at: Optional[datetime]
    tags: list[str]
    is_archived: bool
    created_at: datetime
    messages: list[MessageResponse]

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    thread_id: Optional[int] = None
    recipient_emails: list[str]
    recipient_names: Optional[list[str]] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    ai_draft: bool = False
    ai_tone: Optional[str] = None

    @field_validator("recipient_emails")
    @classmethod
    def validate_recipients(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one recipient is required")
        return v


class AIDraftRequest(BaseModel):
    prompt: str
    context: str
    tone: str = "formal"
    language: str = "en"


class AIImproveRequest(BaseModel):
    current_body: str
    instruction: str


class StatsResponse(BaseModel):
    sent_count: int
    received_count: int
    threads_count: int
    drafts_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thread_to_summary(thread: EmailThread) -> ThreadSummaryResponse:
    return ThreadSummaryResponse(
        id=thread.id,
        subject=thread.subject,
        recipient_emails=_load_json_list(thread.recipient_emails),
        recipient_names=_load_json_list(thread.recipient_names),
        message_count=thread.message_count,
        last_message_at=thread.last_message_at,
        ai_summary=thread.ai_summary,
        tags=_load_json_list(thread.tags),
        is_archived=thread.is_archived,
        created_at=thread.created_at,
    )


def _message_to_response(msg: EmailMessage) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        thread_id=msg.thread_id,
        direction=msg.direction.value,
        from_email=msg.from_email,
        from_name=msg.from_name,
        to_emails=_load_json_list(msg.to_emails),
        subject=msg.subject,
        body_text=msg.body_text,
        body_html=msg.body_html,
        ai_draft=msg.ai_draft,
        ai_tone=msg.ai_tone,
        status=msg.status.value,
        sent_at=msg.sent_at,
        received_at=msg.received_at,
        created_at=msg.created_at,
    )


def _thread_to_detail(thread: EmailThread) -> ThreadDetailResponse:
    return ThreadDetailResponse(
        id=thread.id,
        subject=thread.subject,
        recipient_emails=_load_json_list(thread.recipient_emails),
        recipient_names=_load_json_list(thread.recipient_names),
        message_count=thread.message_count,
        last_message_at=thread.last_message_at,
        ai_summary=thread.ai_summary,
        ai_summary_generated_at=thread.ai_summary_generated_at,
        tags=_load_json_list(thread.tags),
        is_archived=thread.is_archived,
        created_at=thread.created_at,
        messages=[_message_to_response(m) for m in thread.messages],
    )


def _load_json_list(value: Optional[str]) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _dump_json_list(values: Optional[list]) -> str:
    return json.dumps(values or [])


async def _send_via_sendgrid(
    from_email: str,
    to_emails: list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str],
) -> Optional[str]:
    """Send an email via SendGrid and return the X-Message-Id header."""
    from sendgrid import SendGridAPIClient  # type: ignore
    from sendgrid.helpers.mail import Mail  # type: ignore

    message = Mail(
        from_email=(from_email, "ClassBridge"),
        to_emails=to_emails,
        subject=subject,
        plain_text_content=body_text,
        html_content=body_html or body_text,
    )
    sg = SendGridAPIClient(api_key=settings.sendgrid_api_key)
    response = sg.send(message)
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(f"SendGrid returned {response.status_code}: {response.body}")
    msg_id = response.headers.get("X-Message-Id")
    logger.info("Email sent via SendGrid | to=%s | message_id=%s", to_emails, msg_id)
    return msg_id


def _get_or_create_thread(
    db: Session,
    user_id: int,
    thread_id: Optional[int],
    subject: str,
    recipient_emails: list[str],
    recipient_names: list[str],
) -> EmailThread:
    """Return an existing thread or create a new one."""
    if thread_id:
        thread = db.query(EmailThread).filter(
            EmailThread.id == thread_id,
            EmailThread.user_id == user_id,
        ).first()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return thread

    thread = EmailThread(
        user_id=user_id,
        subject=subject,
        recipient_emails=_dump_json_list(recipient_emails),
        recipient_names=_dump_json_list(recipient_names),
        message_count=0,
    )
    db.add(thread)
    db.flush()
    return thread


def _bump_thread_stats(thread: EmailThread, sent_at: datetime) -> None:
    thread.message_count = (thread.message_count or 0) + 1
    if thread.last_message_at is None or sent_at > thread.last_message_at:
        thread.last_message_at = sent_at


# ---------------------------------------------------------------------------
# Thread endpoints
# ---------------------------------------------------------------------------

@router.get("/threads", response_model=list[ThreadSummaryResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_threads(
    request: Request,
    _flag=Depends(require_feature("ai_email_agent")),
    tab: Optional[str] = Query(None, description="inbox | sent | drafts | archived"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    archived: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's email threads."""
    q = db.query(EmailThread).filter(EmailThread.user_id == current_user.id)

    if tab == "archived":
        q = q.filter(EmailThread.is_archived == True)  # noqa: E712
    elif tab is not None:
        q = q.filter(EmailThread.is_archived == False)  # noqa: E712
    elif archived is not None:
        q = q.filter(EmailThread.is_archived == archived)

    if tag:
        q = q.filter(EmailThread.tags.contains(tag))

    threads = (
        q.order_by(EmailThread.last_message_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_thread_to_summary(t) for t in threads]


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_thread(
    request: Request,
    thread_id: int,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a thread with all its messages."""
    thread = db.query(EmailThread).filter(
        EmailThread.id == thread_id,
        EmailThread.user_id == current_user.id,
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _thread_to_detail(thread)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def archive_thread(
    request: Request,
    thread_id: int,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive (soft-delete) a thread."""
    thread = db.query(EmailThread).filter(
        EmailThread.id == thread_id,
        EmailThread.user_id == current_user.id,
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.is_archived = True
    db.commit()


# ---------------------------------------------------------------------------
# Message endpoints
# ---------------------------------------------------------------------------

@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def send_message(
    request: Request,
    data: SendMessageRequest,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a new email or reply, creating/updating a thread as needed."""
    recipient_names = data.recipient_names or []

    thread = _get_or_create_thread(
        db,
        user_id=current_user.id,
        thread_id=data.thread_id,
        subject=data.subject,
        recipient_emails=data.recipient_emails,
        recipient_names=recipient_names,
    )

    from_email = current_user.email or settings.from_email
    now = datetime.now(timezone.utc)

    msg = EmailMessage(
        thread_id=thread.id,
        user_id=current_user.id,
        direction=EmailDirection.OUTBOUND,
        from_email=from_email,
        from_name=current_user.full_name,
        to_emails=_dump_json_list(data.recipient_emails),
        subject=data.subject,
        body_text=data.body_text,
        body_html=data.body_html,
        ai_draft=data.ai_draft,
        ai_tone=data.ai_tone,
        status=EmailStatus.SENT,
        sent_at=now,
    )

    # Attempt to send via SendGrid
    sendgrid_id: Optional[str] = None
    try:
        sendgrid_id = await _send_via_sendgrid(
            from_email=from_email,
            to_emails=data.recipient_emails,
            subject=data.subject,
            body_text=data.body_text,
            body_html=data.body_html,
        )
        msg.sendgrid_message_id = sendgrid_id
        msg.status = EmailStatus.SENT

        # Store the first Message-ID as the thread's external identifier for
        # matching future inbound replies.
        if sendgrid_id and not thread.external_thread_id:
            thread.external_thread_id = sendgrid_id

    except Exception as exc:
        logger.error("SendGrid send failed | error=%s", exc)
        msg.status = EmailStatus.FAILED

    db.add(msg)
    _bump_thread_stats(thread, now)
    db.commit()
    db.refresh(msg)

    logger.info(
        "Email sent | user=%d | thread=%d | message=%d | status=%s",
        current_user.id, thread.id, msg.id, msg.status.value,
    )
    return _message_to_response(msg)


@router.get("/messages/{message_id}", response_model=MessageResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_message(
    request: Request,
    message_id: int,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single email message."""
    msg = db.query(EmailMessage).filter(
        EmailMessage.id == message_id,
        EmailMessage.user_id == current_user.id,
    ).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return _message_to_response(msg)


# ---------------------------------------------------------------------------
# AI assistance endpoints
# ---------------------------------------------------------------------------

@router.post("/ai/draft")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def ai_draft(
    request: Request,
    data: AIDraftRequest,
    _flag=Depends(require_feature("ai_email_agent")),
    current_user: User = Depends(get_current_user),
):
    """Draft a new email using AI.

    Returns {subject: str, body: str, tone: str}.
    """
    service = AIEmailService(user=current_user)
    result = await service.draft_email(
        prompt=data.prompt,
        context=data.context,
        tone=data.tone,
        language=data.language,
    )
    return result


@router.post("/ai/improve")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def ai_improve(
    request: Request,
    data: AIImproveRequest,
    _flag=Depends(require_feature("ai_email_agent")),
    current_user: User = Depends(get_current_user),
):
    """Improve an existing draft based on an instruction."""
    service = AIEmailService(user=current_user)
    improved = await service.improve_draft(
        current_body=data.current_body,
        instruction=data.instruction,
    )
    return {"body": improved}


@router.post("/threads/{thread_id}/summarize")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def summarize_thread(
    request: Request,
    thread_id: int,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or regenerate) an AI summary for a thread."""
    thread = db.query(EmailThread).filter(
        EmailThread.id == thread_id,
        EmailThread.user_id == current_user.id,
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    service = AIEmailService(user=current_user)
    summary = await service.summarize_thread(thread.messages)

    thread.ai_summary = summary
    thread.ai_summary_generated_at = datetime.now(timezone.utc)
    db.commit()

    return {"summary": summary, "generated_at": thread.ai_summary_generated_at}


@router.post("/threads/{thread_id}/suggest-reply")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def suggest_reply(
    request: Request,
    thread_id: int,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest a reply to the most recent inbound message in a thread."""
    thread = db.query(EmailThread).filter(
        EmailThread.id == thread_id,
        EmailThread.user_id == current_user.id,
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Find the most recent inbound message
    last_inbound = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.thread_id == thread_id,
            EmailMessage.direction == EmailDirection.INBOUND,
        )
        .order_by(EmailMessage.created_at.desc())
        .first()
    )
    if not last_inbound:
        # Fall back to most recent message of any direction
        last_inbound = (
            db.query(EmailMessage)
            .filter(EmailMessage.thread_id == thread_id)
            .order_by(EmailMessage.created_at.desc())
            .first()
        )
    if not last_inbound:
        raise HTTPException(status_code=400, detail="No messages in thread to reply to")

    user_context = f"{current_user.full_name}, role: {current_user.role.value if current_user.role else 'user'}"
    service = AIEmailService(user=current_user)
    suggested = await service.suggest_reply(last_inbound, user_context)

    return {"suggested_reply": suggested}


@router.post("/threads/{thread_id}/action-items")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def extract_action_items(
    request: Request,
    thread_id: int,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract action items from a thread."""
    thread = db.query(EmailThread).filter(
        EmailThread.id == thread_id,
        EmailThread.user_id == current_user.id,
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    service = AIEmailService(user=current_user)
    items = await service.extract_action_items(thread.messages)

    return {"action_items": items}


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

@router.get("/search")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def search_emails(
    request: Request,
    _flag=Depends(require_feature("ai_email_agent")),
    q: Optional[str] = Query(None, min_length=2, max_length=200),
    from_addr: Optional[str] = Query(None, alias="from"),
    to_addr: Optional[str] = Query(None, alias="to"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full-text search across the user's email threads and messages."""
    base_q = (
        db.query(EmailMessage)
        .join(EmailThread, EmailMessage.thread_id == EmailThread.id)
        .filter(EmailThread.user_id == current_user.id)
    )

    if q:
        like = f"%{q}%"
        base_q = base_q.filter(
            or_(
                EmailMessage.subject.ilike(like),
                EmailMessage.body_text.ilike(like),
                EmailMessage.from_email.ilike(like),
            )
        )

    if from_addr:
        base_q = base_q.filter(EmailMessage.from_email.ilike(f"%{from_addr}%"))

    if to_addr:
        base_q = base_q.filter(EmailMessage.to_emails.ilike(f"%{to_addr}%"))

    if date_from:
        base_q = base_q.filter(EmailMessage.created_at >= date_from)

    if date_to:
        base_q = base_q.filter(EmailMessage.created_at <= date_to)

    total = base_q.count()
    messages = (
        base_q.order_by(EmailMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "results": [_message_to_response(m) for m in messages],
        "total": total,
        "skip": skip,
        "limit": limit,
        "query": q,
    }


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_stats(
    request: Request,
    _flag=Depends(require_feature("ai_email_agent")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate email statistics for the current user."""
    base = (
        db.query(EmailMessage)
        .join(EmailThread, EmailMessage.thread_id == EmailThread.id)
        .filter(EmailThread.user_id == current_user.id)
    )

    sent_count = base.filter(
        EmailMessage.direction == EmailDirection.OUTBOUND,
        EmailMessage.status != EmailStatus.DRAFT,
    ).count()

    received_count = base.filter(
        EmailMessage.direction == EmailDirection.INBOUND,
    ).count()

    threads_count = (
        db.query(EmailThread)
        .filter(
            EmailThread.user_id == current_user.id,
            EmailThread.is_archived == False,  # noqa: E712
        )
        .count()
    )

    drafts_count = base.filter(
        EmailMessage.status == EmailStatus.DRAFT,
    ).count()

    return StatsResponse(
        sent_count=sent_count,
        received_count=received_count,
        threads_count=threads_count,
        drafts_count=drafts_count,
    )


# ---------------------------------------------------------------------------
# SendGrid Inbound Parse webhook (NO authentication — verified by signature)
# ---------------------------------------------------------------------------

@router.post("/inbound", status_code=status.HTTP_200_OK)
async def inbound_email(request: Request, db: Session = Depends(get_db)):
    """Handle SendGrid Inbound Parse webhook.

    SendGrid posts multipart/form-data whenever an email is received at the
    configured inbound address. This endpoint:
      1. Optionally verifies the SendGrid ECDSA signature
         (requires SENDGRID_WEBHOOK_KEY env var).
      2. Parses the payload.
      3. Matches the email to an existing EmailThread (by In-Reply-To header
         or subject line).
      4. Creates an INBOUND EmailMessage record.

    Returns 200 immediately so SendGrid does not retry.
    """
    # ── Optional signature verification ────────────────────────────────────
    webhook_key = getattr(settings, "sendgrid_webhook_key", "") or ""
    if webhook_key:
        sig = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
        ts = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")
        body_bytes = await request.body()
        if not verify_sendgrid_signature(body_bytes, sig, ts, webhook_key):
            logger.warning("SendGrid inbound webhook: signature verification failed")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    # ── Parse form data ─────────────────────────────────────────────────────
    form = await request.form()
    form_dict = dict(form)
    parsed = parse_sendgrid_inbound(form_dict)

    from_email = parsed["from_email"]
    subject = parsed["subject"]
    body_text = parsed["body_text"]
    body_html = parsed["body_html"]
    in_reply_to = parsed["in_reply_to"]
    to_emails = parsed["to_emails"]
    from_name = parsed["from_name"]
    message_id = parsed["message_id"]

    to_email = to_emails[0] if to_emails else ""

    # ── Thread matching ─────────────────────────────────────────────────────
    thread: Optional[EmailThread] = find_thread_by_reply(in_reply_to, to_email, db)

    if thread is None and subject:
        # Look for the user whose email matches one of the to_emails
        owner: Optional[User] = None
        if to_emails:
            owner = db.query(User).filter(User.email.in_(to_emails)).first()
        if owner:
            thread = find_thread_by_subject(subject, owner.id, db)

    if thread is None:
        # Cannot match — log and return 200 so SendGrid doesn't retry
        logger.warning(
            "Inbound email could not be matched to a thread | from=%s | subject=%s",
            from_email, subject,
        )
        return {"status": "unmatched", "reason": "No matching thread found"}

    now = datetime.now(timezone.utc)
    msg = EmailMessage(
        thread_id=thread.id,
        user_id=thread.user_id,
        direction=EmailDirection.INBOUND,
        from_email=from_email,
        from_name=from_name,
        to_emails=_dump_json_list(to_emails),
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        sendgrid_message_id=message_id,
        status=EmailStatus.RECEIVED,
        received_at=now,
    )
    db.add(msg)
    _bump_thread_stats(thread, now)
    db.commit()
    db.refresh(msg)

    logger.info(
        "Inbound email stored | thread=%d | message=%d | from=%s",
        thread.id, msg.id, from_email,
    )
    return {"status": "ok", "thread_id": thread.id, "message_id": msg.id}
