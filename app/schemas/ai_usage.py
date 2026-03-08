from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    role: str = "unknown"
    ai_usage_count: int = 0
    ai_usage_limit: int = 10

    @field_validator('role', mode='before')
    @classmethod
    def coalesce_role(cls, v):
        if v is None:
            return "unknown"
        # Handle enum values
        return v.value if hasattr(v, 'value') else str(v)

    @field_validator('ai_usage_count', 'ai_usage_limit', mode='before')
    @classmethod
    def coalesce_none(cls, v, info):
        if v is None:
            return 10 if info.field_name == 'ai_usage_limit' else 0
        return v

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


class AIUsageUserList(BaseModel):
    items: list[AIUsageUserResponse]
    total: int


class AILimitRequestList(BaseModel):
    items: list[AILimitRequestResponse]
    total: int


class AIBulkSetLimitRequest(BaseModel):
    ai_usage_limit: int = Field(..., ge=0)
    reset_counts: bool = False


class AIBulkSetLimitResponse(BaseModel):
    updated_count: int
    new_limit: int


class AIUsageSummaryTopUser(BaseModel):
    id: int
    full_name: str
    ai_usage_count: int

    model_config = ConfigDict(from_attributes=True)


class AIUsageSummaryResponse(BaseModel):
    total_ai_calls: int
    top_users: list[AIUsageSummaryTopUser]
