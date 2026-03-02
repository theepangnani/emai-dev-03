"""Resource Library models — shared teaching material repository for teachers.

Tables:
  - teacher_resources: individual teaching materials (lesson plans, worksheets, etc.)
  - resource_ratings: per-teacher ratings (1-5) with optional comments
  - resource_collections: personal curated collections of resources per teacher
"""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class ResourceType(str, enum.Enum):
    LESSON_PLAN = "lesson_plan"
    WORKSHEET = "worksheet"
    PRESENTATION = "presentation"
    ASSESSMENT = "assessment"
    VIDEO_LINK = "video_link"
    ACTIVITY = "activity"
    RUBRIC = "rubric"
    OTHER = "other"


class TeacherResource(Base):
    """A teaching material published by a teacher to the shared resource library."""

    __tablename__ = "teacher_resources"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    resource_type = Column(Enum(ResourceType), nullable=False)
    subject = Column(String(255), nullable=True, index=True)
    grade_level = Column(String(50), nullable=True, index=True)  # e.g. "Grade 9", "Grade 10"

    # Stored as JSON text: ["tag1", "tag2"]
    tags = Column(Text, nullable=True)

    is_public = Column(Boolean, default=False, nullable=False)

    # File or URL reference (mutually exclusive but both optional)
    file_key = Column(String(500), nullable=True)         # stored file reference (relative path)
    external_url = Column(String(2000), nullable=True)    # external link (YouTube, Drive, etc.)

    # Engagement metrics
    download_count = Column(Integer, default=0, nullable=False)
    rating_sum = Column(Integer, default=0, nullable=False)
    rating_count = Column(Integer, default=0, nullable=False)

    # Ontario curriculum alignment
    curriculum_expectation = Column(String(500), nullable=True)  # e.g. "B1.2 — Reading Strategies"

    # Optional link to a lesson plan for remix integration
    linked_lesson_plan_id = Column(
        Integer,
        ForeignKey("lesson_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_id])
    linked_lesson_plan = relationship("LessonPlan", foreign_keys=[linked_lesson_plan_id])
    ratings = relationship(
        "ResourceRating",
        back_populates="resource",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_teacher_resources_teacher_public", "teacher_id", "is_public"),
        Index("ix_teacher_resources_type", "resource_type"),
        Index("ix_teacher_resources_subject_grade", "subject", "grade_level"),
    )

    @property
    def avg_rating(self) -> float:
        """Computed average rating; 0.0 when no ratings yet."""
        if self.rating_count == 0:
            return 0.0
        return round(self.rating_sum / self.rating_count, 2)


class ResourceRating(Base):
    """A teacher's rating (1-5) for a shared resource."""

    __tablename__ = "resource_ratings"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(
        Integer,
        ForeignKey("teacher_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rating = Column(Integer, nullable=False)   # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resource = relationship("TeacherResource", back_populates="ratings")
    teacher = relationship("User", foreign_keys=[teacher_id])

    __table_args__ = (
        UniqueConstraint("resource_id", "teacher_id", name="uq_resource_rating_per_teacher"),
    )


class ResourceCollection(Base):
    """A personally curated collection of teacher resources."""

    __tablename__ = "resource_collections"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # JSON list of resource IDs: [1, 5, 12, ...]
    resource_ids = Column(Text, nullable=True, default="[]")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_id])

    __table_args__ = (
        Index("ix_resource_collections_teacher", "teacher_id"),
    )
