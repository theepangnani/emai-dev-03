"""Translation cache for parent summaries (#2015)."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.db.database import Base


class TranslatedSummary(Base):
    __tablename__ = "translated_summaries"

    id = Column(Integer, primary_key=True)
    study_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(10), nullable=False)
    translated_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("study_guide_id", "language", name="uq_translated_summary_guide_lang"),
    )
