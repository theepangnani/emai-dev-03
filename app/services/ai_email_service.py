"""
AI Email Service — Phase 5 AI Email Agent.

Provides GPT-4o-mini-powered email composition, draft improvement,
thread summarisation, action-item extraction, and reply suggestions.

The platform AI key is used by default. If the user has supplied a BYOK
Anthropic key it will be used via get_anthropic_client() instead.
"""
import json
import logging

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a school communication assistant for ClassBridge, an education platform "
    "used by parents, students, and teachers in Ontario, Canada. "
    "You help compose clear, professional emails between parents and teachers. "
    "Always respect the privacy of students and families. "
    "Do not invent facts. If you are unsure, ask the user to clarify."
)


def _get_client(user=None):
    """Return an Anthropic client, respecting BYOK keys."""
    from app.services.ai_service import get_anthropic_client
    return get_anthropic_client(user)


class AIEmailService:
    """AI-powered email composition and summarisation."""

    def __init__(self, user=None):
        self._user = user

    # ------------------------------------------------------------------
    # Composition helpers
    # ------------------------------------------------------------------

    async def draft_email(
        self,
        prompt: str,
        context: str,
        tone: str = "formal",
        language: str = "en",
    ) -> dict:
        """Draft a new email from a plain-language description.

        Args:
            prompt:   User's description of what to write.
            context:  Relevant context (student name, course, issue, etc.).
            tone:     "formal" | "friendly" | "concise" | "empathetic".
            language: "en" | "fr".

        Returns:
            {"subject": str, "body": str, "tone": tone}
        """
        lang_label = "English" if language == "en" else "French"
        user_message = (
            f"Draft a {tone} email in {lang_label}.\n\n"
            f"Context: {context}\n\n"
            f"Request: {prompt}\n\n"
            "Return a JSON object with exactly two keys: "
            '"subject" (a concise email subject line) and '
            '"body" (the full email body, plain text, ready to send). '
            "Do not include any other text outside the JSON object."
        )

        logger.info("AI draft_email | tone=%s | language=%s", tone, language)
        client = _get_client(self._user)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=800,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.7,
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
            subject = data.get("subject", "")
            body = data.get("body", "")
        except (json.JSONDecodeError, AttributeError):
            # Fallback: treat whole response as body
            subject = ""
            body = raw

        logger.info("AI draft_email completed | subject_len=%d | body_len=%d", len(subject), len(body))
        return {"subject": subject, "body": body, "tone": tone}

    async def improve_draft(
        self,
        current_body: str,
        instruction: str,
    ) -> str:
        """Improve an existing draft based on a user instruction.

        Args:
            current_body: The current draft text.
            instruction:  e.g. "make it shorter", "more formal", "translate to French".

        Returns:
            Revised email body as plain text.
        """
        user_message = (
            f"Here is the current email draft:\n\n{current_body}\n\n"
            f"Instruction: {instruction}\n\n"
            "Return ONLY the revised email body. Do not add any explanation or commentary."
        )

        logger.info("AI improve_draft | instruction=%s", instruction[:80])
        client = _get_client(self._user)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=800,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.5,
        )
        return response.content[0].text.strip()

    # ------------------------------------------------------------------
    # Thread analysis
    # ------------------------------------------------------------------

    async def summarize_thread(self, messages: list) -> str:
        """Summarise an email thread in 2-4 sentences.

        Args:
            messages: list of EmailMessage ORM objects.

        Returns:
            Plain-text summary covering key points, action items, decisions,
            and tone of communication.
        """
        if not messages:
            return "No messages in this thread yet."

        transcript = _build_transcript(messages)
        user_message = (
            "Summarise the following email thread in 2-4 sentences. "
            "Include: key points discussed, action items, decisions made, "
            "and the overall tone of communication.\n\n"
            f"{transcript}"
        )

        logger.info("AI summarize_thread | message_count=%d", len(messages))
        client = _get_client(self._user)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=300,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.3,
        )
        return response.content[0].text.strip()

    async def extract_action_items(self, thread_messages: list) -> list[str]:
        """Extract actionable items from an email thread.

        Args:
            thread_messages: list of EmailMessage ORM objects.

        Returns:
            List of action-item strings (may be empty).
        """
        if not thread_messages:
            return []

        transcript = _build_transcript(thread_messages)
        user_message = (
            "Read the following email thread and extract all action items — "
            "tasks, follow-ups, or commitments that someone needs to do. "
            "Return a JSON array of short action-item strings. "
            "If there are no action items, return an empty array [].\n\n"
            f"{transcript}"
        )

        logger.info("AI extract_action_items | message_count=%d", len(thread_messages))
        client = _get_client(self._user)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.2,
        )
        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            items = json.loads(raw)
            if isinstance(items, list):
                return [str(i) for i in items]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: split by newline if JSON parsing fails
        return [line.lstrip("-• ").strip() for line in raw.splitlines() if line.strip()]

    async def suggest_reply(
        self,
        last_message,
        user_context: str,
    ) -> str:
        """Suggest a reply to the most recent message in a thread.

        Args:
            last_message: EmailMessage ORM object (most recent received message).
            user_context: Brief context about the replying user.

        Returns:
            Suggested reply body as plain text.
        """
        sender = last_message.from_name or last_message.from_email
        user_message = (
            f"The following email was received from {sender}:\n\n"
            f"Subject: {last_message.subject}\n\n"
            f"{last_message.body_text}\n\n"
            f"Context about the person replying: {user_context}\n\n"
            "Draft a professional reply. Return ONLY the reply body — "
            "no subject line, no explanation."
        )

        logger.info("AI suggest_reply | from=%s", last_message.from_email)
        client = _get_client(self._user)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=600,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.6,
        )
        return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_transcript(messages: list) -> str:
    """Build a readable transcript from a list of EmailMessage objects."""
    lines = []
    for msg in messages:
        direction = "→ Received" if msg.direction.value == "inbound" else "→ Sent"
        sender = msg.from_name or msg.from_email
        lines.append(f"[{direction}] From: {sender}")
        lines.append(f"Subject: {msg.subject}")
        lines.append(msg.body_text[:1000])  # cap per-message to avoid token overflow
        lines.append("")
    return "\n".join(lines)
