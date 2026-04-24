"""Parent email digest endpoints.

OAuth endpoints for connecting Gmail, plus CRUD for integrations,
digest settings, and delivery logs.
"""

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import requests as _requests
from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.parent_gmail_integration import (
    ParentGmailIntegration,
    ParentDigestSettings,
    DigestDeliveryLog,
    ParentDigestMonitoredEmail,
    ParentChildProfile,
    ParentChildSchoolEmail,
    ParentDigestMonitoredSender,
    SenderChildAssignment,
)
from app.models.user import User, UserRole
from app.schemas.parent_email_digest import (
    ParentGmailIntegrationResponse,
    ParentGmailIntegrationUpdate,
    ParentDigestSettingsResponse,
    ParentDigestSettingsUpdate,
    DigestDeliveryLogResponse,
    WhatsAppVerifyRequest,
    WhatsAppOTPRequest,
    MonitoredEmailCreate,
    MonitoredEmailResponse,
    MonitoredSenderCreate,
    MonitoredSenderAssignmentsUpdate,
    MonitoredSenderResponse,
    ChildSchoolEmailCreate,
    ChildSchoolEmailResponse,
    ChildProfileResponse,
)
from app.core.encryption import encrypt_token
from app.services.gmail_oauth_service import get_gmail_auth_url, exchange_gmail_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parent/email-digest", tags=["Parent Email Digest"])

ALLOWED_REDIRECT_DOMAINS = ["classbridge.ca", "www.classbridge.ca", "localhost"]


def _validate_redirect_uri(uri: str) -> bool:
    parsed = urlparse(uri)
    return parsed.hostname in ALLOWED_REDIRECT_DOMAINS


def _get_owned_integration(
    db: Session, integration_id: int, user_id: int
) -> ParentGmailIntegration:
    """Fetch an integration owned by the given user, or raise 404."""
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_id == user_id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


def _create_state(user_id: int) -> str:
    """Create a signed JWT state token for CSRF protection."""
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + 600,  # 10 min
        "type": "gmail_oauth",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _consume_state(state: str) -> dict | None:
    """Validate a JWT state token. Returns context or None."""
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "gmail_oauth":
            return None
        return {"user_id": payload["user_id"]}
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# OAuth schemas
# ---------------------------------------------------------------------------


class GmailAuthUrlResponse(BaseModel):
    authorization_url: str
    state: str


class GmailCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class GmailCallbackResponse(BaseModel):
    status: str
    gmail_address: str | None = None
    integration_id: int | None = None


class SendDigestResponse(BaseModel):
    status: str
    email_count: int
    message: str
    # #3880: per-channel outcomes; None = channel not requested, True = sent, False = failed.
    channel_status: dict[str, bool | None] | None = None
    # #3894: machine-readable reason for skipped status. One of
    # "already_delivered", "no_settings", "no_new_emails", "no_eligible_channels",
    # or None when status != "skipped". Frontends use this to gate UI — e.g.,
    # the "Open preferences" link only makes sense for "no_eligible_channels".
    reason: str | None = None


# ---------------------------------------------------------------------------
# OAuth endpoints
# ---------------------------------------------------------------------------


