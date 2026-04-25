"""DCI content-policy v0 (CB-DCI-001 M0-7).

Runs against every AI-generated parent summary BEFORE it is written to
``ai_summaries``. v0 is regex + keyword (NOT a trained ML classifier —
that is fast-follow #4149). The single public entry point is
:func:`check`.

Design tenets
-------------
- **Fail-safe.** The check returns a ``redacted_text`` whenever the only
  problems are deterministically-rewritable PII patterns. For everything
  else (named other-kid, medical, legal) the summary is fully blocked
  and the caller is expected to either retry the model with a redaction
  prompt or fall back to neutral copy.
- **Stateless.** This module performs NO database I/O. The caller (the
  M0-6 summary generator) is responsible for writing the audit row via
  :func:`audit_service.log_action`. We provide :func:`audit_block` as a
  thin convenience wrapper so every call site logs the same shape.
- **Cheap.** All regex patterns are pre-compiled in
  ``dci_policy_rules``. A typical 300-word summary checks in well under
  10 ms.

Result schema
-------------
``check`` returns a plain dict with three keys:

- ``allowed``        : ``True`` when the summary is safe to ship as-is
  OR safe after applying ``redacted_text``. ``False`` means the caller
  must NOT show the input to the parent.
- ``blocked_rules``  : list of rule identifiers that fired. Empty when
  ``allowed=True`` and nothing was redacted. Always populated when
  ``allowed=False``. Examples: ``"pii_phone"``, ``"named_other_kid"``,
  ``"medical_keyword"``, ``"legal_keyword"``.
- ``redacted_text``  : a rewritten version of ``text`` with PII tokens
  replaced by ``[REDACTED_*]`` placeholders. Populated whenever PII was
  found, regardless of whether non-PII rules also fired. ``None`` when
  no rule fired.

Caller protocol
---------------
::

    result = dci_content_policy.check(text=summary, family_kid_names=["Aanya", "Veer"])
    if result["allowed"]:
        # ship as-is OR ship result["redacted_text"] if present
        text_to_store = result["redacted_text"] or summary
    else:
        # 1. retry Sonnet with a redaction prompt and re-check
        # 2. if STILL blocked, store policy_blocked=True + raw to
        #    audit_event and surface neutral fallback copy
        dci_content_policy.audit_block(
            db, parent_id=parent.id, summary_id=ai_summary.id,
            blocked_rules=result["blocked_rules"], raw=summary,
        )
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, TypedDict

from sqlalchemy.orm import Session

from app.services import audit_service
from app.services.dci_policy_rules import (
    LEGAL_KEYWORDS,
    MEDICAL_KEYWORDS,
    PII_PATTERNS,
)

logger = logging.getLogger(__name__)


class PolicyResult(TypedDict):
    allowed: bool
    blocked_rules: list[str]
    redacted_text: str | None


# ---------------------------------------------------------------------------
# Named-other-kid detection
# ---------------------------------------------------------------------------

# School-context anchor words: a capitalised first-name token only counts
# as a "named other kid" when it appears near one of these words. This is
# the v0 precision lever — without it, every "Maple Street" or "Aunt Mary"
# would trip the detector.
_SCHOOL_CONTEXT_WORDS: frozenset[str] = frozenset({
    "class", "classmate", "classmates", "school", "teacher", "student",
    "students", "kid", "kids", "friend", "friends", "playground",
    "recess", "lunch", "group", "team", "partner", "partners",
    "buddy", "buddies", "peer", "peers", "desk", "table",
})

# A "name-shaped" capitalised token: starts with uppercase, then 1-19
# more chars (lower/upper/apostrophe/hyphen) AND must contain at least
# one lowercase letter. The lowercase requirement is what excludes
# all-caps acronyms ("SIN", "OCD", "REDACTED") that would otherwise
# read as 3-letter names. Catches 2-letter names ("Bo", "Al", "Mo"),
# internal caps ("DeShawn", "MacKenzie"), and apostrophe/hyphen names
# ("O'Brien", "Anne-Marie"). We exclude common sentence-start
# uppercased words via the stop list below to keep precision high.
_NAME_TOKEN_RE = re.compile(r"\b([A-Z][A-Za-z'\-]{1,19})\b")


def _is_name_shaped(token: str) -> bool:
    """True iff token is name-shaped: uppercase lead + at least one lowercase."""
    if not _NAME_TOKEN_RE.fullmatch(token):
        return False
    # All-caps acronyms ("SIN", "PTSD", "REDACTED") have no lowercase.
    return any(c.islower() for c in token)

# Common false-positive words that look like names at sentence start.
# The v0 list is short on purpose; ML classifier widens this.
_NAME_STOPLIST: frozenset[str] = frozenset({
    "Today", "Tomorrow", "Yesterday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday", "January", "February",
    "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "Math", "Science", "English",
    "History", "Geography", "French", "Spanish", "Art", "Music",
    "Reading", "Writing", "Spelling", "Recess", "Lunch", "School",
    "Class", "Teacher", "Student", "Mr", "Mrs", "Ms", "Miss", "Dr",
    "Mom", "Dad", "Mum", "Mama", "Papa", "Grandma", "Grandpa",
    "The", "This", "That", "These", "Those", "There", "Then", "When",
    "Where", "What", "Why", "How", "Who", "Which", "While", "After",
    "Before", "During", "Their", "They", "Them", "She", "He", "His",
    "Her", "Hers", "Him", "Our", "Ours", "Your", "Yours", "Its",
    "Tonight", "Morning", "Afternoon", "Evening", "Night",
})


def _detect_named_other_kid(text: str, family_kid_names: Iterable[str]) -> list[str]:
    """Return a list of name tokens that look like other kids.

    A token qualifies when:
      1. It matches the capitalised name pattern.
      2. It is NOT in the family's own kid-name set (case-insensitive).
      3. It is NOT in the broad stoplist of common capitalised words.
      4. It is NOT a sentence-start capitalisation (which catches verbs
         like "Call" and "Visit" that look name-shaped only because they
         lead a sentence).
      5. It appears within 5 tokens of a school-context anchor word
         (so "Aanya's classmate Priya cried" trips, but "We learned
         about Mars" does not).
    """
    if not text:
        return []

    family_lc: set[str] = {n.strip().lower() for n in family_kid_names if n and n.strip()}

    # Tokenize while tracking whether each token starts a new sentence.
    # A token is "sentence-initial" when it's the first token OR is
    # immediately preceded (after stripping whitespace) by '.', '!', or '?'.
    raw_tokens: list[tuple[str, bool]] = []  # (token, is_sentence_initial)
    is_initial_next = True
    # Word tokens may include internal apostrophes / hyphens so names like
    # "O'Brien" and "Anne-Marie" stay one token. Sentence terminators are
    # tracked separately to drive ``is_sentence_initial``.
    for match in re.finditer(r"[A-Za-z][A-Za-z'\-]*|[.!?]", text):
        tok = match.group(0)
        if tok in (".", "!", "?"):
            is_initial_next = True
            continue
        raw_tokens.append((tok, is_initial_next))
        is_initial_next = False

    if not raw_tokens:
        return []

    tokens = [t for t, _ in raw_tokens]
    token_lc = [t.lower() for t in tokens]
    school_indices = [
        i for i, t in enumerate(token_lc) if t in _SCHOOL_CONTEXT_WORDS
    ]
    if not school_indices:
        return []

    flagged: list[str] = []
    seen: set[str] = set()
    for i, (raw, sentence_initial) in enumerate(raw_tokens):
        if not _is_name_shaped(raw):
            continue
        # Normalise possessive ("Aanya's" -> "Aanya") for both stoplist
        # and family-whitelist comparisons. The display token (``raw``)
        # keeps its original form for the flagged list.
        bare = raw[:-2] if raw.lower().endswith("'s") else raw
        if bare in _NAME_STOPLIST:
            continue
        if bare.lower() in family_lc:
            continue
        if sentence_initial:
            # Sentence-start capitalisation is too noisy in v0 — common
            # imperatives ("Call", "Visit") trip the detector. Skip.
            continue
        # within 5 tokens of any school-context word?
        if not any(abs(i - j) <= 5 for j in school_indices):
            continue
        if raw in seen:
            continue
        seen.add(raw)
        flagged.append(raw)
    return flagged


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

_PII_REPLACEMENT = {
    "pii_sin": "[REDACTED_SIN]",
    "pii_phone": "[REDACTED_PHONE]",
    "pii_email": "[REDACTED_EMAIL]",
    "pii_address": "[REDACTED_ADDRESS]",
}


def _scrub_pii(text: str) -> tuple[str, list[str]]:
    """Apply every PII pattern; return scrubbed text + fired rule names.

    Order matters: phone runs FIRST so a string like ``"416-555-1234"``
    is labelled ``pii_phone`` rather than the looser SIN pattern (which
    also accepts 3-3-3 digit groups). SIN runs SECOND to catch the
    no-separator 9-digit form. Address runs THIRD so its multi-word
    capture cannot include a token already replaced by ``[REDACTED_*]``.
    Email runs LAST because the ``@`` anchor makes it the most specific
    pattern and order does not change its match set.
    """
    fired: list[str] = []
    scrubbed = text
    for rule in ("pii_phone", "pii_sin", "pii_address", "pii_email"):
        pattern = PII_PATTERNS[rule]
        if pattern.search(scrubbed):
            fired.append(rule)
            scrubbed = pattern.sub(_PII_REPLACEMENT[rule], scrubbed)
    return scrubbed, fired


# ---------------------------------------------------------------------------
# Keyword detection
# ---------------------------------------------------------------------------

def _find_keyword(text: str, keywords: Iterable[str]) -> str | None:
    """Return the first keyword that matches as a case-insensitive substring."""
    if not text:
        return None
    lower = text.lower()
    for kw in keywords:
        if kw.lower() in lower:
            return kw
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Defensive cap: Sonnet output is bounded to ~16KB in practice, but a
# pathological caller could feed us a megabyte of text. The check still
# runs, but we hard-truncate first so regex backtracking stays bounded.
_MAX_INPUT_CHARS: int = 64_000


def check(text: str, family_kid_names: list[str]) -> PolicyResult:
    """Run the full v0 policy check against an AI-generated summary.

    Args:
        text: The candidate summary text. May be empty/None-ish.
        family_kid_names: First names of every kid attached to the
            parent account. Used to whitelist them in the
            named-other-kid detector. Pass an empty list if unknown
            (the detector will then flag any school-context name).

    Returns:
        A :class:`PolicyResult` dict. See module docstring for shape.
    """
    if text is None:
        text = ""
    if len(text) > _MAX_INPUT_CHARS:
        text = text[:_MAX_INPUT_CHARS]

    blocked_rules: list[str] = []

    # 1. PII — these are deterministically redactable. We scrub first so
    #    later rules see the cleaned text (unlikely to matter but tidy).
    scrubbed, pii_fired = _scrub_pii(text)
    blocked_rules.extend(pii_fired)
    redacted_text: str | None = scrubbed if pii_fired else None

    # 2. Medical keywords — block, no auto-redact.
    medical_hit = _find_keyword(scrubbed, MEDICAL_KEYWORDS)
    if medical_hit is not None:
        blocked_rules.append("medical_keyword")

    # 3. Legal keywords — block, no auto-redact.
    legal_hit = _find_keyword(scrubbed, LEGAL_KEYWORDS)
    if legal_hit is not None:
        blocked_rules.append("legal_keyword")

    # 4. Named other kid — block, no auto-redact.
    named_kids = _detect_named_other_kid(scrubbed, family_kid_names)
    if named_kids:
        blocked_rules.append("named_other_kid")

    # PII alone is redactable → allowed=True with redacted_text. Any
    # non-PII rule firing is fail-closed.
    non_pii_fired = (
        medical_hit is not None
        or legal_hit is not None
        or bool(named_kids)
    )
    allowed = not non_pii_fired

    if not allowed:
        logger.info(
            "dci.policy.blocked rules=%s named_kids=%s",
            blocked_rules,
            named_kids,
        )

    return PolicyResult(
        allowed=allowed,
        blocked_rules=blocked_rules,
        redacted_text=redacted_text,
    )


def audit_block(
    db: Session,
    *,
    parent_id: int | None,
    summary_id: int | None,
    blocked_rules: list[str],
    raw: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Convenience wrapper: write a ``dci_policy_block`` row to ``audit_logs``.

    Every M0-6 summary generator call site that hits a hard block (i.e.
    ``allowed=False`` even after the redaction-prompt retry) MUST call
    this so the incident is captured for the MFIPPA / Bill 194 audit
    trail.
    """
    details: dict[str, Any] = {
        "blocked_rules": blocked_rules,
        # Truncate raw so the audit row stays bounded; the full raw
        # summary lives on ``ai_summaries.summary_json`` with
        # ``policy_blocked=True``.
        "raw_excerpt": (raw or "")[:500],
    }
    if extra:
        # Protect canonical fields — a buggy caller passing ``extra``
        # must not be able to overwrite the audit-trail evidence.
        _protected = {"blocked_rules", "raw_excerpt"}
        for k, v in extra.items():
            if k in _protected:
                logger.warning(
                    "dci.policy.audit_block: ignoring protected key %r in extra", k
                )
                continue
            details[k] = v
    audit_service.log_action(
        db,
        user_id=parent_id,
        action="dci_policy_block",
        resource_type="ai_summary",
        resource_id=summary_id,
        details=details,
    )


__all__ = ["check", "audit_block", "PolicyResult"]
