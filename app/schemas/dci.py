"""Pydantic v2 schemas for CB-DCI-001 Daily Check-In Ritual (#4140).

Read schemas use ``from_attributes=True`` for SQLAlchemy ORM serialization.
Write schemas (Create/Update) are explicit and constrained per the PRD.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────── DailyCheckin ───────────────────────

class DailyCheckinCreate(BaseModel):
    kid_id: int
    parent_id: int
    photo_uris: list[str] = Field(default_factory=list)
    voice_uri: str | None = Field(default=None, max_length=500)
    text_content: str | None = Field(default=None, max_length=280)
    source: str = Field(default="kid_web", pattern="^(kid_web|kid_mobile)$")


class DailyCheckinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kid_id: int
    parent_id: int
    submitted_at: datetime
    photo_uris: list[str]
    voice_uri: str | None
    text_content: str | None
    source: str


# ─────────────────────── ClassificationEvent ───────────────────────

class ClassificationEventCreate(BaseModel):
    checkin_id: int
    artifact_type: str = Field(..., pattern="^(photo|voice|text)$")
    subject: str | None = Field(default=None, max_length=50)
    topic: str | None = Field(default=None, max_length=200)
    strand_code: str | None = Field(default=None, max_length=20)
    deadline_iso: date | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model_version: str | None = Field(default=None, max_length=50)


class ClassificationEventUpdate(BaseModel):
    """Used by the ``PATCH /api/dci/checkin/{id}/correct`` endpoint."""

    subject: str | None = Field(default=None, max_length=50)
    topic: str | None = Field(default=None, max_length=200)
    strand_code: str | None = Field(default=None, max_length=20)
    deadline_iso: date | None = None
    corrected_by_kid: bool | None = None


class ClassificationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checkin_id: int
    artifact_type: str
    subject: str | None
    topic: str | None
    strand_code: str | None
    deadline_iso: date | None
    confidence: float | None
    corrected_by_kid: bool
    model_version: str | None
    created_at: datetime


# ─────────────────────── AISummary ───────────────────────

class AISummaryCreate(BaseModel):
    kid_id: int
    summary_date: date
    summary_json: dict[str, Any]
    model_version: str = Field(..., max_length=50)
    prompt_hash: str = Field(..., max_length=64)
    policy_blocked: bool = False


class AISummaryUpdate(BaseModel):
    """Parent-edit endpoint: replaces summary_json and flips parent_edited."""

    summary_json: dict[str, Any] | None = None
    parent_edited: bool | None = None


class AISummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kid_id: int
    summary_date: date
    summary_json: dict[str, Any]
    generated_at: datetime
    model_version: str
    prompt_hash: str
    policy_blocked: bool
    parent_edited: bool


# ─────────────────────── ConversationStarter ───────────────────────

class ConversationStarterCreate(BaseModel):
    summary_id: int
    text: str = Field(..., min_length=1)
    regenerated_from: int | None = None


class ConversationStarterFeedback(BaseModel):
    """Parent feedback on a starter (used / regenerate / undo_used).

    `undo_used` (#4225) is an explicit untoggle signal sent by the
    frontend when the parent clears the "I used this" state. It is
    interpreted by the route handler as ``was_used = false`` and is
    not persisted in the ``parent_feedback`` column itself.
    """

    was_used: bool | None = None
    parent_feedback: str | None = Field(
        default=None, pattern="^(thumbs_up|regenerate|undo_used)$"
    )


class ConversationStarterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    summary_id: int
    text: str
    was_used: bool | None
    parent_feedback: str | None
    regenerated_from: int | None
    created_at: datetime


# ─────────────────────── CheckinStreakSummary ───────────────────────

class CheckinStreakSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kid_id: int
    current_streak: int
    longest_streak: int
    last_checkin_date: date | None
    updated_at: datetime


# ─────────────────────── CheckinConsent ───────────────────────

class CheckinConsentBase(BaseModel):
    photo_ok: bool = False
    voice_ok: bool = False
    ai_ok: bool = False
    retention_days: int = Field(default=90, ge=1, le=1095)  # 1 d .. 3 yr


class CheckinConsentCreate(CheckinConsentBase):
    parent_id: int
    kid_id: int


class CheckinConsentUpdate(BaseModel):
    """All fields optional — partial-update PATCH semantics."""

    photo_ok: bool | None = None
    voice_ok: bool | None = None
    ai_ok: bool | None = None
    retention_days: int | None = Field(default=None, ge=1, le=1095)


class CheckinConsentResponse(CheckinConsentBase):
    model_config = ConfigDict(from_attributes=True)

    parent_id: int
    kid_id: int
    updated_at: datetime
