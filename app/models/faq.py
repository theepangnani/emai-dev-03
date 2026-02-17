import enum

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class FAQCategory(str, enum.Enum):
    """Valid FAQ categories (used for validation; stored as String in DB)."""
    GETTING_STARTED = "getting-started"
    GOOGLE_CLASSROOM = "google-classroom"
    STUDY_TOOLS = "study-tools"
    ACCOUNT = "account"
    COURSES = "courses"
    MESSAGING = "messaging"
    TASKS = "tasks"
    OTHER = "other"


class FAQQuestionStatus(str, enum.Enum):
    """Valid question statuses (used for validation; stored as String in DB)."""
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class FAQAnswerStatus(str, enum.Enum):
    """Valid answer approval statuses (used for validation; stored as String in DB)."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FAQQuestion(Base):
    __tablename__ = "faq_questions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    # Stored as String for cross-DB compatibility (PostgreSQL Enum stores NAMES not values)
    category = Column(String(50), default=FAQCategory.OTHER.value)
    status = Column(String(20), default=FAQQuestionStatus.OPEN.value)
    error_code = Column(String(100), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_pinned = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by_user_id])
    answers = relationship("FAQAnswer", back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_faq_questions_category_status", "category", "status"),
        Index("ix_faq_questions_pinned", "is_pinned"),
        Index("ix_faq_questions_archived", "archived_at"),
    )


class FAQAnswer(Base):
    __tablename__ = "faq_answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("faq_questions.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Stored as String for cross-DB compatibility
    status = Column(String(20), default=FAQAnswerStatus.PENDING.value)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    is_official = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    question = relationship("FAQQuestion", back_populates="answers")
    creator = relationship("User", foreign_keys=[created_by_user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])

    __table_args__ = (
        Index("ix_faq_answers_question_status", "question_id", "status"),
        Index("ix_faq_answers_pending", "status", "created_at"),
    )
