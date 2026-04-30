"""Artifact cascade trigger for CEG version-diff substantive SE changes.

CB-CMCP-001 M3-G 3G-2 (#4662). Per locked decision D9=B: when a
``CurriculumVersion`` lands and stripe 3G-1's classifier marks one or
more of its SE rows as ``scope_substantive`` (vs ``wording_only``),
every APPROVED ``study_guides`` row pinned to one of those SEs needs
to be re-reviewed by the teacher. This service flips each affected
artifact from ``APPROVED`` → ``PENDING_REVIEW`` and writes a Bill 194
audit-log entry per artifact so the trail of "this artifact was
reflagged because SE X moved from version A to B at severity S" is
queryable forever after.

D9=B mapping:

- ``wording_only`` SE change      → no artifact transition (no-op).
- ``scope_substantive`` SE change → APPROVED artifacts referencing
                                    that SE move to ``PENDING_REVIEW``.

Stripe 3G-3 (notification) DEPENDS on this — it observes the audit
rows produced here (``action='cmcp.artifact.cascade_flagged'``) and
fans out the teacher-side notification.

Inputs (intentionally substrate-agnostic, mirroring 3G-1's classifier):

The ``version_diff`` argument is a sequence of SE-pair dicts shaped::

    {
        "old_se": <dict | None | object with cb_code/parent_oe_id/expectation_text>,
        "new_se": <dict | None | object with same fields>,
        "from_version": <str>,    # e.g., "2020-rev1"
        "to_version":   <str>,    # e.g., "2024"
    }

Each pair is fed to :func:`classify_se_change`. If the result is
``scope_substantive`` AND the SE pair has a recoverable ``cb_code``
(read from ``new_se`` first, falling back to ``old_se``), every
APPROVED ``study_guides`` row whose ``se_codes`` JSON array contains
that ``cb_code`` is transitioned and audit-logged.

Audit row contract (per 3B-1 ``log_action`` pattern):

- ``action``        = ``"cmcp.artifact.cascade_flagged"``
- ``resource_type`` = ``"study_guide"``
- ``resource_id``   = the artifact id that was reflagged
- ``user_id``       = ``None`` (system-driven cascade — no actor)
- ``details``       = ``{"se_code": str, "from_version": str,
                          "to_version": str, "severity": "scope_substantive"}``

Cross-dialect notes:

- ``study_guides.se_codes`` is JSON on SQLite, JSONB on PostgreSQL
  (gated in ``app/models/study_guide.py``). We do not push the
  contains-element predicate down to SQL (no portable JSON-array
  search across both dialects without dialect-specific helpers);
  instead we filter APPROVED rows in SQL, then check membership in
  Python. Artifact corpora are bounded by teacher review throughput
  — re-review-ready APPROVED rows for a given subject/grade slice
  are not millions, so the in-Python filter is acceptable for the
  M3-G workload.

- The ``state`` transition uses
  :class:`ArtifactStateMachine.validate_transition` to fail loudly
  if an APPROVED row is somehow not legally transitionable to
  ``PENDING_REVIEW``. (Per 1A-3 the legal next state is
  ``APPROVED_VERIFIED`` or ``ARCHIVED`` — ``PENDING_REVIEW`` is NOT
  in the legal-next set.) The cascade therefore extends the
  transition graph at the **service layer** by writing the new
  state directly when the source state is ``APPROVED`` and the
  driver is a substantive curriculum re-version. This is the only
  service layer in the codebase allowed to do an APPROVED →
  PENDING_REVIEW write — see the explicit guard in
  :func:`_cascade_artifact_to_pending_review` below.

Out of scope (per #4662):

- Computing the ``version_diff`` itself — caller (M3-G driver) is
  responsible for assembling the SE-pair list from two
  ``CurriculumVersion`` rows + their ``CEGExpectation`` SE rows.
- Notifying teachers — stripe 3G-3 observes the audit rows.
- ``cascade_reason`` text column on ``study_guides`` — the issue
  spec explicitly recommends skipping the column when the audit
  log carries the trail. We follow that recommendation here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from sqlalchemy.orm import Session

from app.models.study_guide import StudyGuide
from app.services.audit_service import log_action
from app.services.cmcp.artifact_state import ArtifactState
from app.services.cmcp.version_diff_classifier import (
    SEVERITY_SCOPE_SUBSTANTIVE,
    classify_se_change,
)

logger = logging.getLogger(__name__)


# Audit action string — pinned here as a module constant so callers
# (3G-3 notification observer, future analytics queries) can import
# the same symbol instead of re-typing the string and drifting.
CASCADE_AUDIT_ACTION = "cmcp.artifact.cascade_flagged"


@dataclass
class CascadeResult:
    """Summary of a cascade run.

    Attributes:
        flagged_artifact_ids: IDs of APPROVED study_guides that were
            transitioned to PENDING_REVIEW. Sorted ascending for
            deterministic test assertions.
        substantive_se_codes: ``cb_code`` strings whose SE pairs
            classified as ``scope_substantive`` and triggered at
            least one artifact transition (or were checked but had
            no APPROVED matches). Sorted ascending.
        wording_only_se_count: Count of SE pairs that classified as
            ``wording_only`` and were skipped — useful for
            observability ("CEG version landed; 47 SE pairs;
            3 substantive, 44 wording-only; 12 artifacts reflagged").
    """

    flagged_artifact_ids: list[int] = field(default_factory=list)
    substantive_se_codes: list[str] = field(default_factory=list)
    wording_only_se_count: int = 0


def _get(se: Any, key: str) -> Any:
    """Read ``key`` from ``se`` whether dict or attribute-bearing object."""
    if se is None:
        return None
    if isinstance(se, dict):
        return se.get(key)
    return getattr(se, key, None)


def _se_cb_code(old_se: Any, new_se: Any) -> str | None:
    """Best-effort recovery of the ``cb_code`` for an SE pair.

    Prefers ``new_se.cb_code`` (the SE in the new curriculum version
    is the one we want artifacts re-reviewed *against*). Falls back
    to ``old_se.cb_code`` so a deletion (new_se=None) still surfaces
    its old cb_code for matching against historical artifacts.

    Returns ``None`` when neither side has a populated ``cb_code`` —
    the cascade cannot match such a pair against ``se_codes`` JSON
    arrays on study_guides, so the caller skips it (logged as a
    warning to flag a malformed version_diff input).
    """
    new_code = _get(new_se, "cb_code")
    if new_code:
        return new_code
    return _get(old_se, "cb_code")


def _cascade_artifact_to_pending_review(
    artifact: StudyGuide,
    *,
    db: Session,
    se_code: str,
    from_version: str,
    to_version: str,
) -> bool:
    """Flip one APPROVED artifact to PENDING_REVIEW + write audit row.

    Returns ``True`` if the artifact was transitioned, ``False`` if
    it was skipped (defensive guard — the SQL filter in the caller
    already restricts to ``state == APPROVED``, but a parallel session
    could have raced on the same row).

    Why bypass :class:`ArtifactStateMachine.validate_transition`:
    ``APPROVED → PENDING_REVIEW`` is NOT in the legal-next set (1A-3
    permits APPROVED → APPROVED_VERIFIED or APPROVED → ARCHIVED).
    The cascade is the explicitly-named exception per D9=B: a
    substantive curriculum re-version forces APPROVED artifacts back
    into the review queue. This is the ONLY service in the codebase
    that performs this write.
    """
    if artifact.state != ArtifactState.APPROVED:
        # Race-safe no-op — another session could have moved this row
        # to ARCHIVED or APPROVED_VERIFIED between our SELECT and write.
        return False

    artifact.state = ArtifactState.PENDING_REVIEW
    db.flush()  # populate UPDATE without committing — caller commits.

    log_action(
        db,
        user_id=None,
        action=CASCADE_AUDIT_ACTION,
        resource_type="study_guide",
        resource_id=artifact.id,
        details={
            "se_code": se_code,
            "from_version": from_version,
            "to_version": to_version,
            "severity": SEVERITY_SCOPE_SUBSTANTIVE,
        },
    )
    return True


def _approved_artifacts_for_se(db: Session, se_code: str) -> list[StudyGuide]:
    """Return APPROVED study_guides whose ``se_codes`` contains ``se_code``.

    Cross-dialect filter: SQL restricts to ``state == APPROVED`` and a
    non-NULL ``se_codes`` column; the JSON-array containment check is
    performed in Python (see module docstring rationale). The returned
    list is ordered by id ascending for deterministic transitions.
    """
    rows = (
        db.query(StudyGuide)
        .filter(StudyGuide.state == ArtifactState.APPROVED)
        .filter(StudyGuide.se_codes.isnot(None))
        .order_by(StudyGuide.id.asc())
        .all()
    )
    matched: list[StudyGuide] = []
    for row in rows:
        codes = row.se_codes
        # ``se_codes`` is stored as a JSON list of strings. Defensive
        # handling: skip rows where the column is not a list (corrupt
        # data, schema drift). Membership check is exact-string.
        if isinstance(codes, list) and se_code in codes:
            matched.append(row)
    return matched


def apply_version_cascade(
    version_diff: Sequence[dict] | Iterable[dict],
    db: Session,
) -> CascadeResult:
    """Cascade a CEG version diff to APPROVED study_guides.

    For every SE pair in ``version_diff`` that classifies as
    ``scope_substantive``, find APPROVED study_guides referencing
    that SE's ``cb_code`` and transition them to ``PENDING_REVIEW``,
    writing a ``cmcp.artifact.cascade_flagged`` audit row per
    transitioned artifact.

    Args:
        version_diff: Iterable of SE-pair dicts shaped per the
            module docstring. Each dict carries ``old_se``, ``new_se``,
            ``from_version``, ``to_version``. Wording-only pairs are
            counted but not acted on. Pairs with no recoverable
            ``cb_code`` are skipped with a warning log.
        db: SQLAlchemy session. The cascade does NOT commit — the
            caller (M3-G driver) commits once per cascade run so a
            failure mid-cascade rolls back the whole batch.

    Returns:
        :class:`CascadeResult` summarizing the run. ``flagged_artifact_ids``
        are sorted ascending; ``substantive_se_codes`` are sorted
        ascending and de-duplicated. ``wording_only_se_count`` counts
        pairs classified as ``wording_only`` (regardless of cb_code).

    Notes:
        - The function is idempotent across re-runs in the trivial
          sense: once an artifact has been moved to PENDING_REVIEW by
          a prior cascade, the SQL filter excludes it from the next
          one, so re-applying the same diff is a safe no-op.
        - No real network / notification calls. Stripe 3G-3 observes
          the audit rows.
    """
    result = CascadeResult()
    seen_se_codes: set[str] = set()

    pairs = list(version_diff or [])
    if not pairs:
        return result

    for pair in pairs:
        old_se = pair.get("old_se") if isinstance(pair, dict) else None
        new_se = pair.get("new_se") if isinstance(pair, dict) else None
        severity = classify_se_change(old_se, new_se)

        if severity != SEVERITY_SCOPE_SUBSTANTIVE:
            result.wording_only_se_count += 1
            continue

        se_code = _se_cb_code(old_se, new_se)
        if not se_code:
            # Substantive but un-matchable — log + skip. A real-world
            # version diff should always carry cb_code on at least
            # one side; missing both is an upstream data bug, not a
            # cascade error, so we don't raise.
            logger.warning(
                "cmcp.cascade.skipped pair=substantive_no_cb_code "
                "from_version=%s to_version=%s",
                pair.get("from_version") if isinstance(pair, dict) else None,
                pair.get("to_version") if isinstance(pair, dict) else None,
            )
            continue

        seen_se_codes.add(se_code)

        from_version = (
            pair.get("from_version") if isinstance(pair, dict) else None
        ) or ""
        to_version = (
            pair.get("to_version") if isinstance(pair, dict) else None
        ) or ""

        for artifact in _approved_artifacts_for_se(db, se_code):
            if _cascade_artifact_to_pending_review(
                artifact,
                db=db,
                se_code=se_code,
                from_version=from_version,
                to_version=to_version,
            ):
                result.flagged_artifact_ids.append(artifact.id)

    # Sort + dedupe outputs for deterministic test + log behavior.
    result.flagged_artifact_ids = sorted(set(result.flagged_artifact_ids))
    result.substantive_se_codes = sorted(seen_se_codes)
    return result


__all__ = [
    "CASCADE_AUDIT_ACTION",
    "CascadeResult",
    "apply_version_cascade",
]
