from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


class QuizAssignmentCreate(BaseModel):
    """Request body for assigning a quiz to a child."""
    student_id: int
    study_guide_id: int
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class QuizAssignmentComplete(BaseModel):
    """Request body for marking a quiz assignment complete."""
    score: float = Field(ge=0, le=100)


class QuizAssignmentResponse(BaseModel):
    """Full quiz assignment response including joined fields."""
    id: int
    parent_user_id: int
    student_id: int
    study_guide_id: int
    difficulty: str
    due_date: Optional[date]
    assigned_at: datetime
    completed_at: Optional[datetime]
    score: Optional[float]
    attempt_count: int
    status: str
    note: Optional[str]

    # Joined fields
    study_guide_title: Optional[str] = None
    course_name: Optional[str] = None
    student_name: Optional[str] = None

    class Config:
        from_attributes = True
