from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    student_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    student_id: Optional[int] = None
    is_completed: Optional[bool] = None


class TaskResponse(BaseModel):
    id: int
    parent_id: int
    student_id: Optional[int]
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    is_completed: bool
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
