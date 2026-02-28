from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from app.schemas.user import strip_whitespace


class StudentCreate(BaseModel):
    user_id: int
    grade_level: int | None = None
    school_name: str | None = Field(default=None, max_length=200)

    @field_validator('school_name', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class StudentResponse(BaseModel):
    id: int
    user_id: int
    grade_level: int | None
    school_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True
