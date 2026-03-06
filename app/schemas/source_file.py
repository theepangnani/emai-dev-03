from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SourceFileResponse(BaseModel):
    """Response schema for source file metadata (no file data)."""
    id: int
    course_content_id: int
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
