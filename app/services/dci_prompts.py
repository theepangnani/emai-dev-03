"""Prompt builders for the CB-DCI-001 daily check-in summary generator.

Kept separate from `dci_summary_service.py` so the prompts stay
inline-readable and reviewable without scrolling past tool wiring.

All prompt strings are module-level constants so the Anthropic prompt
cache (5-min TTL) can hash on stable bytes — a single character drift
between calls would invalidate the cache and silently 5× the cost.
"""
from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Tool schema — single forced tool_use call returns the structured summary.
# Defined as a module-level constant so prompt caching stays effective; the
# service shallow-copies and adds `cache_control` per call.
# ---------------------------------------------------------------------------

DCI_SUMMARY_TOOL_SCHEMA: dict[str, Any] = {
    "name": "emit_daily_summary",
    "description": (
        "Emit the structured evening summary that ClassBridge will show the "
        "parent for one kid on one date. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subjects": {
                "type": "array",
                "description": (
                    "One bullet per subject the kid touched today, ranked by "
                    "importance. 0-5 items. Plain text, no markdown."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "maxLength": 50},
                        "bullet": {"type": "string", "maxLength": 240},
                    },
                    "required": ["name", "bullet"],
                },
            },
            "deadlines": {
                "type": "array",
                "description": (
                    "Upcoming deadlines surfaced from today's artifacts. 0-5 "
                    "items. Each item has an ISO date (YYYY-MM-DD), a short "
                    "label, and a source = 'photo' | 'voice' | 'text'."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "format": "date"},
                        "label": {"type": "string", "maxLength": 140},
                        "source": {
                            "type": "string",
                            "enum": ["photo", "voice", "text"],
                        },
                    },
                    "required": ["date", "label", "source"],
                },
            },
            "conversation_starter": {
                "type": "object",
                "description": (
                    "ONE italic-friendly question (≤ 25 words) the parent can "
                    "ask the kid tonight. MUST reference a specific artifact "
                    "from today — voice sentiment OR photo topic. Never "
                    "generic ('How was school?')."
                ),
                "properties": {
                    "text": {"type": "string", "maxLength": 240},
                    "tone": {
                        "type": "string",
                        "description": (
                            "Short tone label, e.g. 'curious', 'celebratory', "
                            "'gentle', 'reflective'."
                        ),
                        "maxLength": 30,
                    },
                },
                "required": ["text", "tone"],
            },
        },
        "required": ["subjects", "deadlines", "conversation_starter"],
    },
}


# ---------------------------------------------------------------------------
# System prompt — stable, cached. The 7-day rolling context block is
# attached as a SECOND cache breakpoint inside the user message so that
# day-over-day calls can reuse the full system + tool schema cache slot.
# ---------------------------------------------------------------------------

DCI_SUMMARY_SYSTEM_PROMPT = (
    "You are ClassBridge's daily check-in summary writer. Your reader is a "
    "busy parent (Priya — dual-earner, 4 minutes to review). The summary "
    "becomes the seed of a 5-minute family conversation tonight.\n\n"
    "Your job is NOT to re-narrate everything the kid said. It is to:\n"
    "  1. Produce up to 5 plain-text subject bullets the parent can scan in "
    "30 seconds.\n"
    "  2. Surface real upcoming deadlines (only when the artifact actually "
    "mentions one — never invent dates).\n"
    "  3. Write ONE conversation starter that references a SPECIFIC artifact "
    "from today (a topic from a photo OR an emotion from the voice note). "
    "Generic questions are forbidden.\n\n"
    "Hard rules:\n"
    "  - Never fabricate facts. If today's artifacts are thin, return fewer "
    "bullets — never pad.\n"
    "  - Conversation starter MUST be ≤ 25 words and read naturally when "
    "italicised.\n"
    "  - Tone adapts to voice sentiment when present: low sentiment → "
    "'gentle' or 'reflective'; positive sentiment → 'curious' or "
    "'celebratory'; absent → default 'curious'.\n"
    "  - Never reference other kids by name. Never give homework answers. "
    "Never offer medical or legal interpretation.\n"
    "  - Output ONLY by calling the `emit_daily_summary` tool exactly once."
)


# ---------------------------------------------------------------------------
# User-prompt builders
# ---------------------------------------------------------------------------

