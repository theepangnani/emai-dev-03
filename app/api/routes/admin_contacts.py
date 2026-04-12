import logging
from datetime import datetime, timezone, timedelta
from io import StringIO
import csv

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.utils import escape_like
from app.db.database import get_db
from app.models.parent_contact import ParentContact, ParentContactNote, OutreachLog
from app.models.user import User, UserRole
from app.schemas.parent_contact import (
    ParentContactCreate, ParentContactUpdate, ParentContactResponse,
    ParentContactListResponse, ParentContactStats,
    ContactNoteCreate, ContactNoteResponse,
    BulkDeleteRequest, BulkStatusRequest, BulkTagRequest,
)
from app.schemas.outreach import DuplicateGroupResponse, OutreachLogResponse, OutreachLogListResponse
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/contacts", tags=["Admin Contacts"])


# ── List Contacts ──────────────────────────────────────────────────────────
@router.get("", response_model=ParentContactListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def list_contacts(
    request: Request,
    search: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    school: str | None = Query(None),
    tag: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    query = db.query(ParentContact)

    if search:
        pattern = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                ParentContact.full_name.ilike(pattern),
                ParentContact.email.ilike(pattern),
                ParentContact.school_name.ilike(pattern),
                ParentContact.child_name.ilike(pattern),
            )
        )

    if status_filter:
        query = query.filter(ParentContact.status == status_filter)

    if school:
        query = query.filter(ParentContact.school_name.ilike(f"%{escape_like(school)}%"))

    # Get total before tag filtering (tag filter is Python-side for SQLite JSON compat)
    if tag:
        from app.core.config import settings
        if "sqlite" not in settings.database_url:
            from sqlalchemy import text
            query = query.filter(text("tags::jsonb @> :tag_arr").bindparams(tag_arr=f'["{tag}"]'))
            total = query.count()
            items = query.order_by(ParentContact.created_at.desc()).offset(skip).limit(limit).all()
        else:
            all_contacts = query.order_by(ParentContact.created_at.desc()).limit(5000).all()
            filtered = [c for c in all_contacts if c.tags and tag in c.tags]
            total = len(filtered)
            items = filtered[skip:skip + limit]
    else:
        total = query.count()
        items = query.order_by(ParentContact.created_at.desc()).offset(skip).limit(limit).all()

    return ParentContactListResponse(
        items=[ParentContactResponse.model_validate(c) for c in items],
        total=total,
    )


# ── Stats ──────────────────────────────────────────────────────────────────
@router.get("/stats", response_model=ParentContactStats)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    total = db.query(func.count(ParentContact.id)).scalar() or 0

    status_rows = (
        db.query(ParentContact.status, func.count(ParentContact.id))
        .group_by(ParentContact.status)
        .all()
    )
    by_status = {row[0]: row[1] for row in status_rows}

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_outreach_count = (
        db.query(func.count(OutreachLog.id))
        .filter(OutreachLog.created_at >= seven_days_ago)
        .scalar() or 0
    )

    contacts_without_consent = (
        db.query(func.count(ParentContact.id))
        .filter(ParentContact.consent_given == False)  # noqa: E712
        .scalar() or 0
    )

    return ParentContactStats(
        total=total,
        by_status=by_status,
        recent_outreach_count=recent_outreach_count,
        contacts_without_consent=contacts_without_consent,
    )


