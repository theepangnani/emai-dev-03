from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class NoteUpsert(BaseModel):
    content: Optional[str] = Field(default=None, max_length=50000)
    has_images: bool = False


class NoteResponse(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    content: Optional[str]
    plain_text: Optional[str]
    has_images: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class NoteCreateTaskRequest(BaseModel):
    """Request body for creating a task from a note."""
    title: str = Field(min_length=1, max_length=200)
    due_date: Optional[datetime] = None
    priority: str = Field(default="medium", max_length=10)
    linked: bool = True  # If true, link task to note's course_content_id
