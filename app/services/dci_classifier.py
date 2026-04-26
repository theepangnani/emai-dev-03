"""DCI artifact classifier — sync GPT-4o-mini wrapper (#4139, M0-4).

Classifies a kid-submitted artifact (photo OCR text, voice transcript, or
typed text) into ``{subject, topic, deadline_iso, confidence}`` so the
kid web flow can show an `<AIDetectedChip>` within ~2 s p50.

The implementation mirrors ``app/services/asgf_service.classify_intent``
but is scoped to the DCI prompt + return shape and is mock-friendly for
tests (the network call is the only side effect — patch
``app.services.dci_classifier._call_openai`` to bypass it).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import openai

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

CLASSIFIER_MODEL = "gpt-4o-mini"
CLASSIFIER_TIMEOUT_S = 5.0
CLASSIFIER_MAX_TOKENS = 200
CLASSIFIER_VERSION = "dci-classifier-v0-gpt4o-mini"

_SYSTEM_PROMPT = (
    "You are a classifier for a kid's daily school check-in. The kid will "
    "show you a photo of a handout / chalkboard / notebook (already OCR'd), "
    "a short voice transcript, or 1-2 typed lines about their school day. "
    "Your job is to infer four fields:\n"
    "  - subject  (one of: Math, Science, English, History, Geography, "
    "Art, Music, French, Phys-Ed, Other)\n"
    "  - topic    (specific sub-topic, ≤120 chars; e.g. 'Fractions: adding "
    "unlike denominators')\n"
    "  - deadline_iso (YYYY-MM-DD if a due date is mentioned, else null)\n"
    "  - confidence (float 0.0-1.0; >=0.5 for any plausible inference, "
    "<0.5 only when the input is genuinely ambiguous)\n\n"
    "Answer-first policy: ALWAYS return a best-guess classification — "
    "never ask the user to clarify. Return ONLY a JSON object with those "
    "four keys, no markdown."
)


@dataclass
class ClassificationResult:
    """Plain dataclass so tests + service layer don't need Pydantic."""

    subject: str = ""
    topic: str = ""
    deadline_iso: Optional[str] = None
    confidence: float = 0.0
    model_version: str = CLASSIFIER_VERSION

    def as_dict(self) -> dict:
        return {
            "subject": self.subject,
            "topic": self.topic,
            "deadline_iso": self.deadline_iso,
            "confidence": self.confidence,
            "model_version": self.model_version,
        }


def _strip_markdown_fence(content: str) -> str:
    """Drop ```...``` fences if the model wrapped the JSON in them."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    return content.strip()


async def _call_openai(prompt_text: str) -> str:
    """Single network call — split out so tests can patch it cleanly."""
    client = openai.AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=CLASSIFIER_TIMEOUT_S,
    )
    response = await client.chat.completions.create(
        model=CLASSIFIER_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        temperature=0.1,
        max_tokens=CLASSIFIER_MAX_TOKENS,
    )
    return response.choices[0].message.content or ""


async def classify_artifact(prompt_text: str) -> ClassificationResult:
    """Classify a single DCI artifact text into a chip payload.

    Always returns a `ClassificationResult` — never raises. Network /
    parse failures degrade to a zero-confidence empty result so the
    request still succeeds with `202 Accepted` (the chip is best-effort,
    not a contract).
    """
    if not prompt_text or not prompt_text.strip():
        return ClassificationResult()

    if not settings.openai_api_key:
        logger.info(
            "DCI classifier: openai_api_key not configured — returning empty result"
        )
        return ClassificationResult()

    try:
        raw = await _call_openai(prompt_text)
    except (openai.APIError, openai.APITimeoutError) as exc:
        logger.warning("DCI classifier API error: %s", exc)
        return ClassificationResult()
    except Exception:
        logger.exception("DCI classifier unexpected error")
        return ClassificationResult()

    cleaned = _strip_markdown_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("DCI classifier JSON parse error: %s — raw=%r", exc, cleaned[:200])
        return ClassificationResult()

    if not isinstance(data, dict):
        return ClassificationResult()

    deadline = data.get("deadline_iso")
    # Normalize falsy / non-string deadlines to None
    if not deadline or not isinstance(deadline, str):
        deadline = None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    return ClassificationResult(
        subject=str(data.get("subject", "") or "")[:50],
        topic=str(data.get("topic", "") or "")[:200],
        deadline_iso=deadline,
        confidence=max(0.0, min(1.0, confidence)),
    )
