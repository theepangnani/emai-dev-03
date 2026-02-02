from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Any


class InviteCreate(BaseModel):
    email: EmailStr
    invite_type: str  # "student" or "teacher"
    metadata: dict[str, Any] | None = None


class InviteResponse(BaseModel):
    id: int
    email: str
    invite_type: str
    token: str
    expires_at: datetime
    invited_by_user_id: int
    metadata_json: dict[str, Any] | None
    accepted_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: str
