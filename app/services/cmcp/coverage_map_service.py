"""CB-CMCP-001 M3-E 3E-2 (#4654) — strand × content-count coverage map.

Service-layer aggregator that returns a strand-by-strand artifact-count
coverage map for one board. Backs:

- The coverage heatmap UI (3H-1).
- The signed CSV export (3E-3).

Design notes
============

Strand extraction
-----------------
The ``study_guides`` table has no ``strand_id`` FK today (per locked
decision D2=B, M1+ keeps the legacy artifact table and stamps a small
set of curriculum-aware columns). Strand identity is therefore lifted
from the first SE code on each artifact:

    Ontario SE codes are namespaced ``<SUBJECT>.<GRADE>.<STRAND>.<...>``
    (e.g. ``MATH.5.A.1``).

Segment indices:
    [0] subject  [1] grade  [2] strand  [3+] specific-expectation tail

This mirrors :func:`app.mcp.tools.list_catalog._se_subject` and
:func:`app.mcp.tools.list_catalog._se_grade` — both shipped helpers that
already lift subject + grade off ``se_codes[0]``. Adding strand here
keeps one decode site for SE-code structure rather than re-implementing
parsing in the heatmap UI / CSV export downstream.

Cross-board isolation
---------------------
Filtered by ``StudyGuide.board_id == str(board_id)``. Rows with
``board_id IS NULL`` (legacy / non-board-stamped artifacts) are
*excluded* — board admins do NOT see unscoped rows in their coverage
map. This matches the ``_visibility.py`` deny-on-NULL pattern used by
:mod:`app.mcp.tools.get_artifact` and :mod:`app.mcp.tools.list_catalog`.

Empty strands
-------------
Strands with zero APPROVED artifacts simply don't appear in the result
dict — callers that want a "show every strand even if 0" view can
overlay the strand list separately. Returning an empty dict on a board
with no APPROVED rows is the documented contract (NOT an error).

Out of scope
------------
- A "show every strand even if 0" auto-enumeration (UI overlay job).
- Per-grade rollups beyond the strand×grade matrix (CSV export does
  its own re-shaping).
- Caching — coverage maps are O(approved-artifact-count) for one
  board; the heatmap UI is the only caller and it'll re-issue on its
  own SWR cycle. Cache layer can land in M4 if profiling motivates it.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models.study_guide import StudyGuide
from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)


# Type alias: ``dict[strand_code, dict[grade, count]]``. Strand codes are
# whatever the SE-code third segment is (typically a single uppercase
# letter on Ontario boards: "A", "B", "C", ...). Grades are integers.
CoverageMap = dict[str, dict[int, int]]


def _extract_strand_and_grade(
    se_codes: Any,
) -> tuple[str | None, int | None]:
    """Lift ``(strand_code, grade)`` off the first SE code.

    Returns ``(None, None)`` when the row carries no SE codes, the
    first entry isn't a string, or the namespaced shape is malformed
    (fewer than 3 dotted segments, or the grade segment isn't an int).

    Defensive on every step — the JSON column is loosely typed and a
    legacy / non-CMCP row may have a non-string entry. We never want
    aggregation to crash on a single misshapen row; it simply skips.
    """
    if not se_codes:
        return None, None
    try:
        first = se_codes[0]
    except (IndexError, TypeError):
        return None, None
    if not isinstance(first, str):
        return None, None
    parts = first.split(".")
    if len(parts) < 3:
        return None, None
    try:
        grade = int(parts[1])
    except ValueError:
        return None, None
    strand = parts[2].strip()
    if not strand:
        return None, None
    return strand, grade


def compute_coverage_map(
    board_id: int | str, db: Session
) -> CoverageMap:
    """Compute a strand × grade × count coverage map for one board.

    Counts APPROVED artifacts (``StudyGuide.state == 'APPROVED'``)
    grouped by ``(strand, grade)`` and pivots the result into the
    nested-dict shape ``{strand: {grade: count}}``.

    Parameters
    ----------
    board_id:
        The target board's identifier. Accepted as ``int`` (3E-1 REST
        path param shape) OR ``str`` — the underlying
        ``study_guides.board_id`` column is ``String(50)`` and stamped
        from :func:`app.mcp.tools._visibility.resolve_caller_board_id`,
        which today returns whatever string the User row carries. We
        coerce to ``str`` for the SQL filter so both call shapes work
        through one entry point.
    db:
        SQLAlchemy session bound to the request transaction.

    Returns
    -------
    dict[str, dict[int, int]]
        Nested mapping ``{strand_code: {grade: count}}``. Empty when
        the board has no APPROVED rows or every row's SE code is
        malformed. Strands with zero matches simply don't appear —
        callers that want a fully-enumerated heatmap should overlay
        the strand list themselves.

    Cross-board isolation
    ---------------------
    The query filters strictly on ``board_id == str(board_id)``. Rows
    with ``board_id IS NULL`` are excluded — board admins never see
    unscoped artifacts in their coverage. This matches the
    deny-on-NULL pattern used by ``_visibility.py``-driven MCP tools.
    """
    if board_id is None:
        # Defensive guard — callers that pass ``None`` would otherwise
        # match every NULL ``board_id`` row, which is exactly the
        # cross-board leak this service exists to prevent. Log + return
        # empty so the heatmap UI shows "no coverage" rather than
        # erroring on an unauthenticated path.
        logger.warning(
            "coverage_map_service called with board_id=None; "
            "returning empty map"
        )
        return {}

    board_id_str = str(board_id)

    rows = (
        db.query(StudyGuide.se_codes)
        .filter(
            StudyGuide.archived_at.is_(None),
            StudyGuide.state == ArtifactState.APPROVED,
            StudyGuide.board_id == board_id_str,
        )
        .all()
    )

    # ``defaultdict(lambda: defaultdict(int))`` would let us drop the
    # ``setdefault`` dance, but we want to return a plain ``dict`` (not
    # a defaultdict) so the caller's serialization path can't accidentally
    # mutate the structure by lookup. Build with regular dict and the
    # ``setdefault`` idiom.
    result: CoverageMap = {}

    for (se_codes,) in rows:
        strand, grade = _extract_strand_and_grade(se_codes)
        if strand is None or grade is None:
            continue
        result.setdefault(strand, {})
        result[strand][grade] = result[strand].get(grade, 0) + 1

    logger.info(
        "cmcp.coverage_map.computed board_id=%s strands=%s rows=%s",
        board_id_str,
        len(result),
        len(rows),
        extra={
            "event": "cmcp.coverage_map.computed",
            "board_id": board_id_str,
            "strands": len(result),
            "rows": len(rows),
        },
    )

    return result


__all__ = ["CoverageMap", "compute_coverage_map"]
