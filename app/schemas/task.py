from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    priority: str = "medium"
    category: Optional[str] = None
    course_id: Optional[int] = None
    course_content_id: Optional[int] = None
    study_guide_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    is_completed: Optional[bool] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    course_id: Optional[int] = None
    course_content_id: Optional[int] = None
    study_guide_id: Optional[int] = None


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
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
