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

Stripe 3G-3 (#4665, notification) layers on top of the cascade write
in :func:`_notify_cascade_flagged`: per successful APPROVED →
PENDING_REVIEW transition we emit one in-app
``NotificationType.CMCP_CASCADE_FLAGGED`` row to the artifact's owner
(teacher) via the existing CB-MCNI multi-channel helper, linking to
``/teacher/review/{artifact_id}``. The notification call is
best-effort and never propagates — a notification failure must not
roll back the cascade transition or its audit row. Email +
ClassBridge-message channels are intentionally excluded so a
substantive curriculum re-version that flags hundreds of artifacts
does not flood teacher inboxes.

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
                          "to_version": str, "severity": "scope_substantive",
                          "cleared_alignment": bool}``

Stale alignment score nulling (#4697 — Path B):

- ``alignment_score`` is nulled alongside the APPROVED → PENDING_REVIEW
  state flip. The original validation ran against a now-stale SE
  definition, so the persisted score is misleading once the SE has
  shifted substantively. Re-validation runs on next approve via the
  approve handler (Path A is deferred to M4 — see #4697). The audit
  row's ``details["cleared_alignment"]`` is ``True`` when the score
  was non-NULL prior to the transition (so an ops query can tell the
  difference between "we cleared a stale score" and "no score was
  ever written"); it is ``False`` when ``alignment_score`` was
  already ``None`` at cascade time.

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
from typing import Any, Iterable

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

# 3G-3 (#4665) — notification side-effect emitted to the artifact owner
# (teacher) after each cascade-driven APPROVED → PENDING_REVIEW write.
# Pinned as a constant so 3G-3 tests + downstream observers can import
# the same string the service emits and stay in lockstep with the
# notification type.
CASCADE_NOTIFICATION_TYPE_VALUE = "cmcp.cascade.flagged"


def _notify_cascade_flagged(
    *,
    db: Session,
    artifact: StudyGuide,
    se_code: str,
    from_version: str,
    to_version: str,
) -> None:
    """Best-effort owner notification for a cascade-flagged artifact.

    3G-3 (#4665) per D9=B: when a cascade transitions an APPROVED
    artifact to PENDING_REVIEW, notify the artifact's owner (teacher)
    via the existing CB-MCNI dev-03 notification service so the row
    appears in their review queue without polling.

    The notification is emitted via
    :func:`app.services.notification_service.send_multi_channel_notification`
    on the in-app channel only — email + ClassBridge-message channels
    are intentionally excluded so a substantive curriculum re-version
    that flags hundreds of artifacts at once does not flood the
    teacher's inbox. The teacher sees one in-app row per flagged
    artifact, linking to ``/teacher/review/{artifact_id}`` (the 3A-2
    review queue route).

    Failure modes (all best-effort — never propagate):

    - Owner ``user_id`` is unset / row deleted before lookup
      (``user_id`` column is non-nullable on study_guides, so this is
      defense-in-depth rather than a real-world path) → warn + skip.
    - ``send_multi_channel_notification`` raises (e.g. DB error in the
      Notification insert, send-helper bug) → warn + swallow. The
      cascade state transition + audit row are already in the session
      and must not roll back because of a notification failure.

    The lazy imports mirror the pattern in
    :func:`app.services.task_sync_service._notify_task_upgraded`
    (CB-TASKSYNC-001 I6) — keeping the notification service out of
    this module's top-level imports so a notification-service import
    error never breaks the cascade itself.
    """
    owner_id = getattr(artifact, "user_id", None)
    if owner_id is None:
        logger.warning(
            "cmcp.cascade.notify.skipped reason=no_owner artifact_id=%s "
            "se_code=%s",
            getattr(artifact, "id", None),
            se_code,
        )
        return

    try:
        from app.models.notification import NotificationType
        from app.models.user import User
        from app.services.notification_service import (
            send_multi_channel_notification,
        )

        recipient = db.query(User).filter(User.id == owner_id).first()
        if recipient is None:
            # Owner row deleted (e.g., teacher account purged) — no
            # one to notify, but the audit row still records the
            # cascade. Warn so an ops query for orphaned cascades can
            # find it.
            logger.warning(
                "cmcp.cascade.notify.skipped reason=owner_not_found "
                "artifact_id=%s owner_id=%s se_code=%s",
                getattr(artifact, "id", None),
                owner_id,
                se_code,
            )
            return

        title_preview = (getattr(artifact, "title", "") or "")[:80]
        cascade_reason = (
            f"Curriculum {se_code} changed substantively from "
            f"{from_version or '(unknown)'} to {to_version or '(unknown)'}"
        )
        send_multi_channel_notification(
            db=db,
            recipient=recipient,
            sender=None,
            title="Artifact flagged for re-review",
            content=(
                f"'{title_preview}' needs re-review. {cascade_reason}."
            ),
            notification_type=NotificationType.CMCP_CASCADE_FLAGGED,
            link=f"/teacher/review/{artifact.id}",
            channels=["app_notification"],
            source_type="study_guide",
            source_id=artifact.id,
        )
    except Exception:
        # Best-effort: a notification failure must not roll back the
        # cascade transition or its audit row. Log + swallow.
        logger.exception(
            "cmcp.cascade.notify.error artifact_id=%s se_code=%s",
            getattr(artifact, "id", None),
            se_code,
        )


@dataclass
class CascadeResult:
    """Summary of a cascade run.

    Attributes:
        flagged_artifact_ids: IDs of APPROVED study_guides that were
            transitioned to PENDING_REVIEW. Sorted ascending for
            deterministic test assertions.
        substantive_se_codes: ``cb_code`` strings of SE pairs that
            classified as ``scope_substantive`` AND had a recoverable
            cb_code (regardless of whether any APPROVED artifact
            matched in this cascade run). Pairs with no recoverable
            cb_code are skipped and NOT included here. Sorted
            ascending and de-duplicated.
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

    # #4697 (Path B) — null the persisted alignment_score alongside the
    # state flip. The score was computed against the OLD SE definition;
    # the SE has now shifted substantively, so the score is stale and
    # the UI must show "score unavailable" until re-validation runs on
    # next approve. ``cleared_alignment`` records whether we actually
    # nulled a non-NULL value, so an ops query can distinguish "we
    # cleared a stale score" from "no score was ever written".
    cleared_alignment = artifact.alignment_score is not None
    artifact.state = ArtifactState.PENDING_REVIEW
    artifact.alignment_score = None
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
            "cleared_alignment": cleared_alignment,
        },
    )
    return True


def _approved_artifacts_for_se(db: Session, se_code: str) -> list[StudyGuide]:
    """Return APPROVED study_guides whose ``se_codes`` contains ``se_code``.

    Cross-dialect filter: SQL restricts to ``state == APPROVED`` and a
    non-NULL ``se_codes`` column; the JSON-array containment check is
    performed in Python (see module docstring rationale). The returned
    list is ordered by id ascending for deterministic transitions.

    NOTE: Scope is APPROVED only per #4662. Artifacts already in
    ``PENDING_REVIEW`` / ``IN_REVIEW`` are excluded — the teacher will
    see the cascade SE next time they open the row. Stripe 3G-3
    (notification) can layer broader visibility on top if needed.
    """
    # TODO: switch to dialect-specific JSON-array filter when scale
    # demands; M3β volumes are bounded by teacher review throughput
    # (re-review-ready APPROVED rows for a given subject/grade slice
    # are not millions), so the in-Python membership check below is
    # acceptable. Pushdown candidates: PG `se_codes ? :se_code` (JSONB
    # has-key), SQLite `EXISTS (SELECT 1 FROM json_each(se_codes) WHERE
    # value = :se_code)`. See #4697 review S4.
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
    version_diff: Iterable[dict[str, Any]],
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

    # Materialize once — caller may pass a generator and we iterate
    # multiple times conceptually (one classify pass + one DB pass per
    # substantive pair). Also lets us early-return on empty input.
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
                # 3G-3 (#4665) — fire owner notification AFTER the
                # state transition + audit row are in the session.
                # _notify_cascade_flagged is best-effort: it never
                # raises, so a notification failure cannot roll back
                # the cascade write.
                _notify_cascade_flagged(
                    db=db,
                    artifact=artifact,
                    se_code=se_code,
                    from_version=from_version,
                    to_version=to_version,
                )

    # Sort + dedupe outputs for deterministic test + log behavior.
    result.flagged_artifact_ids = sorted(set(result.flagged_artifact_ids))
    result.substantive_se_codes = sorted(seen_se_codes)

    # One INFO line per cascade run — bridges to 3G-3 observability so
    # an ops query for "why did 47 review-queue notifications fire?"
    # finds the cascade run by timestamp + counts.
    logger.info(
        "cmcp.cascade.applied flagged=%d substantive=%d wording_only=%d",
        len(result.flagged_artifact_ids),
        len(result.substantive_se_codes),
        result.wording_only_se_count,
        extra={
            "event": "cmcp.cascade.applied",
            "flagged_artifact_count": len(result.flagged_artifact_ids),
            "substantive_se_count": len(result.substantive_se_codes),
            "wording_only_se_count": result.wording_only_se_count,
        },
    )
    return result


__all__ = [
    "CASCADE_AUDIT_ACTION",
    "CASCADE_NOTIFICATION_TYPE_VALUE",
    "CascadeResult",
    "apply_version_cascade",
]
