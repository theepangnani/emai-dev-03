import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class GoalCategory(str, enum.Enum):
    ACADEMIC = "academic"
    PERSONAL = "personal"
    EXTRACURRICULAR = "extracurricular"
    SKILL = "skill"


class StudentGoal(Base):
    __tablename__ = "student_goals"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=False, default=GoalCategory.ACADEMIC.value)
    target_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default=GoalStatus.ACTIVE.value)
    progress_pct = Column(Integer, nullable=False, default=0)  # 0–100

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    student = relationship("Student", backref="goals")
    milestones = relationship(
        "GoalMilestone",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="GoalMilestone.display_order",
    )

    __table_args__ = (
        Index("ix_student_goals_student_status", "student_id", "status"),
        Index("ix_student_goals_student_category", "student_id", "category"),
    )


class GoalMilestone(Base):
    __tablename__ = "goal_milestones"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("student_goals.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(Date, nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    goal = relationship("StudentGoal", back_populates="milestones")

    __table_args__ = (
        Index("ix_goal_milestones_goal_id", "goal_id"),
    )
