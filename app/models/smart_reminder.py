"""Smart Reminder models — multi-stage urgency tracking and user preferences."""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ReminderUrgency(str, enum.Enum):
    LOW = "low"          # 3+ days out
    MEDIUM = "medium"    # 1 day out
    HIGH = "high"        # 3 hours out
    CRITICAL = "critical"  # past due


class ReminderLog(Base):
    """Records every reminder sent so we never send duplicate reminders at the same urgency level."""

    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True)

    urgency = Column(Enum(ReminderUrgency), nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    channel = Column(String(20), nullable=False, default="in_app")  # "email" | "in_app" | "push"
    priority_score = Column(Float, nullable=True)

    user = relationship("User")

    __table_args__ = (
        # Prevents duplicate reminders at the same urgency level for the same (user, assignment)
        UniqueConstraint("user_id", "assignment_id", "urgency", name="uq_reminder_log_user_assignment_urgency"),
        Index("ix_reminder_logs_user_sent", "user_id", "sent_at"),
        Index("ix_reminder_logs_assignment", "assignment_id"),
    )


class ReminderPreference(Base):
    """Per-user reminder preferences — stored once and updated via API."""

    __tablename__ = "reminder_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    remind_3_days = Column(Boolean, default=True, nullable=False)
    remind_1_day = Column(Boolean, default=True, nullable=False)
    remind_3_hours = Column(Boolean, default=True, nullable=False)
    remind_overdue = Column(Boolean, default=True, nullable=False)

    # Opt in/out of AI-generated personalized messages
    ai_personalized_messages = Column(Boolean, default=True, nullable=False)

    # How many hours overdue before notifying linked parent (0 = never)
    parent_escalation_hours = Column(Integer, default=24, nullable=False)

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")

    __table_args__ = (
        Index("ix_reminder_preferences_user", "user_id"),
    )
