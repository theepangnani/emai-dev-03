import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class ContentType(str, enum.Enum):
    NOTES = "notes"
    SYLLABUS = "syllabus"
    LABS = "labs"
    ASSIGNMENTS = "assignments"
    READINGS = "readings"
    RESOURCES = "resources"
    OTHER = "other"


class CourseContent(Base):
    __tablename__ = "course_contents"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    text_content = Column(Text, nullable=True)  # Full extracted text from uploaded documents
    # Store as string for cross-DB compatibility (SQLite/PostgreSQL)
    content_type = Column(String(20), nullable=False, default=ContentType.OTHER.value)

    reference_url = Column(String(1000), nullable=True)
    google_classroom_url = Column(String(1000), nullable=True)
    google_classroom_material_id = Column(String(255), nullable=True)

    file_path = Column(String(500), nullable=True)
    original_filename = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)

    # Material type classification (#666): notes, test, lab, assignment, report_card
    material_type = Column(String(50), nullable=True)
    # Flag for assessment content (test/quiz types) (#666)
    is_assessment = Column(Integer, nullable=True, default=0)  # 0=False, 1=True (SQLite compat)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)

    course = relationship("Course", backref=backref("contents", passive_deletes=True))
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    @property
    def course_name(self) -> str | None:
        return self.course.name if self.course else None

    __table_args__ = (
        Index("ix_course_contents_course", "course_id"),
        Index("ix_course_contents_type", "course_id", "content_type"),
    )
