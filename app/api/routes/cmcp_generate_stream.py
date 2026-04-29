"""CB-CMCP-001 M1-E 1E-1 — POST /api/cmcp/generate/stream (#4481).

SSE-streaming sibling of the 1A-2 sync ``/api/cmcp/generate`` route.
Long-form content types (Study Guide, Sample Test, Assignment) stream
their AI generation back to the caller progressively as Server-Sent
Events; short-form content types (Quiz, Worksheet, Parent Companion)
are routed to the existing sync endpoint and return ``400`` here with
a redirect message.

Stripe scope (per #4481 + plan §7 M1-E 1E-1)
--------------------------------------------
- Reuse the 1A-2 prompt-build flow:
  * Resolve subject + strand codes against ``CEGSubject`` / ``CEGStrand``.
  * Derive persona from ``current_user.role`` when omitted.
  * Build the system prompt via ``GuardrailEngine.build_prompt()``.
- Stream the AI response via ``app.services.ai_service.generate_content_stream``
  (the existing dev-03 Claude-streaming primitive used by Study Guide
  generation — same yield envelope, same retry/error semantics).
- Wrap each chunk as an SSE ``data: {chunk}`` frame and emit a final
  ``event: complete`` frame carrying the targeted SE codes + persona
  + voice-module pointer (None until 1C-1).
- On stream errors yield ``event: error`` with a user-safe message.

1F-3 extension (#4497) — Parent Companion auto-emit
---------------------------------------------------
After the primary Claude stream completes cleanly for a student-facing
artifact (``persona='student'`` AND ``content_type`` in
``STUDENT_FACING_CONTENT_TYPES``), the route synchronously calls
``ParentCompanionService.generate_5_section()`` against the accumulated
full content and surfaces the structured 5-section result on the
``event: complete`` payload under the ``parent_companion`` key. The
auto-emit is best-effort — if Claude fails or the lint trips, the
service returns ``None`` and the completion event carries
``parent_companion: null`` rather than failing the primary generation.

Out of scope (deferred)
-----------------------
- Per-content-type latency telemetry — 1E-2 wave 3.
- Frontend streaming hook — 1E-3 wave 3.
- Validation pipeline composition into the stream — handled in 1D-2 /
  later stripe; this route makes the basic Claude call only.
- Voice-module registry hookup — 1C-1 / 1C-2.
- Persisting an artifact row — 1A-3 state machine.
- **Persisting the auto-emitted Parent Companion** — M3 territory.
  1F-3 ships the inline auto-emit only.

SSE wire format
---------------
The frontend stream-reader (1E-3) parses each frame as either:
- ``data: <chunk-text>\\n\\n``                 — token / sub-token chunk
- ``event: complete\\ndata: <json>\\n\\n``     — final completion payload
- ``event: error\\ndata: <message>\\n\\n``     — terminal error frame

The ``data: <chunk-text>`` line on token frames carries the raw chunk
text (matches the issue body's ``data: {chunk}\\n\\n`` shape). The
``event: complete`` payload is JSON so 1D-2's validation result + the
voice hash can be carried verbatim once those wires land.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.cmcp_generate import (
    _derive_persona,
    _resolve_subject_and_strand,
    _to_engine_request,
)
from app.api.routes.curriculum import require_cmcp_enabled
from app.db.database import get_db
from app.models.user import User
from app.schemas.cmcp import (
    STUDENT_FACING_CONTENT_TYPES,
    CMCPGenerateRequest,
    TargetPersona,
)
from app.services.ai_service import generate_content_stream
from app.services.cmcp.guardrail_engine import (
    GuardrailEngine,
    NoCurriculumMatchError,
)
from app.services.cmcp.parent_companion_service import ParentCompanionService
from app.services.cmcp.voice_registry import VoiceRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cmcp", tags=["CMCP Generation"])


# Long-form content types stream (the artifact is multi-paragraph and
# benefits from progressive rendering). Short-form types are
# small-response single-shots — the sync ``/api/cmcp/generate`` route is
# the right surface for them and streaming would just add SSE framing
# overhead with no UX win.
_LONG_FORM_CONTENT_TYPES: frozenset[str] = frozenset(
    {"STUDY_GUIDE", "SAMPLE_TEST", "ASSIGNMENT"}
)
_SHORT_FORM_REDIRECT_MESSAGE = (
    "Use /api/cmcp/generate (sync) for short-form content types"
)


def _sse_chunk(text: str) -> str:
    """Format a token-chunk SSE frame.

    Matches the issue's wire shape ``data: {chunk}\\n\\n``. Newlines
    inside the chunk text are escaped to keep the SSE framing intact —
    a literal ``\\n`` would otherwise terminate the ``data:`` line and
    confuse client-side stream readers.
    """
    safe = text.replace("\r", "").replace("\n", "\\n")
    return f"data: {safe}\n\n"


def _sse_event(event: str, data: dict | str) -> str:
    """Format an SSE frame with an explicit ``event:`` line.

    JSON-encodes dict payloads so the completion frame can carry the
    structured ``GenerationPreview``-shaped result without bespoke
    escape rules; string payloads pass through with the same newline
    sanitization as ``_sse_chunk``.
    """
    if isinstance(data, str):
        payload = data.replace("\r", "").replace("\n", "\\n")
    else:
        payload = json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/generate/stream")
def generate_cmcp_stream(
    payload: CMCPGenerateRequest,
    current_user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream a CEG-anchored generation as Server-Sent Events.

    The request body matches 1A-2's ``CMCPGenerateRequest``. Long-form
    content types stream their AI response chunk-by-chunk; short-form
    content types return ``400`` with a redirect to the sync endpoint.

    Resolution + prompt build happens synchronously up-front so subject
    / strand / curriculum-match errors surface as ``422`` (matching the
    sync endpoint) rather than as an SSE error frame buried mid-stream.
    """
    if payload.content_type not in _LONG_FORM_CONTENT_TYPES:
        # Short-form content types never enter the streaming path — the
        # sync route is the correct surface. Returning a structured 400
        # with the canonical redirect message keeps the frontend's
        # decision logic ("which endpoint?") testable without probing
        # the stream itself.
        raise HTTPException(
            status_code=400,
            detail=_SHORT_FORM_REDIRECT_MESSAGE,
        )

    subject, strand = _resolve_subject_and_strand(
        db, payload.subject_code, payload.strand_code
    )

    persona: TargetPersona = payload.target_persona or _derive_persona(
        current_user
    )

    engine_request = _to_engine_request(
        payload, subject_id=subject.id, strand_id=strand.id
    )

    # Resolve the active voice module for the persona so the engine can
    # stamp its hash on the completion frame (#4480 / M1-C 1C-2). Mirrors
    # the 1A-2 sync route — keeps the streaming + sync surfaces aligned
    # until 1C-3 lands DB-backed persistence.
    voice_module_id = VoiceRegistry.active_module_id(persona)

    engine = GuardrailEngine(db)
    try:
        prompt, se_codes, voice_module_hash = engine.build_prompt(
            engine_request,
            class_context_envelope=None,
            voice_module_path=None,
            voice_module_id=voice_module_id,
            target_persona=persona,
        )
    except NoCurriculumMatchError as exc:
        # Mirror the sync route's 422 — surface CEG-empty before
        # opening a stream so callers always see the failure mode in
        # the same shape regardless of which endpoint they hit.
        logger.info(
            "CMCP stream 422 — no CEG match for grade=%s subject=%s strand=%s topic=%r",
            engine_request.grade,
            subject.code,
            strand.code,
            engine_request.topic,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    completion_payload: dict = {
        "se_codes_targeted": list(se_codes),
        "voice_module_id": voice_module_id,
        "voice_module_hash": voice_module_hash,
        "persona": persona,
        "content_type": payload.content_type,
        # 1F-3 (#4497): populated below if the persona+content_type pair
        # hits the auto-emit gate. ``None`` for teacher- and parent-facing
        # generations OR when the auto-emit fails for any reason — the
        # primary generation never depends on auto-emit success.
        "parent_companion": None,
    }

    # Snapshot the inputs the Parent Companion service needs that aren't
    # accessible from inside the event-stream coroutine without re-querying
    # the DB. ``se_codes`` came from the engine prompt build above.
    target_se_codes: list[str] = list(se_codes)
    # ``full_name`` is required-non-null on the User model, but fall back
    # to the email-local-part for safety so the companion prompt always
    # gets a usable identifier.
    student_name: str | None = current_user.full_name
    if not student_name and current_user.email:
        student_name = current_user.email.split("@")[0]
    subject_label = subject.name

    async def _maybe_emit_parent_companion(
        full_content: str,
    ) -> dict | None:
        """Auto-emit the 5-section Parent Companion when gate fires.

        Gate: ``persona == 'student'`` AND ``content_type`` in
        ``STUDENT_FACING_CONTENT_TYPES``. Returns the serialized
        ``ParentCompanionContent`` dict on success, ``None`` when the
        gate is closed OR when ``generate_5_section`` returns ``None``
        (Claude fail / answer-key lint trip / JSON parse failure — all
        already logged by the service).

        Wrapped in a broad ``try/except`` so an unexpected service-side
        error never bubbles up and corrupts the SSE response — auto-emit
        is best-effort by design.
        """
        if persona != "student":
            return None
        if payload.content_type not in STUDENT_FACING_CONTENT_TYPES:
            return None
        if not full_content or not full_content.strip():
            return None
        try:
            companion = await ParentCompanionService.generate_5_section(
                study_guide_content=full_content,
                student_name=student_name,
                subject=subject_label,
                target_se_codes=target_se_codes,
            )
        except Exception:
            logger.exception(
                "CMCP stream parent-companion auto-emit failed unexpectedly"
            )
            return None
        if companion is None:
            return None
        return companion.model_dump()

    async def event_stream() -> AsyncIterator[str]:
        """Yield SSE frames for the duration of the Claude stream.

        The ``ai_service.generate_content_stream`` helper already
        encodes the retry / mid-stream-fail semantics we want — it
        yields ``{"event": "chunk"|"done"|"error", "data": ...}`` dicts
        and never raises mid-stream. We re-frame those into the SSE
        wire format the issue specifies.

        Accumulates the streamed text into ``full_content`` so the
        1F-3 Parent Companion auto-emit can run against the complete
        artifact once the primary stream finishes cleanly.
        """
        full_content_parts: list[str] = []
        try:
            async for ai_event in generate_content_stream(
                prompt="Generate the requested content per the system prompt.",
                system_prompt=prompt,
            ):
                ev_type = ai_event.get("event")
                if ev_type == "chunk":
                    chunk_text = ai_event.get("data", "")
                    full_content_parts.append(chunk_text)
                    yield _sse_chunk(chunk_text)
                elif ev_type == "done":
                    # Stream finished cleanly — run the Parent Companion
                    # auto-emit (no-op for non-student personas) then
                    # emit the completion event with the curriculum
                    # metadata + optional companion payload.
                    done_data = ai_event.get("data") or {}
                    full_content = (
                        done_data.get("full_content")
                        if isinstance(done_data, dict)
                        else None
                    ) or "".join(full_content_parts)
                    completion_payload["parent_companion"] = (
                        await _maybe_emit_parent_companion(full_content)
                    )
                    yield _sse_event("complete", completion_payload)
                    return
                elif ev_type == "error":
                    yield _sse_event(
                        "error",
                        str(ai_event.get("data", "Generation failed")),
                    )
                    return
        except Exception:
            # Defense-in-depth: the helper is documented as never
            # raising mid-stream, but an unexpected exception must not
            # leak to the client as a 500 with a partial body. Log +
            # emit a terminal error frame so the connection closes
            # cleanly.
            logger.exception("CMCP stream unexpected error")
            yield _sse_event("error", "Generation failed")
            return

    return StreamingResponse(event_stream(), media_type="text/event-stream")
