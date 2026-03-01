import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


VALID_RECURRENCE_RULES = {"daily", "weekly", "biweekly", "monthly"}


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id = Column(Integer, primary_key=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), default="medium")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[created_by_user_id])


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    # Stored as lowercase string values for compatibility with existing DB rows.
    priority = Column(String(10), default=TaskPriority.MEDIUM.value)
    category = Column(String(50), nullable=True)

    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Recurring task fields (#880)
    recurrence_rule = Column(String(50), nullable=True)  # daily, weekly, biweekly, monthly
    recurrence_end_date = Column(DateTime(timezone=True), nullable=True)
    template_id = Column(Integer, ForeignKey("task_templates.id", ondelete="SET NULL"), nullable=True)

    # Linked entities (optional)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True)
    study_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="SET NULL"), nullable=True)

    # Legacy columns kept for backwards compat (SQLite can't DROP COLUMN easily)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)

    last_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Google Calendar integration
    google_calendar_event_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[created_by_user_id], backref=backref("created_tasks", passive_deletes=True))
    assignee = relationship("User", foreign_keys=[assigned_to_user_id], backref="assigned_tasks")
    course = relationship("Course", foreign_keys=[course_id])
    course_content = relationship("CourseContent", foreign_keys=[course_content_id])
    study_guide = relationship("StudyGuide", foreign_keys=[study_guide_id])
    template = relationship("TaskTemplate", foreign_keys=[template_id])
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan", order_by="TaskComment.created_at")

    __table_args__ = (
        Index("ix_tasks_creator_completed", "created_by_user_id", "is_completed"),
        Index("ix_tasks_assignee_due", "assigned_to_user_id", "due_date"),
        Index("ix_tasks_archived", "archived_at"),
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    task = relationship("Task", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_task_comments_task_id", "task_id"),
    )
