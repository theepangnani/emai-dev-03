"""
AI service for generating parent email digest summaries using Claude.
"""
import asyncio
import json
import re
import time

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.ai_service import get_anthropic_client, _last_ai_usage, _calc_cost

logger = get_logger(__name__)

# Use Haiku for digest summarization (cost-effective for high-volume digests)
DIGEST_MODEL = "claude-haiku-4-5-20251001"

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


# ---------------------------------------------------------------------------
# Sectioned 3×3 digest (#3956 — Phase A of #3905 multi-variable redesign)
# ---------------------------------------------------------------------------

SECTIONED_JSON_PROMPT = """You are a school email digest assistant for a parent. \
Based on the emails below, produce a JSON object with AT MOST 3 items per section, \
ranked by urgency and recency.

Return ONLY valid JSON matching this schema (no markdown, no prose):
{
  "urgent": [str, str, str],
  "announcements": [str, str, str],
  "action_items": [str, str, str],
  "overflow": {
    "urgent": int, "announcements": int, "action_items": int
  }
}

- "urgent" = items due today or tomorrow (0-3 items)
- "announcements" = classroom posts, not time-sensitive (0-3 items)
- "action_items" = things the parent or child must DO (0-3 items)
- Each item is ONE SHORT SENTENCE (max 140 chars). Do not include HTML tags.
- Omit empty sections by setting them to [].
- "overflow" counts how many additional items we would have included if the cap were higher.

Parent name: {parent_name}
Child name: {child_name}

Emails:
{emails_serialized}
"""

SECTIONED_MAX_TOKENS = 1000


def _strip_json_fence(raw: str) -> str:
    """Strip ```json ... ``` fences from AI responses (common failure mode)."""
    s = raw.strip()
    if s.startswith("```"):
        # Remove opening fence (```json or ```)
        s = re.sub(r"^```(?:json)?\s*\n?", "", s)
        # Remove trailing fence
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _validate_sectioned_dict(parsed: dict) -> dict:
    """Coerce a loosely-shaped dict into the SectionedDigest contract.

    Missing keys default to []/{}; non-list sections default to []; non-string items
    are stringified; overflow values default to 0 and are coerced to int.
    """
    def _as_str_list(v) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x) for x in v if x is not None]

    overflow_in = parsed.get("overflow") if isinstance(parsed.get("overflow"), dict) else {}
    overflow_out: dict[str, int] = {}
    for key in ("urgent", "announcements", "action_items"):
        raw = overflow_in.get(key, 0)
        try:
            overflow_out[key] = max(0, int(raw))
        except (TypeError, ValueError):
            overflow_out[key] = 0

    return {
        "urgent": _as_str_list(parsed.get("urgent", [])),
        "announcements": _as_str_list(parsed.get("announcements", [])),
        "action_items": _as_str_list(parsed.get("action_items", [])),
        "overflow": overflow_out,
    }


async def generate_sectioned_digest(
    emails: list[dict],
    child_name: str,
    parent_name: str,
) -> dict:
    """Generate a sectioned 3×3 digest with urgent / announcements / action_items.

    Returns a dict matching the ``SectionedDigest`` Pydantic schema:
        {
          "urgent": [...],
          "announcements": [...],
          "action_items": [...],
          "overflow": {"urgent": int, "announcements": int, "action_items": int},
        }

    On JSON parse failure, falls back to :func:`generate_parent_digest` and returns
    ``{"legacy_blob": "<html>"}`` so callers can render the old HTML format.

    Empty email list returns all-empty sections with zero overflow.
    """
    if not emails:
        return {
            "urgent": [],
            "announcements": [],
            "action_items": [],
            "overflow": {"urgent": 0, "announcements": 0, "action_items": 0},
        }

    # Serialise emails the same way the legacy prompt does, then slot into the
    # sectioned prompt template.
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
            parts.append(f"Body: {body[:2000]}")
        email_texts.append("\n".join(parts))

    emails_block = "\n---\n".join(email_texts)

    user_prompt = SECTIONED_JSON_PROMPT.format(
        parent_name=parent_name,
        child_name=child_name,
        emails_serialized=emails_block,
    )

    start_time = time.time()
    logger.info(
        "Generating sectioned parent digest | parent=%s | child=%s | email_count=%d",
        parent_name, child_name, len(emails),
    )

    try:
        client = get_anthropic_client()
        message = await asyncio.to_thread(
            client.messages.create,
            model=DIGEST_MODEL,
            max_tokens=SECTIONED_MAX_TOKENS,
            system=(
                "You are ClassBridge's parent email digest assistant. "
                "Return only strict JSON matching the schema requested. "
                "No markdown, no prose, no code fences."
            ),
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
        )

        raw = message.content[0].text
        input_tok = message.usage.input_tokens
        output_tok = message.usage.output_tokens
        duration_ms = (time.time() - start_time) * 1000

        _last_ai_usage.set({
            "prompt_tokens": input_tok,
            "completion_tokens": output_tok,
            "total_tokens": input_tok + output_tok,
            "model_name": DIGEST_MODEL,
            "estimated_cost_usd": _calc_cost(DIGEST_MODEL, input_tok, output_tok),
        })

        try:
            parsed = json.loads(_strip_json_fence(raw))
            if not isinstance(parsed, dict):
                raise ValueError("AI returned non-object JSON")
        except (ValueError, json.JSONDecodeError) as parse_err:
            logger.warning(
                "Sectioned digest JSON parse failed — falling back to legacy blob | error=%s",
                parse_err,
            )
            legacy = await generate_parent_digest(
                emails, child_name, parent_name, digest_format="full"
            )
            return {"legacy_blob": legacy}

        logger.info(
            "Sectioned parent digest generated | duration=%.2fms | input_tokens=%d | output_tokens=%d",
            duration_ms, input_tok, output_tok,
        )

        return _validate_sectioned_dict(parsed)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Sectioned digest generation failed | duration=%.2fms | error=%s",
            duration_ms, e,
        )
        # On upstream AI error, fall back to legacy HTML path so parents still
        # receive a digest (#3956).
        try:
            legacy = await generate_parent_digest(
                emails, child_name, parent_name, digest_format="full"
            )
            return {"legacy_blob": legacy}
        except Exception:
            raise
