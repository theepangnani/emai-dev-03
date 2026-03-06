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
    # Enrichment fields set by the route
    user_name: str | None = None
    user_email: str | None = None
    user_role: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AILimitAdminAction(BaseModel):
    approved_amount: int = Field(..., gt=0)


class AILimitSetRequest(BaseModel):
    ai_usage_limit: int = Field(..., ge=0)


class AIUsageUserResponse(BaseModel):
    id: int
    full_name: str
    email: str | None = None
    role: str
    ai_usage_count: int
    ai_usage_limit: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AIUsageHistoryResponse(BaseModel):
    id: int
    user_id: int
    generation_type: str
    course_material_id: int | None = None
    credits_used: int
    created_at: datetime
    # Enrichment fields set by the route
    user_name: str | None = None
    user_email: str | None = None
    course_material_title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AIUsageHistoryList(BaseModel):
    items: list[AIUsageHistoryResponse]
    total: int
