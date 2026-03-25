from pydantic import BaseModel
from datetime import datetime


class CourseAnnouncementResponse(BaseModel):
    id: int
    course_id: int
    google_announcement_id: str
    text: str | None
    creator_name: str | None
    creator_email: str | None
    creation_time: datetime | None
    update_time: datetime | None
    materials_json: str | None
    alternate_link: str | None
    created_at: datetime

    class Config:
        from_attributes = True
