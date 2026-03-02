"""Pydantic schemas for the Teacher Resource Library feature."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.resource_library import ResourceType


# ---------------------------------------------------------------------------
# TeacherResource schemas
# ---------------------------------------------------------------------------

class TeacherResourceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    resource_type: ResourceType
    subject: Optional[str] = Field(None, max_length=255)
    grade_level: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None
    is_public: bool = False
    external_url: Optional[str] = Field(None, max_length=2000)
    curriculum_expectation: Optional[str] = Field(None, max_length=500)


class TeacherResourceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    resource_type: Optional[ResourceType] = None
    subject: Optional[str] = Field(None, max_length=255)
    grade_level: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    external_url: Optional[str] = Field(None, max_length=2000)
    curriculum_expectation: Optional[str] = Field(None, max_length=500)


class TeacherResourceResponse(BaseModel):
    id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    resource_type: ResourceType
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: bool
    file_key: Optional[str] = None
    external_url: Optional[str] = None
    download_count: int
    avg_rating: float
    rating_count: int
    curriculum_expectation: Optional[str] = None
    linked_lesson_plan_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ResourceRating schemas
# ---------------------------------------------------------------------------

class ResourceRatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class ResourceRatingResponse(BaseModel):
    id: int
    resource_id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ResourceCollection schemas
# ---------------------------------------------------------------------------

class ResourceCollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    resource_ids: Optional[List[int]] = None


class ResourceCollectionResponse(BaseModel):
    id: int
    teacher_id: int
    name: str
    description: Optional[str] = None
    resource_ids: List[int] = []
    resources: Optional[List[TeacherResourceResponse]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Search / filter params
# ---------------------------------------------------------------------------

class ResourceSearchParams(BaseModel):
    q: Optional[str] = None
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    resource_type: Optional[ResourceType] = None
    tags: Optional[List[str]] = None
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Paginated response wrapper
# ---------------------------------------------------------------------------

class PaginatedResourceResponse(BaseModel):
    items: List[TeacherResourceResponse]
    total: int
    page: int
    limit: int
    pages: int
