"""
AI service for generating parent email digest summaries using Claude.
"""
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.logging_config import get_logger
from app.services.ai_service import get_anthropic_client, _last_ai_usage, _calc_cost

logger = get_logger(__name__)

# Use Haiku for digest summarization (cost-effective for high-volume digests)
DIGEST_MODEL = "claude-haiku-4-5-20251001"

# Default timezone for parsing "YYYY-MM-DD" due dates returned by the extraction tool.
_DEFAULT_EXTRACTION_TZ = "America/Toronto"


@dataclass
class DigestTaskItem:
    """Structured urgent/due-date item extracted from school emails.

    Produced by :func:`extract_digest_items` and consumed downstream by the
    task-sync service (CB-TASKSYNC-001 I3/I6) to upsert Task rows. Kept as a
    plain dataclass so it can be imported without pulling in SQLAlchemy.
    """

    title: str
    due_date: datetime  # timezone-aware
    course_name: str | None
    confidence: float
    source_excerpt: str
    gmail_message_id: str | None


# Tool schema used by :func:`extract_digest_items`. Kept as a module-level
# constant so that prompt caching stays effective across requests — Claude
# only charges the full schema tokens on a cache miss, then reuses the
# cached block on subsequent calls within the ~5-minute cache TTL.
_EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_urgent_items",
    "description": "Extract actionable due-date items from school emails.",
    "input_schema": {
        "type": "object",
        "properties": {
            "urgent_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "maxLength": 200},
                        "due_date": {"type": "string", "format": "date"},
                        "course_or_context": {"type": ["string", "null"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source_email_excerpt": {"type": "string", "maxLength": 300},
                        "source_email_index": {"type": "integer"},
                    },
                    "required": ["title", "due_date", "confidence", "source_email_index"],
                },
            }
        },
        "required": ["urgent_items"],
    },
}

_EXTRACTION_SYSTEM_PROMPT = (
    "You are ClassBridge's due-date extractor. Read the numbered school emails "
    "and return ONLY actionable items with an explicit or clearly-implied due date "
    "(permission slips, assignment submissions, RSVPs, fees, form signatures, "
    "scheduled events parents must attend, etc.).\n\n"
    "Rules:\n"
    "- Only emit items that have a date the parent must act on. If no due date is "
    "present, omit the item.\n"
    "- Use ISO format YYYY-MM-DD for `due_date` (date only, no time).\n"
    "- `confidence` is your certainty that (a) the item is actionable and "
    "(b) the due date is correct. Use 0.9+ for explicit dates, 0.7-0.9 for "
    "confidently-implied dates, 0.5-0.7 for ambiguous cases.\n"
    "- `source_email_index` MUST be the 1-based index of the email the item came "
    "from, matching the `Email #N` header in the input.\n"
    "- `source_email_excerpt` is a short verbatim quote (<=300 chars) from the "
    "email that supports the due date.\n"
    "- NEVER fabricate items. If no actionable due-date items exist, return an "
    "empty `urgent_items` array."
)

_FORMAT_CONFIG = {
    "full": {
        "max_tokens": 1200,
        "instruction": (
            "Produce a FULL digest with these sections:\n"
            "1. A warm greeting addressing the parent by name\n"
            "2. **Teacher Messages** — summarize each teacher email\n"
            "3. **School Admin / Announcements** — summarize admin emails\n"
            "4. **Action Items** — list deadlines, forms, RSVPs with dates\n"
            "5. **Urgent** — flag anything due today or tomorrow\n"
            "Use short paragraphs and bullet points. Keep it scannable."
        ),
    },
    "brief": {
        "max_tokens": 400,
        "instruction": (
            "Produce a BRIEF bullet-point digest. No long paragraphs.\n"
            "- One bullet per email, with sender and key point\n"
            "- Separate section for action items with deadlines\n"
            "- Flag urgent items (due today/tomorrow) at the top"
        ),
    },
    "actions_only": {
        "max_tokens": 300,
        "instruction": (
            "Extract ONLY action items and deadlines from the emails.\n"
            "- List each action item with its deadline and source\n"
            "- Flag urgent items (due today/tomorrow)\n"
            "- If no action items, say so briefly"
        ),
    },
}

_SYSTEM_PROMPT = """You are ClassBridge's parent email digest assistant. You summarize school emails \
for busy parents so they can stay informed at a glance.

Rules:
- Address the parent by first name warmly
- Mention the child by first name for context
- Attribute emails to specific senders by name (e.g., "Ms. Johnson sent a reminder about...")
- Group emails by type: Teacher Messages, School Admin, Announcements
- Highlight ACTION ITEMS (deadlines, forms to sign, RSVPs) in a separate section
- Flag URGENT items (due today or tomorrow) clearly
- Emails prefixed with [AUTO] are automated notifications (noreply/system senders). \
Group these together under an "Automated Notifications" section and summarize them \
briefly — do not treat them as personal teacher messages.
- Keep the tone warm, clear, and professional
- NEVER fabricate information — only summarize what is in the source emails
- Format output as clean HTML suitable for embedding in an email template
- Use <h3> for section headers, <ul>/<li> for lists, <strong> for emphasis
- Do NOT include <html>, <head>, or <body> tags — just the content HTML"""


