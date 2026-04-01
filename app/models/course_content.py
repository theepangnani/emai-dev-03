import enum

from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func, text

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

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    category = Column(String(100), nullable=True)
    display_order = Column(Integer, default=0, server_default="0")

    # Material hierarchy (#1740)
<<<<<<< HEAD
    parent_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True)
    is_master = Column(Boolean, nullable=False, default=False, server_default=text("false"))
=======
    parent_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True, index=True)
    is_master = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
>>>>>>> origin/fix/2794-model-consistency
    material_group_id = Column(Integer, nullable=True)

    # Upload source tracking (#2010)
    source_type = Column(String(20), nullable=True, default="local_upload")

    # Study Guide Strategy Pattern (§6.105, #1972)
    document_type = Column(String(30), nullable=True)  # teacher_notes, course_syllabus, past_exam, mock_exam, project_brief, lab_experiment, textbook_excerpt, custom
    study_goal = Column(String(30), nullable=True)  # upcoming_test, final_exam, assignment, lab_prep, general_review, discussion, parent_review
    study_goal_text = Column(String(200), nullable=True)  # Free-form focus text for study goal

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)

    course = relationship("Course", backref=backref("contents", passive_deletes=True))
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    resource_links = relationship("ResourceLink", back_populates="course_content", cascade="all, delete-orphan")

    # Material hierarchy relationships
    parent_material = relationship("CourseContent", remote_side=[id], backref=backref("sub_materials", lazy="dynamic"))

    @property
    def course_name(self) -> str | None:
        return self.course.name if self.course else None

    __table_args__ = (
        Index("ix_course_contents_course", "course_id"),
        Index("ix_course_contents_type", "course_id", "content_type"),
        Index("ix_course_contents_material_group", "material_group_id"),
        Index("ix_course_contents_created_by", "created_by_user_id"),
    )
