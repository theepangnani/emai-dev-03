from datetime import datetime

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
