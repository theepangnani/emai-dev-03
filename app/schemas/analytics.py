from pydantic import BaseModel
from datetime import datetime


# --- Grade Data (from StudentAssignment + Assignment) ---

class GradeItem(BaseModel):
    student_assignment_id: int  # maps to GradeRecord.id for backward compat
    assignment_id: int | None = None  # nullable for course-level grades
    assignment_title: str | None = None
    course_id: int
    course_name: str
    grade: float
    max_points: float
    percentage: float  # pre-computed from GradeRecord
    status: str
    source: str = "manual"  # google_classroom, manual, seed
    submitted_at: datetime | None = None
    due_date: datetime | None = None


class GradeListResponse(BaseModel):
    grades: list[GradeItem]
    total: int


# --- Aggregations ---

class CourseAverage(BaseModel):
    course_id: int
    course_name: str
    average_percentage: float
    graded_count: int
    total_count: int
    completion_rate: float


class GradeTrendPoint(BaseModel):
    date: str  # ISO date string
    percentage: float
    assignment_title: str
    course_name: str


class GradeSummaryResponse(BaseModel):
    overall_average: float
    total_graded: int
    total_assignments: int
    completion_rate: float
    course_averages: list[CourseAverage]
    trend: str  # "improving", "declining", "stable"


class GradeTrendResponse(BaseModel):
    points: list[GradeTrendPoint]
    trend: str


# --- Progress Reports ---

class ProgressReportResponse(BaseModel):
    id: int
    student_id: int
    report_type: str
    period_start: datetime
    period_end: datetime
    data: dict
    generated_at: datetime

    class Config:
        from_attributes = True


# --- AI Insights ---

class AIInsightRequest(BaseModel):
    student_id: int
    focus_area: str | None = None


class AIInsightResponse(BaseModel):
    insight: str
    generated_at: datetime


# --- Sync ---

class GradeSyncResponse(BaseModel):
    synced: int
    errors: int
    message: str
