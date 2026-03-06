from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


VALID_ROLES = {"parent", "student", "teacher"}


class WaitlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    roles: list[str] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:
        for role in v:
            if role not in VALID_ROLES:
                raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v


class WaitlistResponse(BaseModel):
    id: int
    name: str
    email: str
    roles: list[str]
    status: str
    admin_notes: str | None
    invite_token: str | None
    invite_link_clicked: bool
    approved_by_user_id: int | None
    approved_at: datetime | None
    registered_user_id: int | None
    reminder_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WaitlistStats(BaseModel):
    total: int
    pending: int
    approved: int
    registered: int
    declined: int


class WaitlistListResponse(BaseModel):
    items: list[WaitlistResponse]
    total: int


class WaitlistAdminUpdate(BaseModel):
    admin_notes: str | None = None
