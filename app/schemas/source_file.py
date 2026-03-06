from pydantic import BaseModel
from datetime import datetime


class SourceFileResponse(BaseModel):
    """Response schema for a source file (excludes binary data)."""
    id: int
    course_content_id: int
    filename: str
    file_type: str | None = None
    file_size: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True
