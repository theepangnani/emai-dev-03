from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteUpsert(BaseModel):
    content: str = ""
    has_images: bool = False


class NoteResponse(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    content: str
    plain_text: str
    has_images: bool
    created_at: datetime
    updated_at: datetime
    material_title: Optional[str] = None
    course_name: Optional[str] = None

    model_config = {"from_attributes": True}
