"""Pydantic schemas for School Report Card Upload & AI Analysis (§6.121, #2286)."""
from typing import Optional

from pydantic import BaseModel, Field


# ── Upload / List ──

class SchoolReportCardResponse(BaseModel):
    """Response after uploading a report card."""
    id: int
    student_id: int
    original_filename: str
    term: Optional[str] = None
    grade_level: Optional[str] = None
    school_name: Optional[str] = None
    report_date: Optional[str] = None
    school_year: Optional[str] = None
    has_text_content: bool = False
    has_analysis: bool = False
    created_at: str

    class Config:
        from_attributes = True


class SchoolReportCardListItem(BaseModel):
    """Compact item for list view."""
    id: int
    original_filename: str
    term: Optional[str] = None
    grade_level: Optional[str] = None
    school_name: Optional[str] = None
    report_date: Optional[str] = None
    school_year: Optional[str] = None
    has_analysis: bool = False
    created_at: str


# ── Grade / Learning-Skills Analysis ──

class GradeAnalysisItem(BaseModel):
    """Per-subject grade analysis."""
    subject: str
    grade: Optional[str] = None
    median: Optional[str] = None
    level: Optional[int] = None
    teacher_comment: Optional[str] = None
    feedback: str = ""


class LearningSkillRating(BaseModel):
    """Individual learning skill rating."""
    skill: str
    rating: str  # E, G, S, N


class LearningSkillsSummary(BaseModel):
    """Learning skills assessment."""
    ratings: list[LearningSkillRating] = Field(default_factory=list)
    summary: str = ""


class ImprovementArea(BaseModel):
    """Prioritized improvement area."""
    area: str
    detail: str
    priority: str = "medium"  # high, medium, low


class ParentTip(BaseModel):
    """Actionable tip for parents."""
    tip: str
    related_subject: Optional[str] = None


class FullAnalysisResponse(BaseModel):
    """Complete analysis response for a single report card."""
    id: int
    report_card_id: int
    analysis_type: str = "full"
    teacher_feedback_summary: str = ""
    grade_analysis: list[GradeAnalysisItem] = Field(default_factory=list)
    learning_skills: LearningSkillsSummary = Field(default_factory=LearningSkillsSummary)
    improvement_areas: list[ImprovementArea] = Field(default_factory=list)
    parent_tips: list[ParentTip] = Field(default_factory=list)
    overall_summary: str = ""
    created_at: str


# ── Career Path ──

class GradeTrend(BaseModel):
    """Per-subject grade trend across years."""
    subject: str
    trajectory: str  # "improving", "declining", "stable"
    data: str  # "78% → 71% → 71%"
    note: str = ""


class CareerSuggestion(BaseModel):
    """Individual career suggestion."""
    career: str
    reasoning: str
    related_subjects: list[str] = Field(default_factory=list)
    next_steps: str = ""


class CareerPathResponse(BaseModel):
    """Career path analysis across all report cards."""
    id: int
    student_id: int
    strengths: list[str] = Field(default_factory=list)
    grade_trends: list[GradeTrend] = Field(default_factory=list)
    career_suggestions: list[CareerSuggestion] = Field(default_factory=list)
    overall_assessment: str = ""
    report_cards_analyzed: int = 0
    created_at: str


# ── Bulk Upload ──

class UploadReportCardResponse(BaseModel):
    """Response for bulk upload."""
    uploaded: list[SchoolReportCardResponse] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)  # filenames that failed
    total_uploaded: int = 0
