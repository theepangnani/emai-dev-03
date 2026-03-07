"""Pydantic schemas for the Recent Activity feed."""

import enum
from datetime import datetime

from pydantic import BaseModel


class ActivityType(str, enum.Enum):
    COURSE_CREATED = "course_created"
    TASK_CREATED = "task_created"
    MATERIAL_UPLOADED = "material_uploaded"
    TASK_COMPLETED = "task_completed"
    MESSAGE_RECEIVED = "message_received"
    NOTIFICATION_RECEIVED = "notification_received"


class ActivityItem(BaseModel):
    activity_type: ActivityType
    title: str
    description: str
    resource_type: str  # "course", "task", "course_content", "message", "notification"
    resource_id: int
    student_id: int | None = None
    student_name: str | None = None
    created_at: datetime
    icon_type: str  # matches activity_type value for frontend icon mapping

    model_config = {"from_attributes": True}
