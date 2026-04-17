from pydantic import BaseModel
from datetime import datetime


class NoteImageCreate(BaseModel):
    """No fields needed — image comes via file upload."""
    pass


class NoteImageResponse(BaseModel):
    id: int
    note_id: int | None
    user_id: int
    media_type: str
    file_size: int
    created_at: datetime
    image_url: str

    class Config:
        from_attributes = True
