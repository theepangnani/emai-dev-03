from datetime import datetime

from pydantic import BaseModel, EmailStr


class WaitlistCreate(BaseModel):
    name: str
    email: EmailStr
    roles: list[str] | None = None


class WaitlistResponse(BaseModel):
    id: int
    name: str
    email: str
    roles: str | None = None
    status: str
    admin_notes: str | None = None
    invite_token: str | None = None
    invite_token_expires_at: datetime | None = None
    email_validated: bool = False
    approved_by_user_id: int | None = None
    approved_at: datetime | None = None
    registered_user_id: int | None = None
    reminder_sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WaitlistStats(BaseModel):
    total: int
    pending: int
    approved: int
    registered: int
    declined: int


class WaitlistAdminUpdate(BaseModel):
    admin_notes: str


class WaitlistListResponse(BaseModel):
    items: list[WaitlistResponse]
    total: int
