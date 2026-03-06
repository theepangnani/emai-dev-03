"""Notes API — personal notes on course content items.

Endpoints:
  GET    /notes/?course_content_id=       — list current user's notes
  GET    /notes/{course_content_id}       — get single note for content item
  PUT    /notes/{course_content_id}       — upsert note (create or update)
  DELETE /notes/{course_content_id}       — delete note
  GET    /notes/children/{student_id}     — parent: read-only child notes
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.note import Note
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.note import NoteUpsert, NoteResponse, ChildNoteResponse

router = APIRouter(prefix="/notes", tags=["Notes"])

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to produce plain text."""
    text = _TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _has_images(html: str) -> bool:
    """Check whether the HTML content contains <img> tags."""
    return "<img" in html.lower()


# ── GET /notes/ ────────────────────────────────────────────────────────────────
@router.get("/", response_model=list[NoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_notes(
    request: Request,
    course_content_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's notes, optionally filtered by course_content_id."""
    query = db.query(Note).filter(Note.user_id == current_user.id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)
    return query.order_by(Note.updated_at.desc().nullslast(), Note.created_at.desc()).all()


# ── GET /notes/{course_content_id} ─────────────────────────────────────────────
@router.get("/{course_content_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's note for a specific course content item."""
    note = db.query(Note).filter(
        Note.user_id == current_user.id,
        Note.course_content_id == course_content_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


# ── PUT /notes/{course_content_id} ─────────────────────────────────────────────
@router.put("/{course_content_id}", response_model=NoteResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    course_content_id: int,
    data: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the current user's note for a course content item.

    If the content is empty after stripping HTML, the note is auto-deleted.
    """
    plain = _strip_html(data.content)

    # Auto-delete if content is empty
    if not plain:
        existing = db.query(Note).filter(
            Note.user_id == current_user.id,
            Note.course_content_id == course_content_id,
        ).first()
        if existing:
            db.delete(existing)
            db.commit()
        raise HTTPException(status_code=204)

    note = db.query(Note).filter(
        Note.user_id == current_user.id,
        Note.course_content_id == course_content_id,
    ).first()
    if note:
        note.content = data.content
        note.plain_text = plain
        note.has_images = _has_images(data.content)
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=course_content_id,
            content=data.content,
            plain_text=plain,
            has_images=_has_images(data.content),
        )
        db.add(note)
    db.commit()
    db.refresh(note)
    return note


# ── DELETE /notes/{course_content_id} ──────────────────────────────────────────
@router.delete("/{course_content_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the current user's note for a course content item."""
    note = db.query(Note).filter(
        Note.user_id == current_user.id,
        Note.course_content_id == course_content_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()


# ── GET /notes/children/{student_id} ──────────────────────────────────────────
@router.get("/children/{student_id}", response_model=list[ChildNoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_child_notes(
    request: Request,
    student_id: int,
    course_content_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a child's notes (parent read-only access).

    Requires parent-child link via parent_students table.
    Only parents can use this endpoint.
    """
    if not current_user.has_role(UserRole.PARENT):
        raise HTTPException(status_code=403, detail="Only parents can view children's notes")

    # Verify parent-child link
    link = db.query(parent_students).filter(
        parent_students.c.parent_id == current_user.id,
        parent_students.c.student_id == student_id,
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="Not linked to this student")

    # Get student's user_id
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get the student's user record for the name
    student_user = db.query(User).filter(User.id == student.user_id).first()
    student_name = student_user.full_name if student_user else "Unknown"

    # Get notes
    query = db.query(Note).filter(Note.user_id == student.user_id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)
    notes = query.order_by(Note.updated_at.desc().nullslast(), Note.created_at.desc()).all()

    return [
        ChildNoteResponse(
            id=n.id,
            user_id=n.user_id,
            course_content_id=n.course_content_id,
            content=n.content,
            plain_text=n.plain_text,
            has_images=n.has_images,
            read_only=True,
            student_name=student_name,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in notes
    ]
