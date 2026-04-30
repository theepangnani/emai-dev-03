"""
CB-CMCP-001 — Pydantic schemas for the Curriculum-Mapped Content Pipeline.

Stripe scope
------------
- 1A-1 shipped the engine-facing ``GenerationRequest`` (``subject_id`` +
  ``strand_id`` + lowercase content-type literals) — what
  ``GuardrailEngine.build_prompt()`` consumes.
- 1A-2 added the *HTTP-facing* schemas for the
  ``POST /api/cmcp/generate`` route:

  * ``CMCPGenerateRequest`` — request body. Mirrors DD §3.2 wording
    (``subject_code`` / ``strand_code`` / uppercase content-type
    literals / ``GRADE_LEVEL`` difficulty / optional
    ``target_persona``). The route resolves these into a
    ``GenerationRequest`` for the engine — the engine's contract is
    unchanged in this stripe.
  * ``GenerationPreview`` — response model returning the constructed
    prompt + targeted SE codes + persona + voice-module pointer. No
    Claude/OpenAI call yet (M1-E 1E-1 wires that).
- 1F-3 (#4497) adds the typed schema for the streaming route's
  ``event: complete`` payload, including the optional
  ``parent_companion`` field auto-emitted alongside student-facing
  artifacts. Persistence + DCI/Bridge surfacing remains M3 territory —
  this stripe ships the inline auto-emit only.
- 1D-3 (#4494) extends ``StreamCompletionEvent`` with
  ``alignment_score`` + ``flag_for_review`` — the composed result of
  the 1D-2 ``ValidationPipeline`` run over the streamed content.

The id-based ``GenerationRequest`` and the code-based
``CMCPGenerateRequest`` are intentionally kept distinct: the engine is
a pure function over CEG IDs, and the route is a stable HTTP contract
with human-readable subject/strand codes. Translation lives in the
route handler, not in either schema.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.cmcp.parent_companion_service import ParentCompanionContent


# Locked content types (per plan §7 M1-A acceptance gate listing all five).
# The ``content_type`` is consumed by 1A-2's generation route to pick the
# template + length budget; for 1A-1 it's just embedded in the prompt.
ContentType = Literal[
    "quiz",
    "worksheet",
    "study_guide",
    "sample_test",
    "assignment",
]


# Difficulty band matches CB-TUTOR-001/002 conventions (easy/medium/hard).
Difficulty = Literal["easy", "medium", "hard"]


class GenerationRequest(BaseModel):
    """Minimal generation request shape consumed by ``GuardrailEngine``.

    Carries the dimensions needed to query the M0 ``CEGExpectation``
    table for the SE list that anchors the prompt. ``topic`` is an
    optional coarse string-match filter (semantic / pgvector lookup is
    deferred to M3 batch 3I per the locked plan).

    Stripe scope (1A-1):
    - Required dimensions: ``grade``, ``subject_id``, ``strand_id``,
      ``content_type``.
    - Optional: ``topic`` (string filter), ``difficulty``,
      ``curriculum_version_id`` (defaults to "active rows" when None —
      the GuardrailEngine query filters ``active=True``).
    """

    model_config = ConfigDict(extra="forbid")

    grade: int = Field(..., ge=1, le=12, description="Ontario grade level (1-12).")
    subject_id: int = Field(..., gt=0, description="FK -> ceg_subjects.id")
    strand_id: int = Field(..., gt=0, description="FK -> ceg_strands.id")
    content_type: ContentType = Field(
        ..., description="Artifact type (quiz, worksheet, etc.)."
    )
    topic: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Optional coarse topic string. When supplied, the GuardrailEngine "
            "filters CEG SEs by case-insensitive substring match on the "
            "expectation description. Semantic search is M3 territory."
        ),
    )
    difficulty: Difficulty = Field(
        default="medium", description="Difficulty band for the artifact."
    )
    curriculum_version_id: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Optional pin to a specific ``curriculum_versions.id``. When "
            "None, the engine targets the rows with ``active=True`` for the "
            "given (grade, subject_id) — i.e., the live curriculum slice."
        ),
    )


# ---------------------------------------------------------------------------
# 1A-2: HTTP-facing schemas for POST /api/cmcp/generate
# ---------------------------------------------------------------------------

# HTTP-side content-type literal (uppercase, per DD §3.2 + the issue body).
# Distinct from the engine-side ``ContentType`` so the API can carry the
# canonical artifact-type identifiers (STUDY_GUIDE, PARENT_COMPANION, etc.)
# while the engine keeps its prompt-template-friendly lowercase form. The
# route maps between the two — see ``app/api/routes/cmcp_generate.py``.
HTTPContentType = Literal[
    "STUDY_GUIDE",
    "WORKSHEET",
    "QUIZ",
    "SAMPLE_TEST",
    "ASSIGNMENT",
    "PARENT_COMPANION",
]


# HTTP-side difficulty band. ``GRADE_LEVEL`` is the default (matches the
# Ontario "at grade" tier); ``APPROACHING`` and ``EXTENDING`` cover the
# below/above tiers used by the curriculum-aligned content surface. The
# route maps these to the engine-side easy/medium/hard band.
HTTPDifficulty = Literal["APPROACHING", "GRADE_LEVEL", "EXTENDING"]


# Persona literal — lowercase to match the engine's persona-block keys.
# When the request omits ``target_persona`` the route derives it from
# ``current_user.role`` (parent → "parent", student → "student",
# teacher → "teacher"; everyone else falls back to "student").
TargetPersona = Literal["student", "parent", "teacher"]


class CMCPGenerateRequest(BaseModel):
    """Request body for ``POST /api/cmcp/generate``.

    Carries the human-readable subject/strand codes (per DD §3.2). The
    route handler resolves these to the CEG IDs the engine needs, then
    delegates to ``GuardrailEngine.build_prompt()``.

    ``target_persona`` is optional: when ``None``, the route derives it
    from ``current_user.role``.
    """

    model_config = ConfigDict(extra="forbid")

    grade: int = Field(..., ge=1, le=12, description="Ontario grade level (1-12).")
    subject_code: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "CEG subject code (e.g., 'MATH', 'LANG'). Resolved against "
            "``CEGSubject.code`` case-insensitively."
        ),
    )
    strand_code: str | None = Field(
        default=None,
        max_length=32,
        description=(
            "Optional CEG strand code (e.g., 'B'). When provided, the engine "
            "narrows the SE list to that strand under the resolved subject. "
            "When None, the route 422s — strand is required by the 1A-1 "
            "engine contract; future stripes may relax this once cross-"
            "strand prompts are supported."
        ),
    )
    topic: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Optional coarse topic substring filter applied to SE descriptions."
        ),
    )
    content_type: HTTPContentType = Field(
        ..., description="Artifact type (STUDY_GUIDE, WORKSHEET, etc.)."
    )
    difficulty: HTTPDifficulty = Field(
        default="GRADE_LEVEL",
        description="Difficulty tier (APPROACHING / GRADE_LEVEL / EXTENDING).",
    )
    target_persona: TargetPersona | None = Field(
        default=None,
        description=(
            "Optional override for the prompt's persona overlay. When None, "
            "the route derives the persona from ``current_user.role``."
        ),
    )
    course_id: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Optional ``courses.id`` the artifact will be anchored to. When "
            "supplied, the M1-B 1B-2 ``ClassContextResolver`` pulls the "
            "course-scoped envelope (course materials, recent GC announcements, "
            "teacher email digest, matching APPROVED library artifacts) and "
            "the M1-B 1B-3 stripe injects it into the prompt under "
            "``[CLASS_CONTEXT]``. When None, the route falls back to "
            "CEG-only generic content (``fallback_used=True`` on the "
            "envelope's audit metadata)."
        ),
    )


class GenerationPreview(BaseModel):
    """Response body for ``POST /api/cmcp/generate`` in the 1A-2 stripe.

    The route does NOT call Claude in this stripe (M1-E 1E-1 wires that)
    — it returns the constructed system prompt + the targeted SE codes
    + the persona that was resolved + the voice-module pointer (None
    for 1A-2; M1-C 1C-2 will populate this).

    Returning the prompt verbatim is intentional for this stripe: it
    lets integration tests and the upcoming 1E-1 streaming worker share
    one preview surface without branching on "preview vs. live" code
    paths. Once 1E-1 ships, the route will switch to a streaming
    response and this preview model becomes the body of a future
    ``POST /api/cmcp/generate/preview`` debug endpoint.

    M3α prequel (#4575)
    -------------------
    The ``id`` field carries the inserted ``study_guides.id`` so the
    M3 surface stripes (review queue, self-study, dispatcher, parent
    companion fetch) can drive their flows from a returned artifact id
    rather than re-querying. ``None`` is returned only when the INSERT
    is skipped or fails — see the route-handler comments.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(
        default=None,
        description=(
            "Persisted ``study_guides.id`` for the generated artifact. "
            "Populated by the M3α prequel (#4575) — the route inserts a "
            "row carrying all M0/M1 stamped columns after preview "
            "construction succeeds. ``None`` only when persistence is "
            "skipped (legacy callers) or fails."
        ),
    )
    prompt: str = Field(..., description="Constructed system prompt.")
    se_codes_targeted: list[str] = Field(
        default_factory=list,
        description="Ordered list of SE ministry codes anchored in the prompt.",
    )
    voice_module_id: str | None = Field(
        default=None,
        description=(
            "Voice-module identifier resolved for this generation. Populated "
            "from ``VoiceRegistry.active_module_id(persona)`` once 1C-2 wires "
            "the registry-backed loader; pre-1C-2 callers may still see None."
        ),
    )
    voice_module_hash: str | None = Field(
        default=None,
        description=(
            "SHA-256 hex digest of the voice-module contents used for this "
            "generation (M1-C 1C-2 / #4480). Stamped on the artifact so the "
            "wave-3 audit job (1C-3) can flag artifacts whose voice no longer "
            "matches the active module. ``None`` when ``voice_module_id`` is "
            "also ``None``."
        ),
    )
    persona: TargetPersona = Field(
        ..., description="The persona overlay used to build the prompt."
    )


# ---------------------------------------------------------------------------
# 1F-3 (#4497) + 1D-3 (#4494): streaming route completion-event schema
# ---------------------------------------------------------------------------


# Student-facing content types per #4497 + plan §7 M1-F 1F-3 + Amendment A2.
# When the streaming route generates one of these for ``persona='student'``,
# it auto-emits a Parent Companion derivative inline on the completion event.
# QUIZ + WORKSHEET are listed for completeness even though the streaming
# route 400s on them today — the same membership set is the right gate for
# any future surface that grows a streaming path for short-form types.
STUDENT_FACING_CONTENT_TYPES: frozenset[str] = frozenset(
    {"STUDY_GUIDE", "SAMPLE_TEST", "ASSIGNMENT", "QUIZ", "WORKSHEET"}
)


class StreamCompletionEvent(BaseModel):
    """Typed body of the ``event: complete`` SSE frame on the streaming route.

    Mirrors the dict the streaming route already emits today, plus the
    1F-3 (``parent_companion``) extension and the 1D-3
    (``alignment_score`` / ``flag_for_review``) extension. Kept here as a
    typed schema so consumers (frontend hook, integration tests) can pin
    the wire shape without re-deriving it from the route module.

    The ``parent_companion`` field is populated **only** when the
    generation targets a student-facing artifact for ``persona='student'``
    AND the auto-emit succeeds. Auto-emit failure is non-fatal — the
    route logs and emits ``parent_companion=None`` rather than failing
    the primary generation.

    The ``alignment_score`` + ``flag_for_review`` fields (1D-3) carry the
    composed result of ``ValidationPipeline.validate`` (1D-2) run over
    the full streamed content. ``alignment_score`` is ``None`` when the
    validator could not run (empty content) or raised — alignment is a
    soft signal in M1, not a generation gate.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(
        default=None,
        description=(
            "M3α prequel (#4575): persisted ``study_guides.id`` for the "
            "streamed artifact. ``None`` only when persistence is skipped "
            "or fails — best-effort, the completion frame ships either way."
        ),
    )
    se_codes_targeted: list[str] = Field(
        default_factory=list,
        description="Ordered list of SE ministry codes anchored in the prompt.",
    )
    voice_module_id: str | None = Field(
        default=None,
        description="Voice-module identifier resolved for this generation.",
    )
    voice_module_hash: str | None = Field(
        default=None,
        description="SHA-256 hex digest of the voice-module contents used.",
    )
    persona: TargetPersona = Field(
        ..., description="The persona overlay used to build the prompt."
    )
    content_type: HTTPContentType = Field(
        ..., description="HTTP-side artifact type the request targeted."
    )
    parent_companion: ParentCompanionContent | None = Field(
        default=None,
        description=(
            "Parent Companion derivative auto-emitted alongside the primary "
            "student artifact when ``persona='student'`` and ``content_type`` "
            "is in ``STUDENT_FACING_CONTENT_TYPES``. The 5-section "
            "``ParentCompanionContent`` structure (per FR-02.6 / Amendment "
            "A2) is now exposed as a typed nested model so consumers "
            "(frontend hook, future MCP clients, OpenAPI schema) get "
            "field-level guarantees rather than an untyped ``dict``. "
            "``None`` for teacher- and parent-facing generations OR when "
            "auto-emit fails (non-fatal — the primary generation always "
            "succeeds independently)."
        ),
    )
    alignment_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "1D-3 (#4494): composed alignment score from "
            "``ValidationPipeline.validate`` (1D-2) over the streamed "
            "content. ``None`` when the validator could not run (e.g., "
            "empty content) or raised — alignment is a soft signal in M1, "
            "not a generation gate."
        ),
    )
    flag_for_review: bool = Field(
        default=False,
        description=(
            "1D-3 (#4494): True when ``alignment_score < REVIEW_THRESHOLD`` "
            "per the 1D-2 pipeline. False when the validator was skipped or "
            "the score cleared the review threshold."
        ),
    )
    embedding_scores: dict[str, float] | None = Field(
        default=None,
        description=(
            "M3β fu (#4696 / 3I-2): per-SE max cosine-similarity scores "
            "from the embedding-similarity third pass that runs when the "
            "validator is supplied a SQLAlchemy session. ``None`` when the "
            "embedding pass did not run (legacy callers, validator skipped, "
            "or M1-D first/second composition already failed and the "
            "embedding round-trip was elided as a cost-saver)."
        ),
    )
    embedding_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "M3β fu (#4696 / 3I-2): cosine-similarity threshold used by the "
            "embedding pass. ``None`` when the embedding pass did not run."
        ),
    )


# ---------------------------------------------------------------------------
# M3α prequel (#4575) — GET /api/cmcp/artifacts/{id}/parent-companion response
# ---------------------------------------------------------------------------


class ParentCompanionArtifactResponse(BaseModel):
    """Response body for ``GET /api/cmcp/artifacts/{id}/parent-companion``.

    Wraps the persisted artifact's parent companion content + the
    artifact id so callers can correlate. The route returns 422 when
    the requested artifact's ``requested_persona != 'parent'`` (the
    artifact is not a parent-persona artifact). ``content`` is the
    5-section ``ParentCompanionContent`` deserialized from the row's
    ``parent_summary`` JSON, or a minimal stub when no auto-emitted
    parent companion exists yet (M1 sync route doesn't run the AI).
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: int = Field(..., description="``study_guides.id``.")
    content: ParentCompanionContent = Field(
        ...,
        description=(
            "5-section parent companion content. Sourced from the row's "
            "``parent_summary`` JSON when populated by the M1-F 1F-3 "
            "auto-emit; otherwise a minimal stub built from the artifact "
            "row so the page can render a degraded but well-typed view."
        ),
    )


# ---------------------------------------------------------------------------
# M3β follow-up #4694 — GET /api/cmcp/artifacts/{id}/student-view response
# ---------------------------------------------------------------------------


class StudentArtifactViewResponse(BaseModel):
    """Response body for ``GET /api/cmcp/artifacts/{id}/student-view``.

    Minimal student-facing artifact projection — the LTI launch surface
    redirects STUDENT-validated tokens to ``/student/artifact/{id}``,
    and that page calls this endpoint to render title + content. This
    is intentionally a thin pass-through (no parent-companion 5-section
    decomposition) because the LMS-launching student needs the actual
    artifact, not coaching scaffolding for a parent.

    M4 may extend with structured sections, drill anchors, etc.; today
    the contract is: fetch what's safe to render to the resolved
    STUDENT, on the same visibility matrix everyone else uses.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: int = Field(..., description="``study_guides.id``.")
    title: str = Field(..., description="Artifact title (display).")
    content: str = Field(
        ...,
        description=(
            "Raw artifact content as stored on the row. Markdown for the "
            "study-guide-style content types. The student page renders "
            "this as plain text / markdown without further processing."
        ),
    )
    guide_type: str = Field(
        ...,
        description=(
            "Artifact ``guide_type`` (study_guide / quiz / flashcards / "
            "etc.) so the student page can pick a renderer hint."
        ),
    )
