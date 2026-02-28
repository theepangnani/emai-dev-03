from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

from app.models.notification import NotificationType
from app.schemas.user import strip_whitespace


class NotificationCreate(BaseModel):
    user_id: int
    type: NotificationType
    title: str = Field(min_length=1, max_length=255)
    content: Optional[str] = Field(default=None, max_length=5000)
    link: Optional[str] = Field(default=None, max_length=500)

    @field_validator('title', 'content', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    content: Optional[str]
    link: Optional[str]
    read: bool
    created_at: datetime

    # ACK system fields
    requires_ack: bool = False
    acked_at: Optional[datetime] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    reminder_count: int = 0

    class Config:
        from_attributes = True


class NotificationPreferences(BaseModel):
    email_notifications: bool
    assignment_reminder_days: str = Field(max_length=50)
    task_reminder_days: str = Field(default="1,3", max_length=50)


class NotificationSuppressionResponse(BaseModel):
    id: int
    user_id: int
    source_type: str
    source_id: int
    suppressed_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    count: int