def _resolve_sender_display(sender_name: str, sender_email: str) -> str:
    """Resolve a human-readable sender label from parser fields.

    Falls back to the email local-part (e.g., 'grade3.teacher' from
    'grade3.teacher@school.ca') when no display name is set.
    """
    if sender_name:
        return sender_name
    if sender_email and "@" in sender_email:
        return sender_email.split("@", 1)[0]
    return "Unknown sender"


async def generate_parent_digest(
    emails: list[dict],
    child_name: str,
    parent_name: str,
    digest_format: str = "full",
) -> str:
    """Generate an AI-powered digest summary of school emails for a parent.

    Args:
        emails: List of email dicts from the Gmail parser with keys like
            'subject', 'sender_name', 'sender_email', 'snippet', 'body',
            'received_at'.
        child_name: The child's first name for context.
        parent_name: The parent's first name for greeting.
        digest_format: One of 'full', 'brief', 'actions_only'.

    Returns:
        HTML string with the digest content (no wrapper template).
    """
    if not emails:
        return (
            f"<p>Good news, {parent_name} — there are no new school emails "
            f"for {child_name} since the last digest. Enjoy your morning!</p>"
        )

    config = _FORMAT_CONFIG.get(digest_format, _FORMAT_CONFIG["full"])

    # Build the email listing for the prompt
    email_texts = []
    for i, email in enumerate(emails, 1):
        auto_tag = "[AUTO] " if email.get("is_automated") else ""
        parts = [f"Email #{i} {auto_tag}".rstrip()]
        sender_display = _resolve_sender_display(
            email.get("sender_name") or "",
            email.get("sender_email") or "",
        )
        sender_email = email.get("sender_email") or ""
        if sender_email and sender_display != sender_email:
            parts.append(f"From: {sender_display} <{sender_email}>")
        else:
            parts.append(f"From: {sender_display}")
        if email.get("subject"):
            parts.append(f"Subject: {email['subject']}")
        received_at = email.get("received_at")
        if received_at:
            parts.append(f"Date: {received_at}")
        body = email.get("body") or email.get("snippet") or ""
        if body:
            # Truncate very long emails to keep prompt manageable
            parts.append(f"Body: {body[:2000]}")
        email_texts.append("\n".join(parts))

    emails_block = "\n---\n".join(email_texts)

    user_prompt = (
        f"Parent name: {parent_name}\n"
        f"Child name: {child_name}\n"
        f"Number of emails: {len(emails)}\n\n"
        f"Format: {digest_format}\n"
        f"{config['instruction']}\n\n"
        f"--- EMAILS ---\n{emails_block}"
    )

    start_time = time.time()
    logger.info(
        "Generating parent digest | parent=%s | child=%s | format=%s | email_count=%d",
        parent_name, child_name, digest_format, len(emails),
    )

    try:
        client = get_anthropic_client()
        message = await asyncio.to_thread(
            client.messages.create,
            model=DIGEST_MODEL,
            max_tokens=config["max_tokens"],
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.3,
        )

        content = message.content[0].text
        input_tok = message.usage.input_tokens
        output_tok = message.usage.output_tokens
        duration_ms = (time.time() - start_time) * 1000

        # Track token usage via the shared context var
        _last_ai_usage.set({
            "prompt_tokens": input_tok,
            "completion_tokens": output_tok,
            "total_tokens": input_tok + output_tok,
            "model_name": DIGEST_MODEL,
            "estimated_cost_usd": _calc_cost(DIGEST_MODEL, input_tok, output_tok),
        })

        logger.info(
            "Parent digest generated | duration=%.2fms | input_tokens=%d | output_tokens=%d",
            duration_ms, input_tok, output_tok,
        )

        return content

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("Parent digest generation failed | duration=%.2fms | error=%s", duration_ms, e)
        raise


def _build_extraction_user_prompt(emails: list[dict]) -> str:
    """Render emails into a numbered listing for the extraction model."""
    parts = []
    for i, email in enumerate(emails, 1):
        auto_tag = "[AUTO] " if email.get("is_automated") else ""
        block = [f"Email #{i} {auto_tag}".rstrip()]
        sender_display = _resolve_sender_display(
            email.get("sender_name") or "",
            email.get("sender_email") or "",
        )
        sender_email = email.get("sender_email") or ""
        if sender_email and sender_display != sender_email:
            block.append(f"From: {sender_display} <{sender_email}>")
        else:
            block.append(f"From: {sender_display}")
        if email.get("subject"):
            block.append(f"Subject: {email['subject']}")
        received_at = email.get("received_at")
        if received_at:
            block.append(f"Date: {received_at}")
        body = email.get("body") or email.get("snippet") or ""
        if body:
            block.append(f"Body: {body[:2000]}")
        parts.append("\n".join(block))
    return (
        "Extract actionable due-date items from the following school emails. "
        "Call the `extract_urgent_items` tool exactly once with your results.\n\n"
        "--- EMAILS ---\n" + "\n---\n".join(parts)
    )


