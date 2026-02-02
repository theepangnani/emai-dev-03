from pydantic import BaseModel
from datetime import datetime


class StudentCreate(BaseModel):
    user_id: int
    grade_level: int | None = None
    school_name: str | None = None


class StudentResponse(BaseModel):
    id: int
    user_id: int
    grade_level: int | None
    school_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True
