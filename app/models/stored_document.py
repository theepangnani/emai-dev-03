"""StoredDocument model — tracks files saved via FileStorageService (#572)."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class StoredDocument(Base):
    __tablename__ = "stored_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_content_id = Column(
        Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True
    )

    # Storage service key — the path within FileStorageService (e.g. "users/123/uploads/abc.pdf")
    storage_key = Column(String(500), nullable=False)
    original_name = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    sha256 = Column(String(64), nullable=True)  # for dedup
    folder = Column(String(50), nullable=False, default="uploads")  # "uploads" | "report_cards" | "exams"

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    course_content = relationship("CourseContent", foreign_keys=[course_content_id])

    __table_args__ = (
        Index("ix_stored_documents_user_id", "user_id"),
        Index("ix_stored_documents_storage_key", "storage_key"),
    )
