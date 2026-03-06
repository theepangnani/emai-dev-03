from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.note import Note
from app.models.course_content import CourseContent
from app.api.deps import get_current_user
from app.schemas.note import NoteUpsert, NoteResponse, NoteListItem

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get("/", response_model=list[NoteListItem])
def list_notes(
    course_content_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all notes for the current user, optionally filtered by course_content_id."""
    query = db.query(Note).filter(Note.user_id == current_user.id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)
    return query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc()).all()


@router.get("/by-content/{course_content_id}", response_model=NoteResponse | None)
def get_note_by_content(
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the note for a specific course content item (returns null if none exists)."""
    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    return note


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific note by ID."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/by-content/{course_content_id}", response_model=NoteResponse)
def upsert_note(
    course_content_id: int,
    body: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note for a course content item (upsert)."""
    # Verify the course content exists
    cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )

    if note:
        note.content = body.content
        note.plain_text = body.plain_text
        note.has_images = body.has_images
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=course_content_id,
            content=body.content,
            plain_text=body.plain_text,
            has_images=body.has_images,
        )
        db.add(note)

    db.commit()
    db.refresh(note)
    return note


@router.delete("/by-content/{course_content_id}", status_code=204)
def delete_note(
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note for a course content item."""
    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()


@router.get("/by-content/{course_content_id}/children", response_model=list[NoteListItem])
def get_children_notes(
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all notes for children course content items (for parent view)."""
    # Get all course content IDs that are children of the given content
    # For now, return notes for the given content (can be extended for hierarchical content)
    notes = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .order_by(Note.updated_at.desc().nullsfirst())
        .all()
    )
    return notes
