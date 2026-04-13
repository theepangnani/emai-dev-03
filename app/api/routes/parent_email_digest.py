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
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.parent_gmail_integration import (
    ParentGmailIntegration,
    ParentDigestSettings,
    DigestDeliveryLog,
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
    except Exception:
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

        # Auto-create default digest settings in the same transaction
        default_settings = ParentDigestSettings(integration_id=integration.id)
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
