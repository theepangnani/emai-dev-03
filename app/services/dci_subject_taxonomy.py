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
