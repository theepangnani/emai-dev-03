from pydantic import BaseModel
from datetime import datetime


class TeacherResponse(BaseModel):
    id: int
    user_id: int
    school_name: str | None
    department: str | None
    teacher_type: str | None
    created_at: datetime

    class Config:
        from_attributes = True
