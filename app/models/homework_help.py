import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class SubjectArea(str, enum.Enum):
    MATH = "math"
    SCIENCE = "science"
    ENGLISH = "english"
    HISTORY = "history"
    FRENCH = "french"
    GEOGRAPHY = "geography"
    OTHER = "other"


class HelpMode(str, enum.Enum):
    HINT = "hint"
    EXPLAIN = "explain"
    SOLVE = "solve"
    CHECK = "check"


class HomeworkSession(Base):
    __tablename__ = "homework_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(Enum(SubjectArea), nullable=False)
    question = Column(Text, nullable=False)
    mode = Column(Enum(HelpMode), nullable=False)
    response = Column(Text, nullable=False)
    follow_up_count = Column(Integer, default=0, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", foreign_keys=[student_id], backref="homework_sessions")
    saved_solution = relationship(
        "HomeworkSavedSolution",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class HomeworkSavedSolution(Base):
    __tablename__ = "homework_saved_solutions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("homework_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    tags = Column(JSON, nullable=True)  # list of tag strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", foreign_keys=[student_id], backref="homework_saved_solutions")
    session = relationship("HomeworkSession", back_populates="saved_solution")
