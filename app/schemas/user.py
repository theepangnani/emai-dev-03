import re

from pydantic import BaseModel, EmailStr, field_validator, model_validator
from datetime import datetime, date

from app.models.user import UserRole

USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


class UserCreate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    parent_email: EmailStr | None = None
    password: str
    full_name: str
    role: UserRole | None = None  # Single role (backward compat)
    roles: list[UserRole] = []    # New multi-role field
    teacher_type: str | None = None  # only relevant when role=teacher
    google_id: str | None = None
    date_of_birth: date | None = None  # Optional DOB for students (#783)

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

    @model_validator(mode='after')
    def validate_email_or_username(self):
        # Username validation
        if self.username and not USERNAME_PATTERN.match(self.username):
            raise ValueError("Username must be 3-30 characters, alphanumeric and underscores only")

        # Students can register with username + parent_email instead of email
        if UserRole.STUDENT in self.roles:
            if not self.email and not self.username:
                raise ValueError("Student registration requires either a personal email or a username")
            if self.username and not self.email and not self.parent_email:
                raise ValueError("Parent email is required when registering with a username instead of email")
        else:
            # Non-student roles (and roleless registration) require email
            if not self.email and not self.username:
                raise ValueError("Email is required for registration")

        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str | None = None
    username: str | None = None
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
