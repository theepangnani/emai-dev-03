from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course_content import CourseContent
from app.models.note import Note
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.note import NoteResponse, NoteSummary, NoteUpsert

router = APIRouter(prefix="/notes", tags=["Notes"])


def _note_to_response(note: Note) -> NoteResponse:
    resp = NoteResponse.model_validate(note)
    resp.course_content_title = note.course_content.title if note.course_content else None
    return resp


def _note_to_summary(note: Note) -> NoteSummary:
    summary = NoteSummary.model_validate(note)
    summary.plain_text_preview = (note.plain_text or "")[:120]
    summary.course_content_title = note.course_content.title if note.course_content else None
    return summary


@router.get("/", response_model=list[NoteSummary])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_notes(
    request: Request,
    course_content_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all notes for the current user, optionally filtered by course_content_id."""
    query = db.query(Note).filter(Note.user_id == current_user.id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)
    query = query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc())
    notes = query.offset(offset).limit(limit).all()
    return [_note_to_summary(n) for n in notes]


@router.get("/children/{student_id}", response_model=list[NoteSummary])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_child_notes(
    request: Request,
    student_id: int,
    course_content_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """List notes for a linked child (parent/admin only)."""
    # Verify parent-child link
    if current_user.has_role(UserRole.PARENT):
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Not linked to this student")
        # Get the student's user_id
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        target_user_id = student.user_id
    else:
        # Admin: student_id is the student record id
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        target_user_id = student.user_id

    query = db.query(Note).filter(Note.user_id == target_user_id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)
    query = query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc())
    notes = query.offset(offset).limit(limit).all()
    return [_note_to_summary(n) for n in notes]


@router.get("/{note_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single note by ID."""
    note = db.query(Note).filter(
        Note.id == note_id,
        Note.user_id == current_user.id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_to_response(note)


@router.put("/", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    data: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note for a course content item (upsert by user_id + course_content_id)."""
    # Verify course content exists
    cc = db.query(CourseContent).filter(CourseContent.id == data.course_content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    note = db.query(Note).filter(
        Note.user_id == current_user.id,
        Note.course_content_id == data.course_content_id,
    ).first()

    if note:
        note.content = data.content
        note.plain_text = data.plain_text
        note.has_images = data.has_images
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=data.course_content_id,
            content=data.content,
            plain_text=data.plain_text,
            has_images=data.has_images,
        )
        db.add(note)

    db.commit()
    db.refresh(note)
    return _note_to_response(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note."""
    note = db.query(Note).filter(
        Note.id == note_id,
        Note.user_id == current_user.id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
