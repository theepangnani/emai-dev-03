from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.models.teacher_communication import CommunicationType


class TeacherCommunicationResponse(BaseModel):
    id: int
    user_id: int
    type: CommunicationType
    source_id: str
    sender_name: Optional[str]
    sender_email: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    snippet: Optional[str]
    ai_summary: Optional[str]
    course_name: Optional[str]
    is_read: bool
    received_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherCommunicationList(BaseModel):
    items: list[TeacherCommunicationResponse]
    total: int
    page: int
    page_size: int


class EmailMonitoringStatus(BaseModel):
    gmail_enabled: bool
    classroom_enabled: bool
    last_gmail_sync: Optional[datetime]
    last_classroom_sync: Optional[datetime]
    total_communications: int
    unread_count: int
