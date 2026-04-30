"""Parent email digest endpoints.

OAuth endpoints for connecting Gmail, plus CRUD for integrations,
digest settings, and delivery logs.
"""

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests as _requests
from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
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
    ParentDiscoveredSchoolEmail,
    SenderChildAssignment,
)
from app.models.task import Task
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
    MonitoredSenderAssignmentResponse,
    MonitoredSenderResponse,
    ChildSchoolEmailCreate,
    ChildSchoolEmailResponse,
    ChildProfileResponse,
    DiscoveredSchoolEmailResponse,
    DiscoveredAssignBody,
    DiscoveredAssignResponse,
    DashboardResponse,
    DashboardKidView,
    DashboardUrgentItem,
    DashboardWeeklyDay,
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
    # #4434: present only on the unified V2 path. Counts of how each email was
    # attributed to a kid (school_email / sender_tag / applies_to_all /
    # parent_direct / sender_tag_ambiguous / unattributed). Legacy path leaves
    # this null.
    attribution_counts: dict[str, int] | None = None


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
    except Exception as exc:
        email_hash = hashlib.sha256(email_address.encode()).hexdigest()[:12]
        # #4057 — use logger.error with exc_info=False so the traceback
        # (which SQLAlchemy embeds bound params into, including the raw
        # email) is NOT written to logs. Message is defensively scrubbed.
        logger.error(
            "dual_write.failed | parent_id=%s integration_id=%s email_hash=%s exc_type=%s",
            parent_id,
            integration.id,
            email_hash,
            type(exc).__name__,
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
    # Ownership check applies to BOTH branches — `_get_owned_integration` is the
    # authz boundary (404 if not owned by current_user). Per-integration state
    # checks (is_active, digest_settings) are deferred into the legacy branch
    # (see #4450).
    integration = _get_owned_integration(db, integration_id, current_user.id)

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    # #4434: dispatch on the same flag the scheduled job uses (see
    # process_parent_email_digests in app/jobs/parent_email_digest_job.py).
    # Before this fix, the manual "Send Now" trigger always ran the legacy
    # per-integration path even after PR #4104 retired it as the default,
    # producing wall-of-text WhatsApp + per-integration emails that mixed
    # forwarded mail from multiple kids.
    from app.services.feature_flag_service import is_feature_enabled

    if is_feature_enabled("parent.unified_digest_v2", db=db):
        # #4450: under V2 the URL `integration_id` is a *triggering identity*,
        # not a scope — the unified worker covers ALL the parent's active
        # integrations. Don't gate on this integration's per-row `is_active`
        # or settings; a stale UI sending an inactive integration_id must
        # still succeed if other integrations are active.
        from app.jobs.parent_email_digest_job import send_unified_digest_for_parent

        # The unified path doesn't accept create_tasks — the #3929 task-sync
        # pilot only exists on the legacy worker. Warn so callers passing
        # ?create_tasks=true notice it's a no-op under V2. The
        # `task_sync.test_override` warning lives only on the legacy branch
        # below — it shouldn't double-log when create_tasks isn't honored.
        if create_tasks:
            logger.warning(
                "send_digest_now: ignoring create_tasks=true on unified V2 path "
                "| user_id=%s integration_id=%s",
                current_user.id,
                integration.id,
            )

        return await send_unified_digest_for_parent(
            db,
            current_user.id,
            skip_dedup=True,
            since=since_24h,
        )

    # Legacy branch: per-integration semantics still apply — validate THIS
    # integration specifically (#4450 keeps these checks here only).
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

    if create_tasks:
        logger.warning(
            "task_sync.test_override | user_id=%s integration_id=%s — "
            "TEMPORARY: remove post-pilot (#3929)",
            current_user.id,
            integration.id,
        )

    from app.jobs.parent_email_digest_job import send_digest_for_integration

    return await send_digest_for_integration(
        db,
        integration,
        skip_dedup=True,
        since=since_24h,
        create_tasks=create_tasks,
    )


# #4483 (D2/D3): parent-scoped manual "Send Now". The legacy
# `/integrations/{id}/send-digest` route remains for back-compat — it stays
# scoped to a single integration's identity. This new route is parent-scoped
# (no integration_id in the URL) and is what the unified UI should call so
# multi-kid parents always get the V2 multi-kid framing when the flag is on.
@router.post("/send-now", response_model=SendDigestResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def send_digest_now_parent_scoped(
    request: Request,
    since_hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Look-back window in hours, 1-168.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> SendDigestResponse:
    """Manual digest trigger across all of the parent's active integrations.

    Honours the ``parent.unified_digest_v2`` feature flag:

    * flag ON  → ONE envelope per parent via
      :func:`send_unified_digest_for_parent`, with multi-kid attribution-aware
      subject and body.
    * flag OFF → loops the parent's active integrations and falls back to the
      legacy per-integration :func:`send_digest_for_integration`.

    Used by the unified Email Digest page; the per-integration send route at
    ``POST /integrations/{integration_id}/send-digest`` remains for back-compat.
    """
    from app.services.feature_flag_service import is_feature_enabled
    from app.jobs.parent_email_digest_job import (
        send_unified_digest_for_parent,
        send_digest_for_integration,
    )

    since_dt = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    if is_feature_enabled("parent.unified_digest_v2", db=db):
        result = await send_unified_digest_for_parent(
            db,
            current_user.id,
            skip_dedup=True,
            since=since_dt,
        )
        # send_unified_digest_for_parent returns a plain dict; SendDigestResponse
        # tolerates the optional fields (channel_status / reason /
        # attribution_counts) and ignores any extras.
        if isinstance(result, dict):
            return SendDigestResponse(**result)
        return result

    # Legacy fallback: aggregate across all active integrations with digest
    # enabled. Per-integration dedup is bypassed (skip_dedup=True) because
    # this is an explicit manual trigger.
    integrations = (
        db.query(ParentGmailIntegration)
        .join(ParentDigestSettings)
        .filter(ParentGmailIntegration.parent_id == current_user.id)
        .filter(ParentGmailIntegration.is_active == True)  # noqa: E712
        .filter(ParentDigestSettings.digest_enabled == True)  # noqa: E712
        .all()
    )
    if not integrations:
        return SendDigestResponse(
            status="skipped",
            email_count=0,
            message="No active integrations to send digest for.",
            reason="no_integrations",
        )

    sent = 0
    skipped = 0
    failed = 0
    total_emails = 0
    for integ in integrations:
        result = await send_digest_for_integration(
            db,
            integ,
            skip_dedup=True,
            since=since_dt,
            create_tasks=False,
        )
        total_emails += int(result.get("email_count") or 0)
        per_status = result.get("status")
        if per_status == "delivered":
            sent += 1
        elif per_status == "skipped":
            skipped += 1
        else:
            failed += 1

    if sent > 0 and failed == 0:
        overall = "delivered"
    elif sent > 0:
        overall = "partial"
    elif failed > 0:
        overall = "failed"
    else:
        overall = "skipped"

    return SendDigestResponse(
        status=overall,
        email_count=total_emails,
        message=(
            f"{sent} delivered, {skipped} skipped, {failed} failed across "
            f"{len(integrations)} integration(s)."
        ),
    )


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

    fetch_result = await fetch_child_emails(db, integration)
    emails = fetch_result.get("emails", [])
    # #4058 — fetch_child_emails no longer auto-commits last_synced_at.
    # The manual-sync endpoint has no delivery-log step to bundle with, so
    # persist the fetch timestamp here directly.
    synced_at = fetch_result.get("synced_at")
    if synced_at is not None:
        integration.last_synced_at = synced_at
        db.commit()
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
    # #4082: include first_name alongside each ID so clients can render chips
    # without a second lookup. Requires child_profile to be eager-loaded.
    assignments = []
    for a in sender.child_assignments:
        if a.child_profile is None:
            # #4090: FK + cascade make this unreachable in healthy data.
            # Log instead of silently dropping so orphaned rows surface.
            logger.warning(
                "orphaned SenderChildAssignment id=%s sender_id=%s child_profile_id=%s",
                a.id, sender.id, a.child_profile_id,
            )
            continue
        assignments.append(
            MonitoredSenderAssignmentResponse(
                child_profile_id=a.child_profile_id,
                first_name=a.child_profile.first_name,
            )
        )
    return MonitoredSenderResponse(
        id=sender.id,
        email_address=sender.email_address,
        sender_name=sender.sender_name,
        label=sender.label,
        applies_to_all=bool(sender.applies_to_all),
        child_profile_ids=child_ids,
        assignments=assignments,
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
        .options(
            selectinload(ParentDigestMonitoredSender.child_assignments).selectinload(
                SenderChildAssignment.child_profile
            )
        )
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
# Auto-discovered school addresses (#4329)
# ---------------------------------------------------------------------------


@router.get(
    "/discovered-school-emails",
    response_model=list[DiscoveredSchoolEmailResponse],
)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_discovered_school_emails(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List unregistered school-looking To: addresses surfaced by the worker."""
    rows = (
        db.query(ParentDiscoveredSchoolEmail)
        .filter(ParentDiscoveredSchoolEmail.parent_id == current_user.id)
        .order_by(ParentDiscoveredSchoolEmail.last_seen_at.desc())
        .all()
    )
    return rows


@router.post(
    "/discovered-school-emails/{discovery_id}/assign",
    response_model=DiscoveredAssignResponse,
)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def assign_discovered_school_email(
    request: Request,
    discovery_id: int,
    body: DiscoveredAssignBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Move a discovered address into ``parent_child_school_emails``.

    Idempotent: if the address is already registered for the target
    profile, just delete the discovery row (no error).
    """
    discovery = (
        db.query(ParentDiscoveredSchoolEmail)
        .filter(
            ParentDiscoveredSchoolEmail.id == discovery_id,
            ParentDiscoveredSchoolEmail.parent_id == current_user.id,
        )
        .first()
    )
    if not discovery:
        raise HTTPException(status_code=404, detail="Discovered email not found")

    profile = (
        db.query(ParentChildProfile)
        .filter(
            ParentChildProfile.id == body.child_profile_id,
            ParentChildProfile.parent_id == current_user.id,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Child profile not found")

    # #4337 — Stage 1 match is case-insensitive, so storage must be lowercase.
    # `email_address` is NOT NULL on ParentDiscoveredSchoolEmail (#4347).
    normalized = discovery.email_address.strip().lower()
    existing = (
        db.query(ParentChildSchoolEmail)
        .filter(
            ParentChildSchoolEmail.child_profile_id == profile.id,
            ParentChildSchoolEmail.email_address == normalized,
        )
        .first()
    )
    if existing is None:
        db.add(ParentChildSchoolEmail(
            child_profile_id=profile.id,
            email_address=normalized,
        ))

    db.delete(discovery)
    db.commit()
    return {"status": "ok", "child_profile_id": profile.id}


@router.delete("/discovered-school-emails/{discovery_id}", status_code=204)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def dismiss_discovered_school_email(
    request: Request,
    discovery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Dismiss a discovered school address."""
    discovery = (
        db.query(ParentDiscoveredSchoolEmail)
        .filter(
            ParentDiscoveredSchoolEmail.id == discovery_id,
            ParentDiscoveredSchoolEmail.parent_id == current_user.id,
        )
        .first()
    )
    if not discovery:
        raise HTTPException(status_code=404, detail="Discovered email not found")
    db.delete(discovery)
    db.commit()


# ---------------------------------------------------------------------------
# Email Digest Dashboard (CB-EDIGEST-002 E1, #4589)
#
# Single aggregated read-only endpoint powering the parent dashboard at
# `/email-digest`. Combines:
#   - per-kid urgent items (Tasks due today or overdue, not completed)
#   - per-kid weekly deadlines (Mon-Sun grid for the current week)
#   - empty-state sentinels (no_kids / paused / auth_expired / first_run / calm)
#   - last_digest_at + refreshed_at timestamps
#
# Designed for high polling frequency (60/min) — no AI calls, no Gmail
# fetches; reads only from existing tables.
# ---------------------------------------------------------------------------


def _dashboard_empty_state(
    db: Session,
    *,
    parent_id: int,
    profile_count: int,
    integrations: list[ParentGmailIntegration],
    now: datetime,
    has_any_urgent: bool,
) -> Optional[str]:
    """Resolve the dashboard's empty_state per the priority list.

    Priority order (first match wins):
      1. ``no_kids`` — 0 ParentChildProfile rows for the parent.
      2. ``paused`` — every integration is inactive OR currently paused.
      3. ``auth_expired`` — reserved sentinel (no token-failure column exists
         yet on ParentGmailIntegration; we never return this today). Filed as
         a follow-up so the contract is stable while detection lands.
      4. ``first_run`` — no DigestDeliveryLog row has ever been written for
         this parent.
      5. ``calm`` — kids exist but none have urgent items today.
      6. ``None`` — normal content renders.
    """
    if profile_count == 0:
        return "no_kids"

    # Treat an integration as "paused" if either (a) it has been deactivated
    # (is_active=False) or (b) paused_until is set and still in the future.
    if integrations:
        all_paused = True
        for integ in integrations:
            if not integ.is_active:
                continue
            paused_until = integ.paused_until
            if paused_until is not None:
                # Tolerate naive datetimes from SQLite by promoting to UTC.
                if paused_until.tzinfo is None:
                    paused_until = paused_until.replace(tzinfo=timezone.utc)
                if paused_until > now:
                    continue
            all_paused = False
            break
        if all_paused:
            return "paused"
    else:
        # No integrations at all is treated as paused — the dashboard cannot
        # surface fresh data without at least one connected mailbox.
        return "paused"

    # auth_expired detection is intentionally a no-op until a failure column
    # exists on ParentGmailIntegration. See follow-up on the PR for tracking.

    has_log = (
        db.query(DigestDeliveryLog.id)
        .filter(DigestDeliveryLog.parent_id == parent_id)
        .first()
        is not None
    )
    if not has_log:
        return "first_run"

    if not has_any_urgent:
        return "calm"

    return None


def _build_kid_view(
    *,
    profile: ParentChildProfile,
    tasks_for_kid: list,
    today_end_utc: datetime,
    week_start_utc: datetime,
    week_end_utc: datetime,
    parent_tz: ZoneInfo,
) -> DashboardKidView:
    """Shape a kid's tasks into the dashboard's per-kid response payload.

    `tasks_for_kid` must already be filtered to the kid's assignee_id and
    pre-loaded with the ``course`` relationship. The function does NO DB
    work — partitions tasks by today vs. week and builds the day buckets.

    ``parent_tz`` is used to compute the day-bucket key in the parent's
    local zone so a task due 9 PM EDT on the 30th doesn't bucket into
    "May 1" because the UTC date has already rolled (#4630).
    """
    urgent_items: list[DashboardUrgentItem] = []
    week_buckets: dict[str, list[DashboardUrgentItem]] = {}

    for task in tasks_for_kid:
        due = task.due_date
        if due is None:
            # Tasks without a due date can't be scheduled into today/week.
            continue
        if due.tzinfo is None:
            due_utc = due.replace(tzinfo=timezone.utc)
        else:
            due_utc = due.astimezone(timezone.utc)

        item = DashboardUrgentItem(
            id=str(task.id),
            title=task.title,
            due_date=due_utc,
            course_or_context=(task.course.name if task.course else task.category),
            source_email_id=task.source_message_id,
        )

        # Urgent = due today or overdue (and still open — caller filters
        # is_completed/archived_at upstream).
        if due_utc <= today_end_utc:
            urgent_items.append(item)

        # Weekly bucket: the calendar day key is computed in the parent's
        # local timezone so it lines up with the date the parent sees on
        # their calendar (#4630). The response stays timezone-stable
        # because each ``due_date`` is still emitted in UTC.
        if week_start_utc <= due_utc <= week_end_utc:
            day_key = due_utc.astimezone(parent_tz).date().isoformat()
            week_buckets.setdefault(day_key, []).append(item)

    # Stable ordering inside each bucket: earliest due first, then title.
    urgent_items.sort(key=lambda i: (i.due_date or today_end_utc, i.title))
    weekly_deadlines = [
        DashboardWeeklyDay(
            day=day,
            items=sorted(items, key=lambda i: (i.due_date or today_end_utc, i.title)),
        )
        for day, items in sorted(week_buckets.items())
    ]

    return DashboardKidView(
        id=profile.id,
        first_name=profile.first_name,
        urgent_items=urgent_items,
        weekly_deadlines=weekly_deadlines,
        all_clear=(len(urgent_items) == 0),
    )


@router.get("/dashboard", response_model=DashboardResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_email_digest_dashboard(
    request: Request,
    # Pass-1 review I4: validate `since` as a Literal so unknown values
    # return 422 rather than being silently accepted. Reserved for a
    # future 'week' / ISO-date variant — extend the Literal at that
    # point so existing clients keep working.
    since: Literal["today"] = Query(
        "today",
        description=(
            "Time scope for the dashboard view. Currently only 'today' is "
            "supported; reserved for a future 'week' / ISO-date variant."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
) -> DashboardResponse:
    """Aggregated parent dashboard view — urgent today + week + empty states.

    Read-only; safe to poll. Powers the post-login destination at
    ``/email-digest``. See ``docs/design/CB-EDIGEST-002-prd.md`` §F1-F6.
    """
    # Resolve parent timezone (#4630). Every Ontario user is on UTC-4/-5,
    # so computing today/week boundaries in UTC drops evening deadlines
    # from the urgent list and shows next-morning tasks as "today" during
    # certain hours. Look up the configured timezone from any of this
    # parent's ParentDigestSettings rows; fall back to America/Toronto
    # (the install default) if missing or invalid.
    parent_tz_name = "America/Toronto"
    digest_settings_row = (
        db.query(ParentDigestSettings)
        .join(
            ParentGmailIntegration,
            ParentGmailIntegration.id == ParentDigestSettings.integration_id,
        )
        .filter(ParentGmailIntegration.parent_id == current_user.id)
        .first()
    )
    if digest_settings_row and digest_settings_row.timezone:
        parent_tz_name = digest_settings_row.timezone

    try:
        parent_tz = ZoneInfo(parent_tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        # Defensive fallback — never 500 on a bad/typo'd tz string.
        parent_tz = ZoneInfo("America/Toronto")

    now_local = datetime.now(parent_tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_local = today_start_local + timedelta(days=1) - timedelta(microseconds=1)
    # Week window: rolling 7 days starting today. Matches PRD §F2 ("this
    # week's deadlines"); past-week styling is a frontend concern.
    week_end_local = (today_start_local + timedelta(days=7)) - timedelta(microseconds=1)

    # Convert to UTC once for DB filtering + comparison; response stays
    # in UTC (the contract callers already rely on).
    today_start = today_start_local.astimezone(timezone.utc)
    today_end = today_end_local.astimezone(timezone.utc)
    week_end = week_end_local.astimezone(timezone.utc)
    now = now_local.astimezone(timezone.utc)

    # Profiles + integrations are needed for both content and empty-state
    # resolution; load both regardless of the eventual return path so the
    # priority logic always has full inputs.
    profiles = (
        db.query(ParentChildProfile)
        .filter(ParentChildProfile.parent_id == current_user.id)
        .order_by(ParentChildProfile.created_at.asc())
        .all()
    )
    integrations = (
        db.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.parent_id == current_user.id)
        .all()
    )

    # Pull every relevant Task for the parent's kids in one query, then
    # partition in Python — avoids N+1 across kids.
    assignee_ids = [p.student_id for p in profiles if p.student_id is not None]
    tasks_by_assignee: dict[int, list] = {aid: [] for aid in assignee_ids}
    if assignee_ids:
        tasks = (
            db.query(Task)
            .options(selectinload(Task.course))
            .filter(
                Task.assigned_to_user_id.in_(assignee_ids),
                Task.is_completed == False,  # noqa: E712
                Task.archived_at.is_(None),
                Task.due_date.isnot(None),
                Task.due_date <= week_end,
            )
            .all()
        )
        for t in tasks:
            tasks_by_assignee.setdefault(t.assigned_to_user_id, []).append(t)

    # Build per-kid views. Profiles without a linked student_id render with
    # an empty bucket — the dashboard still shows the kid card, just no
    # data until the link is established.
    kids: list[DashboardKidView] = []
    for profile in profiles:
        kid_tasks = (
            tasks_by_assignee.get(profile.student_id, [])
            if profile.student_id is not None
            else []
        )
        kids.append(
            _build_kid_view(
                profile=profile,
                tasks_for_kid=kid_tasks,
                today_end_utc=today_end,
                week_start_utc=today_start,
                week_end_utc=week_end,
                parent_tz=parent_tz,
            )
        )

    # PRD §F6 — kid section with most urgent items first; ties break by
    # creation order (already the input order).
    kids.sort(key=lambda k: -len(k.urgent_items))

    has_any_urgent = any(len(k.urgent_items) > 0 for k in kids)
    empty_state = _dashboard_empty_state(
        db,
        parent_id=current_user.id,
        profile_count=len(profiles),
        integrations=integrations,
        now=now,
        has_any_urgent=has_any_urgent,
    )

    last_log = (
        db.query(DigestDeliveryLog.delivered_at)
        .filter(DigestDeliveryLog.parent_id == current_user.id)
        .order_by(DigestDeliveryLog.delivered_at.desc())
        .first()
    )
    last_digest_at = last_log[0] if last_log else None

    return DashboardResponse(
        kids=kids,
        empty_state=empty_state,
        refreshed_at=now,
        last_digest_at=last_digest_at,
    )


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


class ChildProfileCreate(BaseModel):
    first_name: str
    student_id: int | None = None


@profiles_router.post("", response_model=ChildProfileResponse, status_code=201)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_child_profile(
    request: Request,
    body: ChildProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Create a child profile (#4044).

    Idempotent dedupe:
    - When `student_id` is provided, verify the caller is linked to that
      student and dedupe on (parent_id, student_id).
    - Otherwise, dedupe on (parent_id, LOWER(first_name)) — matches the
      functional unique index used by the v2 dual-write path.
    """
    from sqlalchemy import func as sa_func

    first_name = body.first_name.strip()
    if not first_name:
        raise HTTPException(status_code=422, detail="first_name is required")

    # Dedupe path 1: by student_id (when provided).
    if body.student_id is not None:
        from app.models.student import parent_students, Student

        link = db.execute(
            parent_students.select()
            .join(Student, Student.id == parent_students.c.student_id)
            .where(
                parent_students.c.parent_id == current_user.id,
                Student.user_id == body.student_id,
            )
        ).first()
        if link is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found or not linked to this parent",
            )

        existing = (
            db.query(ParentChildProfile)
            .options(selectinload(ParentChildProfile.school_emails))
            .filter(
                ParentChildProfile.parent_id == current_user.id,
                ParentChildProfile.student_id == body.student_id,
            )
            .first()
        )
        if existing:
            return existing

    # Dedupe path 2: by (parent_id, LOWER(first_name)).
    existing = (
        db.query(ParentChildProfile)
        .options(selectinload(ParentChildProfile.school_emails))
        .filter(
            ParentChildProfile.parent_id == current_user.id,
            sa_func.lower(ParentChildProfile.first_name) == first_name.lower(),
        )
        .first()
    )
    if existing:
        return existing

    profile = ParentChildProfile(
        parent_id=current_user.id,
        student_id=body.student_id,
        first_name=first_name,
    )
    db.add(profile)
    # #4100 pass-1 review:
    # - Catch IntegrityError so a race between two concurrent POSTs (or
    #   between this and the unified worker's auto-create path) doesn't
    #   500 the second caller. The functional unique index on
    #   (parent_id, LOWER(first_name)) and the unique constraint on
    #   (parent_id, student_id) both guarantee at most one row exists;
    #   on collision we re-fetch and return the winner.
    # - Eager-load school_emails so the Pydantic response serializer
    #   doesn't issue a lazy SELECT after refresh.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = (
            db.query(ParentChildProfile)
            .options(selectinload(ParentChildProfile.school_emails))
            .filter(
                ParentChildProfile.parent_id == current_user.id,
                or_(
                    sa_func.lower(ParentChildProfile.first_name) == first_name.lower(),
                    *(
                        [ParentChildProfile.student_id == body.student_id]
                        if body.student_id is not None
                        else []
                    ),
                ),
            )
            .first()
        )
        if winner is None:
            # Should be unreachable — unique constraint fired but no row
            # matches our dedupe predicates. Surface for ops visibility.
            raise HTTPException(
                status_code=500,
                detail="Profile create raced with a concurrent insert that could not be reconciled.",
            )
        return winner

    db.refresh(profile)
    # Initialize the empty relationship explicitly so Pydantic
    # `from_attributes=True` doesn't lazy-load (matches dedupe paths).
    profile.school_emails = []
    return profile


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
            ParentChildSchoolEmail.email_address == body.email_address.strip().lower(),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="School email already exists for this child")

    school_email = ParentChildSchoolEmail(
        child_profile_id=profile_id,
        email_address=body.email_address.strip().lower(),
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
