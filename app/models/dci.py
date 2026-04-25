"""Daily Check-In Ritual (DCI) models — CB-DCI-001 M0 (#4140).

Six tables:
  - DailyCheckin:           one row per kid check-in event
  - ClassificationEvent:    one row per AI artifact classification
  - AISummary:              parent-facing daily summary (one per kid+date)
  - ConversationStarter:    starter history + parent feedback
  - CheckinStreakSummary:   per-kid streak aggregate
  - CheckinConsent:         parent-controlled per-kid consent toggles

Conventions (CLAUDE.md + MEMORY.md):
  - String(20) for enum-like columns (NOT Enum(PythonEnum))
  - DEFAULT FALSE for booleans (server_default="FALSE")
  - DateTime(timezone=True) renders TIMESTAMPTZ on PG, DATETIME on SQLite
  - Pydantic schemas live in app/schemas/dci.py with from_attributes=True

This module contains data model only — no business logic. Routes/services live
in app/api/routes/dci.py and app/services/dci_*.py (later stripes).
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.database import Base


# --- Enum-like string sets (kept in Python; stored as VARCHAR per convention) ---
# Wired into DB-level CheckConstraints below so writes that bypass Pydantic
# (raw SQL, ORM bulk inserts, future migrations) still get rejected at the DB.
# Mirrors the ``_in_clause`` pattern in ``app/models/learning_cycle.py``.

ARTIFACT_TYPES = ("photo", "voice", "text")
CHECKIN_SOURCES = ("kid_web", "kid_mobile")
PARENT_FEEDBACK_VALUES = ("thumbs_up", "regenerate")


# NOTE: ``_in_clause`` interpolates hardcoded tuple values into a SQL CHECK
# constraint string. Values are in-process constants (never user input),
# so there's no injection vector.
def _in_clause(values: tuple) -> str:
    """Build a SQL ``IN (...)`` clause from a tuple of string literals."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


class DailyCheckin(Base):
    """One row per kid check-in event (photo, voice, text, or combination)."""

    __tablename__ = "daily_checkins"

    id = Column(Integer, primary_key=True, index=True)
    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # JSON list of opaque object URIs (family-scoped signed URLs resolved at read)
    photo_uris = Column(JSON, nullable=False, default=list, server_default="[]")
    voice_uri = Column(String(500), nullable=True)
    text_content = Column(String(280), nullable=True)
    # source: 'kid_web' | 'kid_mobile'
    source = Column(
        String(20),
        nullable=False,
        default="kid_web",
        server_default="kid_web",
    )

    # Relationships
    classifications = relationship(
        "ClassificationEvent",
        back_populates="checkin",
        cascade="all, delete-orphan",
        order_by="ClassificationEvent.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            f"source IN {_in_clause(CHECKIN_SOURCES)}",
            name="ck_daily_checkins_source",
        ),
        Index("ix_daily_checkins_kid_date", "kid_id", "submitted_at"),
    )


class ClassificationEvent(Base):
    """One row per AI artifact classification (photo OCR, voice transcript, text)."""

    __tablename__ = "classification_events"

    id = Column(Integer, primary_key=True, index=True)
    checkin_id = Column(
        Integer,
        ForeignKey("daily_checkins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # artifact_type: 'photo' | 'voice' | 'text'
    artifact_type = Column(String(20), nullable=False)
    subject = Column(String(50), nullable=True)
    topic = Column(String(200), nullable=True)
    strand_code = Column(String(20), nullable=True)
    deadline_iso = Column(Date, nullable=True)
    confidence = Column(Float, nullable=True)
    corrected_by_kid = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    model_version = Column(String(50), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    checkin = relationship("DailyCheckin", back_populates="classifications")

    __table_args__ = (
        CheckConstraint(
            f"artifact_type IN {_in_clause(ARTIFACT_TYPES)}",
            name="ck_classification_events_artifact_type",
        ),
    )


class AISummary(Base):
    """Parent-facing daily summary — one row per (kid_id, summary_date)."""

    __tablename__ = "ai_summaries"

    id = Column(Integer, primary_key=True, index=True)
    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_date = Column(Date, nullable=False)
    # JSON blob: {"bullets": [...], "tone": "...", "highlight": "..."}
    summary_json = Column(JSON, nullable=False)
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    model_version = Column(String(50), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    policy_blocked = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    parent_edited = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )

    # Relationships
    starters = relationship(
        "ConversationStarter",
        back_populates="summary",
        cascade="all, delete-orphan",
        order_by="ConversationStarter.created_at",
    )

    __table_args__ = (
        UniqueConstraint("kid_id", "summary_date", name="uq_ai_summaries_kid_date"),
    )


class ConversationStarter(Base):
    """Conversation-starter history with parent feedback / regeneration chain."""

    __tablename__ = "conversation_starters"

    id = Column(Integer, primary_key=True, index=True)
    summary_id = Column(
        Integer,
        ForeignKey("ai_summaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text = Column(Text, nullable=False)
    # was_used is nullable (tri-state: True = used, False = explicitly skipped, NULL = no feedback yet)
    was_used = Column(Boolean, nullable=True)
    # parent_feedback: 'thumbs_up' | 'regenerate'
    parent_feedback = Column(String(20), nullable=True)
    # Self-reference: this starter was regenerated from another starter id
    regenerated_from = Column(
        Integer,
        ForeignKey("conversation_starters.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    summary = relationship("AISummary", back_populates="starters")
    # Self-reference: this starter was regenerated from another starter id.
    # Unidirectional by design — to find children of a starter, query
    # ``.filter(ConversationStarter.regenerated_from == id)``. No inverse
    # collection is exposed to keep the relationship graph simple.
    regenerated_from_starter = relationship(
        "ConversationStarter",
        remote_side="ConversationStarter.id",
        foreign_keys=[regenerated_from],
    )

    __table_args__ = (
        # parent_feedback is nullable — allow NULL or one of the enum values
        CheckConstraint(
            f"parent_feedback IS NULL OR parent_feedback IN "
            f"{_in_clause(PARENT_FEEDBACK_VALUES)}",
            name="ck_conversation_starters_parent_feedback",
        ),
    )


class CheckinStreakSummary(Base):
    """Per-kid check-in streak aggregate. Separate from XP `StreakLog`."""

    __tablename__ = "checkin_streak_summary"

    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_streak = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    longest_streak = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_checkin_date = Column(Date, nullable=True)
    # NOTE: ``onupdate`` fires only on ORM updates. Raw SQL bulk updates
    # (e.g. nightly streak recompute jobs) MUST set updated_at = NOW()
    # explicitly — the ``CREATE TABLE`` migration does not install a DB
    # trigger to back this field.
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CheckinConsent(Base):
    """Parent-controlled per-kid consent toggles (composite PK: parent + kid).

    All toggles default FALSE — feature is opt-in per-channel (P1: parent is
    data controller). `retention_days` defaults to 90 (P7: minimum data).
    """

    __tablename__ = "checkin_consent"

    parent_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_ok = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    voice_ok = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    ai_ok = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    retention_days = Column(
        Integer,
        nullable=False,
        default=90,
        server_default="90",
    )
    # NOTE: ``onupdate`` fires only on ORM updates. Raw SQL bulk updates
    # MUST set updated_at = NOW() explicitly — see CheckinStreakSummary.
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("parent_id", "kid_id", name="pk_checkin_consent"),
    )
