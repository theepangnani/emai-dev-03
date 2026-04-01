from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Float, Integer, String, ForeignKey, DateTime, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AIUsageHistory(Base):
    __tablename__ = "ai_usage_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_type = Column(String(50), nullable=False)  # study_guide, quiz, flashcard, conversation_starters, etc.
    course_material_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True)
    credits_used = Column(Integer, nullable=False, default=1)
    # Token / cost tracking (#1650)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    model_name = Column(String(50), nullable=True)
    # Regeneration tracking (#1651)
    is_regeneration = Column(Boolean, nullable=False, server_default=text("false"))
    parent_generation_id = Column(Integer, ForeignKey("ai_usage_history.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    course_material = relationship("CourseContent", foreign_keys=[course_material_id], lazy="joined")


class AIAdminActionLog(Base):
    __tablename__ = "ai_admin_action_log"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # "set_limit", "reset_count", "approve_request", "decline_request", "bulk_set_limit"
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(String(500), nullable=True)  # JSON or descriptive text
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    admin_user = relationship("User", foreign_keys=[admin_user_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
