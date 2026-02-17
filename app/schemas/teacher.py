from pydantic import BaseModel
from datetime import datetime


class TeacherResponse(BaseModel):
    id: int
    user_id: int | None
    school_name: str | None
    department: str | None
    teacher_type: str | None
    is_shadow: bool = False
    is_platform_user: bool = True
    google_email: str | None = None
    full_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherGoogleAccountResponse(BaseModel):
    id: int
    teacher_id: int
    google_email: str
    display_name: str | None
    account_label: str | None
    is_primary: bool
    connected_at: datetime | None
    last_sync_at: datetime | None

    class Config:
        from_attributes = True
