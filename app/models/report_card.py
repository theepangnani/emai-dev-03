"""ReportCard model — stores uploaded PDF/image report cards with AI-extracted marks."""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.database import Base


class ReportCard(Base):
    __tablename__ = "report_cards"

    id = Column(Integer, primary_key=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    term = Column(String(50), nullable=False)              # "Fall 2025", "Semester 1 2025", etc.
    academic_year = Column(String(20), nullable=True)      # "2025-2026"
    file_name = Column(String(500), nullable=False)
    file_content_b64 = Column(Text, nullable=False)        # base64 PDF/image
    file_size_bytes = Column(Integer, nullable=True)

    # AI-extracted data
    extracted_marks = Column(JSON, nullable=True)          # [{ subject, mark, max_mark, percentage }]
    overall_average = Column(Float, nullable=True)         # computed from extracted_marks
    ai_observations = Column(Text, nullable=True)          # Markdown AI analysis
    ai_strengths = Column(JSON, nullable=True)             # [str] top 3 subjects
    ai_improvement_areas = Column(JSON, nullable=True)     # [str] bottom 3 subjects

    status = Column(String(20), default="uploaded")        # uploaded, processing, analyzed, failed
    uploaded_at = Column(DateTime, default=func.now())
    analyzed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
