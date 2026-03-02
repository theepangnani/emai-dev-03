from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.database import Base


class SessionType(str, enum.Enum):
    WORK = "work"              # 25-minute focus block
    SHORT_BREAK = "short_break"  # 5-minute break
    LONG_BREAK = "long_break"    # 15-minute break


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_type = Column(Enum(SessionType), nullable=False, default=SessionType.WORK)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="study_sessions")
    course = relationship("Course", backref="study_sessions")

    __table_args__ = (
        Index("ix_study_sessions_user_id", "user_id"),
        Index("ix_study_sessions_started_at", "started_at"),
    )


class StudyStreak(Base):
    __tablename__ = "study_streaks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_session_date = Column(Date, nullable=True)
    total_sessions = Column(Integer, nullable=False, default=0)
    total_focus_minutes = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    user = relationship("User", backref="study_streak")

    __table_args__ = (
        Index("ix_study_streaks_user_id", "user_id"),
    )
