from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

from app.models.student_email import EmailType


class StudentEmailCreate(BaseModel):
    email: EmailStr
    email_type: EmailType = EmailType.PERSONAL


class StudentEmailResponse(BaseModel):
    id: int
    student_id: int
    email: str
    email_type: EmailType
    is_primary: bool
    verified_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SetPrimaryRequest(BaseModel):
    email_id: int
