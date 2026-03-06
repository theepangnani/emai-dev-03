import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.note import Note
from app.models.course_content import CourseContent
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role
from app.schemas.note import NoteUpsert, NoteResponse, ChildNoteResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["Notes"])


# ── Own notes CRUD ──────────────────────────────────────────────


@router.get("/", response_model=list[NoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_my_notes(
    request: Request,
    course_content_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's notes, optionally filtered by course_content_id."""
    q = db.query(Note).filter(Note.user_id == current_user.id)
    if course_content_id is not None:
        q = q.filter(Note.course_content_id == course_content_id)
    return q.order_by(Note.updated_at.desc().nullslast(), Note.created_at.desc()).all()


@router.get("/{note_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_my_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single note owned by the current user."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/", response_model=NoteResponse, status_code=200)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    body: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note for the given course_content_id (upsert)."""
    # Verify the course content exists
    cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == body.course_content_id)
        .first()
    )
    if note:
        note.content = body.content
        note.plain_text = body.plain_text
        note.has_images = body.has_images
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=body.course_content_id,
            content=body.content,
            plain_text=body.plain_text,
            has_images=body.has_images,
        )
        db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note owned by the current user."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()


# ── Parent read-only access to children's notes ────────────────


def _verify_parent_child_link(db: Session, parent_id: int, student_id: int) -> Student:
    """Verify that the parent has a linked child with the given student_id. Returns the Student."""
    row = (
        db.query(Student)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(
            parent_students.c.parent_id == parent_id,
            Student.id == student_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=403, detail="Not linked to this child")
    return row


@router.get("/children/{student_id}", response_model=list[ChildNoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_child_notes(
    request: Request,
    student_id: int,
    course_content_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get notes belonging to a linked child (read-only). Parents only."""
    student = _verify_parent_child_link(db, current_user.id, student_id)

    q = db.query(Note).filter(Note.user_id == student.user_id)
    if course_content_id is not None:
        q = q.filter(Note.course_content_id == course_content_id)

    notes = q.order_by(Note.updated_at.desc().nullslast(), Note.created_at.desc()).all()

    child_name = student.user.full_name if student.user else "Child"

    return [
        ChildNoteResponse(
            id=n.id,
            user_id=n.user_id,
            course_content_id=n.course_content_id,
            content=n.content,
            plain_text=n.plain_text,
            has_images=n.has_images,
            child_name=child_name,
            student_id=student.id,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in notes
    ]
