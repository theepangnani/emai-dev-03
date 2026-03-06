from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class DataExportRequest(Base):
    __tablename__ = "data_export_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    file_path = Column(String(500), nullable=True)
    download_token = Column(String(64), unique=True, nullable=False, index=True)
    error_message = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    __table_args__ = (
        Index("ix_data_export_requests_user", "user_id"),
        Index("ix_data_export_requests_status", "status"),
    )
