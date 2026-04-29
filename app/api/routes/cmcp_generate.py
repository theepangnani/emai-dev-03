"""CB-CMCP-001 M1-A 1A-2 — POST /api/cmcp/generate (#4471).

HTTP entry-point for the Curriculum-Mapped Content Pipeline. Wraps the
1A-1 ``GuardrailEngine`` behind:

- the existing ``cmcp.enabled`` feature flag (reused dependency from
  0B-1 — keeps the gating semantics identical to the curriculum
  endpoints), and
- standard JWT auth (``get_current_user`` is invoked first so unauth
  requests always see 401, even when the flag is OFF).

Stripe scope (per #4471 + plan §7 M1-A 1A-2 + M1-B 1B-3 #4479)
---------------------------------------------------------------
- Validate the request body (``CMCPGenerateRequest``).
- Resolve ``subject_code`` + ``strand_code`` to the CEG IDs the engine
  consumes. Subject lookup is case-insensitive (matches
  ``app/api/routes/curriculum.py``); strand lookup is scoped to that
  subject and is also case-insensitive on the ministry strand code.
- Derive ``target_persona`` from ``current_user.role`` when the body
  doesn't override it.
- Resolve the M1-B 1B-2 ``ClassContextEnvelope`` for the request when
  ``course_id`` is supplied; pass it to ``GuardrailEngine.build_prompt``
  so the prompt is grounded in the teacher's own materials. When
  ``course_id`` is None the resolver returns an empty envelope with
  ``fallback_used=True`` and the prompt falls back to CEG-only generic
  content.
- Emit the ``cmcp.generation.envelope`` telemetry log line per A1
  acceptance criteria (envelope_size, cited_source_count, fallback_used,
  course_id, target_se_codes_count).
- Build the prompt via ``GuardrailEngine.build_prompt()`` and return
  it in a ``GenerationPreview``.

Out of scope (deferred to later stripes)
----------------------------------------
- Calling Claude/OpenAI for actual generation — M1-E 1E-1 (streaming).
- Validator composition (alignment scoring) — M1-D 1D-2.
- Voice-module registry-backed prompt-text loader — M1-C 1C-2 wave 3
  (this stripe stamps the hash; embedding the module text via the
  registry comes next).
- Persisting an artifact row — M1-A 1A-3 (state machine).
- Frontend invocation — M3-A teacher review queue + 1F-4 parent
  companion render.

Trust boundary
--------------
The HTTP-facing ``CMCPGenerateRequest`` carries human-readable subject /
strand codes — never raw IDs and never voice-module file paths. The
1A-1 engine docstring already calls out that ``voice_module_path`` is
trusted-caller-only; this route never forwards request input there.
The voice-module pointer remains ``None`` until 1C-1's registry ships.
"""
from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.curriculum import require_cmcp_enabled
from app.db.database import get_db
from app.models.curriculum import CEGStrand, CEGSubject
from app.models.user import User, UserRole
from app.schemas.cmcp import (
    CMCPGenerateRequest,
    GenerationPreview,
    GenerationRequest,
    HTTPContentType,
    HTTPDifficulty,
    TargetPersona,
)
from app.services.cmcp.class_context_resolver import (
    ClassContextEnvelope,
    ClassContextResolver,
)
from app.services.cmcp.generation_telemetry import emit_latency_telemetry
from app.services.cmcp.guardrail_engine import (
    GuardrailEngine,
    NoCurriculumMatchError,
)
from app.services.cmcp.voice_registry import VoiceRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cmcp", tags=["CMCP Generation"])


# ---------------------------------------------------------------------------
# Mapping tables — HTTP literals → engine literals
# ---------------------------------------------------------------------------

# HTTP-side content types (per DD §3.2: STUDY_GUIDE / WORKSHEET / QUIZ /
# SAMPLE_TEST / ASSIGNMENT / PARENT_COMPANION) → engine-side ``ContentType``
# literals (lowercase, used by the GuardrailEngine prompt-template helpers).
#
# ``PARENT_COMPANION`` doesn't have a 1A-1 engine analog — for now it maps
# to ``study_guide`` because the parent companion artifact is rendered as
# a study-guide variant in M1-F. When 1F-4 lands a dedicated parent-
# companion template, this entry moves to its own engine literal.
_CONTENT_TYPE_MAP: dict[str, str] = {
    "STUDY_GUIDE": "study_guide",
    "WORKSHEET": "worksheet",
    "QUIZ": "quiz",
    "SAMPLE_TEST": "sample_test",
    "ASSIGNMENT": "assignment",
    "PARENT_COMPANION": "study_guide",
}


# HTTP-side difficulty tiers → engine-side easy/medium/hard. ``GRADE_LEVEL``
# is the default and maps to ``medium``; the below/above tiers map to the
# corresponding engine bands. This mapping is reversible so future stripes
# can round-trip difficulty between the HTTP surface and any artifact rows.
_DIFFICULTY_MAP: dict[str, str] = {
    "APPROACHING": "easy",
    "GRADE_LEVEL": "medium",
    "EXTENDING": "hard",
}


