from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, LargeBinary, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.db.database import Base


class ContentImage(Base):
    __tablename__ = "content_images"

    id = Column(Integer, primary_key=True, index=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="CASCADE"), nullable=False)
    image_data = Column(LargeBinary, nullable=False)
    media_type = Column(String(50), nullable=False)  # image/png, image/jpeg, etc.
    description = Column(Text, nullable=True)  # Vision OCR description
    position_context = Column(Text, nullable=True)  # Surrounding text from source doc
    position_index = Column(Integer, nullable=False, default=0)  # Order in document
    file_size = Column(Integer, nullable=True)  # Size in bytes
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course_content = relationship("CourseContent", backref=backref("images", passive_deletes=True))

    __table_args__ = (
        Index("ix_content_images_content", "course_content_id"),
    )
