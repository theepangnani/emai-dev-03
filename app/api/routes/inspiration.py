import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.inspiration_message import InspirationMessage
from app.api.deps import get_current_user, require_role
from app.services.inspiration_service import get_random_message, seed_messages
from app.schemas.inspiration import (
    InspirationMessageResponse,
    InspirationMessageCreate,
    InspirationMessageUpdate,
    InspirationRandomResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspiration", tags=["Inspiration"])


@router.get("/random", response_model=InspirationRandomResponse | None)
def random_message(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a random inspirational message for the current user's role."""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    result = get_random_message(db, role)
    if not result:
        return None
    return InspirationRandomResponse(**result)


# ── Admin CRUD ───────────────────────────────────────────────


@router.get("/messages", response_model=list[InspirationMessageResponse])
def list_messages(
    role: str | None = None,
    is_active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all inspiration messages (admin only)."""
    query = db.query(InspirationMessage)
    if role:
        query = query.filter(InspirationMessage.role == role.lower())
    if is_active is not None:
        query = query.filter(InspirationMessage.is_active == is_active)
    query = query.order_by(InspirationMessage.role, InspirationMessage.id)
    return query.offset(skip).limit(limit).all()


@router.post("/messages", response_model=InspirationMessageResponse)
def create_message(
    body: InspirationMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new inspiration message (admin only)."""
    role = body.role.lower()
    if role not in {"parent", "teacher", "student"}:
        raise HTTPException(status_code=400, detail="Role must be parent, teacher, or student")

    msg = InspirationMessage(
        role=role,
        text=body.text,
        author=body.author,
        is_active=True,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/messages/{message_id}", response_model=InspirationMessageResponse)
def update_message(
    message_id: int,
    body: InspirationMessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update an inspiration message (admin only)."""
    msg = db.query(InspirationMessage).filter(InspirationMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if body.text is not None:
        msg.text = body.text
    if body.author is not None:
        msg.author = body.author
    if body.is_active is not None:
        msg.is_active = body.is_active

    db.commit()
    db.refresh(msg)
    return msg


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Delete an inspiration message (admin only)."""
    msg = db.query(InspirationMessage).filter(InspirationMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    db.delete(msg)
    db.commit()
    return {"message": "Deleted"}


@router.post("/seed")
def reseed_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Re-seed inspiration messages from JSON files (admin only). Only runs if table is empty."""
    count = seed_messages(db)
    return {"seeded": count}
