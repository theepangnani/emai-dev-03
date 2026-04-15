"""Pydantic schemas for Learning History (#3391)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class LearningHistoryBase(BaseModel):
    """Shared fields for learning history records."""
    student_id: int
    session_id: str
    session_type: str  # 'asgf', 'flash_tutor', 'parent_teaching'
    question_asked: Optional[str] = None
    subject: Optional[str] = None
    topic_tags: Optional[list[Any]] = None
    grade_level: Optional[str] = None
    school_board: Optional[str] = None
    documents_uploaded: Optional[list[Any]] = None
    quiz_results: Optional[dict[str, Any] | list[Any]] = None
    overall_score_pct: Optional[int] = None
    avg_attempts_per_q: Optional[float] = None
    weak_concepts: Optional[list[Any]] = None
    slides_generated: Optional[list[Any]] = None
    material_id: Optional[int] = None
    assigned_to_course: Optional[str] = None
    session_duration_sec: Optional[int] = None
    teacher_visible: bool = False


class LearningHistoryCreate(LearningHistoryBase):
    """Schema for creating a learning history record."""
    pass


class LearningHistoryResponse(LearningHistoryBase):
    """Schema for returning a learning history record."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