# ── Duplicates ─────────────────────────────────────────────────────────────
@router.get("/duplicates", response_model=list[DuplicateGroupResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def get_duplicates(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    dup_emails = (
        db.query(ParentContact.email)
        .filter(ParentContact.email.isnot(None))
        .group_by(ParentContact.email)
        .having(func.count(ParentContact.id) > 1)
        .all()
    )

    groups = []
    for (email,) in dup_emails:
        contacts = db.query(ParentContact).filter(ParentContact.email == email).all()
        groups.append(DuplicateGroupResponse(
            email=email,
            contacts=[ParentContactResponse.model_validate(c) for c in contacts],
        ))

    return groups


# ── Export CSV ─────────────────────────────────────────────────────────────
@router.get("/export/csv")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def export_csv(
    request: Request,
    search: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    school: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    query = db.query(ParentContact)

    if search:
        pattern = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                ParentContact.full_name.ilike(pattern),
                ParentContact.email.ilike(pattern),
                ParentContact.school_name.ilike(pattern),
                ParentContact.child_name.ilike(pattern),
            )
        )

    if status_filter:
        query = query.filter(ParentContact.status == status_filter)

    if school:
        query = query.filter(ParentContact.school_name.ilike(f"%{escape_like(school)}%"))

    MAX_CSV_ROWS = 10000
    contacts = query.order_by(ParentContact.created_at.desc()).limit(MAX_CSV_ROWS).all()
    truncated = len(contacts) == MAX_CSV_ROWS

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Full Name", "Email", "Phone", "School", "Child Name",
        "Child Grade", "Status", "Source", "Consent Given", "Tags", "Created At",
    ])
    for c in contacts:
        tags_str = ", ".join(c.tags) if c.tags else ""
        writer.writerow([
            c.full_name, c.email or "", c.phone or "", c.school_name or "",
            c.child_name or "", c.child_grade or "", c.status, c.source,
            str(c.consent_given), tags_str,
            c.created_at.isoformat() if c.created_at else "",
        ])

    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=contacts_export.csv"}
    if truncated:
        headers["X-Truncated"] = f"true; limit={MAX_CSV_ROWS}"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers=headers,
    )


