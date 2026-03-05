from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AIUsageResponse(BaseModel):
    count: int
    limit: int
    remaining: int
    warning_threshold: float
    at_limit: bool


class AILimitRequestCreate(BaseModel):
    requested_amount: int = Field(gt=0, description="Number of additional credits requested")
    reason: Optional[str] = Field(default=None, max_length=1000)


class AILimitRequestResponse(BaseModel):
    id: int
    user_id: int
    requested_amount: int
    reason: Optional[str]
    status: str
    approved_amount: Optional[int]
    admin_user_id: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime

    # Joined user info (populated in list endpoints)
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None

    class Config:
        from_attributes = True


class AILimitAdminAction(BaseModel):
    approved_amount: int = Field(gt=0, description="Number of credits to grant")


class AILimitSetRequest(BaseModel):
    ai_usage_limit: int = Field(ge=0, description="New usage limit for the user")


class AIUsageUserResponse(BaseModel):
    id: int
    full_name: str
    email: Optional[str]
    role: Optional[str]
    ai_usage_count: int
    ai_usage_limit: int

    class Config:
        from_attributes = True
