"""Peer Review system models.

Supports student-to-student rubric-based reviews of written assignments,
with teacher oversight, anonymous reviews, and auto-allocation.
"""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# ---------------------------------------------------------------------------
# JSON helper — use SQLAlchemy's JSON type which works for both SQLite and PG
# ---------------------------------------------------------------------------
try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import Text as JSON  # type: ignore


class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class PeerReviewAssignment(Base):
    """A teacher-created peer review assignment with rubric and settings."""

    __tablename__ = "peer_review_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Who created it and which course it belongs to (optional)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)

    is_anonymous = Column(Boolean, default=True, nullable=False)

    # Rubric: list of {criterion: str, max_points: int, description: str}
    rubric = Column(JSON, nullable=True)

    max_reviewers_per_student = Column(Integer, default=2, nullable=False)

    # Whether the teacher has released reviews to students
    reviews_released = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_id])
    course = relationship("Course", foreign_keys=[course_id])
    submissions = relationship(
        "PeerReviewSubmission",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )
    allocations = relationship(
        "PeerReviewAllocation",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class PeerReviewSubmission(Base):
    """A student's written work submitted for peer review."""

    __tablename__ = "peer_review_submissions"

    id = Column(Integer, primary_key=True, index=True)

    assignment_id = Column(
        Integer, ForeignKey("peer_review_assignments.id"), nullable=False, index=True
    )
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    file_key = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    assignment = relationship("PeerReviewAssignment", back_populates="submissions")
    author = relationship("User", foreign_keys=[author_id])
    reviews = relationship(
        "PeerReview",
        back_populates="submission",
        cascade="all, delete-orphan",
    )
    allocations = relationship(
        "PeerReviewAllocation",
        back_populates="submission",
        cascade="all, delete-orphan",
    )


class PeerReview(Base):
    """A peer review written by one student about another's submission."""

    __tablename__ = "peer_reviews"

    id = Column(Integer, primary_key=True, index=True)

    submission_id = Column(
        Integer, ForeignKey("peer_review_submissions.id"), nullable=False, index=True
    )
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # {criterion: score} dict — mirrors rubric criteria keys
    scores = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)
    written_feedback = Column(Text, nullable=True)

    status = Column(String(20), default=ReviewStatus.DRAFT.value, nullable=False)
    is_anonymous = Column(Boolean, default=True, nullable=False)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    submission = relationship("PeerReviewSubmission", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class PeerReviewAllocation(Base):
    """Maps which student should review which submission (auto-allocated by teacher)."""

    __tablename__ = "peer_review_allocations"

    id = Column(Integer, primary_key=True, index=True)

    assignment_id = Column(
        Integer, ForeignKey("peer_review_assignments.id"), nullable=False, index=True
    )
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    submission_id = Column(
        Integer, ForeignKey("peer_review_submissions.id"), nullable=False, index=True
    )

    # Relationships
    assignment = relationship("PeerReviewAssignment", back_populates="allocations")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    submission = relationship("PeerReviewSubmission", back_populates="allocations")

    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "reviewer_id", "submission_id",
            name="uq_peer_review_allocation",
        ),
    )
