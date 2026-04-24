"""Tutor Chat SSE endpoint — CB-TUTOR-002 Phase 1 (#4063).

`POST /api/tutor/chat/stream`
  - Requires auth.
  - Gated on the `tutor_chat_enabled` feature flag (403 when off).
  - Rate-limited at 20 req/hour per authenticated user (slowapi).
  - Calls OpenAI moderation on the user message before streaming.
  - Streams LLM tokens as Server-Sent Events.
  - Persists user + assistant turns in `tutor_conversations` /
    `tutor_messages` once streaming finishes successfully.

SSE wire format (JSON-envelope)
-------------------------------
Each frame is ``data: <json>\\n\\n`` where ``<json>`` is one of:
    {"type": "token",  "text": "..."}
    {"type": "chips",  "suggestions": ["..."]}
    {"type": "done",   "conversation_id": "...", "message_id": "...",
                       "credits_used": 0.25}
    {"type": "safety", "text": "..."}
    {"type": "error",  "code": "...", "text": "..."}
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from functools import lru_cache
from typing import AsyncIterator

import openai
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.db.database import SessionLocal, get_db
from app.models.tutor import TutorConversation, TutorMessage
from app.models.user import User
from app.prompts.tutor_chat import build_system_prompt, build_user_prompt
from app.schemas.tutor import TutorChatRequest
from app.services.feature_flag_service import is_feature_enabled
from app.services.safety_service import moderate, scrub_pii

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tutor", tags=["tutor"])

FEATURE_FLAG_KEY = "tutor_chat_enabled"
MODEL = "gpt-4o-mini"
MAX_HISTORY_PAIRS = 3  # last N (user, assistant) pairs to include as context
MAX_RESPONSE_TOKENS = 800
CREDITS_PER_MESSAGE = 0.25
# Max seconds to wait between consecutive tokens from the OpenAI stream
# before we abort — guards against the upstream hanging mid-response.
INTER_TOKEN_TIMEOUT = 15.0


@lru_cache(maxsize=32)
def _cached_system_prompt(grade_level: int | None) -> str:
    """Memoized wrapper around `build_system_prompt` (same prompt per grade)."""
    return build_system_prompt(grade_level)


def _check_tutor_flag(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Dependency that enforces the `tutor_chat_enabled` flag.

    Depends on `get_current_user` first so that unauthenticated callers
    get the expected 401 (from auth) before we ever read the flag.
    Runs BEFORE the `@limiter.limit(...)` decorator on the route, so a
    disabled flag returns 403 without consuming a rate-limit slot.
    """
    _ = current_user  # silence unused — presence of this dep forces auth first
    if not is_feature_enabled(FEATURE_FLAG_KEY, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tutor chat is currently disabled",
        )


# Matches the trailing suggestion-chip block emitted by the model, e.g.
#   [[CHIPS: "chip1", "chip2", "chip3"]]
# The block is stripped out of the persisted content and emitted as a
# separate SSE `chips` frame.
_CHIPS_BLOCK_RE = re.compile(
    r"\[\[\s*CHIPS\s*:\s*(.*?)\s*\]\]",
    re.IGNORECASE | re.DOTALL,
)
_CHIP_ITEM_RE = re.compile(r'"([^"]*)"')


def _sse(payload: dict) -> str:
    """Format a single SSE frame as a JSON-envelope ``data:`` line.

    The frontend fetch-stream reader parses ``line.slice(6)`` as JSON.
    """
    return f"data: {json.dumps(payload)}\n\n"


def _parse_chips(full_response: str) -> tuple[str, list[str]]:
    """Extract a trailing ``[[CHIPS: ...]]`` block from ``full_response``.

    Returns ``(content_without_block, chips)``. If no block is found, the
    content is returned unchanged with an empty chips list.
    """
    match = _CHIPS_BLOCK_RE.search(full_response)
    if not match:
        return full_response.rstrip(), []
    chips = [c.strip() for c in _CHIP_ITEM_RE.findall(match.group(1)) if c.strip()]
    stripped = (full_response[: match.start()] + full_response[match.end():]).rstrip()
    return stripped, chips


def _load_history(
    db: Session, conversation_id: str, max_pairs: int = MAX_HISTORY_PAIRS
) -> list[dict[str, str]]:
    """Return the last `max_pairs` complete (user, assistant) pairs for a conversation.

    Over-samples rows from the DB and walks them oldest-first so that retries
    (which can leave multiple consecutive assistant rows) don't produce a
    non-alternating history — OpenAI chat completion rejects that. Messages are
    returned oldest-first in OpenAI chat-completion format.
    """
    rows = (
        db.query(TutorMessage)
        .filter(TutorMessage.conversation_id == conversation_id)
        # Stable tiebreak on id — when two rows share a created_at
        # (same-second inserts) the pairing must be deterministic across calls.
        .order_by(desc(TutorMessage.created_at), desc(TutorMessage.id))
        .limit(max_pairs * 4)  # over-sample to survive retries
        .all()
    )
    rows.reverse()  # oldest → newest

    pairs: list[dict[str, str]] = []
    pending_user: TutorMessage | None = None
    for m in rows:
        if m.role == "user":
            pending_user = m
        elif m.role == "assistant" and pending_user is not None:
            pairs.append({"role": "user", "content": pending_user.content})
            pairs.append({"role": "assistant", "content": m.content})
            pending_user = None

    # Keep only the last `max_pairs` pairs (each pair = 2 entries).
    return pairs[-(max_pairs * 2):]