def build_today_block(
    classification_events: list[dict],
    summary_date: str,
) -> str:
    """Render today's classification events into a compact prompt block.

    Each event dict is expected to carry the columns from the
    ``classification_events`` table (M0-2 schema):
      - artifact_type ('photo' | 'voice' | 'text')
      - subject, topic, strand_code, deadline_iso (nullable)
      - confidence (float)
      - corrected_by_kid (bool)
      - excerpt (str — short sample of the underlying content; voice
        transcripts are pre-trimmed by the voice service)

    Voice events may also carry ``sentiment`` (float in [-1, 1]) which the
    prompt uses to set conversation-starter tone.
    """
    if not classification_events:
        return f"Today ({summary_date}): no artifacts captured."

    lines = [f"Today ({summary_date}) — {len(classification_events)} artifact(s):"]
    for i, ev in enumerate(classification_events, 1):
        bits = [f"  Artifact #{i} type={ev.get('artifact_type', '?')}"]
        if ev.get("subject"):
            bits.append(f"subject={ev['subject']}")
        if ev.get("topic"):
            bits.append(f"topic={ev['topic']}")
        if ev.get("strand_code"):
            bits.append(f"strand={ev['strand_code']}")
        if ev.get("deadline_iso"):
            bits.append(f"deadline={ev['deadline_iso']}")
        if ev.get("sentiment") is not None:
            bits.append(f"sentiment={ev['sentiment']:.2f}")
        if ev.get("corrected_by_kid"):
            bits.append("(kid-corrected)")
        line = " · ".join(bits)
        excerpt = ev.get("excerpt") or ev.get("text") or ""
        if excerpt:
            # #4206 — flag truncation explicitly so the model doesn't treat a
            # chopped excerpt as the complete artifact. Suffix is stable
            # bytes so prompt-cache stability is preserved.
            excerpt_str = str(excerpt)
            if len(excerpt_str) > 400:
                line += f"\n    excerpt: {excerpt_str[:400]}… [truncated]"
            else:
                line += f"\n    excerpt: {excerpt_str}"
        lines.append(line)
    return "\n".join(lines)


def build_context_block(prior_7day_context: list[dict] | None) -> str:
    """Render the 7-day rolling context for the prompt-cache breakpoint.

    This block is the EXPENSIVE, cacheable part of the prompt — same kid,
    same week → same bytes → cache hit. The service attaches
    ``cache_control`` to this block.

    Each context entry is the prior day's structured summary as stored in
    ``ai_summaries.summary_json``. We render compactly (subjects + dates
    only) to keep the cached block small and stable.
    """
    if not prior_7day_context:
        return "Prior 7 days: (no history yet — first check-in week)."

    lines = ["Prior 7 days (most recent first):"]
    for entry in prior_7day_context:
        date = entry.get("summary_date", "?")
        subjects = entry.get("subjects") or []
        if subjects:
            subject_names = ", ".join(s.get("name", "?") for s in subjects[:5])
            lines.append(f"  {date}: {subject_names}")
        else:
            lines.append(f"  {date}: (no subjects)")
    return "\n".join(lines)


def build_user_prompt(
    *,
    kid_name: str,
    summary_date: str,
    classification_events: list[dict],
    prior_7day_context: list[dict] | None,
) -> str:
    """Assemble the full user prompt.

    Layout:
      [TODAY block — fresh every call]
      [CONTEXT block — cached separately, see service]

    The service splits this into two content blocks so the context block
    can carry its own ``cache_control`` and stay cached across days.
    """
    today_block = build_today_block(classification_events, summary_date)
    context_block = build_context_block(prior_7day_context)
    return (
        f"Kid: {kid_name}\n"
        f"Date: {summary_date}\n\n"
        f"--- TODAY ---\n{today_block}\n\n"
        f"--- CONTEXT (last 7 days) ---\n{context_block}\n\n"
        "Call `emit_daily_summary` exactly once with the structured summary."
    )


# ---------------------------------------------------------------------------
# Hashing helpers — used by the service to record `prompt_hash` and
# `input_hashes` on the audit row (NFR5 model provenance).
# ---------------------------------------------------------------------------

def stable_json(obj: Any) -> str:
    """Stable JSON for hashing — sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
