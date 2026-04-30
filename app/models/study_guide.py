from sqlalchemy import Boolean, Column, Integer, Numeric, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.core.config import settings
from app.db.database import Base


# CB-CMCP-001 0A-2 (#4413) — JSONB on PG, JSON on SQLite for portable JSON columns
_IS_PG = "sqlite" not in settings.database_url
if _IS_PG:
    from sqlalchemy.dialects.postgresql import JSONB

    _CMCPJSONType = JSONB
else:
    _CMCPJSONType = JSON


class StudyGuide(Base):
    __tablename__ = "study_guides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Optional references to source content
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # Markdown or JSON content
    guide_type = Column(String(50), nullable=False, index=True)  # study_guide, quiz, flashcards, worksheet, weak_area_analysis, high_level_summary, answer_key
    focus_prompt = Column(String(2000), nullable=True)  # User-provided focus area saved for history
    is_truncated = Column(Boolean, default=False, nullable=False)

    # Versioning
    version = Column(Integer, nullable=False, default=1)
    parent_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="SET NULL"), nullable=True, index=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 for duplicate detection
    relationship_type = Column(String(20), nullable=False, default="version", server_default="version")  # "version" or "sub_guide"
    generation_context = Column(Text, nullable=True)  # Selected text that triggered sub-guide generation

    # UTDF worksheet/template columns (§6.131, #2950, #3029)
    # Columns added via POST /api/admin/run-migrations (#3079)
    template_key = Column(String(50), nullable=True)
    num_questions = Column(Integer, nullable=True)
    difficulty = Column(String(20), nullable=True)
    answer_key_markdown = Column(Text, nullable=True)
    weak_topics = Column(Text, nullable=True)
    ai_engine = Column(String(20), nullable=True)

    # Study Guide Strategy Pattern (§6.105, #1972)
    parent_summary = Column(Text, nullable=True)  # Parent-facing simplified summary
    curriculum_codes = Column(Text, nullable=True)  # JSON array of {concept, curriculum_code, strand}
    suggestion_topics = Column(Text, nullable=True)  # JSON array of {label, description}

    # Sharing (parent → child)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    shared_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    viewed_count = Column(Integer, default=0)

    # CB-CMCP-001 0A-2 (#4413) — curriculum-aware columns per locked decision D2=B.
    # All nullable / defaulted so existing rows + non-CMCP code paths continue
    # to work unchanged. Columns are populated by M1+ generation pipelines.
    se_codes = Column(_CMCPJSONType, nullable=True)  # array of CB-format SE codes
    alignment_score = Column(Numeric(4, 3), nullable=True)  # validator score [0.000–1.000]
    ceg_version = Column(Integer, nullable=True)  # curriculum_versions.id stamp (loose, no FK in MVP)
    state = Column(String(30), nullable=False, server_default="DRAFT")
    # state ∈ {DRAFT, PENDING_REVIEW, IN_REVIEW, APPROVED, APPROVED_VERIFIED,
    # REJECTED, ARCHIVED, SELF_STUDY (D3=C hybrid)}
    board_id = Column(String(50), nullable=True)  # board-scoped artifact visibility (M3-E)
    voice_module_hash = Column(String(64), nullable=True)  # Arc voice module hash (M1-C)
    class_context_envelope_summary = Column(_CMCPJSONType, nullable=True)  # captured envelope (M1-B)
    requested_persona = Column(String(20), nullable=True)  # student | parent | teacher | admin

    # CB-CMCP-001 M3-A 3A-1 (#4576) — Teacher Review Queue review-state metadata.
    # ``edit_history`` is an append-only JSON array; each entry shape:
    #   {"editor_id": int, "edit_at": "<ISO-8601 UTC>",
    #    "before_snippet": str, "after_snippet": str}
    # ``rejection_reason`` is required when state transitions to REJECTED.
    edit_history = Column(_CMCPJSONType, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref=backref("study_guides", passive_deletes=True))
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    assignment = relationship("Assignment", backref="study_guides")
    course = relationship("Course", backref="study_guides")
    course_content = relationship("CourseContent", backref="study_guides")
    parent_guide = relationship("StudyGuide", remote_side=[id], backref="child_versions", passive_deletes=True)

    __table_args__ = (
        Index("ix_study_guides_user", "user_id"),
        Index("ix_study_guides_course_content", "course_content_id"),
    )
