from pydantic import BaseModel

from app.schemas.user import UserResponse


class AdminUserList(BaseModel):
    users: list[UserResponse]
    total: int


class AdminStats(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_courses: int
    total_assignments: int
