"""Daily Morning Email Digest endpoints for parents."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.briefing import DailyBriefingResponse
from app.services.daily_digest_service import (
    generate_daily_digest,
    send_daily_digest_email,
)

router = APIRouter(prefix="/digest", tags=["Digest"])


class DigestSendResponse(BaseModel):
    success: bool
    message: str


class UserSettingsUpdate(BaseModel):
    daily_digest_enabled: bool | None = None


class UserSettingsResponse(BaseModel):
    daily_digest_enabled: bool
    email_consent_date: str | None = None


# ── User settings endpoint ──────────────────────────────────


@router.patch("/settings", response_model=UserSettingsResponse, tags=["Users"])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_digest_settings(
    request: Request,
    body: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update digest-related user settings."""
    from datetime import datetime, timezone
    if body.daily_digest_enabled is not None:
        current_user.daily_digest_enabled = body.daily_digest_enabled
        # Track CASL consent
        if body.daily_digest_enabled:
            current_user.email_marketing_consent = True
            if not current_user.email_consent_date:
                current_user.email_consent_date = datetime.now(timezone.utc)
        else:
            current_user.email_marketing_consent = False
    db.commit()
    db.refresh(current_user)
    consent_date = current_user.email_consent_date.isoformat() if current_user.email_consent_date else None
    return UserSettingsResponse(
        daily_digest_enabled=current_user.daily_digest_enabled or False,
        email_consent_date=consent_date,
    )


@router.get("/settings", response_model=UserSettingsResponse, tags=["Users"])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_digest_settings(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get digest-related user settings."""
    consent_date = current_user.email_consent_date.isoformat() if current_user.email_consent_date else None
    return UserSettingsResponse(
        daily_digest_enabled=current_user.daily_digest_enabled or False,
        email_consent_date=consent_date,
    )


# ── Daily digest endpoints ──────────────────────────────────


@router.get("/daily/preview", response_model=DailyBriefingResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def daily_digest_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Preview the daily digest data as JSON."""
    return generate_daily_digest(db, current_user.id)


@router.post("/daily/send", response_model=DigestSendResponse)
@limiter.limit("3/hour", key_func=get_user_id_or_ip)
async def daily_digest_send(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Send the daily digest email to the parent immediately (for testing)."""
    success = await send_daily_digest_email(db, current_user.id, force=True)
    if success:
        return DigestSendResponse(success=True, message="Daily digest sent to your email!")
    return DigestSendResponse(success=False, message="Failed to send email. Please try again later.")
