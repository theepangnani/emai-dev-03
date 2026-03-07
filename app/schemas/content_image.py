from pydantic import BaseModel
from datetime import datetime


class ContentImageResponse(BaseModel):
    id: int
    media_type: str
    description: str | None = None
    position_context: str | None = None
    position_index: int
    file_size: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True
