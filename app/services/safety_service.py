"""Safety utilities for the Arc tutor chat (CB-TUTOR-002 Phase 1).

Exports:
  - ModerationResult: dataclass-ish container (flagged, categories)
  - moderate(text): async wrapper over the OpenAI moderation API
  - scrub_pii(text): regex-based scrubber for phone, email, SIN

The moderation call's failure mode is controlled by
``settings.moderation_fail_mode`` (default ``"closed"``): for K-12 safety,
when the OpenAI API key is absent or the API errors, moderate() returns
``flagged=True`` with category ``"moderation_unavailable"`` so callers can
distinguish an outage-block from a content-block. Setting
``MODERATION_FAIL_MODE=open`` restores the legacy permissive behaviour for
dev/staging.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import openai

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModerationResult:
    """Result of an OpenAI moderation check.

    Attributes:
        flagged: True if any category was flagged.
        categories: Category names that were flagged (empty if not flagged).
    """

    flagged: bool = False
    categories: list[str] = field(default_factory=list)


def _unavailable_result() -> ModerationResult:
    """Build the result returned when moderation cannot be performed.

    In ``closed`` mode (default, K-12 safety) return ``flagged=True`` with a
    distinctive category so callers can render an outage-specific message.
    In ``open`` mode return an unflagged result — the legacy behaviour.
    """
    if settings.moderation_fail_mode == "closed":
        return ModerationResult(flagged=True, categories=["moderation_unavailable"])
    return ModerationResult()


async def moderate(text: str) -> ModerationResult:
    """Check text against the OpenAI moderation API.

    Fail-mode is controlled by ``settings.moderation_fail_mode``:
      - ``"closed"`` (default): on missing key or API error, return
        ``flagged=True, categories=["moderation_unavailable"]``.
      - ``"open"``: on missing key or API error, return an unflagged result
        (legacy behaviour — suitable only for dev/staging).
    Empty / whitespace-only input always returns unflagged.
    """
    if not text or not text.strip():
        return ModerationResult()
    if not settings.openai_api_key:
        logger.warning(
            "OPENAI_API_KEY missing; moderation in fail-%s mode",
            settings.moderation_fail_mode,
        )
        return _unavailable_result()

    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key, timeout=5.0)
        response = await client.moderations.create(
            model="omni-moderation-latest",
            input=text,
        )
        if not response.results:
            return ModerationResult()
        result = response.results[0]
        categories_obj = getattr(result, "categories", None)
        flagged_categories: list[str] = []
        if categories_obj is not None:
            # Pydantic model: iterate fields. Fall back to dict.
            try:
                items = categories_obj.model_dump().items()
            except AttributeError:
                items = (
                    categories_obj.items()
                    if isinstance(categories_obj, dict)
                    else []
                )
            for name, flagged in items:
                if flagged:
                    flagged_categories.append(name)
        return ModerationResult(
            flagged=bool(getattr(result, "flagged", False)),
            categories=flagged_categories,
        )
    except (openai.APIError, openai.APITimeoutError) as e:
        logger.error(
            "Moderation API call failed (fail-%s mode): %s",
            settings.moderation_fail_mode,
            e,
        )
        return _unavailable_result()
    except Exception as e:  # defensive: unexpected errors still honour fail-mode
        logger.exception(
            "Unexpected moderation error (fail-%s mode): %s",
            settings.moderation_fail_mode,
            e,
        )
        return _unavailable_result()


# -- PII scrubbers -----------------------------------------------------------

# North-American phone: optional +1, then 10 digits with - . or space separators.
_PHONE_RE = re.compile(
    r"""
    (?<![\w])                # not preceded by word char
    (?:\+?1[\s\.-]?)?        # optional country code
    \(?\d{3}\)?              # area code (optionally parenthesised)
    [\s\.-]?                 # separator
    \d{3}                    # exchange
    [\s\.-]?                 # separator
    \d{4}                    # subscriber
    (?![\w])                 # not followed by word char
    """,
    re.VERBOSE,
)

# _EMAIL_RE intentionally matches email addresses inside URLs (mailto:, etc.)
# and free text. All matches are redacted regardless of context — this is
# a defensive PII scrubber, not a URL parser.
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+",
)

# Canadian SIN: 9 digits in 3-3-3 with - or space separators. We deliberately
# do NOT match bare 9-digit runs because that branch over-matches student IDs
# and partial phone numbers (e.g. a 9-digit substring of a 10-digit phone).
# The separator form covers the common "write out your SIN" case without
# false positives. (#4078)
_SIN_RE = re.compile(
    r"(?<!\d)\d{3}[\s-]\d{3}[\s-]\d{3}(?!\d)",
)


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Redact phone, email, and SIN from text.

    Returns the scrubbed text and a list of redaction tags, e.g.
    ["phone", "email"]. Scrub order is PHONE → SIN → EMAIL: the phone pattern
    runs first so the looser SIN 9-digit run-on regex cannot eat 9 digits of
    a phone number before the phone matcher gets a chance to redact them.
    """
    if not text:
        return text, []

    redactions: list[str] = []

    def _sub(pattern: re.Pattern[str], label: str, replacement: str, s: str) -> str:
        def _replace(_match: re.Match[str]) -> str:
            redactions.append(label)
            return replacement

        return pattern.sub(_replace, s)

    scrubbed = text
    scrubbed = _sub(_PHONE_RE, "phone", "[REDACTED_PHONE]", scrubbed)
    scrubbed = _sub(_SIN_RE, "sin", "[REDACTED_SIN]", scrubbed)
    scrubbed = _sub(_EMAIL_RE, "email", "[REDACTED_EMAIL]", scrubbed)

    return scrubbed, redactions
