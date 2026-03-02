"""Portfolio models — student curated portfolio feature."""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PortfolioItemType(str, enum.Enum):
    STUDY_GUIDE = "study_guide"
    QUIZ_RESULT = "quiz_result"
    ASSIGNMENT = "assignment"
    DOCUMENT = "document"
    NOTE = "note"
    ACHIEVEMENT = "achievement"


class StudentPortfolio(Base):
    __tablename__ = "student_portfolios"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="My Portfolio")
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    items = relationship(
        "PortfolioItem",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        order_by="PortfolioItem.display_order",
    )
    student = relationship("User", foreign_keys=[student_id])


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("student_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(Enum(PortfolioItemType), nullable=False)
    # Reference to source object (study guide id, quiz result id, etc.) — nullable for manual entries
    item_id = Column(Integer, nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)  # student's reflection
    tags = Column(Text, nullable=True)  # JSON list stored as text
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    portfolio = relationship("StudentPortfolio", back_populates="items")
