"""Embedding-similarity Alignment Validator for CB-CMCP-001 M3-I (#4658).

D4=B in M3 — second-pass alignment validator that uses dense-embedding
cosine similarity rather than a Claude self-report. Composes with
``AlignmentValidator`` (M1-D 1D-1) and ``ValidationPipeline`` (M1-D 1D-2)
in stripe 3I-2; this stripe (3I-1) ships only the embedding validator as
a pure service.

The validator:

1. Loads ``CEGExpectation.description`` for each declared ``se_code``
   (matching on ``ministry_code`` — the canonical SE code returned by
   ``GuardrailEngine.build_prompt``). Inactive rows and rows from prior
   curriculum versions are NOT excluded — the caller is responsible for
   passing the correct version's SE codes.
2. Splits the generated content into sections by markdown ``##`` headings
   (and ``#`` top-level headings as fallback). Empty / whitespace-only
   sections are dropped.
3. Embeds every content section + every SE description via the dev-03
   ``text-embedding-3-small`` abstraction (pattern matches
   ``cli/embed_ceg.py`` and ``app/services/help_embedding_service.py``).
4. Computes a cosine-similarity matrix; for each SE, takes the MAX
   similarity across content sections.
5. Flags any SE whose max similarity falls below ``threshold`` (default
   0.65 per #4658 spec; tunable in M4 pilot).

Returns a structured ``EmbeddingAlignmentResult`` with the per-SE scores,
the threshold, and the list of failed SEs.

This validator is INDEPENDENT — pure async function, no FastAPI
dependencies. The single OpenAI seam is ``_create_embeddings`` so tests
can mock once.
"""
from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger

# NOTE: ``CEGExpectation`` is lazy-imported inside ``_load_se_descriptions``
# rather than at module top. The conftest in tests/ reloads ``app.models``
# at session startup; binding to the model class at import time can leave
# the module holding a stale class registry where SQLAlchemy mapper
# configuration fails (e.g., ``relationship('User')`` cannot resolve).
# Lazy import matches the pattern used in ``cli/embed_ceg.py``.

logger = get_logger(__name__)

# Default cosine-similarity threshold per #4658 spec. M4 pilot may tune.
DEFAULT_THRESHOLD = 0.65

# OpenAI embedding model — must match cli/embed_ceg.py so SE embeddings
# embedded at backfill time are dimensionally compatible. We re-embed SE
# descriptions on every call here (rather than reading the stored
# pgvector column) so the validator is dialect-agnostic and so a single
# mock seam covers both content + SE embeddings.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Maximum characters of content to embed per section, to bound API spend
# on pathologically long generated artifacts. 8000 chars is well under
# the model's 8191-token context window for typical English text.
MAX_SECTION_CHARS = 8000


class EmbeddingAlignmentResult(BaseModel):
    """Structured outcome of the embedding-similarity alignment validation.

    Fields:
        passed: True iff every declared SE has at least one content section
            with cosine similarity >= ``threshold``. False if any SE falls
            below threshold OR if the inputs are degenerate (empty content,
            empty se_codes, missing CEG rows, embedding-API failure).
        scores: Map of ``se_code`` -> max cosine similarity across content
            sections, in ``[-1.0, 1.0]``. SE codes that could not be
            resolved (no matching CEG row, blank description) appear with
            score ``0.0``.
        threshold: The threshold used for this run (echoes input).
        failed_ses: SE codes whose max similarity fell below ``threshold``,
            in the original input casing.
        error: Optional human-readable failure reason. None on success.
            Populated for: empty inputs, embedding-API failure,
            unresolved SE codes.
    """

    passed: bool
    scores: dict[str, float]
    threshold: float = Field(ge=0.0, le=1.0)
    failed_ses: list[str]
    error: str | None = None


def _normalize_code(code: str) -> str:
    """Normalize an SE code for case-insensitive, whitespace-tolerant lookup.

    Mirrors ``alignment_validator._normalize_code`` so the union of matched
    codes from both validators projects onto the same canonical form.
    """
    return code.strip().upper()


