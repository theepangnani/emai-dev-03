"""
Study Session (Pomodoro) model (#2021).
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    subject = Column(String(100), nullable=True)
    duration_seconds = Column(Integer, nullable=False)
    target_duration = Column(Integer, nullable=False, default=1500)
    completed = Column(Boolean, nullable=False, default=False)
    ai_recap = Column(Text, nullable=True)
    xp_awarded = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