@router.get("/gmail/auth-url", response_model=GmailAuthUrlResponse)
def gmail_auth_url(
    request: Request,
    redirect_uri: str,
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Generate a Google OAuth URL for connecting Gmail (gmail.readonly scope).

    The frontend should redirect the user to the returned URL. After consent,
    Google will redirect back to the provided redirect_uri with a code and state.
    """
    if not _validate_redirect_uri(redirect_uri):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri domain",
        )
    state = _create_state(current_user.id)
    url = get_gmail_auth_url(redirect_uri=redirect_uri, state=state)
    return GmailAuthUrlResponse(authorization_url=url, state=state)


@router.post("/gmail/callback", response_model=GmailCallbackResponse)
def gmail_callback(
    request: Request,
    body: GmailCallbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Exchange the Google OAuth code for tokens and store the integration.

    Creates or updates a ParentGmailIntegration record linking the parent's
    ClassBridge account to their personal Gmail for email digest polling.
    """
    if not _validate_redirect_uri(body.redirect_uri):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri domain",
        )
    # Validate state
    state_ctx = _consume_state(body.state)
    if not state_ctx:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    if state_ctx["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OAuth state mismatch",
        )

    # Exchange code for tokens
    try:
        tokens = exchange_gmail_code(code=body.code, redirect_uri=body.redirect_uri)
    except (_requests.RequestException, ValueError, KeyError):
        logger.exception("Gmail OAuth token exchange failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange Gmail authorization code",
        )

    if not tokens.get("refresh_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token received. Please revoke ClassBridge access in your Google account settings and try again.",
        )

    # Get the Gmail address and Google ID from the access token
    userinfo = _get_gmail_userinfo(tokens["access_token"])
    gmail_address = userinfo.get("email") if userinfo else None
    google_id = userinfo.get("id", "") if userinfo else ""

    if not gmail_address:
        logger.warning("Gmail userinfo returned no email for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve your Gmail address from Google. Please try again.",
        )

    # Upsert: update if parent already has an integration, else create
    existing = (
        db.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.parent_id == current_user.id)
        .first()
    )
    if existing:
        existing.gmail_address = gmail_address
        existing.google_id = google_id
        existing.access_token = encrypt_token(tokens["access_token"])
        existing.refresh_token = encrypt_token(tokens["refresh_token"])
        existing.connected_at = datetime.now(timezone.utc)
        existing.is_active = True
        db.commit()
        return GmailCallbackResponse(status="ok", gmail_address=gmail_address, integration_id=existing.id)
    else:
        integration = ParentGmailIntegration(
            parent_id=current_user.id,
            gmail_address=gmail_address,
            google_id=google_id,
            access_token=encrypt_token(tokens["access_token"]),
            refresh_token=encrypt_token(tokens["refresh_token"]),
        )
        db.add(integration)
        db.flush()  # assign integration.id without committing

        # Auto-create default digest settings in the same transaction.
        # #3956: new parents default to the "sectioned" 3x3 format; existing
        # parents stay on their current format until migrated.
        default_settings = ParentDigestSettings(
            integration_id=integration.id,
            digest_format="sectioned",
        )
        db.add(default_settings)
        db.commit()

        return GmailCallbackResponse(status="ok", gmail_address=gmail_address, integration_id=integration.id)


def _get_gmail_userinfo(access_token: str) -> dict | None:
    """Fetch the authenticated user's info from Google userinfo endpoint."""
    try:
        resp = _requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.ok:
            return resp.json()
        logger.warning("Gmail userinfo returned %s: %s", resp.status_code, resp.text[:200])
    except _requests.RequestException:
        logger.exception("Failed to fetch Gmail userinfo")
    return None


# ---------------------------------------------------------------------------
# Integration CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/integrations", response_model=list[ParentGmailIntegrationResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_integrations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List the current parent's Gmail integrations."""
    integrations = (
        db.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.parent_id == current_user.id)
        .order_by(ParentGmailIntegration.created_at.desc())
        .all()
    )
    return integrations


