from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class NotificationSuppression(Base):
    __tablename__ = "notification_suppressions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(50), nullable=False)  # "assignment", "task", etc.
    source_id = Column(Integer, nullable=False)
    suppressed_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "source_type", "source_id", name="uq_notification_suppression"),
        Index("ix_notification_suppressions_user", "user_id"),
    )
