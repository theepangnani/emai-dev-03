"""CB-DCI-001 — single source of truth for the kid-facing subject enum.

The classifier (M0-3) restricts ``subject`` to a fixed enum in its system
prompt. The kid-correction PATCH endpoint (M0-4) and the summary
aggregator (M0-6) must validate against the SAME set so downstream
consumers (per-subject streaks, board dashboards) never see fragmented
values like ``"maths"`` / ``"english class"`` / ``"MATH"``.

This module owns the canonical set + a small validator helper. Both
``app/api/routes/dci.py`` (PATCH endpoint) and
``app/services/dci_summary_service.py`` import from here.

Closes #4187.
"""
from __future__ import annotations

# Canonical subject enum — must match the classifier system prompt
# (`app/services/dci_classifier.py` once M0-3 lands). Order is alphabetic
# except "Other" sinks to the end as a deliberate catch-all.
DCI_VALID_SUBJECTS: frozenset[str] = frozenset({
    "Math",
    "Science",
    "English",
    "History",
    "Geography",
    "Art",
    "Music",
    "French",
    "Phys-Ed",
    "Other",
})


def validate_subject(subject: str | None) -> str | None:
    """Return the subject if it matches the canonical enum, else ``None``.

    Use this in:
      * ``CorrectRequest.subject`` validation (M0-4 PATCH endpoint) — reject
        free-form values like ``"maths"`` or ``"MATH"`` before they hit the
        DB.
      * Summary aggregation guards (M0-6) when ingesting kid-corrected
        rows from older data that pre-dates the validator.

    Args:
        subject: User-supplied subject string (or ``None``).

    Returns:
        The canonical subject string if valid, ``None`` if the input is
        ``None`` or fails the enum check. Callers decide whether ``None``
        means "skip update" (PATCH path) or "drop bullet" (aggregator).
    """
    if subject is None:
        return None
    s = subject.strip()
    if not s:
        return None
    return s if s in DCI_VALID_SUBJECTS else None


# Common kid-typed variants that should map to a canonical subject.
# Keys are lower-cased + whitespace-trimmed; values must be in
# ``DCI_VALID_SUBJECTS``. Keep the list short and obvious — anything
# ambiguous should fall through to ``None`` so the kid can re-pick.
_SUBJECT_ALIASES: dict[str, str] = {
    # Math
    "math": "Math",
    "maths": "Math",
    "mathematics": "Math",
    # Science
    "science": "Science",
    "sci": "Science",
    # English
    "english": "English",
    "reading": "English",
    "language arts": "English",
    "ela": "English",
    # History / Social Studies
    "history": "History",
    "social studies": "History",
    "socials": "History",
    # Geography
    "geography": "Geography",
    "geo": "Geography",
    # Art
    "art": "Art",
    "arts": "Art",
    # Music
    "music": "Music",
    # French
    "french": "French",
    "francais": "French",
    "français": "French",
    # Phys-Ed
    "phys ed": "Phys-Ed",
    "phys-ed": "Phys-Ed",
    "physed": "Phys-Ed",
    "physical education": "Phys-Ed",
    "gym": "Phys-Ed",
    "pe": "Phys-Ed",
    # Other
    "other": "Other",
}


# Case-folded lookup of the canonical enum so coerce_subject can match
# kid-typed casings (``"MATH"``, ``"english"``) without going through
# locale-sensitive ``str.title()`` (which mangles apostrophes and varies
# by Python build — see #4276).
_CANONICAL_BY_CASEFOLD: dict[str, str] = {
    s.casefold(): s for s in DCI_VALID_SUBJECTS
}


def coerce_subject(subject: str | None) -> str | None:
    """Alias-map + case-fold a kid-typed subject, then strict-validate.

    Use this on user-supplied input paths (e.g. the M0-4 PATCH endpoint)
    so kid corrections like ``"math"``, ``"ENGLISH"``, ``"sci"``, or
    ``"phys ed"`` normalise to the canonical enum instead of returning
    ``None`` from ``validate_subject``.

    Lookup order:
      1. Explicit ``_SUBJECT_ALIASES`` (lower-cased keys) — covers
         ``"maths"``, ``"sci"``, ``"gym"``, ``"français"`` etc.
      2. Case-fold match against ``DCI_VALID_SUBJECTS`` — covers
         ``"MATH"`` / ``"math"`` / ``"Math"`` for canonical names that
         aren't in the alias map.
      3. Otherwise ``None`` (kid re-picks).

    Note: this avoids ``str.title()`` because it is locale-sensitive in
    some Python builds and mishandles apostrophes (e.g. ``"l'art"`` →
    ``"L'Art"``), which would silently miss any future apostrophe-bearing
    alias. See #4276.

    Args:
        subject: User-supplied subject string (or ``None``).

    Returns:
        The canonical subject string if it matches an alias or already
        matches the canonical enum (case-insensitive); otherwise ``None``.
    """
    if subject is None:
        return None
    s = subject.strip()
    if not s:
        return None
    key = s.lower()
    canonical = _SUBJECT_ALIASES.get(key)
    if canonical is None:
        canonical = _CANONICAL_BY_CASEFOLD.get(s.casefold())
    return canonical  # already in DCI_VALID_SUBJECTS or None
