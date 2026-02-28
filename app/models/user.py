from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
import enum

from app.db.database import Base


class UserRole(str, enum.Enum):
    PARENT = "parent"
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth users
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=True)  # Nullable for users pending onboarding
    roles = Column(String(50), nullable=True)  # comma-separated: "parent,teacher"
    needs_onboarding = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # Google OAuth
    google_id = Column(String(255), unique=True, nullable=True)
    google_access_token = Column(String(512), nullable=True)
    google_refresh_token = Column(String(512), nullable=True)
    google_granted_scopes = Column(String(1024), nullable=True)  # comma-separated granted scopes

    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    assignment_reminder_days = Column(String(50), default="1,3")
    task_reminder_days = Column(String(50), default="1,3")

    # Onboarding setup checklist
    onboarding_dismissed_at = Column(DateTime(timezone=True), nullable=True)

    # Teacher communication sync state
    gmail_last_sync = Column(DateTime(timezone=True), nullable=True)
    classroom_last_sync = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def has_google_scope(self, scope: str) -> bool:
        """Check if user has been granted a specific Google OAuth scope."""
        if not self.google_granted_scopes:
            return False
        return scope in self.google_granted_scopes.split(",")

    def has_role(self, role: "UserRole") -> bool:
        """Check if user holds a specific role (across ALL their roles, not just active)."""
        if not self.roles:
            return self.role == role if self.role else False
        return role.value in self.roles.split(",")

    def get_roles_list(self) -> list["UserRole"]:
        """Return all roles this user holds."""
        if not self.roles:
            return [self.role] if self.role else []
        return [UserRole(r.strip()) for r in self.roles.split(",") if r.strip()]

    def set_roles(self, roles: list["UserRole"]) -> None:
        """Set the roles column from a list of UserRole enums."""
        self.roles = ",".join(r.value for r in roles)
