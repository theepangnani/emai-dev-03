from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

from app.models.notification import NotificationType
from app.schemas.user import strip_whitespace


class AdvancedNotificationPreferences(BaseModel):
    """Per-type notification preference toggles + digest settings."""
    # In-app toggles
    in_app_assignments: bool = True
    in_app_messages: bool = True
    in_app_tasks: bool = True
    in_app_system: bool = True
    in_app_reminders: bool = True
    # Email toggles
    email_assignments: bool = True
    email_messages: bool = True
    email_tasks: bool = True
    email_reminders: bool = True
    # Digest
    digest_mode: bool = False
    digest_hour: int = Field(default=8, ge=0, le=23)

    class Config:
        from_attributes = True


class AdvancedNotificationPreferencesResponse(AdvancedNotificationPreferences):
    id: int
    user_id: int
    last_digest_sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
