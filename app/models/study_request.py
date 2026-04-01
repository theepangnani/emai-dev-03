"""StudyRequest model — parent-initiated study suggestions for students."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class StudyRequest(Base):
    __tablename__ = "study_requests"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    topic = Column(String(200), nullable=True)
    urgency = Column(String(20), nullable=False, default="normal")  # low, normal, high
    message = Column(String(500), nullable=True)  # Parent's note
    status = Column(String(20), nullable=False, default="pending")  # pending, accepted, deferred, completed
    student_response = Column(String(500), nullable=True)  # Student's reply
    responded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("User", foreign_keys=[parent_id])
    student = relationship("User", foreign_keys=[student_id])
