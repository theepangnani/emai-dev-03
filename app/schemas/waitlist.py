"""Pydantic schemas for the waitlist feature."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import strip_whitespace

_VALID_ROLES = {"parent", "student", "teacher"}


class WaitlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    roles: list[str] = Field(min_length=1)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: object) -> object:
        return strip_whitespace(v)

    @field_validator("roles", mode="after")
    @classmethod
    def _validate_roles(cls, v: list[str]) -> list[str]:
        normalized = [r.strip().lower() for r in v]
        invalid = [r for r in normalized if r not in _VALID_ROLES]
        if invalid:
            raise ValueError(f"Invalid role(s): {', '.join(invalid)}. Must be one of: parent, student, teacher")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate roles are not allowed")
        return normalized


class WaitlistResponse(BaseModel):
    id: int
    name: str
    email: str
    roles: list[str]
    status: str
    created_at: datetime
    invite_token: str | None = None
    invite_token_expires_at: datetime | None = None

    class Config:
        from_attributes = True
