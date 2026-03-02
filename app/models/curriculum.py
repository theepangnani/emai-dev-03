"""
Ontario Curriculum Expectations model (#571).

Stores Ontario curriculum learning outcomes (expectations) keyed by course code,
strand, and expectation code. Used to anchor AI-generated study materials to the
official Ontario curriculum.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.db.database import Base


class CurriculumExpectation(Base):
    __tablename__ = "curriculum_expectations"

    id = Column(Integer, primary_key=True)
    course_code = Column(String(20), nullable=False, index=True)   # "MCR3U"
    strand = Column(String(200), nullable=False)                    # "A: Characteristics of Functions"
    expectation_code = Column(String(20), nullable=False)          # "A1.1", "B2.3"
    description = Column(Text, nullable=False)                     # Full expectation text
    expectation_type = Column(String(20), default="specific")      # "overall" or "specific"
    grade_level = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("course_code", "expectation_code", name="uq_curriculum_code_expectation"),
    )
