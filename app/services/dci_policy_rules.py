"""Curated regex + keyword tables for DCI content-policy v0 (CB-DCI-001 M0-7).

Kept in a separate module so legal/safety reviewers can curate the lists
without touching the policy engine itself. Every entry here SHOULD be
considered a v0 starter — the long-term plan is to replace these with a
trained ML classifier (fast-follow #4149).

Categories
----------
- ``PII_PATTERNS``   : compiled regex patterns that match personally
  identifiable information (SIN, North-American phone, street address,
  email).
- ``MEDICAL_KEYWORDS`` : diagnosis-shaped phrases that the AI summary
  layer must NOT surface to a parent verbatim. Each entry is a
  case-insensitive substring match.
- ``LEGAL_KEYWORDS``  : language that pushes the system into giving
  legal advice or amplifying litigation talk between families/staff.

Capitalised-name detection lives in ``dci_content_policy`` because it
has to be parameterised by the family's own kid names.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# PII regex patterns
# ---------------------------------------------------------------------------

# Canadian Social Insurance Number: 9 digits in 3-3-3 grouping. The DCI
# policy is intentionally MORE aggressive than the generic ``safety_service``
# scrubber — DCI runs against AI-generated parent summaries, not raw user
# input, so the false-positive cost is low (we just regenerate). We accept
# both ``-`` and whitespace separators AND the unseparated 9-digit form.
SIN_PATTERN = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b")

# North-American phone: optional +1, then 10 digits with `-`, `.`, `(` or
# space separators. Mirrors the existing ``safety_service`` pattern but
# requires at least one separator inside the digits (so a bare 10-digit
# student ID won't match).
PHONE_PATTERN = re.compile(
    r"""
    (?<!\w)
    (?:\+?1[\s.\-]?)?
    \(?\d{3}\)?
    [\s.\-]
    \d{3}
    [\s.\-]?
    \d{4}
    (?!\w)
    """,
    re.VERBOSE,
)

# RFC-5322-lite email pattern. Matches inside URLs, mailto links, free text.
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9_.+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+"
)

# Street-address heuristic: <number> <Word> <street-suffix>. v0 is
# deliberately narrow (catches "123 Main Street", "45 Maple Ave."). A
# property-graph address parser is fast-follow.
_STREET_SUFFIXES = (
    "Street", "St", "Avenue", "Ave", "Road", "Rd", "Boulevard", "Blvd",
    "Drive", "Dr", "Lane", "Ln", "Court", "Ct", "Crescent", "Cres",
    "Place", "Pl", "Way", "Terrace", "Ter", "Parkway", "Pkwy",
    "Highway", "Hwy", "Trail", "Trl", "Circle", "Cir",
)
ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3}\s+"
    r"(?:" + "|".join(_STREET_SUFFIXES) + r")\b\.?",
)

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "pii_sin": SIN_PATTERN,
    "pii_phone": PHONE_PATTERN,
    "pii_email": EMAIL_PATTERN,
    "pii_address": ADDRESS_PATTERN,
}


# ---------------------------------------------------------------------------
# Medical keyword list
# ---------------------------------------------------------------------------
#
# These are diagnosis-shaped phrases that the AI summary MUST NOT use about
# a child. Matched as case-insensitive substrings. Kept short on purpose:
# v0 favours precision over recall — the ML classifier (#4149) will widen
# the net.
MEDICAL_KEYWORDS: tuple[str, ...] = (
    "ADHD",
    "autism",
    "autistic",
    "asperger",
    "anxiety disorder",
    "depression diagnosis",
    "diagnosed with depression",
    "diagnosed with",
    "medication for",
    "is medicated",
    "on medication",
    "bipolar",
    "OCD",
    "PTSD",
    "learning disability",
    "dyslexia",
    "dyscalculia",
    "dysgraphia",
    "IEP for",
    "psychiatric",
    "psychotic",
    "self-harm",
    "suicidal",
    "eating disorder",
    "anorexia",
    "bulimia",
)


# ---------------------------------------------------------------------------
# Legal keyword list
# ---------------------------------------------------------------------------
#
# These are phrases that push the system into either giving legal advice or
# amplifying litigation talk inside a family/parent context. v0 blocks the
# whole summary so a human can rewrite — the system never volunteers
# legal opinions about teachers or other families.
LEGAL_KEYWORDS: tuple[str, ...] = (
    "should sue",
    "you should sue",
    "law violation",
    "violation of law",
    "police should",
    "call the police",
    "lawyer says",
    "my lawyer",
    "file a lawsuit",
    "file a complaint with",
    "press charges",
    "human rights complaint",
    "child protective services",
    "custody battle",
    "restraining order",
)


__all__ = [
    "SIN_PATTERN",
    "PHONE_PATTERN",
    "EMAIL_PATTERN",
    "ADDRESS_PATTERN",
    "PII_PATTERNS",
    "MEDICAL_KEYWORDS",
    "LEGAL_KEYWORDS",
]
