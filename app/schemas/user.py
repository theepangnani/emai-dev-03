from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole
    teacher_type: str | None = None  # only relevant when role=teacher
    google_id: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str | None = None
    full_name: str
    role: UserRole
    roles: list[str] = []
    is_active: bool
    google_connected: bool = False
    created_at: datetime

    @field_validator("roles", mode="before")
    @classmethod
    def parse_roles(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str) and v:
            return [r.strip() for r in v.split(",") if r.strip()]
        return []

    class Config:
        from_attributes = True


class SwitchRoleRequest(BaseModel):
    role: str


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
