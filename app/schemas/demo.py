"""Pydantic schemas for Demo Sessions (CB-DEMO-001, #3600)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


RoleLiteral = Literal["parent", "student", "teacher", "other"]
AdminStatusLiteral = Literal["pending", "approved", "rejected", "blocklisted"]


class DemoSessionCreate(BaseModel):
    """Payload for starting a demo session (email + consent)."""

    email: EmailStr
    full_name: Optional[str] = None
    role: RoleLiteral
    consent: bool = Field(..., description="User has accepted consent terms")


class DemoSessionResponse(BaseModel):
    """Demo session record returned to the client."""

    id: str
    created_at: datetime
    email: str
    full_name: Optional[str] = None
    role: RoleLiteral
    verified: bool
    verified_ts: Optional[datetime] = None
    generations_count: int
    admin_status: AdminStatusLiteral

    model_config = ConfigDict(from_attributes=True)


class DemoGenerateRequest(BaseModel):
    """Request body for generating demo content during a session."""

    demo_session_id: str
    prompt: Optional[str] = None
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    input_type: Optional[str] = None  # e.g. 'text', 'image', 'pdf'
    metadata: Optional[dict[str, Any]] = None


class DemoGenerateEvent(BaseModel):
    """One entry stored inside `generations_json` for a demo session."""

    ts: datetime
    kind: str  # e.g. 'quiz', 'summary', 'study_guide'
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    prompt_excerpt: Optional[str] = None
    output_ref: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


class AdminDemoSessionRow(BaseModel):
    """Flattened demo session row for the admin review list."""

    id: str
    created_at: datetime
    email: str
    full_name: Optional[str] = None
    role: RoleLiteral
    verified: bool
    verified_ts: Optional[datetime] = None
    generations_count: int
    admin_status: AdminStatusLiteral
    source_ip_hash: Optional[str] = None
    user_agent: Optional[str] = None
    archived_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
