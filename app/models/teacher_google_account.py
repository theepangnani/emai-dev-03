from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TeacherGoogleAccount(Base):
    __tablename__ = "teacher_google_accounts"
    __table_args__ = (
        UniqueConstraint("teacher_id", "google_email", name="uq_teacher_google_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    google_id = Column(String(255), nullable=False)
    google_email = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    access_token = Column(String(512), nullable=True)
    refresh_token = Column(String(512), nullable=True)
    account_label = Column(String(100), nullable=True)
    is_primary = Column(Boolean, default=False)
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    teacher = relationship("Teacher", backref="google_accounts")
