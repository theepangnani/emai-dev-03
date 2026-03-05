from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.waitlist import Waitlist

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.get("/verify/{token}")
def verify_waitlist_token(token: str, db: Session = Depends(get_db)):
    """Validate a waitlist invite token and return the associated name/email.

    Used by the frontend to pre-fill registration fields when a user
    arrives via a waitlist invitation link.
    """
    record = db.query(Waitlist).filter(Waitlist.invite_token == token).first()
    if not record:
        raise HTTPException(status_code=404, detail="Invalid or expired invitation token")

    now = datetime.now(timezone.utc)
    # Compare as naive UTC to handle mixed tz-aware/naive from SQLite vs PostgreSQL
    expires_at = record.invite_token_expires_at
    if expires_at is None or expires_at.replace(tzinfo=None) < now.replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="This invitation token has expired")

    if record.status != "approved":
        raise HTTPException(status_code=400, detail="This invitation is no longer valid")

    if record.registered_user_id is not None:
        raise HTTPException(status_code=400, detail="This invitation has already been used")

    return {
        "name": record.name,
        "email": record.email,
        "roles": record.roles,
    }
