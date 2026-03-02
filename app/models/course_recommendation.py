"""CourseRecommendation model — AI-generated course suggestions per academic plan (#503).

Stores the latest AI recommendations for a student's plan, including goal,
interests, recommended courses, and overall advice.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CourseRecommendation(Base):
    __tablename__ = "course_recommendations"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("academic_plans.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    goal = Column(String(50), nullable=False)           # university | college | workplace | undecided
    interests = Column(JSON, nullable=True)             # list[str]
    target_programs = Column(JSON, nullable=True)       # list[str]
    recommendations = Column(JSON, nullable=False)      # list of recommendation objects
    overall_advice = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=func.now())

    plan = relationship("AcademicPlan", lazy="select")
    student = relationship("Student", lazy="select")
