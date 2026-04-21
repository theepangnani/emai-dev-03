"""Pydantic schemas for Demo Sessions (CB-DEMO-001, #3600)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


RoleLiteral = Literal["parent", "student", "teacher", "other"]
AdminStatusLiteral = Literal["pending", "approved", "rejected", "blocklisted"]
DemoType = Literal["ask", "study_guide", "flash_tutor"]

# Ask tab multi-turn chatbox (§6.135.5, #3785):
# - History is reconstructed server-side from ``DemoSession.generations_json``
#   (#3819) — the client no longer sends prior turns on the wire. This closes
#   the prompt-injection vector where a crafted ``assistant`` history entry
#   was treated by Haiku as its own prior utterance.
# - Only the most recent completed Ask turn is used for context (1 user +
#   1 assistant) so the total prompt stays at 3 messages max. The
#   invariant lives in ``app.api.routes.demo._reconstruct_ask_history``.
# - Each persisted content string is capped at
#   ``_DEMO_PERSISTED_CONTENT_MAX_CHARS`` chars to bound the tokens we
#   replay on the next turn.
#
# Cap rationale (#3843): the Ask prompt targets ~200 words per turn at
# max_tokens=300. A 20-sample Haiku measurement (c:/tmp/measure_ask_lengths.py,
# ask prompt, temperature 0.7, mix of science/history/math/conversation
# questions) produced p50=837, p95=1108, p99=1145 chars. 80% of typical
# replies exceeded the previous 500-char cap, which truncated honest-user
# answers mid-sentence when replayed as history on turn 2. New cap =
# round(p99 * 1.1) = 1260, still well below the 2000-char "prompt is wrong"
# ceiling. The user-side cap stays at the same value for symmetry — the
# 500-word service-layer check (FR-052) is the real bound on user input.
_DEMO_PERSISTED_CONTENT_MAX_CHARS = 1260


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

    Multi-turn Ask context is reconstructed server-side from the
    ``DemoSession.generations_json`` log (#3819) — the client does not
    send prior turns over the wire. Attempting to do so would be ignored
    by the schema and is rejected as an unknown field.
    """

    model_config = ConfigDict(extra="forbid")

    demo_type: DemoType
    # Max 500 user-supplied words per generation (FR-052). Using a
    # character cap of 500 * 8 ≈ 4000 chars as a permissive upper bound;
    # word-level truncation is enforced in the service layer.
    source_text: Optional[str] = Field(None, max_length=4000)
    question: Optional[str] = Field(None, max_length=500)


class DemoGenerateEvent(BaseModel):
    """One entry stored inside `generations_json` for a demo session (PRD §11.5).

    Ask turns additionally record the ``user_content`` and
    ``assistant_content`` (#3819) so the next turn in the same session can
    be reconstructed server-side. Non-Ask demo types leave those fields
    empty.
    """

    demo_type: DemoType
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_cents: int
    created_at: datetime
    # Server-reconstructed Ask history source (#3819). Both fields are
    # capped at record time so the persisted payload stays bounded
    # regardless of Haiku's output length. The cap was raised from 500
    # to 1260 chars in #3843 after measurement showed 80% of typical
    # Ask replies exceeded 500; see ``_DEMO_PERSISTED_CONTENT_MAX_CHARS``
    # for the rationale.
    user_content: Optional[str] = Field(
        default=None, max_length=_DEMO_PERSISTED_CONTENT_MAX_CHARS
    )
    assistant_content: Optional[str] = Field(
        default=None, max_length=_DEMO_PERSISTED_CONTENT_MAX_CHARS
    )


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
