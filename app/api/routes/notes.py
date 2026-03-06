"""Notes API — per-user notes attached to course content (materials)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.note import Note, strip_html
from app.models.course_content import CourseContent
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.api.deps import get_current_user
from app.schemas.note import NoteUpsert, NoteResponse

router = APIRouter(prefix="/notes", tags=["Notes"])


def _note_to_response(note: Note) -> NoteResponse:
    """Convert a Note ORM object to a NoteResponse, enriching with material/course info."""
    cc = note.course_content
    return NoteResponse(
        id=note.id,
        user_id=note.user_id,
        course_content_id=note.course_content_id,
        content=note.content,
        plain_text=note.plain_text,
        has_images=note.has_images,
        created_at=note.created_at,
        updated_at=note.updated_at,
        material_title=cc.title if cc else None,
        course_name=cc.course.name if cc and cc.course else None,
    )


@router.get("/content/{course_content_id}", response_model=NoteResponse | None)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's note for a specific course content."""
    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    if not note:
        return None
    return _note_to_response(note)


@router.put("/content/{course_content_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    course_content_id: int,
    body: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note for the current user on a course content item."""
    # Verify course content exists
    cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    plain_text = strip_html(body.content)

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )

    if note:
        note.content = body.content
        note.plain_text = plain_text
        note.has_images = body.has_images
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=course_content_id,
            content=body.content,
            plain_text=plain_text,
            has_images=body.has_images,
        )
        db.add(note)

    db.commit()
    db.refresh(note)

    # Auto-delete empty notes
    if not plain_text and not body.has_images:
        db.delete(note)
        db.commit()
        return NoteResponse(
            id=0,
            user_id=current_user.id,
            course_content_id=course_content_id,
            content="",
            plain_text="",
            has_images=False,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    return _note_to_response(note)


@router.delete("/content/{course_content_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the current user's note for a course content item."""
    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()


@router.get("/children", response_model=list[NoteResponse])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_children_notes(
    request: Request,
    course_content_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get notes from linked children (parent-only)."""
    if current_user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail="Parents only")

    child_user_ids = [
        uid
        for (uid,) in db.query(Student.user_id)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    ]
    if not child_user_ids:
        return []

    query = db.query(Note).filter(Note.user_id.in_(child_user_ids))
    if course_content_id:
        query = query.filter(Note.course_content_id == course_content_id)

    notes = query.order_by(Note.updated_at.desc()).all()
    return [_note_to_response(n) for n in notes]
