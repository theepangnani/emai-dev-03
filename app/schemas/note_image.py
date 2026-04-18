from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class NoteImageCreate(BaseModel):
    """No fields needed -- image comes via file upload."""
    pass


class NoteImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note_id: int | None = None
    user_id: int
    media_type: str = Field(..., max_length=50)
    file_size: int = Field(..., ge=0)
    created_at: datetime
    image_url: str
