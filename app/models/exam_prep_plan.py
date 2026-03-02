"""ExamPrepPlan model — AI-generated personalized exam preparation plans (#576)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ExamPrepPlan(Base):
    __tablename__ = "exam_prep_plans"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)  # optional — specific course
    exam_date = Column(Date, nullable=True)
    title = Column(String(300), nullable=False)

    # AI-generated plan content
    weak_areas = Column(JSON, nullable=True)             # [{ topic, confidence_pct, source }]
    study_schedule = Column(JSON, nullable=True)         # [{ day, tasks: [str] }] — daily plan until exam
    recommended_resources = Column(JSON, nullable=True)  # [{ type, title, study_guide_id? }]
    ai_advice = Column(Text, nullable=True)              # Markdown motivational + strategic advice

    status = Column(String(20), default="active")        # active, completed, archived
    generated_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    student = relationship("Student", backref="exam_prep_plans")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    course = relationship("Course", backref="exam_prep_plans")

    __table_args__ = (
        Index("ix_exam_prep_plans_student", "student_id"),
        Index("ix_exam_prep_plans_course", "course_id"),
    )
