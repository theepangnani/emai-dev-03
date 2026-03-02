"""AIInsight model — holistic AI academic analysis for parents (#581)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    generated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Content
    insight_type = Column(String(30), nullable=False, default="on_demand")  # weekly | monthly | on_demand
    summary = Column(Text, nullable=False)                 # 2-3 sentence overview
    strengths = Column(Text, nullable=True)                # JSON list of strength descriptions
    concerns = Column(Text, nullable=True)                 # JSON list of concern descriptions
    recommendations = Column(Text, nullable=True)          # JSON list of actionable items for parents
    subject_analysis = Column(Text, nullable=True)         # JSON: per-subject trends
    learning_style_note = Column(Text, nullable=True)      # AI observation on learning patterns
    parent_actions = Column(Text, nullable=True)           # JSON list of specific things parent can do this week

    # Metadata
    data_snapshot_json = Column(Text, nullable=True)       # JSON of raw data used (for audit)
    generated_at = Column(DateTime, nullable=False, default=func.now())
    period_start = Column(Date, nullable=True)             # if weekly/monthly
    period_end = Column(Date, nullable=True)

    # Relationships
    student = relationship("Student", backref="ai_insights")
    generated_by = relationship("User", foreign_keys=[generated_by_user_id])

    __table_args__ = (
        Index("ix_ai_insights_student", "student_id"),
        Index("ix_ai_insights_generated_at", "generated_at"),
    )
