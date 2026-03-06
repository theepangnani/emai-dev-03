"""Notes API — per-user rich-text notes attached to course content items.

Each (user, course_content) pair has at most one note (upsert semantics).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, can_access_course
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course_content import CourseContent
from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteUpsert, NoteResponse, NoteListItem, _has_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["Notes"])


def _ensure_content_access(db: Session, user: User, course_content_id: int) -> CourseContent:
    """Verify that the course content exists and the user can access its course."""
    cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
    if not cc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course content not found")
    if not can_access_course(db, user, cc.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")
    return cc


@router.get("/content/{course_content_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's note for a specific course content item."""
    _ensure_content_access(db, current_user, course_content_id)

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.put("/content/{course_content_id}", response_model=NoteResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    course_content_id: int,
    data: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the current user's note for a course content item.

    Uses upsert semantics: if a note already exists for this (user, content) pair,
    it is updated; otherwise a new one is created.
    """
    _ensure_content_access(db, current_user, course_content_id)

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )

    if note:
        note.content = data.content
        note.plain_text = data.plain_text
        note.has_images = _has_images(data.content)
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=course_content_id,
            content=data.content,
            plain_text=data.plain_text,
            has_images=_has_images(data.content),
        )
        db.add(note)

    db.commit()
    db.refresh(note)
    return note


@router.delete("/content/{course_content_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the current user's note for a course content item."""
    _ensure_content_access(db, current_user, course_content_id)

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    db.delete(note)
    db.commit()


@router.get("/mine", response_model=list[NoteListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_my_notes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all notes owned by the current user (lightweight, no full content)."""
    notes = (
        db.query(Note)
        .filter(Note.user_id == current_user.id)
        .order_by(Note.updated_at.desc().nullslast(), Note.created_at.desc())
        .all()
    )
    items = []
    for note in notes:
        preview = None
        if note.plain_text:
            preview = note.plain_text[:200]
        items.append(NoteListItem(
            id=note.id,
            user_id=note.user_id,
            course_content_id=note.course_content_id,
            has_images=note.has_images,
            plain_text_preview=preview,
            created_at=note.created_at,
            updated_at=note.updated_at,
        ))
    return items


@router.get("/content/{course_content_id}/children", response_model=list[NoteListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_children_notes(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notes for a course content item from the current user's children.

    Only available to parents. Returns lightweight note metadata for each child
    that has a note on this content item.
    """
    from app.models.user import UserRole
    from app.models.student import Student, parent_students

    if current_user.role != UserRole.PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can view children's notes",
        )

    _ensure_content_access(db, current_user, course_content_id)

    # Get children's user IDs
    child_rows = (
        db.query(parent_students.c.student_id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    )
    child_sids = [r[0] for r in child_rows]
    if not child_sids:
        return []

    child_user_ids = [
        r[0] for r in db.query(Student.user_id).filter(Student.id.in_(child_sids)).all()
    ]
    if not child_user_ids:
        return []

    notes = (
        db.query(Note)
        .filter(
            Note.course_content_id == course_content_id,
            Note.user_id.in_(child_user_ids),
        )
        .order_by(Note.updated_at.desc().nullslast())
        .all()
    )

    items = []
    for note in notes:
        preview = None
        if note.plain_text:
            preview = note.plain_text[:200]
        items.append(NoteListItem(
            id=note.id,
            user_id=note.user_id,
            course_content_id=note.course_content_id,
            has_images=note.has_images,
            plain_text_preview=preview,
            created_at=note.created_at,
            updated_at=note.updated_at,
        ))
    return items
