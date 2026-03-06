from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, LargeBinary, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class SourceFile(Base):
    """Original file uploaded as part of a multi-file OCR course content creation.

    Stores the raw binary data so users can view/download the original files
    even after text extraction has been performed.
    """
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, index=True)
    course_content_id = Column(
        Integer,
        ForeignKey("course_contents.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=True)  # MIME type
    file_size = Column(Integer, nullable=True)  # bytes
    file_data = Column(LargeBinary, nullable=False)  # raw binary content

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course_content = relationship(
        "CourseContent",
        backref=backref("source_files", passive_deletes=True, lazy="dynamic"),
    )

    __table_args__ = (
        Index("ix_source_files_content", "course_content_id"),
    )
