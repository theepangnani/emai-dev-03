from sqlalchemy import BigInteger, Column, Integer, String, Boolean, DateTime, Enum, Text
from sqlalchemy.sql import func
import enum
import json

from app.db.database import Base


class UserRole(str, enum.Enum):
    PARENT = "parent"
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"
    # CB-CMCP-001 M0-A 0A-3 (#4414): curriculum/board admin roles for the
    # Curriculum + Master Content Plan. Actual RBAC gating for these values
    # ships in M2/M3 stripes — exposing the enum members here so dependencies
    # like require_role(UserRole.BOARD_ADMIN) can compile against them.
    BOARD_ADMIN = "BOARD_ADMIN"
    CURRICULUM_ADMIN = "CURRICULUM_ADMIN"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth users
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=True, index=True)  # Nullable for users pending onboarding
    roles = Column(String(120), nullable=True)  # comma-separated: "parent,teacher,BOARD_ADMIN,CURRICULUM_ADMIN" (#4452)
    needs_onboarding = Column(Boolean, default=False)
    onboarding_completed = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    # Google OAuth
    google_id = Column(String(255), unique=True, nullable=True)
    google_access_token = Column(String(2048), nullable=True)
    google_refresh_token = Column(String(1024), nullable=True)
    google_granted_scopes = Column(String(1024), nullable=True)  # comma-separated granted scopes

    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    assignment_reminder_days = Column(String(50), default="1,3")
    task_reminder_days = Column(String(50), default="1,3")
    notification_preferences = Column(Text, nullable=True)  # JSON: per-category in_app/email toggles

    # Onboarding setup checklist
    onboarding_dismissed_at = Column(DateTime(timezone=True), nullable=True)

    # Tutorial completion tracking (JSON: {"step_name": true, ...})
    tutorial_completed = Column(Text, default="{}")

    # AI usage limits
    ai_usage_limit = Column(Integer, default=10)
    ai_usage_count = Column(Integer, default=0)

    # Account lockout (brute-force protection)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_failed_login = Column(DateTime(timezone=True), nullable=True)

    # Teacher communication sync state
    gmail_last_sync = Column(DateTime(timezone=True), nullable=True)
    classroom_last_sync = Column(DateTime(timezone=True), nullable=True)

    # Interests/hobbies for AI prompt personalization
    interests = Column(Text, nullable=True)  # JSON array string, e.g. '["pokemon","basketball"]'

    # Storage limits (#1007)
    storage_used_bytes = Column(BigInteger, default=0)
    storage_limit_bytes = Column(BigInteger, default=104857600)
    upload_limit_bytes = Column(Integer, default=10485760)

    # Multilingual & timezone preferences (#2024, #2422)
    preferred_language = Column(String(10), default="en", nullable=False, server_default="en")
    timezone = Column(String(50), default="America/Toronto", nullable=False, server_default="America/Toronto")

    # Daily email digest opt-in
    daily_digest_enabled = Column(Boolean, default=False)

    # CASL email consent (#2022)
    email_marketing_consent = Column(Boolean, nullable=True, default=False)
    email_consent_date = Column(DateTime, nullable=True)

    # Account deletion (soft-delete with 30-day grace period)
    deletion_requested_at = Column(DateTime(timezone=True), nullable=True)
    deletion_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False)

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

    # ── Notification preference helpers ──────────────────────────

    DEFAULT_NOTIFICATION_PREFERENCES: dict = {
        "assignments": {"in_app": True, "email": True},
        "messages": {"in_app": True, "email": True},
        "study_guides": {"in_app": True, "email": False},
        "tasks": {"in_app": True, "email": True},
        "system": {"in_app": True, "email": False},
    }

    # Map NotificationType values to preference categories
    NOTIFICATION_TYPE_TO_CATEGORY: dict = {
        "assignment_due": "assignments",
        "grade_posted": "assignments",
        "assessment_upcoming": "assignments",
        "project_due": "assignments",
        "message": "messages",
        "parent_request": "messages",
        "link_request": "messages",
        "study_guide_created": "study_guides",
        "material_uploaded": "study_guides",
        "task_due": "tasks",
        "task_created": "tasks",
        "task_upgraded": "tasks",
        "system": "system",
        "survey_completed": "system",
    }

    def get_notification_preferences(self) -> dict:
        """Return parsed notification preferences, falling back to defaults."""
        if self.notification_preferences:
            try:
                saved = json.loads(self.notification_preferences)
                # Merge with defaults so new categories get default values
                merged = {}
                for cat, defaults in self.DEFAULT_NOTIFICATION_PREFERENCES.items():
                    merged[cat] = {**defaults, **saved.get(cat, {})}
                return merged
            except (json.JSONDecodeError, TypeError):
                pass
        return dict(self.DEFAULT_NOTIFICATION_PREFERENCES)

    def set_notification_preferences(self, prefs: dict) -> None:
        """Persist notification preferences as JSON."""
        self.notification_preferences = json.dumps(prefs)

    def should_notify(self, notification_type_value: str, channel: str) -> bool:
        """Check if user wants notifications for a given type and channel.

        Args:
            notification_type_value: e.g. "assignment_due", "message"
            channel: "in_app" or "email"
        """
        category = self.NOTIFICATION_TYPE_TO_CATEGORY.get(notification_type_value)
        if not category:
            return True  # Unknown types default to enabled
        prefs = self.get_notification_preferences()
        cat_prefs = prefs.get(category, {})
        return cat_prefs.get(channel, True)
