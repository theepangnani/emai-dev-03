"""Learning Cycle models for CB-TUTOR-002 Phase 2 (#4067).

Four-table schema:
  - LearningCycleSession: top-level session per (user, topic)
  - LearningCycleChunk:   teach-check-move chunks, ordered within a session
  - LearningCycleQuestion: questions attached to a chunk (mcq / true_false / fill_blank)
  - LearningCycleAnswer:  per-attempt answers for a question

Conventions followed (MEMORY.md):
  - String(20) for enum-like columns (NOT Enum(PythonEnum))
  - server_default="FALSE" for booleans, gated DATETIME vs TIMESTAMPTZ via JSON type helper
  - UUID PKs stored as 36-char strings (PG: UUID, SQLite: VARCHAR(36))
  - ON DELETE CASCADE from chunk->session, question->chunk, answer->question
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.core.config import settings
from app.db.database import Base


# NOTE: _IS_PG is evaluated at module import; tests that need dialect-specific
# behaviour should rely on a fresh interpreter rather than monkeypatching settings.
_IS_PG = "sqlite" not in settings.database_url


if _IS_PG:
    from sqlalchemy.dialects.postgresql import JSONB, UUID

    _JSONType = JSONB

    def _IDColumn():
        return Column(
            UUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        )

    def _UUIDFK(target: str, **kwargs):
        return Column(UUID(as_uuid=False), ForeignKey(target, **kwargs))
else:
    _JSONType = JSON

    def _IDColumn():  # type: ignore[no-redef]
        return Column(
            String(36),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        )

    def _UUIDFK(target: str, **kwargs):  # type: ignore[no-redef]
        return Column(String(36), ForeignKey(target, **kwargs))


# --- Status / format enum string sets (kept in Python for CHECK constraints) ---

_SESSION_STATUSES = ("active", "completed", "abandoned")
_CHUNK_MASTERIES = ("pending", "passed", "moved_on")
_QUESTION_FORMATS = ("mcq", "true_false", "fill_blank")


# NOTE: _in_clause interpolates hardcoded tuple values into a SQL CHECK
# constraint string. Values are in-process constants (never user input),
# so there's no injection vector. Future migration to SQLAlchemy Enum
# types is tracked in issue #4087 S-4.
def _in_clause(values: tuple) -> str:
    """Build a SQL ``IN (...)`` clause from a tuple of string literals."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


class LearningCycleSession(Base):
    """Top-level teach-check-move learning session (CB-TUTOR-002 Phase 2)."""

    __tablename__ = "learning_cycle_sessions"

    id = _IDColumn()
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic = Column(String(200), nullable=False)
    subject = Column(String(100), nullable=False)
    grade_level = Column(Integer, nullable=True)
    # status: 'active' | 'completed' | 'abandoned'
    status = Column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )
    current_chunk_idx = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    chunks = relationship(
        "LearningCycleChunk",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LearningCycleChunk.order_index",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {_in_clause(_SESSION_STATUSES)}",
            name="ck_learning_cycle_sessions_status",
        ),
        Index("ix_learning_cycle_sessions_user_status", "user_id", "status"),
    )


class LearningCycleChunk(Base):
    """A single teach-check chunk within a learning cycle session."""

    __tablename__ = "learning_cycle_chunks"

    id = _IDColumn()
    session_id = _UUIDFK(
        "learning_cycle_sessions.id",
        ondelete="CASCADE",
    )
    order_index = Column(Integer, nullable=False)
    teach_content_md = Column(Text, nullable=False)
    # mastery_status: 'pending' | 'passed' | 'moved_on'
    mastery_status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    # Relationships
    session = relationship("LearningCycleSession", back_populates="chunks")
    questions = relationship(
        "LearningCycleQuestion",
        back_populates="chunk",
        cascade="all, delete-orphan",
        order_by="LearningCycleQuestion.order_index",
    )

    __table_args__ = (
        CheckConstraint(
            f"mastery_status IN {_in_clause(_CHUNK_MASTERIES)}",
            name="ck_learning_cycle_chunks_mastery",
        ),
        Index(
            "ix_learning_cycle_chunks_session_order",
            "session_id",
            "order_index",
        ),
    )


class LearningCycleQuestion(Base):
    """A single check-question attached to a chunk."""

    __tablename__ = "learning_cycle_questions"

    id = _IDColumn()
    chunk_id = _UUIDFK(
        "learning_cycle_chunks.id",
        ondelete="CASCADE",
    )
    order_index = Column(Integer, nullable=False)
    # format: 'mcq' | 'true_false' | 'fill_blank'
    format = Column(String(20), nullable=False)
    prompt = Column(Text, nullable=False)
    options = Column(_JSONType, nullable=True)
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)

    # Relationships
    chunk = relationship("LearningCycleChunk", back_populates="questions")
    answers = relationship(
        "LearningCycleAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="LearningCycleAnswer.attempt_number",
    )

    __table_args__ = (
        CheckConstraint(
            f"format IN {_in_clause(_QUESTION_FORMATS)}",
            name="ck_learning_cycle_questions_format",
        ),
        Index(
            "ix_learning_cycle_questions_chunk_order",
            "chunk_id",
            "order_index",
        ),
    )


class LearningCycleAnswer(Base):
    """A single attempt at answering a check-question."""

    __tablename__ = "learning_cycle_answers"

    id = _IDColumn()
    question_id = _UUIDFK(
        "learning_cycle_questions.id",
        ondelete="CASCADE",
    )
    attempt_number = Column(Integer, nullable=False, default=1, server_default="1")
    answer_given = Column(Text, nullable=False)
    is_correct = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    xp_awarded = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    question = relationship("LearningCycleQuestion", back_populates="answers")

    __table_args__ = (
        Index(
            "ix_learning_cycle_answers_question_attempt",
            "question_id",
            "attempt_number",
        ),
    )
