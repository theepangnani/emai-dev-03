"""Public demo session + streaming generation routes (CB-DEMO-001 B1, #3603).

Two endpoints power the Instant Trial modal:

- ``POST /api/v1/demo/sessions`` — creates a ``demo_sessions`` row,
  issues a 30-minute session JWT, and emails a magic-link + fallback
  code for email verification.
- ``POST /api/v1/demo/generate`` — streams a Haiku completion via SSE
  for one of three demo types (ask, study_guide, flash_tutor),
  enforcing per-email, per-IP, and global cost-cap limits.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.disposable_emails import is_disposable
from app.core.logging_config import get_logger
from app.core.rate_limit import (
    get_client_ip,
    get_email_hash_or_ip,
    get_user_id_or_ip,
    limiter,
)
from app.db.database import get_db
from app.models.demo_session import DemoSession
from app.schemas.demo import (
    _DEMO_PERSISTED_CONTENT_MAX_CHARS,
    DemoGenerateRequest,
    DemoSessionCreate,
)
from app.services.demo_generation import (
    estimate_cost_cents,
    stream_demo_completion,
)
from app.services.demo_rate_limit import (
    check_daily_cost_cap,
    check_email_rate_limit,
    check_input_word_count,
    check_ip_rate_limit,
    reserve_generation_slot,
    update_generation_slot,
)
from app.services.demo_verification import (
    create_fallback_code,
    create_magic_link_token,
    set_verification_credentials,
)
from app.services.email_service import send_email_sync
from app.services.email_templates.demo_verification import (
    build_demo_verification_email,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])

# JWT config for demo session tokens (PRD §12.3 — 30 min session window).
_DEMO_SESSION_TTL = timedelta(minutes=30)
_DEMO_JWT_TYPE = "demo_session"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _app_base_url() -> str:
    return getattr(settings, "app_base_url", None) or "https://www.classbridge.ca"


def _create_demo_session_jwt(session_id: str) -> str:
    """Sign a HS256 JWT with the demo session id as subject, 30-min TTL."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(session_id),
        "exp": now + _DEMO_SESSION_TTL,
        "iat": now,
        "type": _DEMO_JWT_TYPE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload, settings.secret_key, algorithm=settings.algorithm
    )


