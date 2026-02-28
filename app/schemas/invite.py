from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from datetime import datetime, timezone
from typing import Any

from app.schemas.user import strip_whitespace


class InviteCreate(BaseModel):
    email: EmailStr
    invite_type: str = Field(max_length=20)  # "student" or "teacher"
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
    last_resent_at: datetime | None = None
    created_at: datetime
    status: str = "pending"

    @model_validator(mode="after")
    def _compute_status(self) -> "InviteResponse":
        if self.accepted_at:
            self.status = "accepted"
        elif self.expires_at:
            # Handle both naive and aware datetimes (SQLite stores naive)
            now = datetime.now(timezone.utc)
            exp = self.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                self.status = "expired"
            else:
                self.status = "pending"
        else:
            self.status = "pending"
        return self

    class Config:
        from_attributes = True


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=1, max_length=500)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator('full_name', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)
