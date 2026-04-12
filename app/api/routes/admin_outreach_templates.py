import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.parent_contact import OutreachTemplate
from app.models.user import User, UserRole
from app.schemas.outreach import (
    OutreachTemplateCreate,
    OutreachTemplateUpdate,
    OutreachTemplateResponse,
    OutreachTemplateListResponse,
    OutreachTemplatePreviewRequest,
    OutreachTemplatePreviewResponse,
)
from app.services.outreach_service import render_template_text, render_template_html

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/outreach-templates", tags=["Admin Outreach Templates"])


@router.get("", response_model=OutreachTemplateListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_templates(
    request: Request,
    template_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List outreach templates with optional filters."""
    query = db.query(OutreachTemplate)
    if template_type is not None:
        query = query.filter(OutreachTemplate.template_type == template_type)
    if is_active is not None:
        query = query.filter(OutreachTemplate.is_active == is_active)

    total = query.count()
    items = query.order_by(OutreachTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return OutreachTemplateListResponse(items=items, total=total)


@router.post("", response_model=OutreachTemplateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_template(
    request: Request,
    payload: OutreachTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new outreach template."""
    template = OutreachTemplate(
        name=payload.name,
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
        template_type=payload.template_type,
        variables=payload.variables,
        is_active=True,
        created_by_user_id=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=OutreachTemplateResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_template(
    request: Request,
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get a single outreach template."""
    template = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=OutreachTemplateResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_template(
    request: Request,
    template_id: int,
    payload: OutreachTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update an outreach template (partial update)."""
    template = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_template(
    request: Request,
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Soft-delete an outreach template (set is_active=false)."""
    template = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = False
    db.commit()
    return None


@router.post("/{template_id}/preview", response_model=OutreachTemplatePreviewResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def preview_template(
    request: Request,
    template_id: int,
    payload: OutreachTemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Render template with sample variables for preview."""
    template = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    variables = payload.variable_values

    rendered_subject = None
    if template.subject:
        rendered_subject = render_template_text(template.subject, variables)

    rendered_html = None
    if template.body_html:
        rendered_html = render_template_html(template.body_html, variables)

    rendered_text = render_template_text(template.body_text, variables)

    return OutreachTemplatePreviewResponse(
        rendered_subject=rendered_subject,
        rendered_html=rendered_html,
        rendered_text=rendered_text,
    )
