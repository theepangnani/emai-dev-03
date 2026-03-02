"""Newsletter routes — create, generate, list, send, schedule, and template management."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User, UserRole
from app.schemas.newsletter import (
    NewsletterCreate,
    NewsletterUpdate,
    NewsletterResponse,
    NewsletterGenerateRequest,
    NewsletterScheduleRequest,
    NewsletterSendResponse,
    NewsletterTemplateResponse,
)
from app.services.newsletter_service import NewsletterService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/newsletters", tags=["newsletters"])

_service = NewsletterService()


def _admin_or_teacher(current_user: User = Depends(get_current_user)) -> User:
    if not (current_user.has_role(UserRole.ADMIN) or current_user.has_role(UserRole.TEACHER)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# Templates — must be registered BEFORE /{id} to avoid path conflicts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[NewsletterTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Return all active newsletter templates."""
    return _service.get_templates(db)


# ─────────────────────────────────────────────────────────────────────────────
# Newsletters CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=NewsletterResponse, status_code=status.HTTP_201_CREATED)
def create_newsletter(
    data: NewsletterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Create a new newsletter draft."""
    return _service.create_newsletter(current_user.id, data, db)


@router.post("/generate", response_model=NewsletterResponse, status_code=status.HTTP_201_CREATED)
def generate_newsletter(
    data: NewsletterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Use AI (GPT-4o-mini) to generate a newsletter draft."""
    try:
        return _service.generate_ai_newsletter(
            user_id=current_user.id,
            topic=data.topic,
            key_points=data.key_points,
            audience=data.audience,
            tone=data.tone,
            db=db,
        )
    except Exception as exc:
        logger.error(f"AI newsletter generation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(exc)}",
        )


@router.get("/", response_model=list[NewsletterResponse])
def list_newsletters(
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """List newsletters. Admins see all; teachers see their own."""
    return _service.get_newsletters(current_user.id, db)


@router.get("/{newsletter_id}", response_model=NewsletterResponse)
def get_newsletter(
    newsletter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Get a specific newsletter by ID."""
    newsletter = _service.get_newsletter(newsletter_id, db)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    # Only owner or admin can view
    if newsletter.created_by != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return newsletter


@router.patch("/{newsletter_id}", response_model=NewsletterResponse)
def update_newsletter(
    newsletter_id: int,
    data: NewsletterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Update a newsletter draft."""
    newsletter = _service.update_newsletter(newsletter_id, current_user.id, data, db)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found or not owned by you")
    return newsletter


@router.delete("/{newsletter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_newsletter(
    newsletter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Delete a draft newsletter. Sent newsletters cannot be deleted."""
    deleted = _service.delete_newsletter(newsletter_id, current_user.id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Newsletter not found, not owned by you, or already sent")


# ─────────────────────────────────────────────────────────────────────────────
# Send & schedule
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{newsletter_id}/send", response_model=NewsletterSendResponse)
def send_newsletter(
    newsletter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Send a newsletter immediately to all matching recipients."""
    try:
        result = _service.send_newsletter(newsletter_id, current_user.id, db)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Newsletter send failed id={newsletter_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Send failed: {str(exc)}")


@router.post("/{newsletter_id}/schedule", response_model=NewsletterResponse)
def schedule_newsletter(
    newsletter_id: int,
    data: NewsletterScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_or_teacher),
):
    """Schedule a newsletter for future delivery."""
    try:
        newsletter = _service.schedule_newsletter(newsletter_id, data.scheduled_at, current_user.id, db)
        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found or not owned by you")
        return newsletter
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
