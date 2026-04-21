"""Demo-specific rate limit, cost cap, and input validation helpers (CB-DEMO-001, #3605).

Implements PRD FR-050..FR-055 on top of the `demo_sessions` table:

- FR-050: max 3 successful generations per email / 24h
- FR-051: max 10 successful generations per IP  / 24h
- FR-052: reject input texts longer than 500 words
- FR-053: daily global cost cap ($10 CAD = 1000 cents)
- FR-055: append generation events to demo_sessions.generations_json

Counts are computed from the `generations_json` column (JSONB on PG,
JSON/text on SQLite) — this is the single source of truth for
successful generations so we do not need a separate events table.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.demo_session import DemoSession
from app.schemas.demo import _DEMO_PERSISTED_CONTENT_MAX_CHARS, DemoGenerateEvent

logger = get_logger(__name__)


# ── Limits (PRD FR-050..FR-053) ──────────────────────────────────────
EMAIL_DAILY_LIMIT = 3
IP_DAILY_LIMIT = 10
DAILY_COST_CAP_CENTS = 1000  # $10 CAD
MAX_INPUT_WORDS = 500

WINDOW = timedelta(hours=24)

# Columns that `_count_generations_since` is allowed to filter by.
# Gated explicitly because the column name is interpolated into raw SQL
# via f-string below — any future caller passing user input without this
# whitelist would create a SQL injection vector.
_COUNTABLE_COLUMNS: frozenset[str] = frozenset({"email_hash", "source_ip_hash"})


def _is_pg() -> bool:
    return "sqlite" not in settings.database_url


def _window_start() -> datetime:
    return datetime.now(timezone.utc) - WINDOW


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


# ── Shared counting helpers ──────────────────────────────────────────


def _count_generations_since(
    db: Session,
    *,
    column: str,
    value: str,
    since: datetime,
) -> int:
    """Sum the length of `generations_json` entries with `created_at >= since`
    for demo_sessions where `column = value`.

    Uses JSONB `jsonb_array_elements` on PG and `json_each` on SQLite so
    we never load full rows into Python memory.
    """
    if column not in _COUNTABLE_COLUMNS:
        raise ValueError(
            f"column must be one of {sorted(_COUNTABLE_COLUMNS)}, got {column!r}"
        )
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S")
    if _is_pg():
        sql = text(
            f"""
            SELECT COUNT(*) AS n
            FROM demo_sessions ds,
                 jsonb_array_elements(COALESCE(ds.generations_json, '[]'::jsonb)) AS g
            WHERE ds.{column} = :value
              AND (g->>'created_at')::timestamptz >= :since
            """
        )
        row = db.execute(sql, {"value": value, "since": since}).first()
    else:
        sql = text(
            f"""
            SELECT COUNT(*) AS n
            FROM demo_sessions ds,
                 json_each(COALESCE(ds.generations_json, '[]')) AS g
            WHERE ds.{column} = :value
              AND json_extract(g.value, '$.created_at') >= :since
            """
        )
        row = db.execute(sql, {"value": value, "since": since_iso}).first()
    if row is None:
        return 0
    return int(row[0] or 0)


def _sum_cost_cents_since(db: Session, *, since: datetime) -> int:
    """Return SUM(cost_cents) across all demo_sessions.generations_json
    entries with `created_at >= since`.
    """
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S")
    if _is_pg():
        sql = text(
            """
            SELECT COALESCE(SUM((g->>'cost_cents')::int), 0) AS total
            FROM demo_sessions ds,
                 jsonb_array_elements(COALESCE(ds.generations_json, '[]'::jsonb)) AS g
            WHERE (g->>'created_at')::timestamptz >= :since
            """
        )
        row = db.execute(sql, {"since": since}).first()
    else:
        sql = text(
            """
            SELECT COALESCE(SUM(CAST(json_extract(g.value, '$.cost_cents') AS INTEGER)), 0) AS total
            FROM demo_sessions ds,
                 json_each(COALESCE(ds.generations_json, '[]')) AS g
            WHERE json_extract(g.value, '$.created_at') >= :since
            """
        )
        row = db.execute(sql, {"since": since_iso}).first()
    if row is None:
        return 0
    return int(row[0] or 0)


# ── Public checks ────────────────────────────────────────────────────


def check_email_rate_limit(db: Session, email_hash: str) -> tuple[bool, str]:
    """FR-050: max 3 successful generations per email per 24h."""
    count = _count_generations_since(
        db, column="email_hash", value=email_hash, since=_window_start()
    )
    if count >= EMAIL_DAILY_LIMIT:
        return (
            False,
            "You've reached the daily demo limit for this email. Try again tomorrow.",
        )
    return True, ""


def check_ip_rate_limit(db: Session, ip_hash: str) -> tuple[bool, str]:
    """FR-051: max 10 successful generations per IP per 24h."""
    count = _count_generations_since(
        db, column="source_ip_hash", value=ip_hash, since=_window_start()
    )
    if count >= IP_DAILY_LIMIT:
        return (
            False,
            "Too many demo requests from your network. Try again tomorrow.",
        )
    return True, ""


def check_daily_cost_cap(db: Session) -> tuple[bool, str]:
    """FR-053: global daily cost cap of $10 CAD (1000 cents).

    Sums `cost_cents` from all generations_json entries created today
    (UTC) across every demo_session row.
    """
    total = _sum_cost_cents_since(db, since=_today_start())
    if total >= DAILY_COST_CAP_CENTS:
        return False, "Demo is warming up — try again in an hour."
    return True, ""


def check_input_word_count(text: Optional[str]) -> tuple[bool, str]:
    """FR-052: reject inputs with more than 500 words. Empty/None allowed."""
    if not text:
        return True, ""
    words = text.split()
    if len(words) > MAX_INPUT_WORDS:
        return (
            False,
            f"Input is too long ({len(words)} words). The demo accepts up to {MAX_INPUT_WORDS} words.",
        )
    return True, ""


# ── Recording ────────────────────────────────────────────────────────


def _coerce_generations_list(existing) -> list:
    """Normalise `generations_json` to a mutable list (handles None / SQLite str)."""
    if existing is None:
        return []
    if isinstance(existing, str):
        try:
            return list(json.loads(existing))
        except json.JSONDecodeError:
            return []
    return list(existing)


def record_generation(
    db: Session,
    session: DemoSession,
    *,
    demo_type: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cost_cents: int,
) -> DemoGenerateEvent:
    """Append a DemoGenerateEvent to `session.generations_json` and commit.

    DEPRECATED for the main /generate path (race-prone because it writes
    AFTER the stream completes — see #3666). Kept as a fallback and for
    tests that seed generations directly. New code should use
    ``reserve_generation_slot`` BEFORE streaming and
    ``update_generation_slot`` AFTER streaming.

    Also increments `session.generations_count`. Returns the event model
    so callers can surface it in the API response.
    """
    event = DemoGenerateEvent(
        demo_type=demo_type,  # type: ignore[arg-type]
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_cents=cost_cents,
        created_at=datetime.now(timezone.utc),
    )
    # Pydantic v2 — use mode='json' so datetime serialises to ISO string
    # that matches the shape produced by the API and our SQL predicates.
    event_dict = event.model_dump(mode="json")

    existing_list = _coerce_generations_list(session.generations_json)
    existing_list.append(event_dict)
    session.generations_json = existing_list
    session.generations_count = (session.generations_count or 0) + 1

    db.add(session)
    db.commit()
    db.refresh(session)
    return event


# ── Slot reservation (race-safe, #3666) ──────────────────────────────


def reserve_generation_slot(
    db: Session,
    session: DemoSession,
    *,
    demo_type: str,
    user_content: Optional[str] = None,
) -> DemoGenerateEvent:
    """Reserve a slot in `generations_json` BEFORE streaming starts.

    Writes a placeholder row with zero metrics and increments
    `generations_count`, so a concurrent request sees the updated count
    immediately (closes the rate-limit race where both requests read the
    same stale count before either has recorded its generation).

    The stream generator must call ``update_generation_slot`` afterwards
    to fill in real latency / token / cost values. If the stream fails,
    the placeholder row still counts toward the user's rate limit — this
    is intentional defensive cost accounting (FR-050/051).

    ``user_content`` (#3819) — for Ask turns we capture the user question
    immediately so that even if the stream fails midway the user side of
    the turn is persisted. Truncated to ``_DEMO_PERSISTED_CONTENT_MAX_CHARS``
    (see `app.schemas.demo` for cap rationale).
    """
    placeholder = DemoGenerateEvent(
        demo_type=demo_type,  # type: ignore[arg-type]
        latency_ms=0,
        input_tokens=0,
        output_tokens=0,
        cost_cents=0,
        created_at=datetime.now(timezone.utc),
        user_content=(
            user_content[:_DEMO_PERSISTED_CONTENT_MAX_CHARS]
            if user_content else None
        ),
    )
    event_dict = placeholder.model_dump(mode="json")

    existing_list = _coerce_generations_list(session.generations_json)
    existing_list.append(event_dict)
    session.generations_json = existing_list
    session.generations_count = (session.generations_count or 0) + 1

    db.add(session)
    db.commit()
    db.refresh(session)
    return placeholder


def update_generation_slot(
    db: Session,
    session: DemoSession,
    *,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cost_cents: int,
    assistant_content: Optional[str] = None,
) -> None:
    """UPDATE the most recent `generations_json` entry with real metrics.

    Complements ``reserve_generation_slot`` — called after the SSE stream
    finishes successfully to fill in actual latency / tokens / cost. No-op
    if the session has no generations (defensive).

    ``assistant_content`` (#3819) — for Ask turns we persist the final
    assistant reply (truncated to ``_DEMO_PERSISTED_CONTENT_MAX_CHARS``)
    so subsequent turns can be reconstructed server-side without trusting
    any client-supplied ``assistant`` history entries. Non-Ask demo types
    pass ``None``. See `app.schemas.demo` for cap rationale.
    """
    existing_list = _coerce_generations_list(session.generations_json)
    if not existing_list:
        return  # defensive — nothing to update
    # Build a fresh list of fresh dicts so SQLAlchemy's change detection
    # flags the column as dirty (the default JSON type only compares by
    # value equality — mutating a nested dict in place is NOT seen).
    updated = [dict(entry) for entry in existing_list]
    updated[-1]["latency_ms"] = latency_ms
    updated[-1]["input_tokens"] = input_tokens
    updated[-1]["output_tokens"] = output_tokens
    updated[-1]["cost_cents"] = cost_cents
    if assistant_content is not None:
        updated[-1]["assistant_content"] = (
            assistant_content[:_DEMO_PERSISTED_CONTENT_MAX_CHARS]
        )
    session.generations_json = updated

    db.add(session)
    db.commit()
    db.refresh(session)
