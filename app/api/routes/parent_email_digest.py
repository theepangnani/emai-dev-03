from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip

# Stub imports — models and schemas are being created in a parallel branch.
# These will resolve once that branch is merged.
from app.models.parent_gmail_integration import (
    ParentGmailIntegration,
    ParentDigestSettings,
    DigestDeliveryLog,
)
from app.schemas.parent_email_digest import (
    IntegrationResponse,
    DigestSettingsResponse,
    DigestSettingsUpdate,
    DeliveryLogResponse,
    DeliveryLogDetailResponse,
)

router = APIRouter(prefix="/parent/email-digest", tags=["Parent Email Digest"])


# ---------------------------------------------------------------------------
# Integration endpoints
# ---------------------------------------------------------------------------


@router.get("/integrations", response_model=list[IntegrationResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_integrations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List the current parent's Gmail integrations."""
    integrations = (
        db.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.parent_user_id == current_user.id)
        .order_by(ParentGmailIntegration.created_at.desc())
        .all()
    )
    return integrations


@router.get("/integrations/{integration_id}", response_model=IntegrationResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_integration(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get a single Gmail integration by ID (ownership verified)."""
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.delete("/integrations/{integration_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_integration(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Disconnect/delete a Gmail integration."""
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integration)
    db.commit()


@router.post("/integrations/{integration_id}/pause", response_model=IntegrationResponse)
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
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # If no specific time given, pause indefinitely (far future)
    integration.paused_until = paused_until or datetime(2099, 12, 31, tzinfo=timezone.utc)
    db.commit()
    db.refresh(integration)
    return integration


@router.post("/integrations/{integration_id}/resume", response_model=IntegrationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def resume_integration(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Resume digest delivery for an integration (clear paused_until)."""
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.paused_until = None
    db.commit()
    db.refresh(integration)
    return integration


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


@router.get("/settings/{integration_id}", response_model=DigestSettingsResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_digest_settings(
    request: Request,
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get digest settings for a specific integration."""
    # Verify integration ownership first
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    settings = (
        db.query(ParentDigestSettings)
        .filter(ParentDigestSettings.integration_id == integration_id)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=404, detail="Digest settings not found")
    return settings


@router.put("/settings/{integration_id}", response_model=DigestSettingsResponse)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def update_digest_settings(
    request: Request,
    integration_id: int,
    data: DigestSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Update digest settings (delivery_time, timezone, etc.) for an integration."""
    # Verify integration ownership first
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    settings = (
        db.query(ParentDigestSettings)
        .filter(ParentDigestSettings.integration_id == integration_id)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=404, detail="Digest settings not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings


# ---------------------------------------------------------------------------
# Delivery log endpoints
# ---------------------------------------------------------------------------


@router.get("/logs", response_model=list[DeliveryLogResponse])
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
    # Get all integration IDs owned by this parent
    parent_integration_ids = [
        row[0]
        for row in db.query(ParentGmailIntegration.id)
        .filter(ParentGmailIntegration.parent_user_id == current_user.id)
        .all()
    ]
    if not parent_integration_ids:
        return []

    query = db.query(DigestDeliveryLog).filter(
        DigestDeliveryLog.integration_id.in_(parent_integration_ids)
    )

    if integration_id is not None:
        if integration_id not in parent_integration_ids:
            raise HTTPException(status_code=403, detail="Not authorized to view logs for this integration")
        query = query.filter(DigestDeliveryLog.integration_id == integration_id)

    logs = (
        query.order_by(DigestDeliveryLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs


@router.get("/logs/{log_id}", response_model=DeliveryLogDetailResponse)
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
    integration = (
        db.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.id == log.integration_id,
            ParentGmailIntegration.parent_user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Delivery log not found")

    return log
