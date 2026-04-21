"""Pydantic schemas for Demo Sessions (CB-DEMO-001, #3600)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


RoleLiteral = Literal["parent", "student", "teacher", "other"]
AdminStatusLiteral = Literal["pending", "approved", "rejected", "blocklisted"]
DemoType = Literal["ask", "study_guide", "flash_tutor"]
DemoHistoryRole = Literal["user", "assistant"]

# Ask tab multi-turn chatbox (§6.135.5, #3785):
# - History is capped at 2 prior turns (1 user + 1 assistant) so the total
#   message array never exceeds 3 before the current user turn.
# - Each content string is capped at 500 chars to bound the tokens we send.
_DEMO_HISTORY_MAX_TURNS = 2
_DEMO_HISTORY_MAX_CHARS = 500


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


class DemoHistoryTurn(BaseModel):
    """One prior turn in the Ask tab multi-turn chatbox (§6.135.5, #3785).

    Only ``user`` and ``assistant`` roles are permitted. Content is capped
    at 500 chars so we never balloon the upstream prompt accidentally.
    """

    role: DemoHistoryRole
    content: str = Field(..., min_length=1, max_length=_DEMO_HISTORY_MAX_CHARS)


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
    # Multi-turn Ask chatbox (§6.135.5, #3785). Optional; only used by the
    # Ask tab. Capped at ``_DEMO_HISTORY_MAX_TURNS`` prior turns so the
    # full prompt is (history + current user) = ≤3 messages.
    history: Optional[list[DemoHistoryTurn]] = Field(default=None)

    @field_validator("history")
    @classmethod
    def _cap_history_length(
        cls, v: Optional[list[DemoHistoryTurn]]
    ) -> Optional[list[DemoHistoryTurn]]:
        if v is None:
            return v
        if len(v) > _DEMO_HISTORY_MAX_TURNS:
            raise ValueError(
                f"history may not exceed {_DEMO_HISTORY_MAX_TURNS} prior turns"
            )
        return v


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
