"""
API routes for the Learning Journal feature.

Prefix: /api/journal
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User, UserRole
from app.schemas.learning_journal import (
    JournalEntryCreate,
    JournalEntryResponse,
    JournalEntryUpdate,
    JournalStats,
    ReflectionPromptResponse,
)
from app.services.learning_journal import LearningJournalService

router = APIRouter(prefix="/journal", tags=["learning-journal"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _entry_or_404(entry_id: int, requester_id: int, db: Session) -> object:
    entry = LearningJournalService.get_entry(entry_id, requester_id, db)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


# ---------------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------------

@router.post("/entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    data: JournalEntryCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Create a new journal entry for the authenticated student."""
    return LearningJournalService.create_entry(current_user.id, data, db)


@router.get("/entries", response_model=dict)
def list_entries(
    course_id: Optional[int] = Query(None, description="Filter by course"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """List the authenticated student's own journal entries (paginated)."""
    entries, total = LearningJournalService.get_entries(
        current_user.id, db, course_id=course_id, page=page, limit=limit
    )
    return {
        "entries": [JournalEntryResponse.model_validate(e) for e in entries],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/entries/{entry_id}", response_model=JournalEntryResponse)
def get_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single journal entry.
    - Students may access their own entries.
    - Teachers may access entries marked is_teacher_visible=True.
    """
    entry = _entry_or_404(entry_id, current_user.id, db)
    return entry


@router.patch("/entries/{entry_id}", response_model=JournalEntryResponse)
def update_entry(
    entry_id: int,
    data: JournalEntryUpdate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Update an existing journal entry (owner only)."""
    entry = LearningJournalService.update_entry(entry_id, current_user.id, data, db)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Delete an entry (owner only)."""
    deleted = LearningJournalService.delete_entry(entry_id, current_user.id, db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")


@router.get("/stats", response_model=JournalStats)
def get_stats(
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return aggregated journal stats for the authenticated student."""
    return LearningJournalService.get_stats(current_user.id, db)


# ---------------------------------------------------------------------------
# Prompt endpoints (students)
# ---------------------------------------------------------------------------

@router.get("/prompt", response_model=ReflectionPromptResponse)
def get_prompt(
    ai: bool = Query(False, description="If true, generate an AI-personalised prompt"),
    category: Optional[str] = Query(None, description="Filter random prompt by category"),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """
    Get a reflection prompt.
    - ?ai=true  → GPT-4o-mini generates a personalised prompt based on recent activity.
    - ?ai=false → Return a random seed prompt (optionally filtered by category).
    """
    if ai:
        return LearningJournalService.get_ai_reflection_prompt(current_user.id, db)

    prompt = LearningJournalService.get_random_prompt(db, category=category)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prompts found for the given category",
        )
    return ReflectionPromptResponse(
        id=prompt.id,
        prompt_text=prompt.prompt_text,
        category=prompt.category,
        is_ai_generated=False,
    )


@router.get("/prompts", response_model=list[ReflectionPromptResponse])
def list_prompts(
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """List all active seed prompts."""
    prompts = LearningJournalService.get_all_prompts(db)
    return [
        ReflectionPromptResponse(
            id=p.id,
            prompt_text=p.prompt_text,
            category=p.category,
            is_ai_generated=False,
        )
        for p in prompts
    ]


# ---------------------------------------------------------------------------
# Teacher endpoint
# ---------------------------------------------------------------------------

@router.get("/teacher/{course_id}", response_model=list[JournalEntryResponse])
def get_teacher_visible_entries(
    course_id: int,
    current_user: User = Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """
    Return all journal entries for a course that students have opted to share
    with their teacher (is_teacher_visible=True).
    """
    entries = LearningJournalService.get_teacher_visible_entries(
        current_user.id, course_id, db
    )
    return entries