# ── Create Contact ─────────────────────────────────────────────────────────
@router.post("", response_model=ParentContactResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def create_contact(
    request: Request,
    data: ParentContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    # Check for duplicate email (non-blocking warning via header)
    duplicate_warning = None
    if data.email:
        existing = db.query(ParentContact).filter(ParentContact.email == data.email).first()
        if existing:
            duplicate_warning = f"Contact with email {data.email} already exists (id={existing.id})"

    contact = ParentContact(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        school_name=data.school_name,
        child_name=data.child_name,
        child_grade=data.child_grade,
        status=data.status,
        source=data.source,
        tags=data.tags,
        consent_given=data.consent_given,
        consent_date=datetime.now(timezone.utc) if data.consent_given else None,
        created_by_user_id=current_user.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    log_action(
        db,
        user_id=current_user.id,
        action="contact_create",
        resource_type="parent_contact",
        resource_id=contact.id,
        details=f"Created contact: {contact.full_name}",
    )

    response_data = ParentContactResponse.model_validate(contact)
    if duplicate_warning:
        logger.warning(duplicate_warning)
        return JSONResponse(
            content=response_data.model_dump(mode="json"),
            status_code=201,
            headers={"X-Duplicate-Warning": duplicate_warning},
        )
    return response_data


# ── Get Single Contact ─────────────────────────────────────────────────────
@router.get("/{contact_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def get_contact(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contact = db.query(ParentContact).filter(ParentContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    response = ParentContactResponse.model_validate(contact)
    # Attach notes and outreach as extra data
    notes = (
        db.query(ParentContactNote)
        .filter(ParentContactNote.parent_contact_id == contact_id)
        .order_by(ParentContactNote.created_at.desc())
        .limit(50)
        .all()
    )
    outreach = (
        db.query(OutreachLog)
        .filter(OutreachLog.parent_contact_id == contact_id)
        .order_by(OutreachLog.created_at.desc())
        .limit(20)
        .all()
    )
    # Return as dict with extra fields
    result = response.model_dump()
    result["notes"] = [ContactNoteResponse.model_validate(n).model_dump() for n in notes]
    result["outreach_logs"] = [OutreachLogResponse.model_validate(o).model_dump() for o in outreach]
    return result


# ── Update Contact ─────────────────────────────────────────────────────────
@router.patch("/{contact_id}", response_model=ParentContactResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def update_contact(
    request: Request,
    contact_id: int,
    data: ParentContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contact = db.query(ParentContact).filter(ParentContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    # Auto-set consent_date if consent_given changes to True
    if data.consent_given is True and contact.consent_date is None:
        contact.consent_date = datetime.now(timezone.utc)

    db.commit()
    db.refresh(contact)

    log_action(
        db,
        user_id=current_user.id,
        action="contact_update",
        resource_type="parent_contact",
        resource_id=contact.id,
        details=f"Updated contact: {contact.full_name}",
    )

    return ParentContactResponse.model_validate(contact)


# ── Delete Contact ─────────────────────────────────────────────────────────
@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def delete_contact(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contact = db.query(ParentContact).filter(ParentContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact_name = contact.full_name
    db.delete(contact)
    db.commit()

    log_action(
        db,
        user_id=current_user.id,
        action="contact_delete",
        resource_type="parent_contact",
        resource_id=contact_id,
        details=f"Deleted contact: {contact_name}",
    )


# ── List Notes ─────────────────────────────────────────────────────────────
@router.get("/{contact_id}/notes", response_model=list[ContactNoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def list_notes(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contact = db.query(ParentContact).filter(ParentContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    notes = (
        db.query(ParentContactNote)
        .filter(ParentContactNote.parent_contact_id == contact_id)
        .order_by(ParentContactNote.created_at.desc())
        .all()
    )
    return [ContactNoteResponse.model_validate(n) for n in notes]


# ── Add Note ───────────────────────────────────────────────────────────────
@router.post("/{contact_id}/notes", response_model=ContactNoteResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def add_note(
    request: Request,
    contact_id: int,
    data: ContactNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contact = db.query(ParentContact).filter(ParentContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    note = ParentContactNote(
        parent_contact_id=contact_id,
        note_text=data.note_text,
        created_by_user_id=current_user.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return ContactNoteResponse.model_validate(note)


# ── Delete Note ────────────────────────────────────────────────────────────
@router.delete("/{contact_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def delete_note(
    request: Request,
    contact_id: int,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    note = (
        db.query(ParentContactNote)
        .filter(ParentContactNote.id == note_id, ParentContactNote.parent_contact_id == contact_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    db.delete(note)
    db.commit()


# ── Outreach History ───────────────────────────────────────────────────────
@router.get("/{contact_id}/outreach-history", response_model=OutreachLogListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def outreach_history(
    request: Request,
    contact_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contact = db.query(ParentContact).filter(ParentContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    query = (
        db.query(OutreachLog)
        .filter(OutreachLog.parent_contact_id == contact_id)
        .order_by(OutreachLog.created_at.desc())
    )
    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return OutreachLogListResponse(
        items=[OutreachLogResponse.model_validate(o) for o in items],
        total=total,
    )


# ── Bulk Delete ────────────────────────────────────────────────────────────
@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def bulk_delete(
    request: Request,
    data: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contacts = db.query(ParentContact).filter(ParentContact.id.in_(data.ids)).all()
    deleted_count = len(contacts)
    for contact in contacts:
        db.delete(contact)
    db.commit()

    log_action(
        db,
        user_id=current_user.id,
        action="contact_bulk_delete",
        resource_type="parent_contact",
        resource_id=None,
        details=f"Bulk deleted {deleted_count} contacts",
    )


# ── Bulk Status ────────────────────────────────────────────────────────────
@router.post("/bulk-status", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def bulk_status(
    request: Request,
    data: BulkStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    updated = (
        db.query(ParentContact)
        .filter(ParentContact.id.in_(data.ids))
        .update({ParentContact.status: data.status}, synchronize_session="fetch")
    )
    db.commit()

    log_action(
        db,
        user_id=current_user.id,
        action="contact_bulk_status",
        resource_type="parent_contact",
        resource_id=None,
        details=f"Bulk updated {updated} contacts to status: {data.status}",
    )

    return {"updated_count": updated}


# ── Bulk Tag ───────────────────────────────────────────────────────────────
@router.post("/bulk-tag", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def bulk_tag(
    request: Request,
    data: BulkTagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    contacts = db.query(ParentContact).filter(ParentContact.id.in_(data.ids)).all()
    updated_count = 0

    for contact in contacts:
        tags = list(contact.tags) if contact.tags else []
        if data.action == "add":
            if data.tag not in tags:
                tags.append(data.tag)
                contact.tags = tags
                updated_count += 1
        elif data.action == "remove":
            if data.tag in tags:
                tags.remove(data.tag)
                contact.tags = tags
                updated_count += 1

    db.commit()

    log_action(
        db,
        user_id=current_user.id,
        action="contact_bulk_tag",
        resource_type="parent_contact",
        resource_id=None,
        details=f"Bulk {data.action} tag '{data.tag}' on {updated_count} contacts",
    )

    return {"updated_count": updated_count}
