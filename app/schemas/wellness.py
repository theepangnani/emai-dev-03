from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.wellness import MoodLevel, EnergyLevel


class WellnessCheckInCreate(BaseModel):
    mood: MoodLevel
    energy: EnergyLevel
    stress_level: int = Field(..., ge=1, le=5, description="Stress level from 1 (low) to 5 (high)")
    sleep_hours: Optional[float] = Field(None, ge=0, le=24, description="Hours of sleep last night")
    notes: Optional[str] = Field(None, max_length=1000)
    is_private: bool = False


class WellnessCheckInResponse(BaseModel):
    id: int
    student_id: int
    mood: MoodLevel
    energy: EnergyLevel
    stress_level: int
    sleep_hours: Optional[float] = None
    notes: Optional[str] = None
    is_private: bool
    check_in_date: date
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DayTrendPoint(BaseModel):
    date: date
    mood: Optional[MoodLevel] = None
    energy: Optional[EnergyLevel] = None
    stress_level: Optional[int] = None
    sleep_hours: Optional[float] = None
    has_entry: bool = False


class WellnessTrendResponse(BaseModel):
    days: list[DayTrendPoint]
    avg_stress: Optional[float] = None
    avg_sleep: Optional[float] = None
    dominant_mood: Optional[MoodLevel] = None
    dominant_energy: Optional[EnergyLevel] = None
    streak_days: int = 0  # consecutive days checked in


class WellnessSummary(BaseModel):
    student_id: int
    week_avg_stress: Optional[float] = None
    week_avg_sleep: Optional[float] = None
    dominant_mood: Optional[MoodLevel] = None
    dominant_energy: Optional[EnergyLevel] = None
    alert_active: bool = False
    total_check_ins_this_week: int = 0
    streak_days: int = 0
