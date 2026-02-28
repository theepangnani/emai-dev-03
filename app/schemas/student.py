from pydantic import BaseModel
from datetime import datetime, date


class StudentCreate(BaseModel):
    user_id: int
    grade_level: int | None = None
    school_name: str | None = None


class StudentResponse(BaseModel):
    id: int
    user_id: int
    grade_level: int | None
    school_name: str | None
    date_of_birth: date | None = None
    consent_status: str | None = None
    parent_consent_given_at: datetime | None = None
    student_consent_given_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
