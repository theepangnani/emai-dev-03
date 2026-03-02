"""Academic Plan models for Ontario course planning (#501).

AcademicPlan  — multi-year plan per student (Grade 9-12, 2 semesters)
PlanCourse    — individual course entry within a plan
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AcademicPlan(Base):
    __tablename__ = "academic_plans"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), default="My Academic Plan", nullable=False)
    start_grade = Column(Integer, default=9, nullable=False)            # Grade student starts (9)
    target_graduation_year = Column(Integer, nullable=True)
    status = Column(String(20), default="draft", nullable=False)        # draft, active, completed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plan_courses = relationship(
        "PlanCourse",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_academic_plans_student", "student_id"),
        Index("ix_academic_plans_created_by", "created_by_user_id"),
    )


class PlanCourse(Base):
    __tablename__ = "plan_courses"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("academic_plans.id", ondelete="CASCADE"), nullable=False)
    course_code = Column(String(20), nullable=False)        # e.g. "MCR3U" — references CourseCatalogItem.course_code
    course_name = Column(String(300), nullable=False)        # denormalized for display
    subject_area = Column(String(100), nullable=True)
    grade_level = Column(Integer, nullable=False)            # 9, 10, 11, or 12
    semester = Column(Integer, nullable=False)               # 1 or 2
    credit_value = Column(Float, default=1.0, nullable=False)
    pathway = Column(String(10), nullable=True)              # U, C, M, E, O
    status = Column(String(20), default="planned", nullable=False)  # planned, in_progress, completed, dropped
    final_mark = Column(Integer, nullable=True)              # 0-100, set when completed
    is_compulsory = Column(Boolean, default=False, nullable=False)
    compulsory_category = Column(String(100), nullable=True)

    plan = relationship("AcademicPlan", back_populates="plan_courses")

    __table_args__ = (
        UniqueConstraint("plan_id", "course_code", name="uq_plan_course"),
        Index("ix_plan_courses_plan", "plan_id"),
    )
