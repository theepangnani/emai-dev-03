from pydantic import BaseModel
from datetime import datetime


class StudentCreate(BaseModel):
    user_id: int
    grade_level: int | None = None
    school_name: str | None = None
    parent_id: int | None = None


class StudentResponse(BaseModel):
    id: int
    user_id: int
    grade_level: int | None
    school_name: str | None
    parent_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True
