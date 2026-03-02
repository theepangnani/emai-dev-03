from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Per-type in-app toggles
    in_app_assignments = Column(Boolean, default=True, nullable=False)
    in_app_messages = Column(Boolean, default=True, nullable=False)
    in_app_tasks = Column(Boolean, default=True, nullable=False)
    in_app_system = Column(Boolean, default=True, nullable=False)
    in_app_reminders = Column(Boolean, default=True, nullable=False)

    # Per-type email toggles
    email_assignments = Column(Boolean, default=True, nullable=False)
    email_messages = Column(Boolean, default=True, nullable=False)
    email_tasks = Column(Boolean, default=True, nullable=False)
    email_reminders = Column(Boolean, default=True, nullable=False)

    # Digest mode: True = daily digest instead of immediate emails
    digest_mode = Column(Boolean, default=False, nullable=False)
    digest_hour = Column(Integer, default=8, nullable=False)  # 0-23, user's preferred hour
    last_digest_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="notification_preferences")
