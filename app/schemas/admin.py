from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserResponse


class AdminUserList(BaseModel):
    users: list[UserResponse]
    total: int


class AdminStats(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_courses: int
    total_assignments: int


class BroadcastCreate(BaseModel):
    subject: str
    body: str


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
    subject: str
    body: str


class AdminMessageResponse(BaseModel):
    success: bool
    email_sent: bool
