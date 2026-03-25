from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class SchoolReportCard(Base):
    __tablename__ = "school_report_cards"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # File storage
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=True)  # local dev
    gcs_path = Column(String(500), nullable=True)  # GCS prod
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)

    # Extracted text
    text_content = Column(Text, nullable=True)

    # Metadata
    term = Column(String(100), nullable=True)  # "Term 1 February 2026"
    grade_level = Column(String(20), nullable=True)  # "08", "10" (string for JK/SK)
    school_name = Column(String(255), nullable=True)
    report_date = Column(Date, nullable=True)
    school_year = Column(String(20), nullable=True)  # "2025-2026"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    student = relationship("Student", backref="school_report_cards")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])

    __table_args__ = (
        Index("ix_school_report_cards_student", "student_id"),
        Index("ix_school_report_cards_uploaded_by", "uploaded_by_user_id"),
    )


class SchoolReportCardAnalysis(Base):
    __tablename__ = "school_report_card_analyses"

    id = Column(Integer, primary_key=True, index=True)
    report_card_id = Column(Integer, ForeignKey("school_report_cards.id", ondelete="CASCADE"), nullable=True)  # NULL for career_path
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    analysis_type = Column(String(20), nullable=False)  # "full" or "career_path"
    content = Column(Text, nullable=False)  # JSON string
    content_hash = Column(String(64), nullable=True)  # SHA-256 for cache
    ai_model = Column(String(50), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    report_card = relationship("SchoolReportCard", backref="analyses")
    student = relationship("Student")

    __table_args__ = (
        Index("ix_src_analyses_report_card", "report_card_id"),
        Index("ix_src_analyses_student_type", "student_id", "analysis_type"),
    )
