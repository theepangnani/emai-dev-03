from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

from app.schemas.user import strip_whitespace


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    due_date: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    priority: str = Field(default="medium", max_length=10)
    category: Optional[str] = Field(default=None, max_length=50)
    course_id: Optional[int] = None
    course_content_id: Optional[int] = None
    study_guide_id: Optional[int] = None
    recurrence_rule: Optional[str] = None  # daily, weekly, biweekly, monthly
    recurrence_end_date: Optional[datetime] = None
    template_id: Optional[int] = None

    @field_validator('title', 'description', 'category', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    due_date: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    is_completed: Optional[bool] = None
    priority: Optional[str] = Field(default=None, max_length=10)
    category: Optional[str] = Field(default=None, max_length=50)
    course_id: Optional[int] = None
    course_content_id: Optional[int] = None
    study_guide_id: Optional[int] = None
    recurrence_rule: Optional[str] = None
    recurrence_end_date: Optional[datetime] = None

    @field_validator('title', 'description', 'category', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class TaskResponse(BaseModel):
    id: int
    created_by_user_id: int
    assigned_to_user_id: Optional[int]
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    is_completed: bool
    completed_at: Optional[datetime]
    archived_at: Optional[datetime]
    priority: Optional[str]
    category: Optional[str]
    creator_name: str
    assignee_name: Optional[str]
    course_id: Optional[int] = None
    course_content_id: Optional[int] = None
    study_guide_id: Optional[int] = None
    course_name: Optional[str] = None
    course_content_title: Optional[str] = None
    study_guide_title: Optional[str] = None
    study_guide_type: Optional[str] = None
    recurrence_rule: Optional[str] = None
    recurrence_end_date: Optional[datetime] = None
    template_id: Optional[int] = None
    last_reminder_sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskTemplateCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"


class TaskTemplateResponse(BaseModel):
    id: int
    created_by_user_id: int
    title: str
    description: Optional[str]
    priority: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskFromTemplateCreate(BaseModel):
    """Create a task from a template with optional overrides."""
    due_date: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    recurrence_rule: Optional[str] = None
    recurrence_end_date: Optional[datetime] = None


# ── Task Comment schemas (#881) ───────────────────────────

class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    user_name: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