# Persona derivation when ``target_persona`` is omitted from the request.
# The ``UserRole`` enum carries lowercase string values — matches the engine's
# persona keys for parent / student / teacher. Anything else (ADMIN,
# BOARD_ADMIN, CURRICULUM_ADMIN, or a NULL role on a pending-onboarding
# user) falls back to ``"student"`` — the safest default since the student
# voice is the most-used surface and applying it to admin previews still
# produces a usable prompt.
_ROLE_TO_PERSONA: dict[UserRole, TargetPersona] = {
    UserRole.PARENT: "parent",
    UserRole.STUDENT: "student",
    UserRole.TEACHER: "teacher",
}


def _derive_persona(user: User) -> TargetPersona:
    """Return the persona literal for a user when the request omits it.

    Falls back to ``"student"`` for ADMIN / BOARD_ADMIN / CURRICULUM_ADMIN
    or a missing role — see the comment on ``_ROLE_TO_PERSONA`` for the
    rationale. The fallback is deterministic so tests can pin behavior
    for non-PARENT/STUDENT/TEACHER roles.
    """
    if user.role is None:
        return "student"
    return _ROLE_TO_PERSONA.get(user.role, "student")


def _resolve_subject_and_strand(
    db: Session, subject_code: str, strand_code: str | None
) -> tuple[CEGSubject, CEGStrand]:
    """Resolve the CEG subject + strand for a request, raising 422 on miss.

    Subject lookup is case-insensitive on ``CEGSubject.code`` (mirrors
    ``app/api/routes/curriculum.py``). Strand lookup is scoped to that
    subject and case-insensitive on ``CEGStrand.code``.

    The 1A-1 engine contract requires both ``subject_id`` and
    ``strand_id``; this stripe enforces ``strand_code`` at the schema
    level (the route 422s when it's missing) so failure messages point
    at the user-supplied code rather than at the engine internals.
    """
    if not strand_code:
        raise HTTPException(
            status_code=422,
            detail="strand_code is required",
        )

    subject_code_norm = subject_code.upper()
    strand_code_norm = strand_code.upper()

    subject = (
        db.query(CEGSubject)
        .filter(func.upper(CEGSubject.code) == subject_code_norm)
        .first()
    )
    if subject is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown subject_code: {subject_code}",
        )

    strand = (
        db.query(CEGStrand)
        .filter(
            CEGStrand.subject_id == subject.id,
            func.upper(CEGStrand.code) == strand_code_norm,
        )
        .first()
    )
    if strand is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown strand_code {strand_code!r} for subject "
                f"{subject_code_norm}"
            ),
        )
    return subject, strand


def _to_engine_request(
    payload: CMCPGenerateRequest,
    *,
    subject_id: int,
    strand_id: int,
) -> GenerationRequest:
    """Translate the HTTP body into the engine-facing ``GenerationRequest``.

    Maps ``content_type`` + ``difficulty`` from the HTTP literals to the
    engine literals via ``_CONTENT_TYPE_MAP`` / ``_DIFFICULTY_MAP``.
    Both maps are exhaustive over the HTTP literals (Pydantic already
    rejected anything else with a 422 before we got here).
    """
    return GenerationRequest(
        grade=payload.grade,
        subject_id=subject_id,
        strand_id=strand_id,
        content_type=_CONTENT_TYPE_MAP[payload.content_type],
        difficulty=_DIFFICULTY_MAP[payload.difficulty],
        topic=payload.topic,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=GenerationPreview)
def generate_cmcp_preview(
    payload: CMCPGenerateRequest,
    current_user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
) -> GenerationPreview:
    """Build a CEG-anchored prompt + return it as a ``GenerationPreview``.

    Stripe-scope behavior (#4471): does NOT call Claude/OpenAI. Returns
    the constructed system prompt + the SE ministry codes the engine
    targeted + the resolved persona, so the upcoming 1E-1 streaming
    worker can wire on top without forking the gating + resolution
    logic.
    """
    # 1E-2 (#4495): start the latency timer at request entry. ``perf_counter``
    # is monotonic so the delta is unaffected by wall-clock adjustments.
    # The timer + request_id are scoped to this handler — emitting happens
    # in a try/finally below so even 422 / 500 paths produce a telemetry
    # line for breach analysis.
    _start_perf = perf_counter()
    _request_id = uuid4().hex
    try:
        return generate_cmcp_preview_sync(
            payload=payload,
            current_user=current_user,
            db=db,
        )
    finally:
        _latency_ms = int((perf_counter() - _start_perf) * 1000)
        emit_latency_telemetry(
            content_type=payload.content_type,
            latency_ms=_latency_ms,
            request_id=_request_id,
        )


