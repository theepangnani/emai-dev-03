from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, nullable=False)
    role = Column(String(10), nullable=False)  # parent / student / teacher
    ip_address = Column(String(45), nullable=True)
    completed = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    answers = relationship("SurveyAnswer", back_populates="response", cascade="all, delete-orphan")


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("survey_responses.id", ondelete="CASCADE"), nullable=False)
    question_key = Column(String(10), nullable=False, index=True)
    question_type = Column(String(20), nullable=False)
    answer_value = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    response = relationship("SurveyResponse", back_populates="answers")
