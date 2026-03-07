from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ResourceLink(Base):
    __tablename__ = "resource_links"

    id = Column(Integer, primary_key=True, index=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(2048), nullable=False)
    resource_type = Column(String(20), nullable=False)  # "youtube" or "external_link"
    title = Column(String(500), nullable=True)
    topic_heading = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(2048), nullable=True)
    youtube_video_id = Column(String(20), nullable=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course_content = relationship("CourseContent", back_populates="resource_links")

    __table_args__ = (
        Index("ix_resource_links_course_content", "course_content_id"),
        Index("ix_resource_links_type", "course_content_id", "resource_type"),
    )