def _context_dict(body: TutorChatRequest) -> dict:
    """Serialize TutorChatContextOverride into a plain dict (None-fields dropped)."""
    ctx = body.context_override
    if ctx is None:
        return {}
    out: dict = {}
    if ctx.grade_level is not None:
        out["grade_level"] = ctx.grade_level
    if ctx.subject:
        out["subject"] = ctx.subject
    if ctx.course_id is not None:
        out["course_id"] = ctx.course_id
    if ctx.child_id is not None:
        out["child_id"] = ctx.child_id
    return out


async def _stream_completion(
    system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    """Yield token deltas from the OpenAI chat completion stream.

    Each `anext` on the underlying stream is wrapped in
    ``asyncio.wait_for(..., INTER_TOKEN_TIMEOUT)`` so a stalled upstream
    surfaces as ``openai.APITimeoutError`` rather than hanging the SSE
    connection indefinitely.
    """
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
    stream = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=MAX_RESPONSE_TOKENS,
        stream=True,
    )
    stream_iter = stream.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(
                stream_iter.__anext__(), timeout=INTER_TOKEN_TIMEOUT
            )
        except StopAsyncIteration:
            return
        except asyncio.TimeoutError as exc:
            # `openai.APITimeoutError.__init__` takes an httpx.Request; we
            # don't have one handy from the stream iterator, so surface a
            # plain asyncio.TimeoutError and let event_stream catch it.
            raise exc
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


@router.post("/chat/stream", dependencies=[Depends(_check_tutor_flag)])
@limiter.limit("20/hour", key_func=get_user_id_or_ip)
async def tutor_chat_stream(
    request: Request,
    body: TutorChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a tutor response as Server-Sent Events (see module docstring).

    The `tutor_chat_enabled` flag is enforced by ``_check_tutor_flag`` in
    ``dependencies=[...]`` so that a disabled flag short-circuits with 403
    BEFORE the rate limiter decrements the caller's quota.
    """
    # Resolve (but DO NOT create) the conversation. Creation is deferred
    # until moderation passes so that blocked requests don't leave orphan
    # rows in `tutor_conversations`. An unknown or cross-user
    # conversation_id is an explicit error — we must NOT silently create
    # a brand-new conversation for the caller.
    conversation: TutorConversation | None = None
    if body.conversation_id:
        conversation = (
            db.query(TutorConversation)
            .filter(
                TutorConversation.id == body.conversation_id,
                TutorConversation.user_id == current_user.id,
            )
            .first()
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation_not_found",
            )

    history = (
        _load_history(db, conversation.id) if conversation is not None else []
    )
    context = _context_dict(body)
    system_prompt = _cached_system_prompt(context.get("grade_level"))
    user_prompt = build_user_prompt(body.message, history, context)

    # Run moderation before opening the stream so we can emit the error
    # as the first SSE frame with no partial output — and so we can avoid
    # creating an empty conversation row when the message is blocked.
    mod_result = await moderate(body.message)

    async def event_stream() -> AsyncIterator[str]:
        nonlocal conversation
        assistant_message_id = str(uuid.uuid4())

        if mod_result.flagged:
            if "moderation_unavailable" in mod_result.categories:
                yield _sse(
                    {
                        "type": "safety",
                        "code": "moderation_unavailable",
                        "text": (
                            "Safety checks are temporarily unavailable. "
                            "Please try again in a moment."
                        ),
                    }
                )
            else:
                yield _sse(
                    {
                        "type": "safety",
                        "code": "moderation_blocked",
                        "text": "This message was blocked by the safety filter.",
                    }
                )
            return

        # Moderation passed — create the conversation now if the caller
        # didn't supply one. This is the first DB write for this request,
        # so a blocked message never leaves an orphan row.
        if conversation is None:
            conversation = TutorConversation(
                id=str(uuid.uuid4()), user_id=current_user.id
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        conversation_id = conversation.id
        collected: list[str] = []
        try:
            async for delta in _stream_completion(system_prompt, user_prompt):
                collected.append(delta)
                yield _sse({"type": "token", "text": delta})
        except asyncio.TimeoutError as exc:
            logger.warning("Tutor OpenAI inter-token stall: %s", exc)
            yield _sse(
                {
                    "type": "error",
                    "code": "timeout",
                    "text": "The tutor stopped responding. Please try again.",
                }
            )
            return
        except (openai.APIError, openai.APITimeoutError, openai.RateLimitError) as exc:
            logger.warning("Tutor OpenAI stream error: %s", exc)
            yield _sse(
                {
                    "type": "error",
                    "code": "internal",
                    "text": "The tutor is temporarily unavailable.",
                }
            )
            return
        except Exception:
            logger.exception("Tutor stream unexpected error")
            yield _sse(
                {
                    "type": "error",
                    "code": "internal",
                    "text": "Something went wrong.",
                }
            )
            return

        full_response = "".join(collected).strip()
        assistant_content, chips = _parse_chips(full_response)
        scrubbed_content, _redactions = scrub_pii(assistant_content)

        # Persist the turn (user + assistant) once streaming completes.
        # Use a fresh SessionLocal rather than the request-scoped `db`, which
        # may already be closed by the time the generator's finally runs.
        # Both user and assistant content are stored with PII scrubbed.
        stream_db = SessionLocal()
        try:
            scrubbed_user, _ = scrub_pii(body.message)
            stream_db.add(
                TutorMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role="user",
                    content=scrubbed_user,
                )
            )
            if scrubbed_content:
                stream_db.add(
                    TutorMessage(
                        id=assistant_message_id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=scrubbed_content,
                    )
                )
            stream_db.commit()
        except Exception:
            stream_db.rollback()
            logger.exception(
                "Tutor failed to persist conversation turn (conv=%s)",
                conversation_id,
            )
        finally:
            stream_db.close()

        if chips:
            yield _sse({"type": "chips", "suggestions": chips})
        yield _sse(
            {
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": assistant_message_id,
                "credits_used": CREDITS_PER_MESSAGE,
            }
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
