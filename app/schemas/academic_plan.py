"""Pydantic schemas for Academic Plan (#501) and Graduation Engine (#502)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# PlanCourse schemas
# ---------------------------------------------------------------------------

class PlanCourseCreate(BaseModel):
    """Body for POST /academic-plans/{plan_id}/courses."""
    course_code: str = Field(..., min_length=1, max_length=20)
    grade_level: int = Field(..., ge=9, le=12)
    semester: int = Field(..., ge=1, le=2)
    status: str = Field("planned", pattern="^(planned|in_progress|completed|dropped)$")
    # Optional overrides — normally fetched from catalog
    course_name: str | None = Field(None, max_length=300)
    subject_area: str | None = Field(None, max_length=100)
    credit_value: float | None = Field(None, ge=0.0, le=2.0)
    pathway: str | None = Field(None, max_length=10)
    is_compulsory: bool | None = None
    compulsory_category: str | None = Field(None, max_length=100)
    final_mark: int | None = Field(None, ge=0, le=100)

    @field_validator("course_code", mode="before")
    @classmethod
    def uppercase_course_code(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class PlanCourseResponse(BaseModel):
    id: int
    plan_id: int
    course_code: str
    course_name: str
    subject_area: str | None
    grade_level: int
    semester: int
    credit_value: float
    pathway: str | None
    status: str
    final_mark: int | None
    is_compulsory: bool
    compulsory_category: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AcademicPlan schemas
# ---------------------------------------------------------------------------

class AcademicPlanCreate(BaseModel):
    """Body for POST /academic-plans/."""
    student_id: int | None = None    # Required for parents; students infer from their own profile
    name: str = Field("My Academic Plan", min_length=1, max_length=200)
    start_grade: int = Field(9, ge=9, le=12)
    target_graduation_year: int | None = Field(None, ge=2020, le=2040)
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class AcademicPlanUpdate(BaseModel):
    """Body for PUT /academic-plans/{plan_id}."""
    name: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = Field(None, pattern="^(draft|active|completed)$")
    notes: str | None = None
    target_graduation_year: int | None = Field(None, ge=2020, le=2040)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class AcademicPlanResponse(BaseModel):
    id: int
    student_id: int
    created_by_user_id: int | None
    name: str
    start_grade: int
    target_graduation_year: int | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
    plan_courses: list[PlanCourseResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ValidationResult schema (returned by GET /academic-plans/{id}/validate)
# ---------------------------------------------------------------------------

class ValidationResultResponse(BaseModel):
    """Serializable form of graduation_engine.ValidationResult."""
    is_valid: bool
    total_credits: float
    compulsory_credits: float
    elective_credits: float
    completion_pct: float
    missing_requirements: list[str]
    warnings: list[str]
    fulfilled_requirements: list[str]
    suggested_courses: list[str] = []
