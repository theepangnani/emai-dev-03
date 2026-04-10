"""
AI service for generating parent email digest summaries using Claude.
"""
import asyncio
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
- Group emails by type: Teacher Messages, School Admin, Announcements
- Highlight ACTION ITEMS (deadlines, forms to sign, RSVPs) in a separate section
- Flag URGENT items (due today or tomorrow) clearly
- Keep the tone warm, clear, and professional
- NEVER fabricate information — only summarize what is in the source emails
- Format output as clean HTML suitable for embedding in an email template
- Use <h3> for section headers, <ul>/<li> for lists, <strong> for emphasis
- Do NOT include <html>, <head>, or <body> tags — just the content HTML"""


async def generate_parent_digest(
    emails: list[dict],
    child_name: str,
    parent_name: str,
    digest_format: str = "full",
) -> str:
    """Generate an AI-powered digest summary of school emails for a parent.

    Args:
        emails: List of email dicts with keys like 'subject', 'from', 'snippet', 'body', 'date'.
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
        parts = [f"Email #{i}"]
        if email.get("from"):
            parts.append(f"From: {email['from']}")
        if email.get("subject"):
            parts.append(f"Subject: {email['subject']}")
        if email.get("date"):
            parts.append(f"Date: {email['date']}")
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
