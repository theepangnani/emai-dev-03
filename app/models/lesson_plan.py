"""Lesson Plan model for TeachAssist-compatible lesson planning.

Supports three plan types matching Ontario teaching practice:
  - LONG_RANGE: whole-year overview (LRP)
  - UNIT: 2-6 week unit plan (UP)
  - DAILY: individual day lesson plan
"""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class LessonPlanType(str, enum.Enum):
    LONG_RANGE = "long_range"  # LRP: whole-year overview
    UNIT = "unit"              # UP: 2-6 week unit
    DAILY = "daily"            # Day plan: individual lesson


class LessonPlan(Base):
    """Lesson plan record compatible with Ontario TeachAssist planning structure."""

    __tablename__ = "lesson_plans"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id = Column(
        Integer,
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    plan_type = Column(Enum(LessonPlanType), nullable=False)
    title = Column(String(500), nullable=False)

    # Ontario curriculum metadata
    strand = Column(String(255), nullable=True)          # e.g. "Number Sense"
    unit_number = Column(Integer, nullable=True)
    grade_level = Column(String(10), nullable=True)      # "9", "10", "11", "12"
    subject_code = Column(String(20), nullable=True)     # Ontario code e.g. "MPM2D"

    # Curriculum expectations stored as JSON arrays
    big_ideas = Column(Text, nullable=True)                    # JSON list
    curriculum_expectations = Column(Text, nullable=True)      # JSON list of codes e.g. ["B1.1"]
    overall_expectations = Column(Text, nullable=True)         # JSON list
    specific_expectations = Column(Text, nullable=True)        # JSON list

    # Learning design
    learning_goals = Column(Text, nullable=True)         # JSON list
    success_criteria = Column(Text, nullable=True)       # JSON list

    # 3-Part Lesson structure (Ontario standard)
    three_part_lesson = Column(Text, nullable=True)      # JSON: {minds_on, action, consolidation}

    # Assessment
    assessment_for_learning = Column(Text, nullable=True)  # formative strategies
    assessment_of_learning = Column(Text, nullable=True)   # summative strategies

    # Differentiation
    differentiation = Column(Text, nullable=True)        # JSON: {enrichment, support, ell}

    # Resources
    materials_resources = Column(Text, nullable=True)    # JSON list
    cross_curricular = Column(Text, nullable=True)       # JSON list of connected subjects

    # Scheduling
    duration_minutes = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Template / import metadata
    is_template = Column(Boolean, default=False, nullable=False)
    imported_from = Column(String(50), nullable=True)    # "teachassist", "manual", "ai_generated"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    teacher = relationship("Teacher", backref=backref("lesson_plans", passive_deletes=True))
    course = relationship("Course", foreign_keys=[course_id])

    __table_args__ = (
        Index("ix_lesson_plans_teacher_type", "teacher_id", "plan_type"),
        Index("ix_lesson_plans_teacher_course", "teacher_id", "course_id"),
        Index("ix_lesson_plans_template", "is_template"),
    )
