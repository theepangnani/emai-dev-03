from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AIUsageResponse(BaseModel):
    count: int
    limit: int
    remaining: int
    warning_threshold: float
    at_limit: bool


class AILimitRequestCreate(BaseModel):
    requested_amount: int = Field(..., gt=0)
    reason: str | None = None


class AILimitRequestResponse(BaseModel):
    id: int
    user_id: int
    requested_amount: int
    reason: str | None
    status: str
    approved_amount: int | None
    admin_user_id: int | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AILimitAdminAction(BaseModel):
    approved_amount: int = Field(..., gt=0)
