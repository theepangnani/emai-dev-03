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

1D-3 extension (#4494) — alignment_score + flag_for_review
----------------------------------------------------------
After the primary Claude stream completes cleanly (and after the 1F-3
parent-companion auto-emit), the route runs the 1D-2
``ValidationPipeline`` over the accumulated content and stamps
``alignment_score`` + ``flag_for_review`` onto the completion frame.
Validator failure is non-fatal — alignment is a soft signal in M1
(not a generation gate), so a pipeline exception logs and ships
``alignment_score=None`` rather than returning a 500.

1E-2 extension (#4495) — per-content-type latency telemetry + SLO alerts
-------------------------------------------------------------------------
At request entry the route mints a ``request_id`` and starts a
monotonic perf-counter. The 1E-2 helper ``emit_latency_telemetry`` fires
at end-of-stream (``done`` / ``error`` / mid-stream exception alike via
the ``event_stream`` ``finally`` block) and on the 4xx prep-failure
paths (short-form 400 redirect + subject/strand/no-CEG-match 422), so
every per-type latency sample lands in the structured-log feed with a
deterministic ``slo_breached`` flag.

Out of scope (deferred)
-----------------------
- Frontend streaming hook — 1E-3 wave 3.
- Voice-module registry hookup — 1C-1 / 1C-2.
- Persisting an artifact row — 1A-3 state machine.
- **Persisting the auto-emitted Parent Companion** — M3 territory.
  1F-3 ships the inline auto-emit only.
- **Persisting the alignment_score** — M3 territory. 1D-3 surfaces
  the score on the completion frame only.

SSE wire format
---------------
The frontend stream-reader (1E-3) parses each frame as either:
- ``data: <chunk-text>\\n\\n``                 — token / sub-token chunk
- ``event: complete\\ndata: <json>\\n\\n``     — final completion payload
- ``event: error\\ndata: <message>\\n\\n``     — terminal error frame

The ``data: <chunk-text>`` line on token frames carries the raw chunk
text (matches the issue body's ``data: {chunk}\\n\\n`` shape). The
``event: complete`` payload is JSON shaped like ``StreamCompletionEvent``.
"""
# NOTE (#4533 — refactor deferred to M3): this route is ~450 LOC after
# 5 stripes (1B-3 / 1C-2 / 1D-3 / 1E-2 / 1F-3). M3 will rewrite the
# completion path for persistence + surface dispatch + Tasks emit, so
# extracting `_resolve_envelope` / `_resolve_voice` / `_run_validation`
# / `_emit_completion` helpers now would be throwaway work — see the
# M3 section of docs/design/CB-CMCP-001-batch-implementation-plan.md.
from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import AsyncIterator
from uuid import uuid4

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
from app.db.database import SessionLocal
from app.models.user import User
from app.schemas.cmcp import (
    STUDENT_FACING_CONTENT_TYPES,
    CMCPGenerateRequest,
    StreamCompletionEvent,
    TargetPersona,
)
from app.services.ai_service import generate_content_stream
from app.services.cmcp.artifact_persistence import persist_cmcp_artifact
from app.services.cmcp.class_distribution_authority import (
    validate_class_distribution_authority,
)
from app.services.cmcp.generation_telemetry import emit_latency_telemetry
from app.services.cmcp.guardrail_engine import (
    GuardrailEngine,
    NoCurriculumMatchError,
)
from app.services.cmcp.parent_companion_service import ParentCompanionService
from app.services.cmcp.validation_pipeline import ValidationPipeline
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
    # 1E-2 (#4495): start the latency timer at request entry and mint a
    # request_id. Both are captured into the inner ``event_stream``
    # closure so telemetry emits exactly once at end-of-stream — matches
    # the sync route's "one telemetry line per request" contract.
    _start_perf = perf_counter()
    _request_id = uuid4().hex

    if payload.content_type not in _LONG_FORM_CONTENT_TYPES:
        # Short-form content types never enter the streaming path — the
        # sync route is the correct surface. Returning a structured 400
        # with the canonical redirect message keeps the frontend's
        # decision logic ("which endpoint?") testable without probing
        # the stream itself.
        #
        # Emit the breach-eligible telemetry line for the gating-only
        # path so dashboards still see a per-content-type sample for the
        # 400 case (latency here is tiny — well under any SLO).
        emit_latency_telemetry(
            content_type=payload.content_type,
            latency_ms=int((perf_counter() - _start_perf) * 1000),
            request_id=_request_id,
        )
        raise HTTPException(
            status_code=400,
            detail=_SHORT_FORM_REDIRECT_MESSAGE,
        )

    # 1E-2 (#4495): emit a telemetry line on the 422 paths too — wrap
    # the synchronous resolution / prompt build so dashboards see a
    # per-content-type sample for the failure modes that close before
    # the SSE stream opens. The success path emits inside ``event_stream``
    # to capture full end-of-stream latency.
    try:
        subject, strand = _resolve_subject_and_strand(
            db, payload.subject_code, payload.strand_code
        )

        # M3α 3B-1 (#4577): enforce D3=C class-distribution authority
        # BEFORE opening the SSE stream so 403s surface as plain HTTP
        # errors (matching the sync route) rather than as mid-stream
        # error frames. No-op when ``payload.course_id`` is None.
        validate_class_distribution_authority(
            user=current_user, course_id=payload.course_id, db=db
        )

        persona: TargetPersona = payload.target_persona or _derive_persona(
            current_user
        )

        engine_request = _to_engine_request(
            payload, subject_id=subject.id, strand_id=strand.id
        )

        # Resolve the active voice module for the persona so the engine
        # can stamp its hash on the completion frame (#4480 / M1-C 1C-2).
        # Mirrors the 1A-2 sync route — keeps the streaming + sync
        # surfaces aligned until 1C-3 lands DB-backed persistence.
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
    except HTTPException:
        # Emit telemetry for the 422 / 4xx prep-failure paths so per-type
        # failure rates show up alongside successful streams. Re-raise
        # the original HTTPException untouched.
        emit_latency_telemetry(
            content_type=payload.content_type,
            latency_ms=int((perf_counter() - _start_perf) * 1000),
            request_id=_request_id,
        )
        raise

    se_codes_list = list(se_codes)

    # Snapshot the request's resolved grade + subject_code so the
    # post-stream validator call (1D-3) doesn't reach back into ``payload``
    # / ``subject`` (which carry SQLAlchemy session state we don't want
    # to touch from the async generator).
    validator_grade = engine_request.grade
    validator_subject_code = subject.code

    completion_payload: dict = {
        # M3α prequel (#4575): populated in the done-event handler
        # below by the persistence call. ``None`` until the row is
        # inserted so the typed schema validates even if persistence
        # is skipped (e.g. the request user has been deleted).
        "id": None,
        "se_codes_targeted": se_codes_list,
        "voice_module_id": voice_module_id,
        "voice_module_hash": voice_module_hash,
        "persona": persona,
        "content_type": payload.content_type,
        # 1F-3 (#4497): populated below if the persona+content_type pair
        # hits the auto-emit gate. ``None`` for teacher- and parent-facing
        # generations OR when the auto-emit fails for any reason — the
        # primary generation never depends on auto-emit success.
        "parent_companion": None,
        # 1D-3 (#4494): populated below by the ValidationPipeline. ``None``
        # / ``False`` when the validator was skipped (empty content / no
        # SEs) or raised — alignment is a soft signal, not a generation
        # gate, in M1.
        "alignment_score": None,
        "flag_for_review": False,
        # M3β fu (#4696 / 3I-2): populated below from the validator's
        # embedding-similarity third pass. ``None`` when the validator
        # was skipped or the M1-D composition already failed (the
        # embedding round-trip is elided as a cost-saver in that case).
        "embedding_scores": None,
        "embedding_threshold": None,
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

    # M3α prequel (#4575): snapshot the user id + course id so the
    # post-stream persistence call can construct + commit a row without
    # carrying the ORM-bound ``current_user`` into the async generator
    # (the request session may be closed by then). The persistence
    # helper opens its own session via ``SessionLocal`` and re-loads the
    # user row by id — far simpler than expiring + reattaching.
    persist_user_id = current_user.id
    persist_course_id = payload.course_id
    persist_content_type = payload.content_type
    persist_target_persona = persona
    persist_voice_module_hash = voice_module_hash
    persist_se_codes = list(se_codes)

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
        1F-3 Parent Companion auto-emit + the 1D-3 ValidationPipeline
        run can both operate against the complete artifact once the
        primary stream finishes cleanly.
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
                    # run the 1D-3 alignment pipeline before emitting
                    # the completion event.
                    done_data = ai_event.get("data") or {}
                    full_content = (
                        done_data.get("full_content")
                        if isinstance(done_data, dict)
                        else None
                    ) or "".join(full_content_parts)
                    completion_payload["parent_companion"] = (
                        await _maybe_emit_parent_companion(full_content)
                    )
                    # M3β fu (#4696): supply a fresh ``SessionLocal`` to
                    # the validator so the 3I-2 embedding-similarity pass
                    # actually runs in production — the request-scoped
                    # ``db`` may already be closed by the time this async
                    # generator drains, mirroring the persistence call
                    # below. Wrap in try/finally so a validator exception
                    # never leaks an open session.
                    _validator_db = SessionLocal()
                    try:
                        (
                            alignment_score,
                            flag_for_review,
                            embedding_scores,
                            embedding_threshold,
                        ) = await _run_alignment_pipeline(
                            generated_content=full_content,
                            expected_se_codes=se_codes_list,
                            grade=validator_grade,
                            subject_code=validator_subject_code,
                            db=_validator_db,
                        )
                    finally:
                        _validator_db.close()
                    completion_payload["alignment_score"] = alignment_score
                    completion_payload["flag_for_review"] = flag_for_review
                    completion_payload["embedding_scores"] = embedding_scores
                    completion_payload["embedding_threshold"] = (
                        embedding_threshold
                    )

                    # M3α prequel (#4575): persist the artifact row
                    # before emitting the completion frame so the M3
                    # surface stripes (review queue, dispatcher, parent
                    # companion fetch) can drive their flows from a real
                    # ``study_guides.id``. Persistence opens its own
                    # session via ``SessionLocal`` because the request-
                    # scoped session may be closed by the time the async
                    # generator drains. Best-effort — a failed INSERT
                    # must not corrupt the SSE stream; we log + ship the
                    # completion frame with ``id=None`` so the frontend
                    # can fall back to a not-yet-persisted UI.
                    artifact_id: int | None = None
                    try:
                        _persist_db = SessionLocal()
                        try:
                            _user = _persist_db.query(User).filter(
                                User.id == persist_user_id
                            ).first()
                            if _user is not None:
                                _artifact = persist_cmcp_artifact(
                                    db=_persist_db,
                                    user=_user,
                                    title=f"CMCP {persist_content_type}",
                                    content=full_content,
                                    http_content_type=persist_content_type,
                                    target_persona=persist_target_persona,
                                    se_codes=persist_se_codes,
                                    voice_module_hash=persist_voice_module_hash,
                                    envelope=None,
                                    course_id=persist_course_id,
                                    alignment_score=alignment_score,
                                    parent_companion=completion_payload[
                                        "parent_companion"
                                    ],
                                )
                                artifact_id = _artifact.id
                        finally:
                            _persist_db.close()
                    except Exception:
                        logger.exception(
                            "CMCP stream persist failed user_id=%s "
                            "content_type=%s",
                            persist_user_id,
                            persist_content_type,
                        )

                    completion_payload["id"] = artifact_id

                    # Round-trip through the typed schema so the wire
                    # payload matches ``StreamCompletionEvent`` exactly
                    # (catches typos in payload-building via Pydantic's
                    # ``extra='forbid'`` config + per-field validators).
                    typed = StreamCompletionEvent(**completion_payload)
                    yield _sse_event("complete", typed.model_dump())
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
        finally:
            # 1E-2 (#4495): emit per-type latency telemetry at end-of-
            # stream. ``finally`` runs on done / error / mid-stream
            # exception alike, so dashboards always see a sample. The
            # latency captures full wall-clock from request entry through
            # the last yielded frame — matches the SLO definition (full
            # end-to-end response time, not just AI call duration).
            emit_latency_telemetry(
                content_type=payload.content_type,
                latency_ms=int((perf_counter() - _start_perf) * 1000),
                request_id=_request_id,
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _run_alignment_pipeline(
    *,
    generated_content: str,
    expected_se_codes: list[str],
    grade: int,
    subject_code: str,
    db: Session | None = None,
) -> tuple[float | None, bool, dict[str, float] | None, float | None]:
    """Run the 1D-2 ``ValidationPipeline`` and return its surfaced fields.

    Returns ``(score, flag, embedding_scores, embedding_threshold)``.
    Returns ``(None, False, None, None)`` when the validator was skipped
    (empty content / no expected SEs) or raised — alignment is a soft
    signal in M1, not a generation gate, so a pipeline exception MUST NOT
    block the artifact from reaching the client.

    The streaming route does not currently ask the model to emit a
    ``se_codes_covered`` self-report (that wire is deferred until
    persistence lands in M3). We pass the expected SE codes as the
    "self-report" — i.e., we trust the prompt's anchoring — so the
    composed ``alignment_score`` collapses to the second-pass coverage
    rate, which is the only independent signal we have in M1.

    M3β fu (#4696): when ``db`` is supplied, the 3I-2 embedding-similarity
    pass runs as a third gate inside ``ValidationPipeline.validate`` and
    its scores + threshold are surfaced back to the caller for inclusion
    in the completion frame / persisted artifact metadata. Legacy callers
    that omit ``db`` keep the score-based ``flag_for_review`` semantics.
    """
    if not generated_content or not generated_content.strip():
        return None, False, None, None
    if not expected_se_codes:
        return None, False, None, None
    try:
        pipeline = ValidationPipeline()
        result = await pipeline.validate(
            generated_content=generated_content,
            model_self_report_se_codes=list(expected_se_codes),
            expected_se_codes=list(expected_se_codes),
            grade=grade,
            subject_code=subject_code,
            db=db,
        )
    except Exception:
        # Validator failure must not block the artifact — log + ship
        # the artifact with ``alignment_score=None`` so the client
        # can render a "score unavailable" pill rather than a 500.
        logger.exception(
            "CMCP stream alignment validation failed grade=%s subject=%s",
            grade,
            subject_code,
        )
        return None, False, None, None
    return (
        result.alignment_score,
        result.flag_for_review,
        result.embedding_scores,
        result.embedding_threshold,
    )