@router.get("/integrations/{integration_id}", response_model=ParentGmailIntegrationResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_integration(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get a single Gmail integration by ID (ownership verified)."""
    return _get_owned_integration(db, integration_id, current_user.id)


@router.delete("/integrations/{integration_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_integration(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Disconnect/delete a Gmail integration."""
    integration = _get_owned_integration(db, integration_id, current_user.id)
    db.delete(integration)
    db.commit()


@router.patch("/integrations/{integration_id}", response_model=ParentGmailIntegrationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_integration(
    request: Request,
    integration_id: int,
    data: ParentGmailIntegrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Update integration details (child info, etc.)."""
    integration = _get_owned_integration(db, integration_id, current_user.id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(integration, field, value)
    db.commit()
    db.refresh(integration)
    return integration


@router.post("/integrations/{integration_id}/pause", response_model=ParentGmailIntegrationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def pause_integration(
    request: Request,
    integration_id: int,
    paused_until: Optional[datetime] = Query(
        None, description="ISO datetime until which the digest is paused. Omit for indefinite pause."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Pause digest delivery for an integration."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    # If no specific time given, pause indefinitely (far future)
    integration.paused_until = paused_until or datetime(2099, 12, 31, tzinfo=timezone.utc)
    db.commit()
    db.refresh(integration)
    return integration


@router.post("/integrations/{integration_id}/resume", response_model=ParentGmailIntegrationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def resume_integration(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Resume digest delivery for an integration (clear paused_until)."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    integration.paused_until = None
    db.commit()
    db.refresh(integration)
    return integration


# ---------------------------------------------------------------------------
# Monitored emails CRUD (#3178)
# ---------------------------------------------------------------------------


@router.get("/integrations/{integration_id}/monitored-emails", response_model=list[MonitoredEmailResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_monitored_emails(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List all monitored email addresses for an integration."""
    integration = _get_owned_integration(db, integration_id, current_user.id)
    return integration.monitored_emails


@router.post("/integrations/{integration_id}/monitored-emails", response_model=MonitoredEmailResponse, status_code=201)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def add_monitored_email(
    request: Request,
    integration_id: int,
    body: MonitoredEmailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Add an email address or sender name to monitor."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    # Check for duplicate on the combined (email_address, sender_name) tuple
    existing = (
        db.query(ParentDigestMonitoredEmail)
        .filter(
            ParentDigestMonitoredEmail.integration_id == integration.id,
            ParentDigestMonitoredEmail.email_address == body.email_address,
            ParentDigestMonitoredEmail.sender_name == body.sender_name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Monitored sender already exists")

    # Limit to 10 monitored entries per integration
    count = (
        db.query(ParentDigestMonitoredEmail)
        .filter(ParentDigestMonitoredEmail.integration_id == integration.id)
        .count()
    )
    if count >= 10:
        raise HTTPException(status_code=400, detail="Maximum of 10 monitored senders per integration")

    monitored = ParentDigestMonitoredEmail(
        integration_id=integration.id,
        email_address=body.email_address,
        sender_name=body.sender_name,
        label=body.label,
    )
    db.add(monitored)
    db.flush()

    # #4014 dual-write: mirror into unified v2 tables so new digest worker
    # sees the sender even if the legacy endpoint is still the write path.
    # Only dual-write when we have an email address (v2 keys on email).
    if body.email_address:
        _dual_write_sender_v2(
            db,
            parent_id=current_user.id,
            integration=integration,
            email_address=body.email_address,
            sender_name=body.sender_name,
            label=body.label,
        )

    db.commit()
    db.refresh(monitored)
    return monitored


def _dual_write_sender_v2(
    db: Session,
    *,
    parent_id: int,
    integration: ParentGmailIntegration,
    email_address: str,
    sender_name: Optional[str],
    label: Optional[str],
) -> None:
    """Mirror a legacy monitored-email write into the unified v2 tables.

    Find-or-create ParentDigestMonitoredSender on (parent_id, email_address),
    find the matching ParentChildProfile for the integration's
    child_first_name (case-insensitive), and create a SenderChildAssignment
    if both exist and no duplicate already does. Uses a SAVEPOINT
    (begin_nested) so a failure here rolls back only the v2 inserts — the
    outer legacy transaction stays healthy.
    """
    normalized_email = (email_address or "").strip().lower()
    if not normalized_email:
        return

    try:
        with db.begin_nested():
            sender = (
                db.query(ParentDigestMonitoredSender)
                .filter(
                    ParentDigestMonitoredSender.parent_id == parent_id,
                    ParentDigestMonitoredSender.email_address == normalized_email,
                )
                .first()
            )
            if sender is None:
                sender = ParentDigestMonitoredSender(
                    parent_id=parent_id,
                    email_address=normalized_email,
                    sender_name=sender_name,
                    label=label,
                    applies_to_all=False,
                )
                db.add(sender)
                db.flush()
            else:
                # Update label/sender_name if the caller provided new values.
                if sender_name and not sender.sender_name:
                    sender.sender_name = sender_name
                if label and not sender.label:
                    sender.label = label

            # Only link to a child profile if we have a first name on the
            # integration and a matching profile exists for this parent.
            first_name = (integration.child_first_name or "").strip()
            if not first_name:
                return

            from sqlalchemy import func as sa_func
            profile = (
                db.query(ParentChildProfile)
                .filter(
                    ParentChildProfile.parent_id == parent_id,
                    sa_func.lower(ParentChildProfile.first_name) == first_name.lower(),
                )
                .first()
            )
            if profile is None:
                return

            existing = (
                db.query(SenderChildAssignment)
                .filter(
                    SenderChildAssignment.sender_id == sender.id,
                    SenderChildAssignment.child_profile_id == profile.id,
                )
                .first()
            )
            if existing is None:
                db.add(SenderChildAssignment(
                    sender_id=sender.id,
                    child_profile_id=profile.id,
                ))
                db.flush()
    except Exception:
        logger.exception(
            "dual_write.failed | parent_id=%s integration_id=%s email=%s",
            parent_id,
            integration.id,
            email_address,
        )


@router.delete("/integrations/{integration_id}/monitored-emails/{email_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def remove_monitored_email(
    request: Request,
    integration_id: int,
    email_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Remove a monitored email address."""
    _get_owned_integration(db, integration_id, current_user.id)
    monitored = (
        db.query(ParentDigestMonitoredEmail)
        .filter(
            ParentDigestMonitoredEmail.id == email_id,
            ParentDigestMonitoredEmail.integration_id == integration_id,
        )
        .first()
    )
    if not monitored:
        raise HTTPException(status_code=404, detail="Monitored email not found")
    db.delete(monitored)
    db.commit()


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


@router.get("/settings/{integration_id}", response_model=ParentDigestSettingsResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_digest_settings(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get digest settings for a specific integration."""
    _get_owned_integration(db, integration_id, current_user.id)

    digest_settings = (
        db.query(ParentDigestSettings)
        .filter(ParentDigestSettings.integration_id == integration_id)
        .first()
    )
    if not digest_settings:
        raise HTTPException(status_code=404, detail="Digest settings not found")
    return digest_settings


@router.put("/settings/{integration_id}", response_model=ParentDigestSettingsResponse)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def update_digest_settings(
    request: Request,
    integration_id: int,
    data: ParentDigestSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Update digest settings (delivery_time, timezone, etc.) for an integration."""
    _get_owned_integration(db, integration_id, current_user.id)

    digest_settings = (
        db.query(ParentDigestSettings)
        .filter(ParentDigestSettings.integration_id == integration_id)
        .first()
    )
    if not digest_settings:
        raise HTTPException(status_code=404, detail="Digest settings not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(digest_settings, field, value)

    db.commit()
    db.refresh(digest_settings)
    return digest_settings


# ---------------------------------------------------------------------------
# Delivery log endpoints
# ---------------------------------------------------------------------------


@router.get("/logs", response_model=list[DigestDeliveryLogResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_delivery_logs(
    request: Request,
    integration_id: Optional[int] = Query(None, description="Filter by integration ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List delivery logs for the current parent (paginated, optionally filtered by integration)."""
    # Subquery for integration IDs owned by this parent (avoids loading all IDs into memory)
    parent_integration_ids_subquery = (
        db.query(ParentGmailIntegration.id)
        .filter(ParentGmailIntegration.parent_id == current_user.id)
        .subquery()
    )

    query = db.query(DigestDeliveryLog).filter(
        DigestDeliveryLog.integration_id.in_(parent_integration_ids_subquery)
    )

    if integration_id is not None:
        # Verify the integration belongs to this parent
        owns_integration = (
            db.query(ParentGmailIntegration.id)
            .filter(
                ParentGmailIntegration.id == integration_id,
                ParentGmailIntegration.parent_id == current_user.id,
            )
            .first()
        )
        if not owns_integration:
            raise HTTPException(status_code=403, detail="Not authorized to view logs for this integration")
        query = query.filter(DigestDeliveryLog.integration_id == integration_id)

    logs = (
        query.order_by(DigestDeliveryLog.delivered_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs


@router.get("/logs/{log_id}", response_model=DigestDeliveryLogResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_delivery_log(
    request: Request,
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get a single delivery log with full digest_content."""
    log = db.query(DigestDeliveryLog).filter(DigestDeliveryLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Delivery log not found")

    # Verify ownership via the integration
    _get_owned_integration(db, log.integration_id, current_user.id)

    return log


# ---------------------------------------------------------------------------
# Sync & forwarding verification endpoints
# ---------------------------------------------------------------------------


@router.post("/integrations/{integration_id}/send-digest", response_model=SendDigestResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def send_digest_now(
    request: Request,
    integration_id: int,
    # TEMPORARY (CB-TASKSYNC-001 MVP-1 pilot, follow-up #3929): the
    # `create_tasks` query param allows manual task creation for dedup
    # verification. §6.13.1 locks the contract that the HTTP "Send digest
    # now" endpoint MUST NOT create Tasks in production — this override is
    # strictly for pilot testing and MUST be removed before public launch
    # (see #3929). Defaults to False so production behaviour is preserved.
    create_tasks: bool = Query(
        False,
        description=(
            "TEMPORARY (CB-TASKSYNC-001 MVP-1 pilot, #3929) — opt-in task "
            "creation for dedup verification. Defaults False; must be "
            "removed before public launch."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> SendDigestResponse:
    integration = _get_owned_integration(db, integration_id, current_user.id)
    if not integration.is_active:
        raise HTTPException(
            status_code=400,
            detail="Integration is not active — please reconnect Gmail",
        )

    digest_settings = (
        db.query(ParentDigestSettings)
        .filter(ParentDigestSettings.integration_id == integration_id)
        .first()
    )
    if not digest_settings:
        raise HTTPException(status_code=404, detail="Digest settings not found")

    # Ensure digest_settings is loaded on the integration object
    integration.digest_settings = digest_settings

    from app.jobs.parent_email_digest_job import send_digest_for_integration

    if create_tasks:
        logger.warning(
            "task_sync.test_override | user_id=%s integration_id=%s — "
            "TEMPORARY: remove post-pilot (#3929)",
            current_user.id,
            integration.id,
        )

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await send_digest_for_integration(
        db,
        integration,
        skip_dedup=True,
        since=since_24h,
        create_tasks=create_tasks,
    )
    return result


@router.post("/integrations/{integration_id}/sync")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def trigger_manual_sync(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> dict:
    """Manually trigger email sync for an integration."""
    integration = _get_owned_integration(db, integration_id, current_user.id)
    if not integration.is_active:
        raise HTTPException(
            status_code=400,
            detail="Integration is not active — please reconnect Gmail",
        )

    from app.services.parent_gmail_service import fetch_child_emails

    emails = await fetch_child_emails(db, integration)
    return {"email_count": len(emails), "message": f"Synced {len(emails)} emails successfully"}


@router.post("/integrations/{integration_id}/verify-forwarding")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def verify_email_forwarding(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> dict:
    """Check if child's school email is forwarding to parent's Gmail."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    from app.services.parent_gmail_service import verify_forwarding

    result = await verify_forwarding(db, integration)
    return result


# ---------------------------------------------------------------------------
# WhatsApp endpoints (#2967)
# ---------------------------------------------------------------------------


@router.post("/integrations/{integration_id}/whatsapp/send-otp")
@limiter.limit("3/minute", key_func=get_user_id_or_ip)
def send_whatsapp_otp(
    request: Request,
    integration_id: int,
    body: WhatsAppVerifyRequest,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
) -> dict:
    """Send OTP to verify WhatsApp phone number."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    from app.services.whatsapp_service import generate_otp, send_otp, is_whatsapp_enabled
    if not is_whatsapp_enabled():
        raise HTTPException(status_code=503, detail="WhatsApp integration not configured")

    otp_code = generate_otp()
    integration.whatsapp_phone = body.phone
    integration.whatsapp_otp_code = otp_code
    integration.whatsapp_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    integration.whatsapp_verified = False
    db.commit()

    success = send_otp(body.phone, otp_code)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send OTP via WhatsApp")

    return {"message": "OTP sent to WhatsApp", "phone": body.phone}


@router.post("/integrations/{integration_id}/whatsapp/verify-otp")
@limiter.limit("3/minute", key_func=get_user_id_or_ip)
def verify_whatsapp_otp(
    request: Request,
    integration_id: int,
    body: WhatsAppOTPRequest,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
) -> dict:
    """Verify WhatsApp OTP code."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    if not integration.whatsapp_otp_code:
        raise HTTPException(status_code=400, detail="No OTP pending — send OTP first")

    if integration.whatsapp_otp_expires_at:
        expires = integration.whatsapp_otp_expires_at
        now = datetime.now(timezone.utc)
        # Handle naive datetimes from SQLite
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(status_code=400, detail="OTP expired — request a new code")

    if not secrets.compare_digest(integration.whatsapp_otp_code, body.otp_code):
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    integration.whatsapp_verified = True
    integration.whatsapp_otp_code = None
    integration.whatsapp_otp_expires_at = None

    # Add whatsapp to delivery channels if not already there
    digest_settings = integration.digest_settings
    if digest_settings and "whatsapp" not in (digest_settings.delivery_channels or ""):
        channels = digest_settings.delivery_channels or "in_app,email"
        digest_settings.delivery_channels = f"{channels},whatsapp"

    db.commit()
    return {"message": "WhatsApp verified successfully", "phone": integration.whatsapp_phone}


@router.delete("/integrations/{integration_id}/whatsapp")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def disconnect_whatsapp(
    request: Request,
    integration_id: int,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
) -> dict:
    """Remove WhatsApp from an integration."""
    integration = _get_owned_integration(db, integration_id, current_user.id)

    integration.whatsapp_phone = None
    integration.whatsapp_verified = False
    integration.whatsapp_otp_code = None
    integration.whatsapp_otp_expires_at = None

    # Remove whatsapp from delivery channels
    digest_settings = integration.digest_settings
    if digest_settings and digest_settings.delivery_channels:
        channels = [c.strip() for c in digest_settings.delivery_channels.split(",") if c.strip() != "whatsapp"]
        digest_settings.delivery_channels = ",".join(channels)

    db.commit()
    return {"message": "WhatsApp disconnected"}


# ---------------------------------------------------------------------------
# Unified Digest v2 — parent-level monitored senders (#4012, #4014)
# ---------------------------------------------------------------------------


def _sender_to_response(sender: ParentDigestMonitoredSender) -> MonitoredSenderResponse:
    """Shape a sender row + its assignments into the API response."""
    child_ids = [a.child_profile_id for a in sender.child_assignments]
    return MonitoredSenderResponse(
        id=sender.id,
        email_address=sender.email_address,
        sender_name=sender.sender_name,
        label=sender.label,
        applies_to_all=bool(sender.applies_to_all),
        child_profile_ids=child_ids,
        created_at=sender.created_at,
    )


def _apply_assignments(
    db: Session,
    sender: ParentDigestMonitoredSender,
    parent_id: int,
    child_profile_ids,
) -> None:
    """Replace a sender's child assignments.

    - If ``child_profile_ids == "all"``: mark applies_to_all=True and clear
      per-kid assignments.
    - Otherwise: validate each profile ID belongs to the parent, then
      replace the assignment set.
    """
    if child_profile_ids == "all":
        sender.applies_to_all = True
        for a in list(sender.child_assignments):
            db.delete(a)
        db.flush()
        return

    # Explicit list — validate ownership
    ids = list(dict.fromkeys(int(x) for x in (child_profile_ids or [])))  # dedupe, preserve order
    if ids:
        owned = (
            db.query(ParentChildProfile.id)
            .filter(
                ParentChildProfile.parent_id == parent_id,
                ParentChildProfile.id.in_(ids),
            )
            .all()
        )
        owned_ids = {row[0] for row in owned}
        missing = [i for i in ids if i not in owned_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Child profile(s) not found: {missing}",
            )

    sender.applies_to_all = False
    # Remove existing assignments not in the new set
    existing_by_profile = {a.child_profile_id: a for a in list(sender.child_assignments)}
    for pid, assignment in existing_by_profile.items():
        if pid not in ids:
            db.delete(assignment)
    # Add missing
    for pid in ids:
        if pid not in existing_by_profile:
            db.add(SenderChildAssignment(sender_id=sender.id, child_profile_id=pid))
    db.flush()


@router.get("/monitored-senders", response_model=list[MonitoredSenderResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_monitored_senders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List the current parent's monitored senders with their child assignments."""
    senders = (
        db.query(ParentDigestMonitoredSender)
        .options(selectinload(ParentDigestMonitoredSender.child_assignments))
        .filter(ParentDigestMonitoredSender.parent_id == current_user.id)
        .order_by(ParentDigestMonitoredSender.created_at.asc())
        .all()
    )
    return [_sender_to_response(s) for s in senders]


@router.post("/monitored-senders", response_model=MonitoredSenderResponse, status_code=201)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_or_update_monitored_sender(
    request: Request,
    body: MonitoredSenderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Create a new monitored sender for the parent, or update assignments if it exists.

    Dedupes on (parent_id, email_address). If the sender already exists, the
    child assignments are replaced with the provided set (same semantics as
    PATCH /monitored-senders/{id}/assignments).
    """
    sender = (
        db.query(ParentDigestMonitoredSender)
        .filter(
            ParentDigestMonitoredSender.parent_id == current_user.id,
            ParentDigestMonitoredSender.email_address == body.email_address,
        )
        .first()
    )
    if sender is None:
        sender = ParentDigestMonitoredSender(
            parent_id=current_user.id,
            email_address=body.email_address,
            sender_name=body.sender_name,
            label=body.label,
            applies_to_all=(body.child_profile_ids == "all"),
        )
        db.add(sender)
        db.flush()
    else:
        if body.sender_name is not None:
            sender.sender_name = body.sender_name
        if body.label is not None:
            sender.label = body.label

    _apply_assignments(db, sender, current_user.id, body.child_profile_ids)
    db.commit()
    db.refresh(sender)
    return _sender_to_response(sender)


@router.patch(
    "/monitored-senders/{sender_id}/assignments",
    response_model=MonitoredSenderResponse,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_sender_assignments(
    request: Request,
    sender_id: int,
    body: MonitoredSenderAssignmentsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Replace the child assignments for a monitored sender."""
    sender = (
        db.query(ParentDigestMonitoredSender)
        .filter(
            ParentDigestMonitoredSender.id == sender_id,
            ParentDigestMonitoredSender.parent_id == current_user.id,
        )
        .first()
    )
    if not sender:
        raise HTTPException(status_code=404, detail="Monitored sender not found")

    _apply_assignments(db, sender, current_user.id, body.child_profile_ids)
    db.commit()
    db.refresh(sender)
    return _sender_to_response(sender)


@router.delete("/monitored-senders/{sender_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_monitored_sender(
    request: Request,
    sender_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Delete a monitored sender (cascades to its child assignments)."""
    sender = (
        db.query(ParentDigestMonitoredSender)
        .filter(
            ParentDigestMonitoredSender.id == sender_id,
            ParentDigestMonitoredSender.parent_id == current_user.id,
        )
        .first()
    )
    if not sender:
        raise HTTPException(status_code=404, detail="Monitored sender not found")
    db.delete(sender)
    db.commit()


# ---------------------------------------------------------------------------
# Unified Digest v2 — parent-level child profiles + school emails (#4014)
# ---------------------------------------------------------------------------

profiles_router = APIRouter(prefix="/parent/child-profiles", tags=["Parent Child Profiles"])


def _get_owned_profile(db: Session, profile_id: int, parent_id: int) -> ParentChildProfile:
    profile = (
        db.query(ParentChildProfile)
        .filter(
            ParentChildProfile.id == profile_id,
            ParentChildProfile.parent_id == parent_id,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Child profile not found")
    return profile


@profiles_router.get("", response_model=list[ChildProfileResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_child_profiles(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List the caller's child profiles with nested school emails."""
    profiles = (
        db.query(ParentChildProfile)
        .options(selectinload(ParentChildProfile.school_emails))
        .filter(ParentChildProfile.parent_id == current_user.id)
        .order_by(ParentChildProfile.created_at.asc())
        .all()
    )
    return profiles


@profiles_router.post(
    "/{profile_id}/school-emails",
    response_model=ChildSchoolEmailResponse,
    status_code=201,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def add_child_school_email(
    request: Request,
    profile_id: int,
    body: ChildSchoolEmailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Add a school email to a child profile owned by the caller."""
    _get_owned_profile(db, profile_id, current_user.id)

    existing = (
        db.query(ParentChildSchoolEmail)
        .filter(
            ParentChildSchoolEmail.child_profile_id == profile_id,
            ParentChildSchoolEmail.email_address == body.email_address,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="School email already exists for this child")

    school_email = ParentChildSchoolEmail(
        child_profile_id=profile_id,
        email_address=body.email_address,
    )
    db.add(school_email)
    db.commit()
    db.refresh(school_email)
    return school_email


@profiles_router.delete(
    "/{profile_id}/school-emails/{email_id}",
    status_code=204,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_child_school_email(
    request: Request,
    profile_id: int,
    email_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Delete a school email from a child profile owned by the caller."""
    _get_owned_profile(db, profile_id, current_user.id)
    school_email = (
        db.query(ParentChildSchoolEmail)
        .filter(
            ParentChildSchoolEmail.id == email_id,
            ParentChildSchoolEmail.child_profile_id == profile_id,
        )
        .first()
    )
    if not school_email:
        raise HTTPException(status_code=404, detail="School email not found")
    db.delete(school_email)
    db.commit()
