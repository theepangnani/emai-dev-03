"""Schemas for the Weekly Family Report Card email (#2228)."""

from pydantic import BaseModel


class ReportChildStreak(BaseModel):
    current_streak: int = 0
    longest_streak: int = 0
    tier_label: str = "Getting Started"


class ReportChildTask(BaseModel):
    completed: int = 0
    total: int = 0


class ReportChildAssignment(BaseModel):
    submitted: int = 0
    due: int = 0


class ReportChildQuiz(BaseModel):
    quiz_count: int = 0
    average_percentage: float | None = None


class ReportUpcomingDeadline(BaseModel):
    id: int
    title: str
    due_date: str | None = None
    item_type: str  # "task" or "assignment"
    course_name: str | None = None


class ChildReport(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None = None
    tasks: ReportChildTask = ReportChildTask()
    assignments: ReportChildAssignment = ReportChildAssignment()
    study_guides_created: int = 0
    quizzes: ReportChildQuiz = ReportChildQuiz()
    streak: ReportChildStreak = ReportChildStreak()
    upcoming_deadlines: list[ReportUpcomingDeadline] = []
    engagement_score: int = 0  # 0-100 percentage
    highlight: str = ""


class WeeklyFamilyReportResponse(BaseModel):
    """JSON preview of the weekly family report card."""
    week_start: str  # ISO date
    week_end: str  # ISO date
    greeting: str
    children: list[ChildReport] = []
    family_engagement_score: int = 0  # 0-100 percentage
    overall_summary: str = ""
    share_url: str | None = None


class WeeklyReportSendResponse(BaseModel):
    success: bool
    message: str
