from pydantic import BaseModel
from datetime import datetime


class NoteUpsert(BaseModel):
    course_content_id: int
    content: str  # HTML content
    highlights_json: str | None = None


class NoteResponse(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str | None
    has_images: bool
    highlights_json: str | None = None
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
    highlights_json: str | None = None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class NoteVersionResponse(BaseModel):
    id: int
    note_id: int
    content: str
    version_number: int
    created_at: datetime
    created_by_user_id: int | None

    class Config:
        from_attributes = True


class SaveAsMaterialRequest(BaseModel):
    title: str
    course_id: int


class SaveAsMaterialResponse(BaseModel):
    id: int
    title: str
    message: str


class NoteVersionListItem(BaseModel):
    id: int
    note_id: int
    version_number: int
    created_at: datetime
    created_by_user_id: int | None
    preview: str  # First ~100 chars of plain text

    class Config:
        from_attributes = True
