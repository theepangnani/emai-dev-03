"""CB-DCI-001 M0-6 — daily check-in summary generator.

Produces the parent-facing evening summary for one kid on one date:
  * up to 5 subject bullets,
  * deadlines surfaced from today's artifacts,
  * one italic-friendly conversation starter (≤ 25 words) anchored to a
    specific artifact (voice sentiment or photo topic).

Design notes (see `docs/design/CB-DCI-001-daily-checkin.md` § 8 + § 9):
  * Model: Claude Sonnet 4.6 (`claude-sonnet-4-6`). Prompt caching enabled
    on the 7-day-context block (5-min TTL) so day-over-day calls hit the
    cache and stay under the $0.02/family/day target.
  * Opus 4.7 fallback: a single env flag (`DCI_SUMMARY_MODEL_OVERRIDE`)
    swaps the model — no code branching.
  * Idempotent: re-runs REPLACE the existing `ai_summaries` row for the
    (kid_id, summary_date) UNIQUE pair, then write a fresh
    `conversation_starters` row.
  * Cost: target ≤ $0.02/family/day; the service emits a structured
    log warning above $0.05 so the M0 telemetry job can alert.
  * Provenance (NFR5): writes `model_version`, `prompt_hash`, and
    `input_hashes` to `audit_event` (we use the existing `audit_logs`
    table via `audit_service.log_action` until M0-2's dedicated
    `audit_event` ships).
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.ai_service import (
    _calc_cost,
    _last_ai_usage,
    get_anthropic_client,
)
from app.services.audit_service import log_action
from app.services.dci_prompts import (
    DCI_SUMMARY_SYSTEM_PROMPT,
    DCI_SUMMARY_TOOL_SCHEMA,
    build_context_block,
    build_today_block,
    stable_json,
)

logger = get_logger(__name__)

# Default model. The override env var (`DCI_SUMMARY_MODEL_OVERRIDE`) is
# resolved at *call* time, not import time, so test fixtures can monkey-
# patch `settings` without re-importing the module.
DCI_SUMMARY_MODEL_DEFAULT = "claude-sonnet-4-6"

# Cost guard — see § 13 "Cost ceiling" in design doc.
DCI_COST_TARGET_USD = 0.02
DCI_COST_ALERT_USD = 0.05

# Token cap for the summary call. Sonnet 4.6 emits the structured tool
# call comfortably under 800 tokens; cap at 1024 for safety headroom.
DCI_SUMMARY_MAX_TOKENS = 1024


def _resolve_model() -> str:
    """Pick the effective model — env override wins, default is Sonnet 4.6."""
    override = settings.dci_summary_model_override
    if override:
        return override.strip()
    return DCI_SUMMARY_MODEL_DEFAULT


def _hash_str(s: str) -> str:
    """SHA-256 hex digest, used for prompt + input provenance hashes."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _extract_summary_payload(message: Any) -> dict[str, Any]:
    """Pull the `emit_daily_summary` tool_use input out of a Claude reply.

    Raises ValueError if the model returned no tool_use block — at which
    point the caller decides whether to retry or fail open with an empty
    summary. Sonnet under forced ``tool_choice`` should never hit this
    branch in practice.
    """
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "tool_use":
            # Use getattr (not `block.input or {}`) so a missing/None
            # `input` field surfaces as a hard error instead of silently
            # producing an empty summary — that path masks SDK regressions
            # and would write a meaningless row to ai_summaries.
            payload = getattr(block, "input", None)
            if payload is None:
                raise ValueError(
                    "DCI summary: tool_use block missing `input` field"
                )
            if not isinstance(payload, dict):
                raise ValueError(
                    "DCI summary: tool_use input is "
                    f"{type(payload).__name__}, expected dict"
                )
            return payload
    raise ValueError("DCI summary: no tool_use block in Claude response")


