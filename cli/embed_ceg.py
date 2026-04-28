"""Embedding-backfill CLI for the Curriculum Expectations Graph (CB-CMCP-001 0B-4).

Backfills OpenAI ``text-embedding-3-small`` vectors onto ``CEGExpectation``
rows where ``embedding IS NULL``. The CLI is:

- Idempotent — re-running skips rows that already have an embedding.
- Rate-limited — minimum throttle between requests so we never burst the
  OpenAI rate limit (configurable via ``--min-interval-ms``; default 100ms
  ≈ 10 req/sec).
- Scoped — optional ``--grade`` / ``--subject`` filters narrow the run to
  one slice (handy for re-running just one batch after extraction).
- Dry-run capable — ``--dry-run`` reports what would be embedded without
  making a single API call or writing to the DB.
- Progress-logged — emits ``logging`` records every row processed and on
  every API failure (with retry/backoff diagnostics).

Per CB-CMCP-001 0B-4 acceptance: this CLI uses the dev-03 OpenAI
abstraction (a single internal helper that routes through ``openai.AsyncOpenAI``
configured via ``app.core.config.settings.openai_api_key``) — *never* a
direct SDK call scattered through the orchestration code. Tests mock that
single helper, so no real API calls happen in CI.

Usage (from repo root):

    # Embed everything that's missing:
    python cli/embed_ceg.py

    # Dry-run (no API calls, no writes):
    python cli/embed_ceg.py --dry-run

    # Cap at 50 rows this run:
    python cli/embed_ceg.py --limit 50

    # Scope to Grade 7 Math:
    python cli/embed_ceg.py --grade 7 --subject MATH

Exit codes:
    0  success
    1  generic / unexpected error
    2  argparse error (handled by argparse itself)
    3  OpenAI API error after retries are exhausted
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure the repo root is on sys.path so we can import `app.*` when this
# file is invoked directly as `python cli/embed_ceg.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("cli.embed_ceg")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Rate-limit defaults: 100ms between requests ≈ 10 req/sec, well under the
# tier-1 OpenAI embeddings limit (3,000 RPM = 50 req/sec).
DEFAULT_MIN_INTERVAL_MS = 100

# Per-row API retry policy on transient OpenAI errors.
MAX_API_RETRIES = 3
RETRY_BACKOFF_BASE_S = 1.0  # 1s, 2s, 4s exponential backoff

# Exit codes (per stripe spec).
EXIT_OK = 0
EXIT_GENERIC_ERROR = 1
EXIT_OPENAI_ERROR = 3


# ---------------------------------------------------------------------------
# Custom errors
# ---------------------------------------------------------------------------


class EmbeddingAPIError(RuntimeError):
    """Raised when the OpenAI embedding API fails after all retries."""


class MalformedExpectationError(ValueError):
    """Raised when an expectation row cannot be embedded due to bad text."""


# ---------------------------------------------------------------------------
# OpenAI abstraction (single helper — tests mock this one function)
# ---------------------------------------------------------------------------


async def _create_embedding(text: str) -> list[float]:
    """Create a single embedding via the dev-03 OpenAI abstraction.

    This is the *only* place the CLI talks to the OpenAI SDK. Every call
    site in this module routes through this helper so tests have one
    seam to mock and there are no scattered direct SDK calls.

    Pattern matches the existing dev-03 embedding services
    (``app/services/help_embedding_service.py`` and
    ``app/services/intent_embedding_service.py``):
    lazy-imported ``openai.AsyncOpenAI`` configured from
    ``settings.openai_api_key``.

    Raises:
        MalformedExpectationError: if ``text`` is empty or non-string.
        EmbeddingAPIError: if the API call fails after retries (caller
            wraps the OpenAI exception).
    """
    if not isinstance(text, str) or not text.strip():
        raise MalformedExpectationError(
            f"Expectation text must be a non-empty string; got {type(text).__name__!r}"
        )

    # Lazy import keeps the openai package out of the module-load path so
    # unit tests that monkeypatch this helper never instantiate a real
    # client. Also matches the ``help_embedding_service.py`` pattern.
    import openai

    from app.core.config import settings

    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise EmbeddingAPIError(
            "OPENAI_API_KEY not configured — cannot create embeddings"
        )

    client = openai.AsyncOpenAI(api_key=api_key)
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text],
    )
    return list(response.data[0].embedding)


# ---------------------------------------------------------------------------
# Embedding writeback (dialect-aware: pgvector on PG, JSON list on SQLite)
# ---------------------------------------------------------------------------


def _is_postgres() -> bool:
    """True iff configured ``database_url`` is PostgreSQL.

    The model layer in ``app/models/curriculum.py`` has the same gate; we
    re-evaluate here so the CLI's behaviour matches whatever DB the
    process is currently pointed at (settings reload via env vars works
    on a fresh CLI invocation).
    """
    from app.core.config import settings

    return "sqlite" not in settings.database_url


def _persist_embedding(row: Any, vector: list[float]) -> None:
    """Write a 1536-dim ``vector`` back to the row's ``embedding`` column.

    On PG the column is a pgvector ``vector(1536)`` — the SQLAlchemy
    pgvector binding accepts a Python list of floats and serialises it
    server-side, so the assignment is identical on both dialects from
    Python's perspective. We keep this helper as a single seam so any
    future dialect-specific encoding (e.g., binary protocol for big
    rows) lives in one place.
    """
    if len(vector) != EMBEDDING_DIM:
        raise EmbeddingAPIError(
            f"Embedding length {len(vector)} != expected {EMBEDDING_DIM}"
        )
    row.embedding = vector


# ---------------------------------------------------------------------------
# Query: rows missing an embedding
# ---------------------------------------------------------------------------


def _query_pending_rows(
    db_session: Any,
    *,
    grade: int | None,
    subject: str | None,
    limit: int | None,
) -> list[Any]:
    """Return the list of ``CEGExpectation`` rows that need embeddings.

    Filters:
        - ``embedding`` is unset (idempotency — already-embedded rows are skipped)
        - optional ``--grade`` filter
        - optional ``--subject`` code filter (joined via ``CEGSubject.code``)
        - optional ``--limit`` cap

    Result ordering is by id (stable so re-runs visit rows deterministically).

    Dialect note: on PostgreSQL the ``embedding`` column is a pgvector
    ``vector(1536)`` and unset values are stored as SQL ``NULL``. On SQLite
    the column is a SQLAlchemy ``JSON`` and unset values are stored as the
    JSON literal ``'null'`` (string), NOT SQL ``NULL``. A plain ``IS NULL``
    filter therefore misses unset rows on SQLite. We over-fetch the candidate
    set (filter only by --grade / --subject / --limit at SQL) and apply the
    "needs embedding" gate in Python, which works identically on both
    dialects.
    """
    # Lazy import: avoid pulling SQLAlchemy / models at CLI startup. Also
    # keeps a clean mock seam if downstream tests want to swap the model.
    from app.models.curriculum import CEGExpectation, CEGSubject

    query = db_session.query(CEGExpectation)

    if grade is not None:
        query = query.filter(CEGExpectation.grade == grade)

    if subject is not None:
        query = query.join(
            CEGSubject, CEGSubject.id == CEGExpectation.subject_id
        ).filter(CEGSubject.code == subject)

    query = query.order_by(CEGExpectation.id.asc())

    candidates = query.all()
    pending = [row for row in candidates if _needs_embedding(row.embedding)]
    if limit is not None:
        pending = pending[:limit]
    return pending


def _needs_embedding(value: Any) -> bool:
    """True iff the column value indicates "no embedding yet".

    Handles both PG (SQL NULL → Python None) and SQLite-JSON (which stores
    Python None as the JSON literal ``'null'`` string in some setups, plus
    the genuinely-unset SQL NULL when the row was inserted before the
    JSON serializer ran). We treat an empty list as "no embedding" too —
    an empty 1536-dim vector is meaningless.
    """
    if value is None:
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Rate-limit helper
# ---------------------------------------------------------------------------


async def _throttle(last_call_ts: float, min_interval_s: float) -> float:
    """Sleep just enough to honour ``min_interval_s`` between API calls.

    Returns the timestamp of the next call (i.e., ``time.monotonic()`` after
    the sleep) so callers can chain ``last_call_ts = await _throttle(...)``.
    """
    if last_call_ts == 0.0:
        return time.monotonic()
    elapsed = time.monotonic() - last_call_ts
    remaining = min_interval_s - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)
    return time.monotonic()


# ---------------------------------------------------------------------------
# Per-row embed-with-retry wrapper
# ---------------------------------------------------------------------------


async def _embed_with_retry(text: str) -> list[float]:
    """Call ``_create_embedding`` with exponential-backoff retry.

    Retries on any exception that isn't ``MalformedExpectationError``
    (caller-side bad input — re-raise immediately). After
    ``MAX_API_RETRIES`` attempts, wraps the last exception in
    ``EmbeddingAPIError``.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            return await _create_embedding(text)
        except MalformedExpectationError:
            # Bad text — no point retrying.
            raise
        except Exception as exc:  # noqa: BLE001 — surface any API failure
            last_exc = exc
            if attempt >= MAX_API_RETRIES:
                break
            backoff = RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
            logger.warning(
                "OpenAI embedding call failed (attempt %d/%d): %s — "
                "retrying in %.1fs",
                attempt,
                MAX_API_RETRIES,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)
    raise EmbeddingAPIError(
        f"OpenAI embedding API failed after {MAX_API_RETRIES} attempts: {last_exc}"
    ) from last_exc


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def backfill_embeddings(
    db_session: Any,
    *,
    grade: int | None,
    subject: str | None,
    limit: int | None,
    dry_run: bool,
    min_interval_s: float,
) -> dict[str, int]:
    """Run the backfill loop. Returns a stats dict.

    Stats keys:
        ``found`` — total rows matching the filter that need embeddings
        ``embedded`` — rows successfully embedded + persisted
        ``skipped_malformed`` — rows skipped due to malformed text
        ``failed`` — rows that hit the OpenAI retry cap (only meaningful
            when the caller chooses to continue past failures; current
            behaviour is to raise on the first hard failure)
    """
    rows = _query_pending_rows(
        db_session, grade=grade, subject=subject, limit=limit
    )
    total = len(rows)
    logger.info(
        "Found %d expectation row(s) needing embeddings (grade=%s subject=%s limit=%s).",
        total,
        grade if grade is not None else "*",
        subject if subject is not None else "*",
        limit if limit is not None else "*",
    )

    if dry_run:
        logger.info("--dry-run: no API calls and no DB writes will be made.")
        for row in rows:
            logger.info(
                "[dry-run] would embed id=%s ministry_code=%s grade=%s",
                row.id,
                getattr(row, "ministry_code", "?"),
                getattr(row, "grade", "?"),
            )
        return {
            "found": total,
            "embedded": 0,
            "skipped_malformed": 0,
            "failed": 0,
        }

    embedded = 0
    skipped_malformed = 0
    last_call_ts = 0.0

    for idx, row in enumerate(rows, start=1):
        text = getattr(row, "description", None)
        try:
            last_call_ts = await _throttle(last_call_ts, min_interval_s)
            vector = await _embed_with_retry(text or "")
            _persist_embedding(row, vector)
            db_session.commit()
            embedded += 1
            logger.info(
                "[%d/%d] embedded id=%s ministry_code=%s",
                idx,
                total,
                row.id,
                getattr(row, "ministry_code", "?"),
            )
        except MalformedExpectationError as exc:
            db_session.rollback()
            skipped_malformed += 1
            logger.warning(
                "[%d/%d] SKIP id=%s — malformed expectation_text: %s",
                idx,
                total,
                row.id,
                exc,
            )
            continue
        except EmbeddingAPIError:
            db_session.rollback()
            raise

    logger.info(
        "Backfill complete: found=%d embedded=%d skipped_malformed=%d",
        total,
        embedded,
        skipped_malformed,
    )
    return {
        "found": total,
        "embedded": embedded,
        "skipped_malformed": skipped_malformed,
        "failed": 0,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="embed_ceg",
        description=(
            "Backfill OpenAI text-embedding-3-small vectors onto "
            "CEGExpectation rows where embedding IS NULL "
            "(CB-CMCP-001 stripe 0B-4)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be embedded without making API calls or writes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Embed at most N rows this run (default: no cap).",
    )
    parser.add_argument(
        "--grade",
        type=int,
        default=None,
        help="Scope to a single grade (1-12). Combined with --subject if given.",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="Scope to a single subject code (e.g., MATH). Combined with --grade if given.",
    )
    parser.add_argument(
        "--min-interval-ms",
        type=int,
        default=DEFAULT_MIN_INTERVAL_MS,
        help=(
            f"Minimum delay between OpenAI calls in ms "
            f"(default: {DEFAULT_MIN_INTERVAL_MS}ms ≈ 10 req/sec)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose (DEBUG) logging.",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    """Validate user-supplied flag combinations. Raises ValueError on bad input."""
    if args.grade is not None and not (1 <= args.grade <= 12):
        raise ValueError(
            f"--grade must be between 1 and 12, got {args.grade}"
        )
    if args.limit is not None and args.limit <= 0:
        raise ValueError(f"--limit must be positive, got {args.limit}")
    if args.min_interval_ms < 0:
        raise ValueError(
            f"--min-interval-ms must be >= 0, got {args.min_interval_ms}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        _validate_args(args)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_GENERIC_ERROR

    # Lazy DB import — keeps CLI import lightweight and lets tests inject
    # a mock session via ``backfill_embeddings`` directly.
    from app.db.database import SessionLocal

    db_session = SessionLocal()
    try:
        stats = asyncio.run(
            backfill_embeddings(
                db_session,
                grade=args.grade,
                subject=args.subject,
                limit=args.limit,
                dry_run=args.dry_run,
                min_interval_s=args.min_interval_ms / 1000.0,
            )
        )
    except EmbeddingAPIError as e:
        print(f"ERROR: OpenAI API failure: {e}", file=sys.stderr)
        return EXIT_OPENAI_ERROR
    except Exception as e:  # noqa: BLE001 — top-level safety net
        print(
            f"ERROR: Unexpected failure: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return EXIT_GENERIC_ERROR
    finally:
        db_session.close()

    print(
        f"embed_ceg: found={stats['found']} embedded={stats['embedded']} "
        f"skipped_malformed={stats['skipped_malformed']}"
        + (" [dry-run]" if args.dry_run else "")
    )
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
