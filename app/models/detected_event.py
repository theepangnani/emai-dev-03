"""DetectedEvent model — stores assessment dates found in documents or Google Classroom."""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class DetectedEvent(Base):
    __tablename__ = "detected_events"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id"), nullable=True)
    event_type = Column(String(30), nullable=False)  # test, exam, quiz, assignment, lab
    event_title = Column(String(200), nullable=False)
    event_date = Column(Date, nullable=False)
    source = Column(String(30), nullable=False, default="document_parse")  # document_parse, google_classroom
    dismissed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
