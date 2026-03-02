from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserResponse, strip_whitespace


class AdminUserList(BaseModel):
    users: list[UserResponse]
    total: int


class AdminStats(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_courses: int
    total_assignments: int


class BroadcastCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)

    @field_validator('subject', 'body', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class BroadcastResponse(BaseModel):
    id: int
    subject: str
    body: str
    recipient_count: int
    email_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class BroadcastListItem(BaseModel):
    id: int
    subject: str
    recipient_count: int
    email_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AdminMessageCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)

    @field_validator('subject', 'body', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class AdminMessageResponse(BaseModel):
    success: bool
    email_sent: bool


# ── Email Template schemas ────────────────────────────────────────────────────

class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    subject: str
    html_body: str
    text_body: Optional[str] = None
    description: Optional[str] = None
    is_customized: bool
    updated_at: Optional[datetime] = None
    updated_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class EmailTemplateListItem(BaseModel):
    id: int
    name: str
    subject: str
    description: Optional[str] = None
    is_customized: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailTemplateUpdate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    html_body: str = Field(min_length=1)
    text_body: Optional[str] = None

    @field_validator('subject', 'html_body', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class EmailTemplatePreviewResponse(BaseModel):
    html: str


# ── Broadcast Detail schema (Feature 2) ──────────────────────────────────────

class BroadcastDetail(BaseModel):
    id: int
    subject: str
    body: str
    recipient_count: int
    email_count: int
    created_at: datetime

    class Config:
        from_attributes = True
