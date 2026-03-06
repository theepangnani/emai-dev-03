from pydantic import BaseModel
from datetime import datetime


class NoteUpsert(BaseModel):
    course_content_id: int
    content: str = ""
    plain_text: str = ""
    has_images: bool = False


class NoteResponse(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str
    has_images: bool
    created_at: datetime
    updated_at: datetime | None = None
    course_content_title: str | None = None

    class Config:
        from_attributes = True


class NoteSummary(BaseModel):
    id: int
    course_content_id: int
    has_images: bool
    plain_text_preview: str = ""
    updated_at: datetime | None = None
    course_content_title: str | None = None

    class Config:
        from_attributes = True
