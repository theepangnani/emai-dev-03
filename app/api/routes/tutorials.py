import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User

router = APIRouter(prefix="/tutorials", tags=["tutorials"])


class CompleteStepRequest(BaseModel):
    step: str


@router.get("/progress")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_tutorial_progress(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the user's tutorial completion state."""
    raw = getattr(current_user, "tutorial_completed", None) or "{}"
    try:
        completed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        completed = {}
    return {"completed": completed}


@router.post("/complete")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def complete_tutorial_step(
    request: Request,
    body: CompleteStepRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single tutorial step as complete."""
    raw = getattr(current_user, "tutorial_completed", None) or "{}"
    try:
        completed = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (json.JSONDecodeError, TypeError):
        completed = {}

    completed[body.step] = True
    current_user.tutorial_completed = json.dumps(completed)  # type: ignore[attr-defined]
    db.commit()
    return {"completed": completed}


@router.post("/reset")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def reset_tutorials(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset all tutorial progress (useful for testing or replaying)."""
    current_user.tutorial_completed = "{}"  # type: ignore[attr-defined]
    db.commit()
    return {"completed": {}}
