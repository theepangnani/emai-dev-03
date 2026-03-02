"""Notes API routes.

Routes:
  GET    /api/notes/         — list user's non-archived notes (filterable by course_id, search, pinned)
  POST   /api/notes/         — create note
  PATCH  /api/notes/{id}     — update note fields
  DELETE /api/notes/{id}     — soft-delete (set is_archived=True)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_feature
from app.models.user import User
from app.models.note import Note
from app.models.course import Course
from app.models.study_guide import StudyGuide
from app.models.task import Task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["Notes"])

VALID_COLORS = {"yellow", "blue", "green", "pink", "purple"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class NoteCreate(BaseModel):
    title: Optional[str] = None
    content: str
    color: Optional[str] = "yellow"
    is_pinned: Optional[bool] = False
    course_id: Optional[int] = None
    study_guide_id: Optional[int] = None
    task_id: Optional[int] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    color: Optional[str] = None
    is_pinned: Optional[bool] = None
    course_id: Optional[int] = None
    study_guide_id: Optional[int] = None
    task_id: Optional[int] = None
    is_archived: Optional[bool] = None


class NoteResponse(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    content: str
    color: str
    is_pinned: bool
    course_id: Optional[int]
    study_guide_id: Optional[int]
    task_id: Optional[int]
    course_name: Optional[str]
    study_guide_title: Optional[str]
    task_title: Optional[str]
    is_archived: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


def _serialize_note(note: Note) -> dict:
    return {
        "id": note.id,
        "user_id": note.user_id,
        "title": note.title,
        "content": note.content,
        "color": note.color or "yellow",
        "is_pinned": note.is_pinned or False,
        "course_id": note.course_id,
        "study_guide_id": note.study_guide_id,
        "task_id": note.task_id,
        "course_name": note.course.name if note.course else None,
        "study_guide_title": note.study_guide.title if note.study_guide else None,
        "task_title": note.task.title if note.task else None,
        "is_archived": note.is_archived or False,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def list_notes(
    _flag=Depends(require_feature("notes_projects")),
    course_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pinned: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's non-archived notes. Pinned notes appear first."""
    q = (
        db.query(Note)
        .filter(Note.user_id == current_user.id, Note.is_archived == False)  # noqa: E712
    )

    if course_id is not None:
        q = q.filter(Note.course_id == course_id)

    if pinned is True:
        q = q.filter(Note.is_pinned == True)  # noqa: E712

    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(
                Note.title.ilike(term),
                Note.content.ilike(term),
            )
        )

    # Pinned first, then most recently updated
    notes = q.order_by(Note.is_pinned.desc(), Note.updated_at.desc()).all()
    return [_serialize_note(n) for n in notes]


@router.post("/", status_code=201)
def create_note(
    payload: NoteCreate,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.color and payload.color not in VALID_COLORS:
        raise HTTPException(status_code=400, detail=f"Invalid color. Use: {', '.join(sorted(VALID_COLORS))}")

    note = Note(
        user_id=current_user.id,
        title=payload.title,
        content=payload.content,
        color=payload.color or "yellow",
        is_pinned=payload.is_pinned or False,
        course_id=payload.course_id,
        study_guide_id=payload.study_guide_id,
        task_id=payload.task_id,
        is_archived=False,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialize_note(note)


@router.patch("/{note_id}")
def update_note(
    note_id: int,
    payload: NoteUpdate,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if payload.color is not None and payload.color not in VALID_COLORS:
        raise HTTPException(status_code=400, detail=f"Invalid color. Use: {', '.join(sorted(VALID_COLORS))}")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)

    db.commit()
    db.refresh(note)
    return _serialize_note(note)


@router.delete("/{note_id}", status_code=204)
def delete_note(
    note_id: int,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.is_archived = True
    db.commit()
