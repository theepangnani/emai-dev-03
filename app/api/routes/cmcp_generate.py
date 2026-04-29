"""CB-CMCP-001 M1-A 1A-2 — POST /api/cmcp/generate (#4471).

HTTP entry-point for the Curriculum-Mapped Content Pipeline. Wraps the
1A-1 ``GuardrailEngine`` behind:

- the existing ``cmcp.enabled`` feature flag (reused dependency from
  0B-1 — keeps the gating semantics identical to the curriculum
  endpoints), and
- standard JWT auth (``get_current_user`` is invoked first so unauth
  requests always see 401, even when the flag is OFF).

Stripe scope (per #4471 + plan §7 M1-A 1A-2)
--------------------------------------------
- Validate the request body (``CMCPGenerateRequest``).
- Resolve ``subject_code`` + ``strand_code`` to the CEG IDs the engine
  consumes. Subject lookup is case-insensitive (matches
  ``app/api/routes/curriculum.py``); strand lookup is scoped to that
  subject and is also case-insensitive on the ministry strand code.
- Derive ``target_persona`` from ``current_user.role`` when the body
  doesn't override it.
- Build the prompt via ``GuardrailEngine.build_prompt()`` and return
  it in a ``GenerationPreview``.

Out of scope (deferred to later stripes)
----------------------------------------
- Calling Claude/OpenAI for actual generation — M1-E 1E-1 (streaming).
- Validator composition (alignment scoring) — M1-D 1D-2.
- Voice-module hash + registry-backed loader — M1-C 1C-1 / 1C-2.
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
from app.services.cmcp.guardrail_engine import (
    GuardrailEngine,
    NoCurriculumMatchError,
)

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
    subject, strand = _resolve_subject_and_strand(
        db, payload.subject_code, payload.strand_code
    )

    persona: TargetPersona = payload.target_persona or _derive_persona(
        current_user
    )

    engine_request = _to_engine_request(
        payload, subject_id=subject.id, strand_id=strand.id
    )

    engine = GuardrailEngine(db)
    try:
        prompt, se_codes = engine.build_prompt(
            engine_request,
            class_context_envelope=None,
            voice_module_path=None,
            target_persona=persona,
        )
    except NoCurriculumMatchError as exc:
        # The engine refuses to compose an unanchored prompt. Surface
        # this to the caller as a 422 — the request was syntactically
        # valid but no CEG rows match the (grade, subject, strand,
        # topic) tuple, which is a curated-data problem the caller
        # needs to know about.
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
        voice_module_id=None,
        persona=persona,
    )
