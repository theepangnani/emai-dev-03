"""Pydantic schemas for Smart Study Time Suggestions (#2227)."""
from pydantic import BaseModel, Field


class StudyTimeSlot(BaseModel):
    """A recommended study time window."""
    day_of_week: str  # e.g., "Monday", "Weekdays", "Weekends"
    time_of_day: str  # e.g., "Evening (7-9 PM)"
    period: str  # "morning", "afternoon", "evening"
    score: float = Field(description="Relative activity score 0-100")
    label: str  # Human-readable e.g., "You study best on weekday evenings 7-9 PM"


class DailyStudyMinutes(BaseModel):
    """Study minutes for a single day (last 7 days)."""
    day: str  # e.g., "Mon", "Tue"
    date: str  # ISO date e.g., "2026-03-24"
    minutes: int


class StudySuggestionsResponse(BaseModel):
    """Full study suggestions payload."""
    top_slots: list[StudyTimeSlot] = Field(default_factory=list, description="Top 3 recommended time slots")
    weekly_chart: list[DailyStudyMinutes] = Field(default_factory=list, description="Last 7 days study minutes")
    current_week_minutes: int = 0
    previous_week_minutes: int = 0
    weekly_trend: str = "steady"  # "up", "down", "steady"
    next_suggested_session: str | None = None  # e.g., "Today at 7 PM"
