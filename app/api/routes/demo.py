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
from app.schemas.demo import DemoGenerateRequest, DemoSessionCreate
from app.services.demo_generation import (
    estimate_cost_cents,
    stream_demo_completion,
)
from app.services.demo_rate_limit import (
    check_daily_cost_cap,
    check_email_rate_limit,
    check_input_word_count,
    check_ip_rate_limit,
    record_generation,
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
        db.delete(session)
        db.commit()
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
    session_id_capture = session.id

    async def event_stream():
        # We use a fresh DB session inside the generator so the request-
        # scoped ``db`` from Depends is not held open while streaming.
        from app.db.database import SessionLocal

        input_tokens = 0
        output_tokens = 0
        latency_ms = 0
        had_error = False
        try:
            async for event in stream_demo_completion(
                demo_type,
                source_text=source_text,
                question=question,
            ):
                if event["event"] == "chunk":
                    yield _sse_frame("token", {"chunk": event["data"]})
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

        # Record on a new session so we don't race the request-scoped one.
        try:
            with SessionLocal() as record_db:
                record_session = (
                    record_db.query(DemoSession)
                    .filter(DemoSession.id == session_id_capture)
                    .first()
                )
                if record_session is not None:
                    record_generation(
                        record_db,
                        record_session,
                        demo_type=demo_type,
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_cents=cost_cents,
                    )
        except Exception as e:
            logger.error(
                "demo: record_generation failed | session_id=%s | %s: %s",
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
