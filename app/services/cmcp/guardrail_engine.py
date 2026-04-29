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
    >>> prompt, se_codes = engine.build_prompt(request)
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
        target_persona: str = "student",
    ) -> tuple[str, list[str]]:
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
            Hash stamping (``voice_module_hash`` artifact column) is
            1C-2's job, not this stripe's.
        target_persona:
            ``"student"`` (default), ``"parent"``, or ``"teacher"``. Other
            values raise ``ValueError`` — keeps the persona space pinned.

        Returns
        -------
        tuple[str, list[str]]
            (system_prompt, ordered list of SE ministry codes targeted).

        Raises
        ------
        ValueError
            If ``target_persona`` is not in the locked persona set.
        NoCurriculumMatchError
            If zero SE rows match the request dimensions (after optional
            topic filter).
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
        return system_prompt, se_codes

    def get_target_se_codes(self, request: GenerationRequest) -> list[str]:
        """Return the ordered SE ministry codes for the request.

        Light-additive helper introduced in M1-B 1B-3 so the route layer
        can drive the ``ClassContextResolver`` without having to call
        ``build_prompt`` first (the resolver's input (d) — teacher
        library artifacts — needs the SE list to compute overlap).

        Returns an empty list when no CEG SEs match (the route maps that
        to a 422 via the same ``NoCurriculumMatchError`` path
        ``build_prompt`` raises).
        """
        ses, _oes = self._fetch_curriculum_rows(request)
        return [se.ministry_code for se in ses]

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

        Two envelope shapes are supported, in order of preference:

        1. The M1-B 1B-2 ``ClassContextEnvelope`` shape (preferred): keys
           ``course_contents``, ``classroom_announcements``,
           ``teacher_digest_summary``, ``teacher_library_artifacts``, plus
           audit metadata (``envelope_size``, ``cited_source_count``,
           ``fallback_used``). Each populated category is rendered as a
           short bulleted excerpt under a labelled subheading so the
           downstream model can ground its output in the teacher's own
           class materials.
        2. The legacy 1A-1 stub shape: keys ``summary`` and
           ``cited_sources``. Preserved for back-compat with callers that
           pass a hand-built dict; the new resolver-fed callers should
           prefer shape 1.

        When neither shape carries content (empty envelope, or
        ``fallback_used=True`` with all four input lists empty), a stable
        placeholder string is returned so the block still appears in the
        prompt — useful as a debugging signal that a caller signalled
        intent to inject context but had nothing to inject.
        """
        if envelope is None:
            return None

        lines: list[str] = []

        # Shape 1: ClassContextEnvelope (1B-2). We probe by key presence
        # rather than by isinstance() so the engine stays decoupled from
        # the resolver's Pydantic model — callers can pass either the
        # model's ``.model_dump()`` or a dict of the same shape.
        course_contents = envelope.get("course_contents") or []
        announcements = envelope.get("classroom_announcements") or []
        digest = envelope.get("teacher_digest_summary")
        library = envelope.get("teacher_library_artifacts") or []

        if course_contents:
            lines.append("Course materials (teacher uploads):")
            for cc in course_contents:
                title = cc.get("title") or "(untitled)"
                summary = cc.get("summary") or ""
                if summary:
                    lines.append(f"- {title}: {summary}")
                else:
                    lines.append(f"- {title}")

        if announcements:
            if lines:
                lines.append("")
            lines.append("Recent classroom announcements:")
            for ann in announcements:
                creator = ann.get("creator_name") or "(unknown)"
                text = ann.get("text") or ""
                lines.append(f"- {creator}: {text}")

        if digest:
            if lines:
                lines.append("")
            count = digest.get("count", 0)
            window_days = digest.get("window_days", 30)
            lines.append(
                f"Teacher email digest (last {window_days} days, {count} items):"
            )
            for item in (digest.get("items") or []):
                subject = item.get("subject") or "(no subject)"
                ai_summary = item.get("ai_summary") or ""
                if ai_summary:
                    lines.append(f"- {subject} — {ai_summary}")
                else:
                    lines.append(f"- {subject}")

        if library:
            if lines:
                lines.append("")
            lines.append("Approved library artifacts (matching SEs):")
            for art in library:
                title = art.get("title") or "(untitled)"
                guide_type = art.get("guide_type") or "(unknown)"
                matched = art.get("matched_se_codes") or []
                lines.append(
                    f"- {title} [{guide_type}] — SEs: {', '.join(matched)}"
                )

        # Shape 2: legacy 1A-1 stub (summary + cited_sources). Only used
        # when shape 1 didn't render any content — keeps the legacy path
        # free of duplicated headings when a caller mixes shapes.
        if not lines:
            summary = envelope.get("summary") or ""
            cited = envelope.get("cited_sources") or []
            if summary:
                lines.append(f"Summary: {summary}")
            if cited:
                lines.append("Cited sources:")
                for src in cited:
                    lines.append(f"- {src}")

        if not lines:
            # Empty envelope provided — return a stable placeholder so
            # the block still appears in the prompt (caller signalled
            # intent to inject context but had nothing to inject).
            return "(envelope provided but empty — fallback to CEG-only grounding)"
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
