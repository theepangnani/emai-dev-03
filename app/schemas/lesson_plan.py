"""Pydantic schemas for Lesson Plan (TeachAssist integration)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ThreePartLesson(BaseModel):
    """Ontario 3-Part Lesson structure."""
    minds_on: Optional[str] = None
    action: Optional[str] = None
    consolidation: Optional[str] = None


class DifferentiationPlan(BaseModel):
    """Differentiation strategies."""
    enrichment: Optional[str] = None
    support: Optional[str] = None
    ell: Optional[str] = None


class LessonPlanCreate(BaseModel):
    """Request body for creating or updating a lesson plan."""
    plan_type: str  # LessonPlanType value: long_range | unit | daily
    title: str
    course_id: Optional[int] = None
    strand: Optional[str] = None
    unit_number: Optional[int] = None
    grade_level: Optional[str] = None
    subject_code: Optional[str] = None

    big_ideas: Optional[list[str]] = []
    curriculum_expectations: Optional[list[str]] = []
    overall_expectations: Optional[list[str]] = []
    specific_expectations: Optional[list[str]] = []
    learning_goals: Optional[list[str]] = []
    success_criteria: Optional[list[str]] = []

    three_part_lesson: Optional[ThreePartLesson] = None
    assessment_for_learning: Optional[str] = None
    assessment_of_learning: Optional[str] = None
    differentiation: Optional[DifferentiationPlan] = None
    materials_resources: Optional[list[str]] = []
    cross_curricular: Optional[list[str]] = []

    duration_minutes: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_template: bool = False


class LessonPlanUpdate(BaseModel):
    """Partial update — all fields optional."""
    plan_type: Optional[str] = None
    title: Optional[str] = None
    course_id: Optional[int] = None
    strand: Optional[str] = None
    unit_number: Optional[int] = None
    grade_level: Optional[str] = None
    subject_code: Optional[str] = None

    big_ideas: Optional[list[str]] = None
    curriculum_expectations: Optional[list[str]] = None
    overall_expectations: Optional[list[str]] = None
    specific_expectations: Optional[list[str]] = None
    learning_goals: Optional[list[str]] = None
    success_criteria: Optional[list[str]] = None

    three_part_lesson: Optional[ThreePartLesson] = None
    assessment_for_learning: Optional[str] = None
    assessment_of_learning: Optional[str] = None
    differentiation: Optional[DifferentiationPlan] = None
    materials_resources: Optional[list[str]] = None
    cross_curricular: Optional[list[str]] = None

    duration_minutes: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_template: Optional[bool] = None


class LessonPlanResponse(BaseModel):
    """Full lesson plan response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    course_id: Optional[int]
    plan_type: str
    title: str
    strand: Optional[str]
    unit_number: Optional[int]
    grade_level: Optional[str]
    subject_code: Optional[str]

    big_ideas: Optional[list[str]]
    curriculum_expectations: Optional[list[str]]
    overall_expectations: Optional[list[str]]
    specific_expectations: Optional[list[str]]
    learning_goals: Optional[list[str]]
    success_criteria: Optional[list[str]]

    three_part_lesson: Optional[ThreePartLesson]
    assessment_for_learning: Optional[str]
    assessment_of_learning: Optional[str]
    differentiation: Optional[DifferentiationPlan]
    materials_resources: Optional[list[str]]
    cross_curricular: Optional[list[str]]

    duration_minutes: Optional[int]
    start_date: Optional[date]
    end_date: Optional[date]
    is_template: bool
    imported_from: Optional[str]

    created_at: datetime
    updated_at: Optional[datetime]
