from pydantic import BaseModel
from datetime import datetime


class NoteUpsert(BaseModel):
    course_content_id: int
    content: str  # HTML content


class NoteResponse(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str | None
    has_images: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class NoteListItem(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    plain_text: str | None
    has_images: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True
