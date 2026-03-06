from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NoteUpsert(BaseModel):
    """PUT body for creating or updating a note on a course content item."""
    content: str = Field(default="", max_length=50000)


class NoteResponse(BaseModel):
    """Response for a single note."""
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str
    has_images: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChildNoteResponse(BaseModel):
    """Response for a child's note (parent read-only view)."""
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str
    has_images: bool
    read_only: bool = True
    student_name: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
