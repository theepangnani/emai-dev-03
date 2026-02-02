from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
import html


class MessageCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Strip HTML to prevent XSS
        return html.escape(v.strip())


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: str
    content: str
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    recipient_id: int
    student_id: Optional[int] = None
    subject: Optional[str] = None
    initial_message: str

    @field_validator("initial_message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        return html.escape(v.strip())

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return html.escape(v.strip())
        return v


class ConversationSummary(BaseModel):
    id: int
    other_participant_id: int
    other_participant_name: str
    student_id: Optional[int]
    student_name: Optional[str]
    subject: Optional[str]
    last_message_preview: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: int
    participant_1_id: int
    participant_1_name: str
    participant_2_id: int
    participant_2_name: str
    student_id: Optional[int]
    student_name: Optional[str]
    subject: Optional[str]
    messages: list[MessageResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class RecipientOption(BaseModel):
    user_id: int
    full_name: str
    role: str
    student_names: list[str]

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    total_unread: int