def _split_into_sections(content: str) -> list[str]:
    """Split markdown content into sections by ``##`` and ``#`` headings.

    Strategy:
        - First try to split on ``##`` (level-2 headings) — typical for
          generated study guides which use a single ``#`` title and ``##``
          for each section.
        - If no ``##`` headings are present, fall back to splitting on
          ``#`` (top-level headings).
        - If still only one section, return the whole content as a single
          section. This preserves the validator's contract: there is
          always at least one section to embed when content is non-empty.

    Returns the list of section bodies (heading text included so the
    embedding captures the heading context). Empty / whitespace-only
    sections are dropped. Each section is truncated to ``MAX_SECTION_CHARS``
    to bound API spend on pathologically long inputs.
    """
    if not content or not content.strip():
        return []

    # Split on lines that start with `## ` (level-2 markdown headings).
    # Keeping the heading line as part of the following section is more
    # semantically faithful than dropping it — the heading is short but
    # carries strong topical signal for the cosine match.
    parts = re.split(r"(?m)^(?=##\s)", content)
    if len(parts) <= 1:
        # Fall back to top-level `# ` headings.
        parts = re.split(r"(?m)^(?=#\s)", content)

    sections: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        sections.append(stripped[:MAX_SECTION_CHARS])

    if not sections:
        # Defensive: content was non-empty whitespace pattern but the
        # split produced no non-blank parts. Keep the whole content as
        # one section so downstream embedding still has something to chew.
        sections = [content.strip()[:MAX_SECTION_CHARS]]

    return sections


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length float vectors.

    Returns 0.0 when either vector has zero magnitude (degenerate case
    that the OpenAI API never produces in practice but we guard against
    so a stub mock never triggers a ZeroDivisionError).
    """
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    mag_a = 0.0
    mag_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        mag_a += x * x
        mag_b += y * y
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (math.sqrt(mag_a) * math.sqrt(mag_b))


async def _create_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via the dev-03 OpenAI abstraction.

    This is the *only* place this module talks to the OpenAI SDK. Tests
    patch this function with a stub to avoid real API calls.

    Pattern matches ``cli/embed_ceg.py``: lazy-imported ``openai.AsyncOpenAI``
    configured from ``settings.openai_api_key``. We do NOT memoize the
    client here (unlike the CLI) because this validator runs inside
    long-lived FastAPI workers and a per-call client keeps the mock seam
    obvious + avoids cross-worker connection-pool surprises.

    Raises:
        RuntimeError: if ``OPENAI_API_KEY`` is unset or the API call fails.
            ``validate_embedding_alignment`` catches this and surfaces it
            as a non-passing result with ``error`` populated.
    """
    if not texts:
        return []

    import openai

    from app.core.config import settings

    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not configured — cannot create embeddings"
        )

    client = openai.AsyncOpenAI(api_key=api_key)
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [list(item.embedding) for item in response.data]


def _load_se_descriptions(
    db: Session, se_codes: list[str]
) -> dict[str, str]:
    """Return ``{normalized_se_code: description}`` for each declared SE.

    Looks up SE codes by ``ministry_code`` (the canonical form returned by
    ``GuardrailEngine.build_prompt``). Codes are matched case-insensitively
    by normalizing both the input list and the DB rows; the returned dict
    keys are the normalized form so the caller can reconcile against the
    original input casing.

    SE codes that don't resolve to a row (or that resolve to a row with a
    blank description) are simply absent from the returned dict — the
    caller surfaces those as a non-passing result.

    Note: this query does NOT filter by ``active=True`` or by curriculum
    version. The caller (e.g., the validation pipeline) is responsible
    for passing the SE codes from the version the artifact was generated
    against. M3-G adds version cascading; this stripe is independent.
    """
    if not se_codes:
        return {}

    # Lazy-imported (see module-level note) so the model class is taken
    # from the live registry, not a stale one bound at module load time.
    from app.models.curriculum import CEGExpectation

    normalized = [_normalize_code(c) for c in se_codes]
    # Use SQL-side UPPER for the WHERE so the lookup is index-friendly on
    # PG (functional index can be added later) and case-insensitive on
    # SQLite where the column has no case-insensitive collation.
    from sqlalchemy import func as sql_func

    rows: list[CEGExpectation] = (
        db.query(CEGExpectation)
        .filter(sql_func.upper(CEGExpectation.ministry_code).in_(normalized))
        .all()
    )

    result: dict[str, str] = {}
    for row in rows:
        norm = _normalize_code(row.ministry_code)
        desc = (row.description or "").strip()
        if desc:
            result[norm] = desc
    return result


