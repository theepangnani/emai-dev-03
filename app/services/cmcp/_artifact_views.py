"""Shared artifact-summary projectors for CB-CMCP-001 surfaces (#4701).

Single source of truth for "what fields are public for a CMCP artifact"
across MCP ``list_catalog`` (M2-B 2B-3 / #4554), REST ``board_catalog``
(M3-E 3E-1 / #4653), the teacher review queue (M3-A 3A-1 / #4576), and
Bridge cards (M3-C 3C-4). Per-surface stripes can wrap with extras
(e.g. the review queue adds ``user_id`` + ``requested_persona``) but the
common base set is defined here so the public summary shape can't drift
between surfaces.

Why a single projector
----------------------
Three surfaces previously projected ``StudyGuide`` rows independently:

- ``list_catalog._row_to_summary``  → id, title, guide_type, content_type
  (alias), state, subject_code, grade, se_codes, course_id, created_at.
- ``board_catalog._row_to_artifact`` → id, title, content_type only,
  state, subject_code, grade, se_codes, alignment_score, ai_engine,
  course_id, created_at.
- ``cmcp_review._to_queue_item`` → id, title, guide_type, state,
  course_id, user_id, se_codes, requested_persona, created_at (richer
  shape — review queue's audit needs).

A client hitting both MCP ``list_catalog`` and REST ``board_catalog``
for the "same artifact" got two different shapes. ``alignment_score``
was REST-only. Future drift risk was high; surfaces were copy-pasting
``_se_subject`` + ``_se_grade`` helpers across modules.

This module owns the canonical projection. Surfaces import + use it.
The review queue keeps its richer shape (it has surface-specific extras
like ``requested_persona`` and ``user_id``) but is free to *wrap* the
common projector when the M3-A schema can absorb the extra fields.

Design notes
------------
- ``cmcp_artifact_summary_v1`` returns the full common field set,
  including ``alignment_score`` and ``ai_engine``. Surfaces that do
  *not* want a particular field can drop it from the dict. This avoids
  the prior pattern where ``alignment_score`` was REST-only by accident
  rather than by design.
- ``content_type`` is included as an alias for ``guide_type`` so MCP-
  spec consumers (which use the ``content_type`` name) and direct-DB
  consumers (which use ``guide_type``) both find the field they expect.
- ``grade`` is parsed from the SE-code prefix because the
  ``study_guides`` table has no dedicated grade column today (M3+ may
  add one). The ``hasattr(row, "grade")`` branch is forward-compat.
- ``se_codes`` is always a list (never ``None``) — surface envelopes
  validate against ``list[str]`` and the empty list is the meaningful
  "no codes attached" signal.

Versioning
----------
The function is named ``..._v1`` so a future shape change can ship a
``..._v2`` and let surfaces migrate independently. Today's contract:
the v1 dict shape MUST NOT change without bumping the version (and
auditing every call-site). New optional fields are additive.
"""
from __future__ import annotations

from typing import Any


def _se_subject(se_codes: Any) -> str | None:
    """Best-effort subject prefix from the first SE code.

    Ontario SE codes are namespaced ``<SUBJECT>.<GRADE>.<STRAND>.<...>``
    (e.g. ``MATH.5.A.1``); the prefix before the first ``.`` is the
    canonical subject code. Returns ``None`` when the row carries no SE
    codes — non-CMCP study-guide rows fall here, which is fine because
    the response field is informational only (the list filter still
    works through the explicit ``subject_code`` filter on the query).

    Hoisted here from :mod:`app.mcp.tools.list_catalog` so both MCP and
    REST surfaces share one implementation.
    """
    if not se_codes:
        return None
    try:
        first = se_codes[0]
    except (IndexError, TypeError):
        return None
    if not isinstance(first, str) or "." not in first:
        return None
    return first.split(".", 1)[0].upper()


def _se_grade(se_codes: Any) -> int | None:
    """Best-effort grade integer from the first SE code.

    Ontario SE codes are namespaced ``<SUBJECT>.<GRADE>.<STRAND>.<...>``;
    the second segment is the grade. Returns ``None`` when the row has
    no SE codes, the second segment isn't an integer, or the row's
    schema doesn't expose a parseable code. Used by the Python-side
    ``grade`` post-filter in :func:`list_catalog` because the
    ``study_guides`` table has no dedicated ``grade`` column today (it's
    embedded in the SE code; M3+ may add a real column).

    Hoisted here from :mod:`app.mcp.tools.list_catalog` so both MCP and
    REST surfaces share one implementation.
    """
    if not se_codes:
        return None
    try:
        first = se_codes[0]
    except (IndexError, TypeError):
        return None
    if not isinstance(first, str):
        return None
    parts = first.split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def cmcp_artifact_summary_v1(row: Any) -> dict[str, Any]:
    """Common public summary projection for a ``StudyGuide`` artifact row.

    Parameters
    ----------
    row:
        A ``StudyGuide`` ORM row (or any object that quacks like one —
        ``SimpleNamespace`` works for tests). Must expose: ``id``,
        ``title``, ``guide_type``, ``state``, ``se_codes``,
        ``alignment_score``, ``ai_engine``, ``course_id``, ``created_at``.

    Returns
    -------
    dict
        A dict with the common public fields. ``content_type`` is an
        alias of ``guide_type`` for MCP-spec consumers; ``subject_code``
        and ``grade`` are derived from ``se_codes`` if present.
        ``alignment_score`` is coerced to ``float`` (not ``Decimal``) so
        the JSON response is a plain number. ``se_codes`` is always a
        list (never ``None``).

    Notes
    -----
    Surfaces that don't want a field can drop it post-projection. The
    review queue (which has surface-specific extras like
    ``user_id`` + ``requested_persona``) is free to wrap this and add
    fields on top.
    """
    # ``alignment_score`` and ``ai_engine`` are only populated on
    # CMCP-pipeline rows; non-CMCP study guides (the catalog reuses the
    # ``study_guides`` table per D2=B) and test fakes may omit them
    # entirely. ``getattr`` with a ``None`` default keeps the projector
    # tolerant of both shapes.
    alignment = getattr(row, "alignment_score", None)
    if alignment is not None:
        # ``alignment_score`` is stored as Numeric — coerce to float so
        # the JSON response is a plain number, not a Decimal string.
        alignment = float(alignment)
    ai_engine = getattr(row, "ai_engine", None)

    # Forward-compat: prefer a real ``grade`` column when the schema
    # exposes one (M3+); otherwise fall back to the SE-code prefix.
    grade_attr = getattr(row, "grade", None)
    if grade_attr is not None:
        grade = grade_attr
    else:
        grade = _se_grade(row.se_codes)

    return {
        "id": row.id,
        "title": row.title,
        "guide_type": row.guide_type,
        "content_type": row.guide_type,  # alias for MCP-spec consumers
        "state": row.state,
        "subject_code": _se_subject(row.se_codes),
        "grade": grade,
        "se_codes": list(row.se_codes) if row.se_codes else [],
        "alignment_score": alignment,
        "ai_engine": ai_engine,
        "course_id": row.course_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


__all__ = [
    "cmcp_artifact_summary_v1",
    "_se_subject",
    "_se_grade",
]