def _parse_due_date(raw: str, tz_name: str) -> datetime | None:
    """Parse a YYYY-MM-DD string into a timezone-aware datetime at local midnight.

    Returns ``None`` if the string isn't a valid date, so a single bad item
    can be dropped without poisoning the rest of the extraction.
    """
    if not raw or not isinstance(raw, str):
        return None
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(_DEFAULT_EXTRACTION_TZ)
    try:
        # Accept "YYYY-MM-DD" — strip any stray time/tz component defensively.
        date_part = raw.strip().split("T", 1)[0].split(" ", 1)[0]
        parsed = datetime.strptime(date_part, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=tz)


async def extract_digest_items(
    emails: list[dict],
    tz_name: str = _DEFAULT_EXTRACTION_TZ,
) -> list[DigestTaskItem]:
    """Extract structured urgent/due-date items from school emails.

    Runs a second Claude Haiku call (tool-use with forced ``tool_choice``)
    alongside :func:`generate_parent_digest`. The HTML digest remains the
    primary output; this structured list feeds the CB-TASKSYNC-001 pipeline.

    Args:
        emails: Same email dicts passed to :func:`generate_parent_digest`.
            Must carry a ``source_id`` key (Gmail message id) so we can map
            extracted items back to their originating email.
        tz_name: IANA timezone to interpret the date-only ``due_date`` in.
            Defaults to the parent integration's local timezone.

    Returns:
        A list of :class:`DigestTaskItem` — may be empty. Never raises:
        any error (API failure, malformed tool output, missing keys) is
        logged and an empty list is returned so the HTML digest still ships.
    """
    if not emails:
        return []

    start_time = time.time()
    logger.info(
        "Extracting digest items | email_count=%d | tz=%s",
        len(emails), tz_name,
    )

    try:
        client = get_anthropic_client()
        # Attach cache_control to the tool schema (dict) and the system
        # prompt so repeated runs hit the prompt cache. The tool schema is
        # attached via a copy to avoid mutating the module-level constant.
        tool_with_cache = {**_EXTRACTION_TOOL_SCHEMA, "cache_control": {"type": "ephemeral"}}
        system_with_cache = [
            {
                "type": "text",
                "text": _EXTRACTION_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        message = await asyncio.to_thread(
            client.messages.create,
            model=DIGEST_MODEL,
            max_tokens=1024,
            system=system_with_cache,
            tools=[tool_with_cache],
            tool_choice={"type": "tool", "name": "extract_urgent_items"},
            messages=[{"role": "user", "content": _build_extraction_user_prompt(emails)}],
            temperature=0.0,
        )

        # Track token usage (same pattern as generate_parent_digest).
        try:
            input_tok = message.usage.input_tokens
            output_tok = message.usage.output_tokens
            _last_ai_usage.set({
                "prompt_tokens": input_tok,
                "completion_tokens": output_tok,
                "total_tokens": input_tok + output_tok,
                "model_name": DIGEST_MODEL,
                "estimated_cost_usd": _calc_cost(DIGEST_MODEL, input_tok, output_tok),
            })
        except AttributeError:
            # usage metadata missing (rare) — don't let it kill extraction
            pass

        # Find the tool_use block. With forced tool_choice the model must
        # emit one, but defensively handle missing/empty cases.
        tool_block = None
        for block in message.content or []:
            if getattr(block, "type", None) == "tool_use":
                tool_block = block
                break

        if tool_block is None:
            logger.warning("Digest extraction: no tool_use block in response")
            return []

        raw_items = (tool_block.input or {}).get("urgent_items") or []
        if not isinstance(raw_items, list):
            logger.warning("Digest extraction: urgent_items not a list, got %s", type(raw_items))
            return []

        results: list[DigestTaskItem] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            due_raw = item.get("due_date")
            idx = item.get("source_email_index")
            confidence = item.get("confidence")

            if not title or due_raw is None or idx is None or confidence is None:
                continue

            due_date = _parse_due_date(str(due_raw), tz_name)
            if due_date is None:
                continue

            # source_email_index is 1-based in the prompt; map to 0-based list.
            try:
                source_pos = int(idx) - 1
            except (ValueError, TypeError):
                continue
            if source_pos < 0 or source_pos >= len(emails):
                logger.warning(
                    "Digest extraction: source_email_index %s out of range (emails=%d)",
                    idx, len(emails),
                )
                continue

            gmail_message_id = emails[source_pos].get("source_id")

            try:
                confidence_f = float(confidence)
            except (ValueError, TypeError):
                continue

            results.append(DigestTaskItem(
                title=str(title)[:200],
                due_date=due_date,
                course_name=item.get("course_or_context"),
                confidence=confidence_f,
                source_excerpt=str(item.get("source_email_excerpt") or "")[:300],
                gmail_message_id=gmail_message_id,
            ))

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Digest extraction complete | duration=%.2fms | items=%d",
            duration_ms, len(results),
        )
        return results

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Digest extraction failed — returning [] | duration=%.2fms | error=%s",
            duration_ms, e,
        )
        return []
