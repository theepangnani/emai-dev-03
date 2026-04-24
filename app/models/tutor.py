"""Tutor Chat models — CB-TUTOR-002 Phase 1 (#4063).

Stores short-lived tutoring conversations for the unified `/tutor` chat
experience. Each conversation belongs to a single user and contains an
ordered sequence of user/assistant messages.

Design notes
------------
- Use UUIDs (stored as VARCHAR(36)) for both IDs so the same schema runs
  on SQLite (dev) and PostgreSQL (prod) without extra extensions.
- `role` is a plain VARCHAR(10) (not SA Enum) because SA Enum stores NAMES
  not values on PostgreSQL — see CLAUDE.md memory.
- Messages are append-only; context window truncation happens at read
  time (load last 3 user/assistant pairs) rather than via deletes.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
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

from app.db.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class TutorConversation(Base):
    __tablename__ = "tutor_conversations"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    messages = relationship(
        "TutorMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="TutorMessage.created_at",
    )

    __table_args__ = (
        Index("ix_tutor_conversations_user_created", "user_id", "created_at"),
    )


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    conversation_id = Column(
        String(36),
        ForeignKey("tutor_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'user' | 'assistant'
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation = relationship("TutorConversation", back_populates="messages")

    __table_args__ = (
        Index("ix_tutor_messages_conv_created", "conversation_id", "created_at"),
    )
