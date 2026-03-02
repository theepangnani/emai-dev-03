from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, func

from app.db.database import Base


class ImportSession(Base):
    __tablename__ = "import_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    source_type = Column(String(50), nullable=False)  # screenshot, copypaste, email, csv, ics, bookmarklet
    status = Column(String(50), nullable=False, default="processing")  # processing, ready_for_review, imported, failed
    raw_data = Column(Text, nullable=True)  # original input (pasted text, email body, etc.)
    parsed_data = Column(JSON, nullable=True)  # AI-extracted structured JSON
    reviewed_data = Column(JSON, nullable=True)  # user-edited JSON ready for commit
    courses_created = Column(Integer, default=0)
    assignments_created = Column(Integer, default=0)
    materials_created = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
