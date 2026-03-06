import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.note import Note
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.note import NoteListItem, NoteResponse, NoteUpsert

router = APIRouter(prefix="/notes", tags=["Notes"])


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace to produce plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _has_images(html: str) -> bool:
    """Check if HTML content contains image tags or base64 image data."""
    return bool(re.search(r"<img[\s>]", html, re.IGNORECASE))


def _get_linked_child_user_ids(db: Session, parent_id: int) -> list[int]:
    """Return user_ids for all children linked to the given parent."""
    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == parent_id
    ).all()
    child_student_ids = [r[0] for r in rows]
    if not child_student_ids:
        return []
    students = db.query(Student.user_id).filter(
        Student.id.in_(child_student_ids)
    ).all()
    return [s[0] for s in students]


@router.get("/", response_model=list[NoteListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_notes(
    request: Request,
    course_content_id: int | None = Query(None),
    user_id: int | None = Query(None, description="Filter by user (admin only)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notes for the current user, optionally filtered by course_content_id."""
    query = db.query(Note)

    if current_user.has_role(UserRole.ADMIN) and user_id is not None:
        query = query.filter(Note.user_id == user_id)
    else:
        query = query.filter(Note.user_id == current_user.id)

    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)

    query = query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc())
    return query.offset(offset).limit(limit).all()


@router.get("/children/{student_id}", response_model=list[NoteListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_child_notes(
    request: Request,
    student_id: int,
    course_content_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parent endpoint: list notes for a linked child (read-only)."""
    if not current_user.has_role(UserRole.PARENT):
        raise HTTPException(status_code=403, detail="Only parents can access children's notes")

    child_user_ids = _get_linked_child_user_ids(db, current_user.id)
    if student_id not in child_user_ids:
        raise HTTPException(status_code=403, detail="Student is not linked to your account")

    query = db.query(Note).filter(Note.user_id == student_id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)

    query = query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc())
    return query.offset(offset).limit(limit).all()


@router.get("/{note_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single note. Owner sees own; parent can see child's note."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Owner can always see their own note
    if note.user_id == current_user.id:
        return note

    # Parent can see child's note
    if current_user.has_role(UserRole.PARENT):
        child_user_ids = _get_linked_child_user_ids(db, current_user.id)
        if note.user_id in child_user_ids:
            return note

    # Admin can see any note
    if current_user.has_role(UserRole.ADMIN):
        return note

    raise HTTPException(status_code=404, detail="Note not found")


@router.put("/", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    data: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note. Empty content auto-deletes the note."""
    plain = _strip_html(data.content)

    # Empty content → auto-delete
    if not plain:
        existing = db.query(Note).filter(
            Note.user_id == current_user.id,
            Note.course_content_id == data.course_content_id,
        ).first()
        if existing:
            db.delete(existing)
            db.commit()
        return Response(status_code=204)

    existing = db.query(Note).filter(
        Note.user_id == current_user.id,
        Note.course_content_id == data.course_content_id,
    ).first()

    if existing:
        existing.content = data.content
        existing.plain_text = plain
        existing.has_images = _has_images(data.content)
        db.commit()
        db.refresh(existing)
        return existing

    note = Note(
        user_id=current_user.id,
        course_content_id=data.course_content_id,
        content=data.content,
        plain_text=plain,
        has_images=_has_images(data.content),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note. Owner only."""
    note = db.query(Note).filter(
        Note.id == note_id,
        Note.user_id == current_user.id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
