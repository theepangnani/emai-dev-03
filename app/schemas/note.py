from pydantic import BaseModel, Field
from datetime import datetime


class NoteUpsert(BaseModel):
    """Request to create or update a note (PUT upsert)."""
    content: str = Field(default="", max_length=100000)
    plain_text: str = Field(default="", max_length=100000)
    has_images: bool = False


class NoteResponse(BaseModel):
    """Note response."""
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str
    has_images: bool
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class NoteListItem(BaseModel):
    """Lightweight note item for list endpoints."""
    id: int
    course_content_id: int
    plain_text: str
    has_images: bool
    updated_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
