from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)

    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parent = relationship("User", foreign_keys=[parent_id], backref="created_tasks")
    student = relationship("Student", backref="tasks")

    __table_args__ = (
        Index("ix_tasks_parent_completed", "parent_id", "is_completed"),
        Index("ix_tasks_student_due", "student_id", "due_date"),
    )
