from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.survey_questions import VALID_SURVEY_ROLES


class SurveyAnswerCreate(BaseModel):
    question_key: str = Field(min_length=1, max_length=10)
    question_type: str = Field(min_length=1, max_length=20)
    answer_value: Any


class SurveySubmission(BaseModel):
    role: str
    session_id: str = Field(min_length=1, max_length=36)
    answers: list[SurveyAnswerCreate] = Field(min_length=1)
    website: str = ""  # honeypot field — should always be empty
    started_at: Optional[float] = None  # elapsed seconds since form load (bot protection)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_SURVEY_ROLES:
            raise ValueError(f"Invalid role '{v}'. Must be one of: {', '.join(sorted(VALID_SURVEY_ROLES))}")
        return v


class SurveyAnswerOut(BaseModel):
    id: int
    question_key: str
    question_type: str
    answer_value: Any
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SurveyResponseOut(BaseModel):
    id: int
    session_id: str
    role: str
    completed: bool
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SurveyResponseDetailOut(SurveyResponseOut):
    answers: list[SurveyAnswerOut] = []


class SurveyStatsResponse(BaseModel):
    total_responses: int
    by_role: dict[str, int]
    completion_rate: float


class SurveyQuestionAnalytics(BaseModel):
    question_key: str
    question_text: str
    question_type: str
    total_answers: int
    distribution: dict[str, int] | None = None
    average: float | None = None
    sub_item_averages: dict[str, float] | None = None
    free_text_responses: list[str] | None = None


class SurveyAnalyticsResponse(BaseModel):
    stats: SurveyStatsResponse
    questions: list[SurveyQuestionAnalytics]
    daily_submissions: list[dict[str, Any]]


class SurveyResponseListResponse(BaseModel):
    items: list[SurveyResponseOut]
    total: int
