from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

from app.models.faq import FAQCategory, FAQAnswerStatus
from app.schemas.user import strip_whitespace

VALID_FAQ_CATEGORIES = {c.value for c in FAQCategory}
VALID_FAQ_ANSWER_STATUSES = {s.value for s in FAQAnswerStatus}


# ── Question schemas ──────────────────────────────────────────────


class FAQQuestionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: str = "other"

    @field_validator('title', 'description', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_FAQ_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(sorted(VALID_FAQ_CATEGORIES))}")
        return normalized


class FAQQuestionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=20)

    @field_validator('title', 'description', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_FAQ_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(sorted(VALID_FAQ_CATEGORIES))}")
        return normalized


class FAQQuestionResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: str
    status: str
    error_code: Optional[str]
    created_by_user_id: int
    is_pinned: bool
    view_count: int
    creator_name: str = ""
    answer_count: int = 0
    approved_answer_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime]
    archived_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FAQQuestionDetail(FAQQuestionResponse):
    """Extended response that includes the list of answers."""
    answers: list["FAQAnswerResponse"] = []


class FAQQuestionPin(BaseModel):
    is_pinned: bool


class FAQAdminQuestionCreate(BaseModel):
    """Create an official FAQ entry (question + auto-approved answer) in one shot."""
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: str = "other"
    answer_content: str = Field(min_length=10, max_length=20000)
    is_official: bool = True

    @field_validator('title', 'description', 'answer_content', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_FAQ_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(sorted(VALID_FAQ_CATEGORIES))}")
        return normalized


# ── Answer schemas ────────────────────────────────────────────────


class FAQAnswerCreate(BaseModel):
    content: str = Field(max_length=20000)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Answer must be at least 10 characters")
        return stripped


class FAQAnswerUpdate(BaseModel):
    content: Optional[str] = Field(default=None, max_length=20000)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Answer must be at least 10 characters")
        return stripped


class FAQAnswerResponse(BaseModel):
    id: int
    question_id: int
    content: str
    created_by_user_id: int
    status: str
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    is_official: bool
    creator_name: str = ""
    reviewer_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Resolve forward reference
FAQQuestionDetail.model_rebuild()
