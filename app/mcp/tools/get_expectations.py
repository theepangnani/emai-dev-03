"""MCP tool: ``get_expectations`` — read-only CEG expectations lookup.

CB-CMCP-001 M2-B 2B-1 (#4552) — wraps the M0-B
``GET /api/curriculum/{course_code}`` REST surface for MCP clients.

Returns the Ontario curriculum's specific-expectation (SE) rows for a
given subject + grade slice, optionally narrowed to a single strand.
The shape is the *flat* list MCP clients expect (one row per SE), not
the strand-grouped tree the REST endpoint returns — grouping is a
presentation concern that doesn't make sense at the tool surface.

Catalog semantics, not lookup semantics
---------------------------------------
Unknown ``(subject_code, grade)`` combos return ``{"expectations": []}``
rather than 404. Rationale: the MCP transport is a read-only catalog
browse surface for LLM clients; "no rows match these filters" is a
valid result, not an error. The REST ``GET /api/curriculum/{code}``
endpoint returns 404 because it's a noun-style lookup ("show me MATH")
and 404 is the correct verdict when MATH is unseeded; here the noun is
"expectations" and an empty list is the correct verdict when the
filters select zero rows. This matches the precedent set by 2B-3
``list_catalog`` (also planned to return empty arrays for empty
filters).

Filtering
---------
``review_state == "accepted"`` AND ``active is True`` are applied
unconditionally — pending / rejected rows must never leak through MCP
even if they're somehow visible elsewhere. Same gate the REST surface
uses (see ``app/api/routes/curriculum.py`` ``_load_course_expectations``).

Why SE-only
-----------
The 2B-1 issue spec asks for "SE list filtered by subject_code + grade
+ optional strand_code". OE rows are surfaced separately by the
guardrail engine (``_load_oes_and_ses``), and a mixed OE+SE list is
ambiguous to consume on the MCP side (the tree relationship is lost).
LLM clients that want the OE→SE tree can call back into the REST
endpoint until a future stripe surfaces a richer ``get_curriculum``
tool.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_expectations_handler(
    arguments: Mapping[str, Any],
    current_user: Any,
    db: Session,
) -> dict[str, Any]:
    """Dispatch entry for the ``get_expectations`` MCP tool.

    Reads from ``CEGSubject``/``CEGStrand``/``CEGExpectation`` directly.
    Returns ``{"expectations": [...]}`` where each row carries
    ``se_code`` (Ontario ministry code), ``expectation_text`` (the
    description), ``topic`` (currently aliased to the SE description —
    the CEG schema doesn't yet carry a separate topic dimension; this
    keeps the response shape stable for when M3 adds one),
    ``strand_code``, and ``strand_name``.

    JSON Schema validation upstream (in the route layer) ensures
    ``subject_code`` is a string and ``grade`` is an integer; this
    handler additionally tolerates ``arguments`` being missing keys
    when called directly from unit tests by short-circuiting to an
    empty result.
    """
    # Lazy imports keep this module importable without dragging in the
    # SQLAlchemy model layer at module load — same pattern as 2B-2's
    # ``get_artifact`` handler.
    from app.models.curriculum import (
        EXPECTATION_TYPE_SPECIFIC,
        CEGExpectation,
        CEGStrand,
        CEGSubject,
    )

    # Argument validation. The route layer's Pydantic + JSON Schema
    # validation already enforces the shape for HTTP callers, but
    # direct-handler unit tests can pass anything. We coerce empty /
    # missing values to an empty result rather than raising — matches
    # catalog semantics (see module docstring).
    subject_code_raw = arguments.get("subject_code") if arguments else None
    grade_raw = arguments.get("grade") if arguments else None

    if not isinstance(subject_code_raw, str) or not subject_code_raw.strip():
        return {"expectations": []}
    if not isinstance(grade_raw, int) or isinstance(grade_raw, bool):
        # ``bool`` is a subclass of ``int`` — explicit reject so
        # ``True``/``False`` doesn't silently become a grade-1/0 query.
        return {"expectations": []}

    subject_code = subject_code_raw.strip().upper()
    grade = grade_raw

    strand_code_raw = arguments.get("strand_code") if arguments else None
    strand_code: str | None = None
    if isinstance(strand_code_raw, str) and strand_code_raw.strip():
        strand_code = strand_code_raw.strip().upper()

    # Build the query. We always filter to SE rows + accepted + active,
    # mirroring the REST surface's gates. Joining strand + subject up
    # front lets us populate ``strand_code`` / ``strand_name`` in the
    # response without per-row N+1 lookups.
    query = (
        db.query(
            CEGExpectation,
            CEGStrand.code.label("strand_code"),
            CEGStrand.name.label("strand_name"),
        )
        .join(CEGStrand, CEGExpectation.strand_id == CEGStrand.id)
        .join(CEGSubject, CEGExpectation.subject_id == CEGSubject.id)
        .filter(
            CEGSubject.code == subject_code,
            CEGExpectation.grade == grade,
            CEGExpectation.expectation_type == EXPECTATION_TYPE_SPECIFIC,
            CEGExpectation.active.is_(True),
            CEGExpectation.review_state == "accepted",
        )
    )
    if strand_code is not None:
        query = query.filter(CEGStrand.code == strand_code)

    rows = query.order_by(
        CEGStrand.code, CEGExpectation.ministry_code
    ).all()

    expectations = [
        {
            "se_code": exp.ministry_code,
            "expectation_text": exp.description,
            # CEG schema has no separate ``topic`` column today —
            # surface the SE description so MCP consumers have a
            # stable key. When M3 adds a topic dimension this field
            # can switch to ``exp.topic`` without a breaking change.
            "topic": exp.description,
            "strand_code": s_code,
            "strand_name": s_name,
        }
        for exp, s_code, s_name in rows
    ]

    return {"expectations": expectations}


__all__ = ["get_expectations_handler"]
