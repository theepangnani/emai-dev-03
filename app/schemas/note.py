from pydantic import BaseModel, Field
from datetime import datetime


class NoteUpsert(BaseModel):
    """Request body to create or update a note (upsert by user_id + course_content_id)."""
    course_content_id: int
    content: str = Field(default="", max_length=100000)
    plain_text: str = Field(default="", max_length=100000)
    has_images: bool = False


class NoteResponse(BaseModel):
    """Note returned from API."""
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


class ChildNoteResponse(BaseModel):
    """Note belonging to a child, viewed by parent (read-only)."""
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str
    has_images: bool
    child_name: str
    student_id: int
    created_at: datetime
    updated_at: datetime | None = None
