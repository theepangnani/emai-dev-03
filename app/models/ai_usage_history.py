from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AIUsageHistory(Base):
    __tablename__ = "ai_usage_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_type = Column(String(20), nullable=False)  # study_guide, quiz, flashcard
    course_material_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True)
    credits_used = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    course_material = relationship("CourseContent", foreign_keys=[course_material_id], lazy="joined")
