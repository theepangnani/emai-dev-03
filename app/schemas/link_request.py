from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal


class LinkRequestUserInfo(BaseModel):
    id: int
    full_name: str
    email: str | None = None

    class Config:
        from_attributes = True


class LinkRequestResponse(BaseModel):
    id: int
    request_type: str
    status: str
    requester: LinkRequestUserInfo
    target: LinkRequestUserInfo
    student_id: int | None = None
    relationship_type: str | None = None
    message: str | None = None
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None = None

    class Config:
        from_attributes = True


class LinkRequestRespondRequest(BaseModel):
    action: Literal["approve", "reject"]


class LinkRequestCreateRequest(BaseModel):
    parent_email: EmailStr
    relationship_type: str = Field(default="guardian", max_length=20)
    message: str | None = Field(default=None, max_length=500)
