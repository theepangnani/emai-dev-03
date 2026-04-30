import enum

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class NotificationType(str, enum.Enum):
    ASSIGNMENT_DUE = "assignment_due"
    GRADE_POSTED = "grade_posted"
    MESSAGE = "message"
    SYSTEM = "system"
    TASK_DUE = "task_due"
    TASK_CREATED = "task_created"
    TASK_UPGRADED = "task_upgraded"
    LINK_REQUEST = "link_request"
    MATERIAL_UPLOADED = "material_uploaded"
    STUDY_GUIDE_CREATED = "study_guide_created"
    PARENT_REQUEST = "parent_request"
    ASSESSMENT_UPCOMING = "assessment_upcoming"
    PROJECT_DUE = "project_due"
    STUDY_GUIDE_SHARED = "study_guide_shared"
    SURVEY_COMPLETED = "survey_completed"
    PARENT_EMAIL_DIGEST = "parent_email_digest"
    ILE_AHA_MOMENT = "ile_aha_moment"
    ILE_KNOWLEDGE_DECAY = "ile_knowledge_decay"
    CMCP_CASCADE_FLAGGED = "cmcp.cascade.flagged"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)
    read = Column(Boolean, default=False)

    # ACK system for persistent reminders
    requires_ack = Column(Boolean, default=False)
    acked_at = Column(DateTime(timezone=True), nullable=True)
    source_type = Column(String(50), nullable=True)  # "assignment", "task", "course_content"
    source_id = Column(Integer, nullable=True)
    next_reminder_at = Column(DateTime(timezone=True), nullable=True)
    reminder_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "read", "created_at"),
        Index("ix_notifications_ack_reminder", "requires_ack", "acked_at", "next_reminder_at"),
    )
