from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class BugReport(Base):
    __tablename__ = "bug_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    screenshot_url = Column(String(500), nullable=True)
    page_url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    github_issue_number = Column(Integer, nullable=True)
    github_issue_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index("ix_bug_reports_user_created", "user_id", "created_at"),
    )