def _decode_demo_session_jwt(token: str) -> Optional[str]:
    """Return the demo session id if the JWT is valid, else None."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except (ExpiredSignatureError, JWTClaimsError, JWTError):
        return None
    if payload.get("type") != _DEMO_JWT_TYPE:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def _extract_demo_token(
    request: Request,
    x_demo_session: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    """Pull the raw JWT from ``X-Demo-Session`` or ``Authorization: Bearer``."""
    if x_demo_session:
        return x_demo_session.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(None, 1)[1].strip()
    return None


# Denylist of literal injection-shaped tokens to strip from Haiku's own
# output before it is persisted + replayed as prior assistant context on
# the next Ask turn (#3842, defense-in-depth follow-up to #3819).
#
# The Anthropic messages API already treats role=assistant content as a
# plain string (role-tag tokens do not structurally split the turn), but a
# Haiku reply containing these patterns could still be quoted back on the
# next turn and nudge the model toward instruction-following behaviour.
# Stripping them before persistence keeps the stored transcript clean and
# removes the replay vector. The list is intentionally conservative —
# legitimate Haiku Ask answers never contain these markers.
_ASSISTANT_CONTENT_DENYLIST = re.compile(
    r"<\|im_start\|>|<\|im_end\|>|"
    r"<\|(?:system|user|assistant|human)\|>|"
    r"<\s*/?\s*system\s*>|\[\s*/?\s*system\s*\]|"
    r"^\s*(?:Human|Assistant|System)\s*:",
    re.IGNORECASE | re.MULTILINE,
)


def _sanitize_assistant_content(text: Optional[str]) -> Optional[str]:
    """Strip injection-shaped tokens from Haiku's assistant reply (#3842).

    Applied BEFORE the reply is written to ``generations_json`` so that
    the replayed context on subsequent turns cannot carry fabricated role
    markers or fake system tags forward. Returns the cleaned string or
    ``None`` if the input was falsy / fully stripped.

    Trust-model note: the denylist matches ``Human:`` / ``Assistant:`` /
    ``System:`` only at the start of a line (``^\\s*...``) so that the
    word ``human`` (and similar) occurring mid-sentence in legitimate
    prose is preserved. A mid-line ``. Human:`` separator is therefore
    not stripped — this is an intentional tradeoff to avoid over-stripping
    educational content. The primary structural defence against forged
    role context is the server-side history reconstruction from #3819;
    this sanitiser is a secondary layer against quoted role tokens.
    """
    if not text:
        return None
    cleaned = _ASSISTANT_CONTENT_DENYLIST.sub("", text).strip()
    return cleaned or None


def _reconstruct_ask_history(generations_json) -> Optional[list[dict]]:
    """Rebuild the Ask prior-turn history from a session's generations log.

    Traverses ``generations_json`` (most recent last) and returns the
    most recent completed Ask turn as ``[{role:user,...}, {role:assistant,...}]``.
    A turn is considered completed when both ``user_content`` and a
    non-empty ``assistant_content`` are present (a placeholder where the
    stream failed before ``update_generation_slot`` ran is skipped).

    Returns ``None`` when there is no prior Ask turn — matching the
    previous semantics of ``history_payload is None``.

    Security: this is the only producer of Haiku's ``history`` list in
    the demo path (#3819). It reads exclusively from the server's own
    persisted state; a compromised client cannot influence its output.
    ``assistant_content`` is additionally sanitised at write time
    (#3842) so the replayed context cannot re-inject role-like markers
    even if Haiku ever emits them.
    """
    if not generations_json:
        return None
    entries = generations_json
    if isinstance(entries, str):  # SQLite may hand back a raw JSON string
        try:
            entries = json.loads(entries)
        except json.JSONDecodeError:
            return None
    if not isinstance(entries, list):
        return None

    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue
        if entry.get("demo_type") != "ask":
            continue
        user_content = entry.get("user_content")
        assistant_content = entry.get("assistant_content")
        if not isinstance(user_content, str) or not user_content:
            continue
        if not isinstance(assistant_content, str) or not assistant_content:
            continue
        # Re-apply sanitisation on replay (#3842) as belt-and-braces for
        # any row persisted before the write-time sanitiser landed. If the
        # sanitised assistant string is empty, fall back to single-shot.
        safe_assistant = _sanitize_assistant_content(assistant_content)
        if not safe_assistant:
            return None
        return [
            {"role": "user", "content": user_content[:_DEMO_PERSISTED_CONTENT_MAX_CHARS]},
            {"role": "assistant", "content": safe_assistant[:_DEMO_PERSISTED_CONTENT_MAX_CHARS]},
        ]
    return None


def _waitlist_preview_position(db: Session) -> int:
    """Best-effort ``COUNT(*) + 1`` for the waitlist preview badge."""
    try:
        row = db.execute(text("SELECT COUNT(*) FROM waitlist")).first()
        if row and row[0] is not None:
            return int(row[0]) + 1
    except Exception as e:  # pragma: no cover - defensive (missing table etc.)
        logger.info("demo: waitlist count unavailable | %s", e)
    return 0


# ── POST /sessions ────────────────────────────────────────────────────


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour", key_func=get_email_hash_or_ip)
async def create_demo_session(
    request: Request,
    db: Session = Depends(get_db),
):
    """Start a demo session (FR-010/011/012/013)."""
    # Parse body manually so the honeypot field can be inspected *before*
    # Pydantic validation rejects unknown keys.
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # Honeypot — drop silently with a generic 400.
    honeypot = raw.get("_hp")
    if isinstance(honeypot, str) and honeypot.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request",
        )

    # Strip the honeypot before schema validation.
    raw.pop("_hp", None)
    try:
        payload = DemoSessionCreate.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.errors(),
        )

    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required to start a demo.",
        )

    email = payload.email.strip()
    normalised_email = email.lower()

    if is_disposable(normalised_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please use a non-disposable email address.",
        )

    email_hash = _sha256_hex(normalised_email)
    client_ip = get_client_ip(request)
    ip_hash = _sha256_hex(client_ip or "")
    user_agent = (request.headers.get("user-agent") or "")[:1024]

    # Build the session record.
    now = datetime.now(timezone.utc)
    session = DemoSession(
        email_hash=email_hash,
        email=email,
        full_name=(payload.full_name or None),
        role=payload.role,
        consent_ts=now,
        source_ip_hash=ip_hash,
        user_agent=user_agent or None,
        admin_status="pending",
    )
    db.add(session)
    db.flush()  # assigns `id` without committing yet.

    raw_token, token_hash = create_magic_link_token(session.id, email)
    raw_code, code_hash = create_fallback_code()
    set_verification_credentials(
        db, session, token_hash=token_hash, code_hash=code_hash
    )

    session_jwt = _create_demo_session_jwt(session.id)

    # Send verification email — if delivery fails we must not leave an
    # orphan session row that the user can't actually verify (#3664).
    magic_link_url = (
        f"{_app_base_url().rstrip('/')}/api/v1/demo/verify?token={raw_token}"
    )
    try:
        subject, html_body = build_demo_verification_email(
            full_name=payload.full_name,
            email=email,
            magic_link_url=magic_link_url,
            fallback_code=raw_code,
        )
        send_email_sync(email, subject, html_body)
    except Exception as e:
        logger.warning(
            "demo: verification email failed to send — rolling back session "
            "| session_id=%s | %s",
            session.id, e,
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "email_delivery_failed",
                "message": (
                    "We couldn't send the verification email. "
                    "Please try again shortly."
                ),
            },
        )

    preview_position = _waitlist_preview_position(db)

    db.commit()

    return {
        "session_jwt": session_jwt,
        "verification_required": True,
        "waitlist_preview_position": preview_position,
    }


# ── POST /generate ────────────────────────────────────────────────────


def _sse_frame(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post("/generate")
@limiter.limit("10/hour", key_func=get_user_id_or_ip)
async def generate_demo(
    request: Request,
    body: DemoGenerateRequest,
    db: Session = Depends(get_db),
    x_demo_session: Optional[str] = Header(None, alias="X-Demo-Session"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """Stream a demo completion (FR-020..FR-035)."""
    token = _extract_demo_token(request, x_demo_session, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo session token required.",
        )

    session_id = _decode_demo_session_jwt(token)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired demo session token.",
        )

    session = db.query(DemoSession).filter(DemoSession.id == session_id).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo session not found.",
        )
    if session.admin_status == "blocklisted":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This demo session has been blocked.",
        )

    input_text = body.source_text or body.question or ""
    ok, msg = check_input_word_count(input_text)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    ok, msg = check_email_rate_limit(db, session.email_hash)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg
        )

    ok, msg = check_ip_rate_limit(db, session.source_ip_hash or "")
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg
        )

    ok, msg = check_daily_cost_cap(db)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "demo_warming_up",
                "message": "Demo is warming up — try again in an hour.",
            },
        )

    demo_type = body.demo_type
    source_text = body.source_text
    question = body.question
    # Multi-turn Ask chatbox (§6.135.5, #3785) — reconstruct prior turns
    # server-side from the session's generations_json log (#3819). This
    # replaces the previous client-supplied ``history`` field and closes
    # the prompt-injection vector where a crafted ``assistant`` entry was
    # treated by Haiku as its own prior utterance.
    history_payload: Optional[list[dict]] = None
    if demo_type == "ask":
        history_payload = _reconstruct_ask_history(session.generations_json)
    session_id_capture = session.id

    # User question captured at reservation time so the turn is persisted
    # even if the stream fails midway. Only meaningful for Ask turns.
    reserved_user_content: Optional[str] = None
    if demo_type == "ask" and question:
        reserved_user_content = question

    # #3666 — reserve a placeholder slot BEFORE streaming so concurrent
    # requests see the incremented generations_count immediately and
    # cannot slip past the rate limit. The placeholder has cost_cents=0
    # so it doesn't falsely trip the cost cap. update_generation_slot
    # fills in real metrics after the stream completes.
    reserve_generation_slot(
        db, session, demo_type=demo_type, user_content=reserved_user_content
    )

    async def event_stream():
        # We use a fresh DB session inside the generator so the request-
        # scoped ``db`` from Depends is not held open while streaming.
        from app.db.database import SessionLocal

        input_tokens = 0
        output_tokens = 0
        latency_ms = 0
        had_error = False
        # Accumulate the streamed assistant text so the Ask turn can be
        # persisted (#3819) and used to reconstruct history on the next
        # turn. Non-Ask demo types leave this empty.
        assistant_chunks: list[str] = []
        try:
            async for event in stream_demo_completion(
                demo_type,
                source_text=source_text,
                question=question,
                history=history_payload,
            ):
                if event["event"] == "chunk":
                    chunk_text = event["data"]
                    if demo_type == "ask" and isinstance(chunk_text, str):
                        assistant_chunks.append(chunk_text)
                    yield _sse_frame("token", {"chunk": chunk_text})
                elif event["event"] == "done":
                    data = event["data"]
                    input_tokens = int(data.get("input_tokens", 0))
                    output_tokens = int(data.get("output_tokens", 0))
                    latency_ms = int(data.get("latency_ms", 0))
                elif event["event"] == "error":
                    had_error = True
                    yield _sse_frame(
                        "error",
                        {"message": event["data"], "code": "generation_failed"},
                    )
                    return
        except Exception as e:  # pragma: no cover - defensive
            logger.error(
                "demo: stream crashed | session_id=%s | %s: %s",
                session_id_capture, type(e).__name__, e,
            )
            yield _sse_frame(
                "error",
                {"message": "AI generation failed.", "code": "generation_failed"},
            )
            return

        if had_error:
            return

        cost_cents = estimate_cost_cents(input_tokens, output_tokens)
        assistant_content: Optional[str] = None
        if demo_type == "ask" and assistant_chunks:
            # Sanitise Haiku's own reply BEFORE persisting (#3842). Any
            # role-like markers or fake system tags the model emits would
            # otherwise be replayed as prior assistant context on the
            # next turn and influence model behaviour. Cap at the shared
            # persisted-content limit (#3843) after sanitisation.
            assistant_content = _sanitize_assistant_content(
                "".join(assistant_chunks)
            )
            if assistant_content is not None:
                assistant_content = assistant_content[:_DEMO_PERSISTED_CONTENT_MAX_CHARS]

        # Update the reserved slot with real metrics on a fresh DB
        # session (the request-scoped `db` is already closed by now).
        try:
            with SessionLocal() as record_db:
                record_session = (
                    record_db.query(DemoSession)
                    .filter(DemoSession.id == session_id_capture)
                    .first()
                )
                if record_session is not None:
                    update_generation_slot(
                        record_db,
                        record_session,
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_cents=cost_cents,
                        assistant_content=assistant_content,
                    )
        except Exception as e:
            logger.error(
                "demo: update_generation_slot failed | session_id=%s | %s: %s",
                session_id_capture, type(e).__name__, e,
            )

        yield _sse_frame(
            "done",
            {
                "demo_type": demo_type,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_cents": cost_cents,
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