def _normalise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Defensive cleanup of the model's structured output.

    The tool schema enforces the shape, but we still:
      * coerce missing arrays to []
      * trim conversation starter text to ≤ 25 words (hard cap)
      * default tone to 'curious' if missing
    """
    subjects = payload.get("subjects") or []
    if not isinstance(subjects, list):
        subjects = []
    deadlines = payload.get("deadlines") or []
    if not isinstance(deadlines, list):
        deadlines = []

    starter = payload.get("conversation_starter") or {}
    if not isinstance(starter, dict):
        starter = {}
    text = str(starter.get("text") or "").strip()
    tone = str(starter.get("tone") or "curious").strip() or "curious"

    # Hard 25-word cap — design doc § 8 + acceptance criterion.
    words = text.split()
    if len(words) > 25:
        text = " ".join(words[:25])

    return {
        "subjects": [
            {"name": str(s.get("name", "")).strip()[:50],
             "bullet": str(s.get("bullet", "")).strip()[:240]}
            for s in subjects
            if isinstance(s, dict) and s.get("name") and s.get("bullet")
        ],
        "deadlines": [
            {
                "date": str(d.get("date", "")).strip(),
                "label": str(d.get("label", "")).strip()[:140],
                "source": str(d.get("source", "")).strip(),
            }
            for d in deadlines
            if isinstance(d, dict) and d.get("date") and d.get("label")
        ],
        "conversation_starter": {"text": text, "tone": tone},
    }


def _persist_summary(
    db: Session | None,
    *,
    kid_id: int,
    summary_date: str,
    payload: dict[str, Any],
    model_version: str,
    prompt_hash: str,
) -> tuple[int | None, int | None]:
    """Idempotent write of `ai_summaries` + `conversation_starters`.

    Re-runs REPLACE the existing summary row for (kid_id, summary_date).
    Returns (summary_id, starter_id) — both may be ``None`` when running
    against a DB that doesn't yet have these tables (M0-2 owns the
    schema; until then runtime calls still attempt the writes per
    design § 10 ORM signature, but tests mock the session).
    """
    if db is None:
        return None, None

    # Lazy import: M0-2 will land the ORM models. Keeping the import
    # inside the function lets this service load cleanly even when the
    # models aren't on disk yet.
    try:
        from app.models.dci import AiSummary, ConversationStarter  # type: ignore
    except Exception as exc:  # pragma: no cover — M0-2 not yet merged
        logger.info(
            "DCI summary persist skipped — models not present yet (%s)", exc,
        )
        return None, None

    # Idempotent REPLACE: delete any existing summary row for the same
    # (kid, date) so the UNIQUE constraint stays clean and the new
    # generation wins. Belt-and-braces: explicitly purge dependent
    # `conversation_starters` rows first rather than rely on
    # `ON DELETE CASCADE` on the FK (M0-2 owns that schema and we don't
    # want a silent FK violation if CASCADE is omitted there).
    existing_rows = (
        db.query(AiSummary.id)
        .filter(
            AiSummary.kid_id == kid_id,
            AiSummary.summary_date == summary_date,
        )
        .all()
    )
    existing_ids = [r[0] for r in existing_rows]
    if existing_ids:
        db.query(ConversationStarter).filter(
            ConversationStarter.summary_id.in_(existing_ids),
        ).delete(synchronize_session=False)
    db.query(AiSummary).filter(
        AiSummary.kid_id == kid_id,
        AiSummary.summary_date == summary_date,
    ).delete(synchronize_session=False)

    summary_row = AiSummary(
        kid_id=kid_id,
        summary_date=summary_date,
        summary_json=payload,
        model_version=model_version,
        prompt_hash=prompt_hash,
        policy_blocked=False,
        parent_edited=False,
    )
    db.add(summary_row)
    db.flush()

    starter_row = ConversationStarter(
        summary_id=summary_row.id,
        text=payload["conversation_starter"]["text"],
    )
    db.add(starter_row)
    db.flush()

    return summary_row.id, starter_row.id


def _record_audit(
    db: Session | None,
    *,
    kid_id: int,
    summary_date: str,
    model_version: str,
    prompt_hash: str,
    input_hashes: dict[str, str],
    summary_id: int | None,
    cost_usd: float,
) -> None:
    """Write an `audit_event` row capturing model provenance (NFR5).

    Until M0-2's dedicated ``audit_event`` table ships, we route through
    the existing ``audit_logs`` table via ``audit_service.log_action``.
    The action name + details payload give us the hooks needed for the
    audit dashboard without a schema change.
    """
    if db is None:
        return
    try:
        log_action(
            db,
            user_id=None,
            action="dci.summary.generated",
            resource_type="ai_summary",
            resource_id=summary_id,
            details={
                "kid_id": kid_id,
                "summary_date": summary_date,
                "model_version": model_version,
                "prompt_hash": prompt_hash,
                "input_hashes": input_hashes,
                "estimated_cost_usd": round(cost_usd, 6),
            },
        )
    except Exception:
        # Audit failures must never break the summary path — log_action
        # already swallows DB errors, but guard anyway in case the
        # import path is mocked in tests.
        logger.warning("DCI summary audit log failed", exc_info=True)


async def generate_summary(
    kid_id: int,
    summary_date: str,
    classification_events: list[dict],
    prior_7day_context: list[dict] | None = None,
    *,
    kid_name: str = "your kid",
    db: Session | None = None,
) -> dict[str, Any]:
    """Generate the parent-facing daily summary for one kid.

    Args:
        kid_id: Students.id of the kid.
        summary_date: ISO date (YYYY-MM-DD) of the day being summarised.
        classification_events: Raw artifact rows from
            ``classification_events`` (M0-5 output) for this kid + date.
        prior_7day_context: Prior 7 days of structured summaries — the
            cacheable block. Pass ``None`` for the kid's first week.
        kid_name: Optional first name — purely for prompt warmth; the
            kid's identity is never exposed in the structured payload.
        db: Optional SQLAlchemy session. When provided, the service
            stages INSERTs (via ``db.add`` + ``db.flush``) for
            ``ai_summaries`` + ``conversation_starters``, idempotently
            REPLACING any existing row for that date, plus an
            ``audit_event`` row. **The caller MUST commit the session**
            — this service never commits so it can compose with a
            wider transaction (e.g. M0-7 scheduler batch). Audit row is
            committed separately by ``audit_service.log_action`` via
            its own SAVEPOINT. When ``db`` is ``None`` (e.g. dry-run,
            tests), the function still returns the structured payload.

    Returns:
        ``{"subjects": [...], "deadlines": [...], "conversation_starter":
        {"text": str, "tone": str}}`` — the same shape we persist.
    """
    model = _resolve_model()
    today_block = build_today_block(classification_events, summary_date)
    context_block = build_context_block(prior_7day_context)

    # Two-block user message so the 7-day context can carry its own
    # cache_control — same kid, same week → cache hit.
    user_content_blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"Kid: {kid_name}\nDate: {summary_date}\n\n"
                f"--- TODAY ---\n{today_block}\n\n"
                "Call `emit_daily_summary` exactly once with the structured summary."
            ),
        },
        {
            "type": "text",
            "text": f"--- CONTEXT (last 7 days) ---\n{context_block}",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    # System + tool schema also cached: stable across all kids/days, so
    # the prompt cache amortises across the whole family fleet.
    system_blocks = [
        {
            "type": "text",
            "text": DCI_SUMMARY_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    tool_with_cache = {**DCI_SUMMARY_TOOL_SCHEMA, "cache_control": {"type": "ephemeral"}}

    # Hashes for audit provenance (NFR5). prompt_hash captures the full
    # prompt envelope; input_hashes hash each input dimension so the
    # audit dashboard can answer "did the same inputs produce the same
    # output?" without storing raw kid content.
    prompt_hash = _hash_str(
        DCI_SUMMARY_SYSTEM_PROMPT
        + "\n"
        + stable_json(DCI_SUMMARY_TOOL_SCHEMA)
        + "\n"
        + stable_json(user_content_blocks)
    )
    input_hashes = {
        "classification_events": _hash_str(stable_json(classification_events or [])),
        "prior_7day_context": _hash_str(stable_json(prior_7day_context or [])),
        "summary_date": _hash_str(summary_date),
    }

    start = time.time()
    logger.info(
        "DCI summary generate | kid_id=%s | date=%s | events=%d | model=%s",
        kid_id, summary_date, len(classification_events or []), model,
    )

    client = get_anthropic_client()
    message = await asyncio.to_thread(
        client.messages.create,
        model=model,
        max_tokens=DCI_SUMMARY_MAX_TOKENS,
        system=system_blocks,
        tools=[tool_with_cache],
        tool_choice={"type": "tool", "name": "emit_daily_summary"},
        messages=[{"role": "user", "content": user_content_blocks}],
        temperature=0.4,
    )

    # Cost + token telemetry (mirrors parent_digest_ai_service.py).
    usage = getattr(message, "usage", None)
    input_tok = getattr(usage, "input_tokens", 0) if usage else 0
    output_tok = getattr(usage, "output_tokens", 0) if usage else 0
    cost_usd = _calc_cost(model, input_tok, output_tok)
    _last_ai_usage.set({
        "prompt_tokens": input_tok,
        "completion_tokens": output_tok,
        "total_tokens": input_tok + output_tok,
        "model_name": model,
        "estimated_cost_usd": cost_usd,
    })

    # Cost-cap alert log — the M0 telemetry job tails for this string.
    if cost_usd > DCI_COST_ALERT_USD:
        logger.warning(
            "DCI summary cost ALERT | kid_id=%s | date=%s | cost=$%.4f | "
            "alert_threshold=$%.4f | model=%s",
            kid_id, summary_date, cost_usd, DCI_COST_ALERT_USD, model,
        )
    elif cost_usd > DCI_COST_TARGET_USD:
        logger.info(
            "DCI summary cost above target | kid_id=%s | date=%s | "
            "cost=$%.4f | target=$%.4f",
            kid_id, summary_date, cost_usd, DCI_COST_TARGET_USD,
        )

    payload = _normalise_payload(_extract_summary_payload(message))

    summary_id, starter_id = _persist_summary(
        db,
        kid_id=kid_id,
        summary_date=summary_date,
        payload=payload,
        model_version=model,
        prompt_hash=prompt_hash,
    )

    _record_audit(
        db,
        kid_id=kid_id,
        summary_date=summary_date,
        model_version=model,
        prompt_hash=prompt_hash,
        input_hashes=input_hashes,
        summary_id=summary_id,
        cost_usd=cost_usd,
    )

    duration_ms = (time.time() - start) * 1000
    logger.info(
        "DCI summary done | kid_id=%s | date=%s | duration=%.1fms | "
        "input_tok=%d | output_tok=%d | cost=$%.4f | summary_id=%s | starter_id=%s",
        kid_id, summary_date, duration_ms, input_tok, output_tok, cost_usd,
        summary_id, starter_id,
    )

    return payload
