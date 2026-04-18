"""Pydantic schemas for Demo Sessions (CB-DEMO-001, #3600)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


RoleLiteral = Literal["parent", "student", "teacher", "other"]
AdminStatusLiteral = Literal["pending", "approved", "rejected", "blocklisted"]
DemoType = Literal["ask", "study_guide", "flash_tutor"]


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
    """Request body for POST /api/v1/demo/generate (PRD §11.6).

    The session is identified by the session JWT cookie/header, not by
    a body field.
    """

    demo_type: DemoType
    # Max 500 user-supplied words per generation (FR-052). Using a
    # character cap of 500 * 8 ≈ 4000 chars as a permissive upper bound;
    # word-level truncation is enforced in the service layer.
    source_text: Optional[str] = Field(None, max_length=4000)
    question: Optional[str] = Field(None, max_length=500)


class DemoGenerateEvent(BaseModel):
    """One entry stored inside `generations_json` for a demo session (PRD §11.5)."""

    demo_type: DemoType
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_cents: int
    created_at: datetime


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