async def validate_embedding_alignment(
    content: str,
    se_codes: list[str],
    db: Session,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Validate that ``content`` aligns with each declared ``se_code`` via
    embedding cosine similarity.

    Args:
        content: The generated artifact text. Split into sections by
            markdown ``##`` (or ``#``) headings.
        se_codes: Declared SE ministry codes (e.g.,
            ``["MTH1W-B2.3", "MTH1W-B2.4"]``).
        db: SQLAlchemy session — used to load
            ``CEGExpectation.description`` for each declared SE.
        threshold: Cosine similarity threshold below which an SE is
            considered uncovered. Default ``0.65`` per #4658 spec.

    Returns:
        A dict matching the ``EmbeddingAlignmentResult`` schema:
        ``{passed: bool, scores: dict[str, float], threshold: float,
        failed_ses: list[str], error: str | None}``.

        Returned as a plain dict (not the Pydantic model) so callers in
        3I-2 can compose with ``ValidationPipeline`` results without an
        intermediate model conversion. Construct an
        ``EmbeddingAlignmentResult`` from the dict if a typed object is
        needed.

    Behaviour on degenerate inputs:
        - Empty / whitespace-only ``content`` → ``passed=False``,
          ``failed_ses`` = all input codes, ``error`` populated.
        - Empty ``se_codes`` → ``passed=False``, ``failed_ses=[]``,
          ``error`` populated.
        - SE codes that do not resolve to a CEG row or whose description
          is blank → score ``0.0``, included in ``failed_ses``,
          ``error`` populated to flag the missing-row condition.
        - Embedding API failure → ``passed=False``,
          ``failed_ses`` = all input codes, ``error`` populated. Never
          raises out of this function.
    """
    # ----- Input validation -----------------------------------------------
    if not se_codes:
        return EmbeddingAlignmentResult(
            passed=False,
            scores={},
            threshold=threshold,
            failed_ses=[],
            error="no se_codes provided",
        ).model_dump()

    if not content or not content.strip():
        return EmbeddingAlignmentResult(
            passed=False,
            scores={code: 0.0 for code in se_codes},
            threshold=threshold,
            failed_ses=list(se_codes),
            error="empty content",
        ).model_dump()

    # ----- Section splitting ---------------------------------------------
    sections = _split_into_sections(content)
    if not sections:
        # Defensive: _split_into_sections guarantees a non-empty list
        # when content is non-empty, but the explicit check makes the
        # contract obvious to readers.
        return EmbeddingAlignmentResult(
            passed=False,
            scores={code: 0.0 for code in se_codes},
            threshold=threshold,
            failed_ses=list(se_codes),
            error="empty content",
        ).model_dump()

    # ----- SE description lookup -----------------------------------------
    se_descriptions = _load_se_descriptions(db, se_codes)
    # Track which input codes resolved to a description (preserve input
    # casing in the output). ``unresolved`` codes get score 0.0 and
    # always appear in ``failed_ses``.
    resolved: list[tuple[str, str]] = []  # (original_code, description)
    unresolved: list[str] = []
    for code in se_codes:
        norm = _normalize_code(code)
        desc = se_descriptions.get(norm)
        if desc:
            resolved.append((code, desc))
        else:
            unresolved.append(code)

    if not resolved:
        # Every declared SE failed to resolve — no point calling OpenAI.
        return EmbeddingAlignmentResult(
            passed=False,
            scores={code: 0.0 for code in se_codes},
            threshold=threshold,
            failed_ses=list(se_codes),
            error=(
                "no SE descriptions resolved from db "
                f"(unresolved={unresolved})"
            ),
        ).model_dump()

    # ----- Embedding -----------------------------------------------------
    # Embed sections + SE descriptions in a single batched call to the
    # OpenAI API. Order matters: sections first, then SE descriptions in
    # the order of ``resolved``. This lets us slice the result back into
    # two arrays without a second round-trip.
    se_texts = [desc for _code, desc in resolved]
    all_texts = sections + se_texts

    try:
        embeddings = await _create_embeddings(all_texts)
    except Exception as e:  # noqa: BLE001 — fail-safe: never raise out
        logger.warning(
            "EmbeddingAlignmentValidator: embedding API call failed: %s", e
        )
        return EmbeddingAlignmentResult(
            passed=False,
            scores={code: 0.0 for code in se_codes},
            threshold=threshold,
            failed_ses=list(se_codes),
            error=f"embedding_error: {type(e).__name__}: {e}",
        ).model_dump()

    if len(embeddings) != len(all_texts):
        logger.warning(
            "EmbeddingAlignmentValidator: embedding count mismatch "
            "(got %d, expected %d)",
            len(embeddings), len(all_texts),
        )
        return EmbeddingAlignmentResult(
            passed=False,
            scores={code: 0.0 for code in se_codes},
            threshold=threshold,
            failed_ses=list(se_codes),
            error=(
                f"embedding_count_mismatch: got {len(embeddings)}, "
                f"expected {len(all_texts)}"
            ),
        ).model_dump()

    section_embs = embeddings[: len(sections)]
    se_embs = embeddings[len(sections):]

    # ----- Cosine similarity matrix -------------------------------------
    # For each resolved SE, take the MAX similarity across content
    # sections. An SE counts as covered when at least one section
    # discusses its expectation closely enough.
    scores: dict[str, float] = {}
    for (code, _desc), se_emb in zip(resolved, se_embs):
        max_sim = max(
            (_cosine_similarity(sec_emb, se_emb) for sec_emb in section_embs),
            default=0.0,
        )
        scores[code] = max_sim

    # Unresolved SEs already score 0.0.
    for code in unresolved:
        scores[code] = 0.0

    # ----- Threshold check ----------------------------------------------
    failed_ses: list[str] = [
        code for code in se_codes if scores.get(code, 0.0) < threshold
    ]
    passed = not failed_ses

    error: str | None = None
    if unresolved:
        # Even when other SEs pass, surface unresolved codes so callers
        # know the result is partial. ``passed`` is already False because
        # unresolved codes scored 0.0 < threshold.
        error = f"unresolved_se_codes: {unresolved}"

    logger.info(
        "EmbeddingAlignmentValidator: ses=%d sections=%d threshold=%.2f "
        "passed=%s failed=%d unresolved=%d",
        len(se_codes), len(sections), threshold,
        passed, len(failed_ses), len(unresolved),
    )

    return EmbeddingAlignmentResult(
        passed=passed,
        scores=scores,
        threshold=threshold,
        failed_ses=failed_ses,
        error=error,
    ).model_dump()
