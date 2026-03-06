"""Notes API — user notes linked to course content, with task creation."""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.note import Note
from app.models.task import Task
from app.models.course_content import CourseContent
from app.models.student import Student
from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.note import NoteUpsert, NoteResponse, NoteCreateTaskRequest
from app.schemas.task import TaskResponse
from app.services.audit_service import log_action

router = APIRouter(prefix="/notes", tags=["Notes"])

VALID_PRIORITIES = {"low", "medium", "high"}


def _strip_html(html: Optional[str]) -> Optional[str]:
    """Strip HTML tags and decode entities to produce plain text."""
    if not html:
        return None
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


@router.get("/by-content/{course_content_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note_by_content(
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
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/by-content/{course_content_id}", response_model=NoteResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    course_content_id: int,
    data: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note for a specific course content (upsert)."""
    # Verify course content exists
    cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )

    plain_text = _strip_html(data.content)

    if note:
        note.content = data.content
        note.plain_text = plain_text
        note.has_images = data.has_images
    else:
        note = Note(
            user_id=current_user.id,
            course_content_id=course_content_id,
            content=data.content,
            plain_text=plain_text,
            has_images=data.has_images,
        )
        db.add(note)

    db.commit()
    db.refresh(note)

    # Auto-delete: if content is empty/whitespace, remove the note
    if not plain_text:
        db.delete(note)
        db.commit()
        raise HTTPException(status_code=204, detail="Note deleted (empty content)")

    return note


@router.delete("/by-content/{course_content_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    course_content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the current user's note for a specific course content."""
    note = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.course_content_id == course_content_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()


@router.get("/", response_model=list[NoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_notes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all notes for the current user."""
    notes = (
        db.query(Note)
        .filter(Note.user_id == current_user.id)
        .order_by(Note.updated_at.desc().nullslast(), Note.created_at.desc())
        .all()
    )
    return notes


@router.post("/{note_id}/create-task", response_model=TaskResponse, status_code=201)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def create_task_from_note(
    request: Request,
    note_id: int,
    data: NoteCreateTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a task from a note.

    - Task description is set to the first 500 chars of the note's plain text.
    - If linked=true, the task's course_content_id is set from the note's material.
    """
    note = (
        db.query(Note)
        .options(selectinload(Note.course_content))
        .filter(Note.id == note_id, Note.user_id == current_user.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Validate priority
    priority = data.priority.strip().lower()
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority. Use: low, medium, high")

    # Build task description from note snippet
    description = None
    if note.plain_text:
        description = note.plain_text[:500]

    # Resolve legacy student_id
    legacy_student_id = None
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if student:
        legacy_student_id = student.id

    # Determine linked fields
    course_content_id = note.course_content_id if data.linked else None
    course_id = note.course_content.course_id if data.linked and note.course_content else None

    task = Task(
        created_by_user_id=current_user.id,
        parent_id=current_user.id,
        student_id=legacy_student_id,
        title=data.title,
        description=description,
        due_date=data.due_date,
        priority=priority,
        course_id=course_id,
        course_content_id=course_content_id,
        note_id=note.id,
    )
    db.add(task)
    db.flush()

    log_action(
        db, user_id=current_user.id, action="create", resource_type="task",
        resource_id=task.id, details={"title": data.title, "from_note": note.id},
    )
    db.commit()
    db.refresh(task)

    # Build response using the same pattern as tasks routes
    from app.api.routes.tasks import _task_to_response, _task_eager_options
    task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task.id).first()

    return _task_to_response(task)
