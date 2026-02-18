from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.models.notification import NotificationType


class NotificationCreate(BaseModel):
    user_id: int
    type: NotificationType
    title: str
    content: Optional[str] = None
    link: Optional[str] = None


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
    assignment_reminder_days: str
    task_reminder_days: str = "1,3"


class UnreadCountResponse(BaseModel):
    count: int
