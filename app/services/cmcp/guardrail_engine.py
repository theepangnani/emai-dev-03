"""
CB-CMCP-001 M1-A 1A-1 — GuardrailEngine.

Composes the system prompt that anchors every CB-CMCP generation to
Ontario curriculum expectations. This is the *core* prompt-construction
layer — it does NOT call Claude/OpenAI (that's 1A-2's generation route)
and it does NOT persist artifacts (that's 1A-3's state machine).

Inputs (per the issue body + plan §7 M1-A 1A-1):
1. CEG SE list — queried from the M0 ``CEGExpectation`` model using
   ``(grade, subject_id, strand_id, expectation_type='specific')``.
   When ``topic`` is supplied on the request, an additional
   case-insensitive substring filter is applied. The OE rows the SEs
   roll up to are also fetched so the prompt can reference them.
2. Class-context envelope — accepted as ``dict | None`` for this stripe.
   Real envelope construction is M1-B 1B-2's job; here we just embed
   the supplied dict's ``summary`` + ``cited_sources`` if present.
3. Voice overlay module path — accepted as ``str | None``. Hash stamping
   + module loading is M1-C 1C-1/1C-2's job; here we embed the contents
   of the file at the path if it exists, otherwise note the placeholder.
4. Persona overlay — ``"student"`` (default; Arc voice), ``"parent"``
   (warm-coaching tone), or ``"teacher"`` (neutral-professional).

Returns ``(system_prompt, list_of_se_codes_targeted)`` so the caller
can record which SEs the artifact is pinned to (drives the
``GuardrailEnvelope`` value object recorded per generation; see DD §3.2).

Empty CEG result → raises ``NoCurriculumMatchError``. The plan's "fall
back to a 'no SEs' disclaimer" path is a future option, but for 1A-1 we
fail fast — silently generating CEG-unanchored content would defeat the
whole purpose of the guardrail layer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Final

from sqlalchemy.orm import Session

from app.models.curriculum import (
    CEGExpectation,
    EXPECTATION_TYPE_OVERALL,
    EXPECTATION_TYPE_SPECIFIC,
)
from app.schemas.cmcp import GenerationRequest
from app.services.cmcp.voice_registry import VoiceRegistry


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NoCurriculumMatchError(ValueError):
    """Raised when the CEG query returns zero SE rows for the request.

    The GuardrailEngine refuses to compose a prompt with no curriculum
    anchor — it would defeat the purpose of the guardrail layer. Callers
    should surface this as a 422 from the M1-A 1A-2 generation route.
    """


# ---------------------------------------------------------------------------
# Persona overlay blocks
# ---------------------------------------------------------------------------

# Persona blocks — short, deliberately-distinct strings so callers (and
# tests) can verify the right block was injected. Real voice content
# lives in the voice-module registry (M1-C 1C-1).
_PERSONA_BLOCKS: Final[dict[str, str]] = {
    "student": (
        "Audience: STUDENT. Default voice is Arc — warm, curious, short "
        "sentences, no jargon. Encourage effort over correctness."
    ),
    "parent": (
        "Audience: PARENT. Use a warm-coaching tone — frame learning as "
        "partnership, never use answer-key phrasing, suggest concrete "
        "talking points the parent can use with the student."
    ),
    "teacher": (
        "Audience: TEACHER. Use a neutral-professional tone — concise, "
        "pedagogically precise, reference the SE codes by their ministry "
        "identifier; assume the reader is a subject-matter expert."
    ),
}

_VALID_PERSONAS: Final[frozenset[str]] = frozenset(_PERSONA_BLOCKS.keys())


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GuardrailEngine:
    """Composes the CEG-anchored system prompt for a generation request.

    Construct with a SQLAlchemy session bound to the request's transaction.
    The engine performs read-only queries against the M0 CEG tables and
    does not mutate state.

    Example
    -------
    >>> engine = GuardrailEngine(db)
    >>> prompt, se_codes, voice_hash = engine.build_prompt(request)
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # -- public API --------------------------------------------------------

    def build_prompt(
        self,
        request: GenerationRequest,
        *,
        class_context_envelope: dict | None = None,
        voice_module_path: str | None = None,
        voice_module_id: str | None = None,
        target_persona: str = "student",
    ) -> tuple[str, list[str], str | None]:
        """Build the system prompt + SE-code list for a generation request.

        Parameters
        ----------
        request:
            Generation request. ``grade``, ``subject_id``, ``strand_id``
            drive the CEG SE lookup; ``topic`` is an optional substring
            filter; ``content_type`` + ``difficulty`` are embedded in the
            prompt for the downstream model.
        class_context_envelope:
            Optional dict produced by M1-B 1B-2's class-context resolver.
            Recognized keys: ``"summary"`` (str), ``"cited_sources"``
            (list[str | dict]). Any other keys are ignored. ``None`` =
            no envelope (the generic / not-class-anchored path).
        voice_module_path:
            Optional path to a voice-overlay module file (M1-C registry).
            When supplied + readable, the file's text is embedded verbatim.
            Trusted-caller-only — see ``_render_voice_block`` docstring.
            Tests pass paths produced by ``tmp_path`` fixtures; production
            callers prefer ``voice_module_id`` (looked up via the registry).
        voice_module_id:
            Optional voice-module identifier (e.g., ``"arc_voice_v1"``)
            registered in :class:`VoiceRegistry`. When supplied, the
            engine returns the SHA-256 ``voice_module_hash`` for that
            module as the third tuple element so the caller (1A-2 route)
            can stamp it on the artifact response (#4480 / DD §3.2).
            ``voice_module_path`` and ``voice_module_id`` are
            independent — the path drives prompt-text embedding (1A-1
            placeholder until 1C-2 wires the registry-backed loader),
            and the id drives hash stamping (this stripe). Callers will
            usually pass both, but missing either is non-fatal.
        target_persona:
            ``"student"`` (default), ``"parent"``, or ``"teacher"``. Other
            values raise ``ValueError`` — keeps the persona space pinned.

        Returns
        -------
        tuple[str, list[str], str | None]
            (system_prompt,
             ordered list of SE ministry codes targeted,
             SHA-256 hex digest of the voice module's contents — or
             ``None`` when ``voice_module_id`` was not supplied).

        Raises
        ------
        ValueError
            If ``target_persona`` is not in the locked persona set.
        NoCurriculumMatchError
            If zero SE rows match the request dimensions (after optional
            topic filter).
        FileNotFoundError
            If ``voice_module_id`` is supplied but the registry can't
            find the corresponding ``.txt`` file. Surfaces straight
            from :py:meth:`VoiceRegistry.module_hash` — fail fast rather
            than silently returning ``None``, since the artifact's
            voice-consistency audit (1C-3) relies on every artifact
            carrying a valid hash when an id was specified.
        """
        if target_persona not in _VALID_PERSONAS:
            raise ValueError(
                f"target_persona must be one of {sorted(_VALID_PERSONAS)}, "
                f"got {target_persona!r}"
            )

        ses, oes = self._fetch_curriculum_rows(request)
        if not ses:
            raise NoCurriculumMatchError(
                "No CEG specific expectations matched "
                f"grade={request.grade} subject_id={request.subject_id} "
                f"strand_id={request.strand_id} topic={request.topic!r}. "
                "Refusing to compose an unanchored prompt."
            )

        guardrail_block = self._render_guardrail_block(oes, ses)
        request_block = self._render_request_block(request)
        envelope_block = self._render_envelope_block(class_context_envelope)
        voice_block = self._render_voice_block(voice_module_path)
        persona_block = _PERSONA_BLOCKS[target_persona]

        # Assembly order matters: curriculum first (load-bearing), then
        # request shape, then class context (optional), then voice
        # (optional), then persona (always last so it influences the
        # final tone the model commits to). Each block is separated by
        # a labelled marker so downstream tooling can split deterministically.
        sections = [
            "[CURRICULUM_GUARDRAIL]\n" + guardrail_block,
            "[REQUEST]\n" + request_block,
        ]
        if envelope_block is not None:
            sections.append("[CLASS_CONTEXT]\n" + envelope_block)
        if voice_block is not None:
            sections.append("[VOICE]\n" + voice_block)
        sections.append("[PERSONA]\n" + persona_block)

        system_prompt = "\n\n".join(sections)
        se_codes = [se.ministry_code for se in ses]

        # Voice hash stamping (#4480, M1-C 1C-2). We delegate the digest
        # to the registry rather than re-hashing here so the wave-3
        # audit job (1C-3) and this route always see the same hash for
        # the same module bytes. ``module_hash`` reads the file at call
        # time (no caching) — that's deliberate: voice modules are tiny
        # and a fresh read keeps hot-swap (FR-02.7) consistent.
        voice_module_hash: str | None = None
        if voice_module_id is not None:
            voice_module_hash = VoiceRegistry.module_hash(voice_module_id)

        return system_prompt, se_codes, voice_module_hash

    # -- internal helpers --------------------------------------------------

    def _fetch_curriculum_rows(
        self, request: GenerationRequest
    ) -> tuple[list[CEGExpectation], list[CEGExpectation]]:
        """Return (specific_expectations, overall_expectations) for the request.

        The query targets ``active=True`` rows by default. When
        ``request.curriculum_version_id`` is supplied, the version filter
        replaces the active filter (callers may want to inspect a frozen
        snapshot).
        """
        base = (
            self._db.query(CEGExpectation)
            .filter(
                CEGExpectation.grade == request.grade,
                CEGExpectation.subject_id == request.subject_id,
                CEGExpectation.strand_id == request.strand_id,
            )
        )
        if request.curriculum_version_id is not None:
            base = base.filter(
                CEGExpectation.curriculum_version_id
                == request.curriculum_version_id
            )
        else:
            base = base.filter(CEGExpectation.active.is_(True))

        ses_query = base.filter(
            CEGExpectation.expectation_type == EXPECTATION_TYPE_SPECIFIC
        )
        if request.topic:
            # Coarse case-insensitive substring filter — semantic match is
            # M3 territory. ``ilike`` works on both SQLite and Postgres.
            ses_query = ses_query.filter(
                CEGExpectation.description.ilike(f"%{request.topic}%")
            )

        ses = ses_query.order_by(CEGExpectation.ministry_code).all()

        oes = (
            base.filter(
                CEGExpectation.expectation_type == EXPECTATION_TYPE_OVERALL
            )
            .order_by(CEGExpectation.ministry_code)
            .all()
        )
        return ses, oes

    def _render_guardrail_block(
        self,
        oes: list[CEGExpectation],
        ses: list[CEGExpectation],
    ) -> str:
        """Render the OE + SE listing as the curriculum guardrail block."""
        lines: list[str] = []
        if oes:
            lines.append("Overall Expectations (OEs):")
            for oe in oes:
                lines.append(f"- {oe.ministry_code}: {oe.description}")
            lines.append("")
        lines.append("Specific Expectations (SEs) — anchor the artifact to these:")
        for se in ses:
            lines.append(f"- {se.ministry_code}: {se.description}")
        return "\n".join(lines)

    def _render_request_block(self, request: GenerationRequest) -> str:
        """Render the request dimensions (grade, content_type, etc.)."""
        topic_line = (
            f"Topic filter: {request.topic}" if request.topic else "Topic filter: (none)"
        )
        return (
            f"Grade: {request.grade}\n"
            f"Content type: {request.content_type}\n"
            f"Difficulty: {request.difficulty}\n"
            f"{topic_line}"
        )

    def _render_envelope_block(
        self, envelope: dict | None
    ) -> str | None:
        """Render the optional class-context envelope.

        Recognized keys: ``"summary"`` and ``"cited_sources"``. Anything
        else is ignored — the full envelope schema lands in M1-B 1B-2.
        """
        if envelope is None:
            return None
        summary = envelope.get("summary") or ""
        cited = envelope.get("cited_sources") or []
        lines: list[str] = []
        if summary:
            lines.append(f"Summary: {summary}")
        if cited:
            lines.append("Cited sources:")
            for src in cited:
                lines.append(f"- {src}")
        if not lines:
            # Empty dict provided — return a stable placeholder so the
            # block still appears in the prompt (caller signalled intent).
            return "(envelope provided but empty — placeholder until 1B-2 ships)"
        return "\n".join(lines)

    def _render_voice_block(
        self, voice_module_path: str | None
    ) -> str | None:
        """Render the optional voice-overlay block.

        For 1A-1, we just slurp the file at the path if it exists. Hash
        stamping + the registry-backed loader land in M1-C 1C-1/1C-2.

        Trust boundary
        --------------
        ``voice_module_path`` is **trusted-caller-only** input — it must
        never come directly from an HTTP request body. M1-A 1A-2's
        generation route will accept a *module ID* (string key) and
        translate it via the M1-C 1C-1 registry to a path rooted under
        ``prompt_modules/voice/``. Until that registry ships, callers
        in tests pass paths produced by ``tmp_path`` fixtures. If a
        future caller is tempted to forward a request-supplied path
        here, that's a path-traversal / local-file-disclosure bug —
        block it at the route layer.
        """
        if voice_module_path is None:
            return None
        path = Path(voice_module_path)
        if not path.is_file():
            # Don't raise — the issue says "placeholder until 1C-2 ships".
            # A missing file is the placeholder case.
            return (
                f"(voice module {voice_module_path!r} not found — "
                "placeholder until 1C-2 ships)"
            )
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            return (
                f"(voice module {voice_module_path!r} could not be read: "
                f"{exc} — placeholder until 1C-2 ships)"
            )
