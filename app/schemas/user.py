from pydantic import BaseModel, EmailStr, field_validator, model_validator
from datetime import datetime

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole | None = None  # Single role (backward compat)
    roles: list[UserRole] = []    # New multi-role field
    teacher_type: str | None = None  # only relevant when role=teacher
    google_id: str | None = None

    @model_validator(mode='after')
    def validate_roles(self):
        # If roles list is empty, use single role field
        if not self.roles and self.role:
            self.roles = [self.role]
        # No roles provided = roleless registration (onboarding deferred)
        # This is valid — user will complete onboarding post-login

        # Prevent self-assigned admin
        if UserRole.ADMIN in self.roles:
            raise ValueError("Admin role cannot be self-registered")

        # Set primary role (first in list becomes active role)
        if self.roles and not self.role:
            self.role = self.roles[0]

        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str | None = None
    full_name: str
    role: UserRole | None = None
    roles: list[str] = []
    is_active: bool
    google_connected: bool = False
    needs_onboarding: bool = False
    email_verified: bool = False
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


class OnboardingRequest(BaseModel):
    roles: list[str]
    teacher_type: str | None = None


class EmailVerifyRequest(BaseModel):
    token: str