def generate_cmcp_preview_sync(
    payload: CMCPGenerateRequest,
    current_user: User,
    db: Session,
) -> GenerationPreview:
    """Build a CEG-anchored ``GenerationPreview`` for *payload*.

    This is the shared service-layer entry-point for both the REST route
    above and the MCP transport's ``generate_content`` tool (CB-CMCP-001
    M2-B 2B-4 #4555). Both surfaces want identical behaviour: resolve
    subject + strand → derive persona → build prompt → return preview.
    Extracting it here keeps the prompt-construction pipeline in *one*
    place — the MCP tool imports this function rather than duplicating
    the resolve / build / preview logic.

    Raises ``HTTPException`` (422) on bad subject / strand / empty SE
    list — the route layer surfaces the status as-is, and the MCP tool
    layer re-raises so the dispatcher can map it to the MCP error shape.
    Synchronous + side-effect-free apart from the structured telemetry
    log line emitted on success.
    """
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
    # stamp its hash on the response (#4480 / M1-C 1C-2). The lookup is
    # in-memory (per-process) until 1C-3 lands DB-backed persistence.
    # ``active_module_id`` is total over the locked persona set, so the
    # ``persona`` literal validated above guarantees a hit.
    voice_module_id = VoiceRegistry.active_module_id(persona)

    engine = GuardrailEngine(db)

    # M1-B 1B-3 (#4479): build the class-context envelope BEFORE composing
    # the prompt so the GuardrailEngine can ground its output in the
    # teacher's own materials. We resolve the SE list first (cheap CEG
    # query) so the resolver can populate input (d) — APPROVED library
    # artifacts whose SE codes overlap the target set. ``course_id`` is
    # optional on the request body; when None, the resolver returns an
    # empty envelope with ``fallback_used=True`` and the prompt falls
    # back to CEG-only generic content.
    try:
        target_se_codes = engine.get_target_se_codes(engine_request)
    except NoCurriculumMatchError as exc:
        # Same 422 path as ``build_prompt`` would raise — surface it
        # before the resolver query so we don't waste DB round-trips
        # building an envelope for a request that's about to fail.
        logger.info(
            "CMCP generate 422 — no CEG match for grade=%s subject=%s strand=%s topic=%r",
            engine_request.grade,
            subject.code,
            strand.code,
            engine_request.topic,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not target_se_codes:
        # ``get_target_se_codes`` returns [] only when no SEs match;
        # ``build_prompt`` would raise ``NoCurriculumMatchError`` next
        # so short-circuit with the same 422.
        logger.info(
            "CMCP generate 422 — empty SE list for grade=%s subject=%s strand=%s topic=%r",
            engine_request.grade,
            subject.code,
            strand.code,
            engine_request.topic,
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "No CEG specific expectations matched the request. Refusing "
                "to compose an unanchored prompt."
            ),
        )

    envelope: ClassContextEnvelope = ClassContextResolver().resolve(
        user_id=current_user.id,
        course_id=payload.course_id,
        target_se_codes=target_se_codes,
        db=db,
    )

    # Structured telemetry per A1 acceptance criteria (#4479). Five
    # fields are required: envelope_size, cited_source_count,
    # fallback_used, course_id, target_se_codes_count. ``extra=`` keeps
    # the values on the LogRecord so a JSON formatter (M3 telemetry)
    # can promote them to top-level fields without restringifying.
    logger.info(
        "cmcp.generation.envelope course_id=%s envelope_size=%d "
        "cited_source_count=%d fallback_used=%s target_se_codes_count=%d",
        payload.course_id,
        envelope.envelope_size,
        envelope.cited_source_count,
        envelope.fallback_used,
        len(target_se_codes),
        extra={
            "event": "cmcp.generation.envelope",
            "course_id": payload.course_id,
            "envelope_size": envelope.envelope_size,
            "cited_source_count": envelope.cited_source_count,
            "fallback_used": envelope.fallback_used,
            "target_se_codes_count": len(target_se_codes),
        },
    )

    try:
        prompt, se_codes, voice_module_hash = engine.build_prompt(
            engine_request,
            class_context_envelope=envelope.model_dump(),
            voice_module_path=None,
            voice_module_id=voice_module_id,
            target_persona=persona,
        )
    except NoCurriculumMatchError as exc:
        # Defensive: ``get_target_se_codes`` already gated this path,
        # but keep the catch so a race between the two queries doesn't
        # surface as a 500.
        logger.info(
            "CMCP generate 422 — no CEG match for grade=%s subject=%s strand=%s topic=%r",
            engine_request.grade,
            subject.code,
            strand.code,
            engine_request.topic,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GenerationPreview(
        prompt=prompt,
        se_codes_targeted=se_codes,
        voice_module_id=voice_module_id,
        voice_module_hash=voice_module_hash,
        persona=persona,
    )
