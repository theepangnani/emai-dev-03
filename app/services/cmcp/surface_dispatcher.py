"""CB-CMCP-001 M3α 3C-1 (#4586) — Surface dispatcher.

Synchronous, in-process fan-out of an APPROVED CMCP artifact to the
three M3α surfaces (Bridge / DCI / Digest). Best-effort with a per-
surface retry budget — failure on one surface does NOT block the
others, and the caller (the approve endpoint) still returns 200 even
when one or more surfaces fail. Telemetry is emitted via
:mod:`app.services.cmcp.surface_telemetry` (3C-5).

What this stripe writes
-----------------------
For each (artifact, surface) pair, the dispatcher writes one row to
``cmcp_surface_dispatches`` (see
:class:`app.models.cmcp_surface_dispatch.CMCPSurfaceDispatch` for
schema rationale). The row is the durable record that:

* The 3C-4 frontend (Bridge card list) reads to render the card list:
  ``SELECT * FROM cmcp_surface_dispatches WHERE surface='bridge' AND
  parent_id=:p AND status='ok'``.
* Future DCI / digest block-list endpoints query when composing
  parent-facing payloads (M3β).
* Ops use to compute the 24h-surface rate metric.

What this stripe does NOT do
----------------------------
* Actually call the DCI / digest renderers — those run at consumption
  time (``render_cmcp_coach_card``, ``render_cb_cmcp_artifact_summary``).
  The dispatcher's role is to mark the artifact as eligible for each
  surface; the renderer applies the visibility matrix when the
  consumer endpoint runs.
* Cross-process queue / worker — M3β can layer that on top.
* Frontend rendering of the dispatched rows — covered by 3C-4.

Retry policy
------------
Per-surface retry budget: 3 attempts with exponential back-off
(``0.05s, 0.10s, 0.20s``). The back-off base is short on purpose —
M3α is in-process synchronous + the user is waiting on the approve
HTTP response, so the dispatcher cannot hold the request thread for
seconds. Failures are recorded in the audit table with
``status='failed'`` + ``attempts=3`` + a 500-char ``last_error``
excerpt for ops inspection. Telemetry only fires on the *terminal*
state (one ``log_dispatched`` per surface success).
"""
from __future__ import annotations

import logging
import time
from functools import partial
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cmcp_surface_dispatch import CMCPSurfaceDispatch
from app.services.cmcp.artifact_state import ArtifactState
from app.services.cmcp.surface_telemetry import (
    SURFACE_BRIDGE,
    SURFACE_DCI,
    SURFACE_DIGEST,
    log_dispatched,
)

logger = logging.getLogger(__name__)


# Number of attempts per surface (1 initial + 2 retries = 3 total).
_RETRY_ATTEMPTS = 3

# Exponential back-off base (seconds). Short on purpose — see module
# docstring. The dispatcher runs inside the user-facing approve request.
_RETRY_BACKOFF_BASE = 0.05

# Cap on the persisted ``last_error`` excerpt. Matches the column
# ``String(500)`` width.
_LAST_ERROR_MAX_CHARS = 500


# Stable error tokens persisted on dispatch failure. Promoted to
# module-level constants so future ops dashboards / log queries can
# match on them without hard-coding the same strings in two places.
_ERR_ARTIFACT_NOT_FOUND = "artifact-not-found"
_ERR_STATE_NOT_RENDERABLE = "state-not-renderable"


def _truncate_error(exc: BaseException) -> str:
    """Return a 500-char excerpt of the exception's repr for audit."""
    text = repr(exc)
    if len(text) > _LAST_ERROR_MAX_CHARS:
        return text[: _LAST_ERROR_MAX_CHARS - 1] + "…"
    return text


def _retry(
    fn: Callable[[], Any],
    *,
    surface: str,
    artifact_id: int,
) -> tuple[bool, int, BaseException | None]:
    """Run ``fn`` with the surface retry policy.

    Returns ``(success, attempts_used, last_exc)``. The function is
    retried up to ``_RETRY_ATTEMPTS`` times with exponential back-off
    on each retry. The first attempt is NOT delayed — back-off only
    applies between retries.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            fn()
            return True, attempt, None
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "cmcp.surface.dispatch attempt failed surface=%s "
                "artifact_id=%s attempt=%d/%d error=%r",
                surface,
                artifact_id,
                attempt,
                _RETRY_ATTEMPTS,
                exc,
            )
            if attempt < _RETRY_ATTEMPTS:
                # Exponential: 0.05s, 0.10s, 0.20s ...
                time.sleep(_RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
    return False, _RETRY_ATTEMPTS, last_exc


def _find_existing_dispatch(
    db: Session,
    *,
    artifact_id: int,
    surface: str,
    parent_id: int | None,
    kid_id: int | None,
) -> CMCPSurfaceDispatch | None:
    """Return the existing audit row for the (artifact, surface, p, k) tuple.

    SQL ``=`` does not match NULL in either SQLite or Postgres — so we
    branch on whether ``parent_id`` / ``kid_id`` are None and use
    ``IS NULL`` filters there. The unique constraint at the DB layer
    also treats NULL values as distinct in both dialects, so we cannot
    rely on it for upsert when either anchor is NULL.
    """
    q = db.query(CMCPSurfaceDispatch).filter(
        CMCPSurfaceDispatch.artifact_id == artifact_id,
        CMCPSurfaceDispatch.surface == surface,
    )
    if parent_id is None:
        q = q.filter(CMCPSurfaceDispatch.parent_id.is_(None))
    else:
        q = q.filter(CMCPSurfaceDispatch.parent_id == parent_id)
    if kid_id is None:
        q = q.filter(CMCPSurfaceDispatch.kid_id.is_(None))
    else:
        q = q.filter(CMCPSurfaceDispatch.kid_id == kid_id)
    return q.first()


def _record_dispatch(
    db: Session,
    *,
    artifact_id: int,
    surface: str,
    parent_id: int | None,
    kid_id: int | None,
    status: str,
    attempts: int,
    last_error: str | None,
) -> CMCPSurfaceDispatch | None:
    """Persist (or upsert) the audit row for one (artifact, surface) tuple.

    Tuple match on (artifact_id, surface, parent_id, kid_id) — re-
    dispatch on retry / duplicate approve updates the existing row in
    place rather than inserting a duplicate. NULL-aware lookup is in
    :func:`_find_existing_dispatch` (SQL ``=`` doesn't match NULL on
    either dialect).

    Returns the persisted row, or ``None`` when the persist itself
    failed — the dispatcher logs + degrades gracefully so the user-
    visible surface call still succeeds even when the audit failed.
    """
    try:
        existing = _find_existing_dispatch(
            db,
            artifact_id=artifact_id,
            surface=surface,
            parent_id=parent_id,
            kid_id=kid_id,
        )
        if existing is not None:
            existing.status = status
            existing.attempts = attempts
            existing.last_error = last_error
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        row = CMCPSurfaceDispatch(
            artifact_id=artifact_id,
            surface=surface,
            parent_id=parent_id,
            kid_id=kid_id,
            status=status,
            attempts=attempts,
            last_error=last_error,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        # Concurrent dispatcher beat us to the insert (PG-only race
        # since the unique constraint matches NULL there only when
        # both anchors are non-NULL). Re-fetch + update in place.
        db.rollback()
        existing = _find_existing_dispatch(
            db,
            artifact_id=artifact_id,
            surface=surface,
            parent_id=parent_id,
            kid_id=kid_id,
        )
        if existing is None:
            # IntegrityError but no row found — schema collision we
            # can't recover from in-process. Log + return None.
            logger.warning(
                "cmcp.surface.dispatch audit upsert failed artifact_id=%s "
                "surface=%s — IntegrityError but no existing row",
                artifact_id,
                surface,
            )
            return None
        existing.status = status
        existing.attempts = attempts
        existing.last_error = last_error
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    except Exception as exc:  # pragma: no cover — error path
        db.rollback()
        logger.warning(
            "cmcp.surface.dispatch audit persist failed artifact_id=%s "
            "surface=%s error=%r",
            artifact_id,
            surface,
            exc,
        )
        return None


def _emit_bridge(
    *,
    artifact_id: int,
    parent_id: int | None,
    kid_id: int | None,
    db: Session,
) -> None:
    """Bridge surface emit — writes the dispatch audit row.

    The Bridge card itself is a derived view: the 3C-4 frontend queries
    ``cmcp_surface_dispatches WHERE surface='bridge' AND parent_id=:p
    AND status='ok'`` and joins back to ``study_guides`` for the
    artifact body. So the "emit" for Bridge is just persisting the
    eligibility row — no separate render step.

    Raises on persist failure so the retry policy in :func:`_retry`
    kicks in. The persist itself uses a SAVEPOINT-style rollback +
    upsert in :func:`_record_dispatch`; this wrapper surfaces a
    persist-rollback as a recoverable exception for the retry loop.
    """
    row = _record_dispatch(
        db,
        artifact_id=artifact_id,
        surface=SURFACE_BRIDGE,
        parent_id=parent_id,
        kid_id=kid_id,
        status="ok",
        attempts=1,
        last_error=None,
    )
    if row is None:
        raise RuntimeError(
            f"bridge dispatch persist failed artifact_id={artifact_id}"
        )


def _emit_dci(
    *,
    artifact_id: int,
    parent_id: int | None,
    kid_id: int | None,
    db: Session,
) -> None:
    """DCI surface emit — writes the dispatch audit row.

    The DCI block renderer (``render_cmcp_coach_card``) is pull-based;
    the dispatcher's job is to mark the artifact as eligible. The
    renderer applies the visibility + state checks at consumption time.
    """
    row = _record_dispatch(
        db,
        artifact_id=artifact_id,
        surface=SURFACE_DCI,
        parent_id=parent_id,
        kid_id=kid_id,
        status="ok",
        attempts=1,
        last_error=None,
    )
    if row is None:
        raise RuntimeError(
            f"dci dispatch persist failed artifact_id={artifact_id}"
        )


def _emit_digest(
    *,
    artifact_id: int,
    parent_id: int | None,
    kid_id: int | None,
    db: Session,
) -> None:
    """Digest surface emit — writes the dispatch audit row.

    The digest block renderer (``render_cb_cmcp_artifact_summary``) is
    pull-based; the dispatcher only persists eligibility. The unified
    digest worker (CB-PEDI-002 V2) calls the renderer at parent-digest
    composition time.
    """
    row = _record_dispatch(
        db,
        artifact_id=artifact_id,
        surface=SURFACE_DIGEST,
        parent_id=parent_id,
        kid_id=kid_id,
        status="ok",
        attempts=1,
        last_error=None,
    )
    if row is None:
        raise RuntimeError(
            f"digest dispatch persist failed artifact_id={artifact_id}"
        )


# Mapping from surface string → emit callable. Module-level so tests
# can patch a single surface's emitter without rebuilding the registry.
_SURFACE_EMITTERS: dict[str, Callable[..., None]] = {
    SURFACE_BRIDGE: _emit_bridge,
    SURFACE_DCI: _emit_dci,
    SURFACE_DIGEST: _emit_digest,
}


def _resolve_recipients(
    db: Session, artifact_id: int
) -> list[tuple[int | None, int | None]]:
    """Resolve ALL ``(parent_id, kid_id)`` recipient tuples for the artifact.

    M3α scope: the dispatcher records one audit row per surface
    *per recipient*. Co-parents (two linked parents on the same
    student) are extremely common — the original single-parent
    resolver silently dropped one of them, which would manifest as
    "where's my kid's artifact?" support tickets the moment the
    feature flag turns on for a real family. This helper iterates
    ``parent_students`` so every linked parent gets a dispatch row.

    Resolution rules (applied in order):
      * Artifact owner resolves to a ``Student`` row →
        return one ``(parent_id, student.id)`` tuple per linked
        parent. If the student has zero linked parents, return one
        ``(None, student.id)`` audit-only tuple so ops still see the
        dispatch landed (consumer endpoints treat ``parent_id=None``
        as not user-visible).
      * Artifact owner is a non-student user (parent / teacher) AND
        the artifact has a ``course_id`` → enumerate ALL active
        ``student_courses`` enrollments for that course, then for
        each enrolled student enumerate ``parent_students`` →
        yield one ``(parent_id, student.id)`` tuple per
        (enrolled-student, linked-parent) pair. Co-parent fan-out
        mirrors the Student-owned branch above. Includes one
        ``(owner_user_id, None)`` tuple for the artifact owner so
        the teacher/parent who authored the class-distributed
        artifact still sees their own audit row (preserves the
        legacy contract for the teacher's own surfaces).
        See #4635 (CB-CMCP-001 M3α follow-up) for rationale: without
        this fan-out, class-distributed APPROVED artifacts never
        reach enrolled students' parents through the digest table —
        the unified digest worker (CB-PEDI-002 V2) reads from
        ``cmcp_surface_dispatches`` and finds zero parent rows for
        a teacher-authored artifact under the M3α merged dispatcher.
      * Artifact owner is a non-student user with NO ``course_id``
        (parent-self generated, no class) → return one
        ``(owner_user_id, None)`` tuple — the parent / teacher is
        the recipient of their own self-generated artifact.
      * Artifact owner cannot be resolved → return one
        ``(None, None)`` audit-only tuple.
      * Any unexpected exception → return one ``(None, None)`` audit-
        only tuple. Defence-in-depth so a SQL fault in this resolver
        never blocks the rest of the dispatch.

    Returned list always has at least one tuple — every successful
    or failed dispatch must produce at least one audit row per
    surface. Per-row visibility checks in the renderers (3C-2/3C-3)
    still gate final delivery; the dispatcher's job is recipient
    enumeration, not authorization.
    """
    try:
        # Lazy import — match the rest of the CMCP service layer.
        from app.models.course import student_courses  # noqa: PLC0415
        from app.models.student import Student, parent_students  # noqa: PLC0415
        from app.models.study_guide import StudyGuide  # noqa: PLC0415

        artifact = (
            db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
        )
        if artifact is None:
            # Defensive — the public dispatcher entry point already
            # short-circuits on missing artifact upstream. Kept here
            # so direct callers of ``_resolve_recipients`` still get a
            # safe default.
            return [(None, None)]

        owner_user_id = artifact.user_id
        if owner_user_id is None:
            return [(None, None)]

        student = (
            db.query(Student).filter(Student.user_id == owner_user_id).first()
        )
        if student is None:
            # Artifact owner is not a student row — teacher- or
            # parent-authored. Two sub-cases.
            course_id = getattr(artifact, "course_id", None)
            if course_id is None:
                # Parent-self / teacher-self generated, no class
                # context → owner is the only recipient.
                return [(owner_user_id, None)]

            # Class-distributed artifact (#4635). Fan out to all
            # enrolled students' linked parents. Single SQL join
            # (student_courses ⋈ parent_students) keeps this O(1)
            # query — one round-trip regardless of class size.
            rows = (
                db.query(
                    parent_students.c.parent_id,
                    student_courses.c.student_id,
                )
                .join(
                    student_courses,
                    student_courses.c.student_id
                    == parent_students.c.student_id,
                )
                .filter(student_courses.c.course_id == course_id)
                .order_by(
                    student_courses.c.student_id.asc(),
                    parent_students.c.parent_id.asc(),
                )
                .all()
            )
            # Owner audit row first, then dedupe (parent, kid)
            # tuples in case the join surfaced duplicates (e.g.,
            # legacy data with multiple parent_students rows for the
            # same pair — uq constraint should prevent it but the
            # dedup keeps the dispatcher tolerant).
            recipients: list[tuple[int | None, int | None]] = [
                (owner_user_id, None)
            ]
            seen: set[tuple[int, int]] = set()
            for parent_id, student_id in rows:
                key = (parent_id, student_id)
                if key in seen:
                    continue
                seen.add(key)
                recipients.append((parent_id, student_id))
            return recipients

        # Iterate ALL linked parents. ``ORDER BY parent_id`` keeps the
        # iteration order deterministic (stable retry semantics +
        # predictable ops triage when two parents see the same row).
        links = (
            db.query(parent_students.c.parent_id)
            .filter(parent_students.c.student_id == student.id)
            .order_by(parent_students.c.parent_id.asc())
            .all()
        )
        if not links:
            # Student with zero linked parents — record audit-only row
            # so ops can spot the orphan family.
            return [(None, student.id)]
        return [(link[0], student.id) for link in links]
    except Exception as exc:  # pragma: no cover — defence-in-depth
        logger.warning(
            "cmcp.surface.dispatch recipient resolution failed artifact_id=%s "
            "error=%r",
            artifact_id,
            exc,
        )
        return [(None, None)]


def dispatch_artifact_to_surfaces(
    artifact_id: int,
    db: Session,
) -> dict[str, str]:
    """Fan-out an APPROVED artifact to all three M3α surfaces.

    Args:
        artifact_id: ``study_guides.id`` of the artifact to dispatch.
            The dispatcher checks the artifact exists + is in a
            renderable state (APPROVED / SELF_STUDY); other states
            result in all three surfaces marked ``"failed"`` with a
            ``state-not-renderable`` audit error.
        db: SQLAlchemy session (caller-managed lifecycle).

    Returns:
        A dict ``{surface: "ok" | "failed"}`` for the three known
        surfaces. Unknown / partial returns are intentionally
        prevented — every key in :data:`SURFACES` is always present.

        For artifacts with multiple linked parents (co-parents), the
        dispatcher writes one audit row PER (recipient, surface) pair
        but collapses the per-surface return to ``"ok"`` only when
        ALL recipients succeeded for that surface. Any single
        recipient failure marks the surface ``"failed"`` in the
        return dict — the per-recipient breakdown lives in the
        ``cmcp_surface_dispatches`` table.

    Side effects:
        * One ``cmcp_surface_dispatches`` row per surface PER
          recipient tuple (insert OR update on the unique tuple).
        * One ``cmcp.surface.dispatched`` log line per surface +
          recipient combo that succeeded.
        * Per-attempt warning logs on transient failures (info-only).

    Best-effort guarantee:
        A failure on one surface NEVER raises out of this function.
        The caller (approve endpoint) reads the returned dict to
        decide whether to surface the failure to the user — M3α
        contract is "approve still returns 200; surface failures are
        ops-only".
    """
    # Lazy import — match the rest of the CMCP service layer.
    from app.models.study_guide import StudyGuide  # noqa: PLC0415

    # Capture the dispatch start time for the latency telemetry below.
    started_at_ns = time.monotonic_ns()

    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
    )

    # If the artifact is missing or not in a renderable state, persist a
    # "failed" audit row per surface + return failed for all three. This
    # preserves the contract "every surface key is always present" while
    # giving ops a visible signal that something went wrong upstream.
    if artifact is None:
        logger.warning(
            "cmcp.surface.dispatch skipped: artifact missing artifact_id=%s",
            artifact_id,
        )
        for s in (SURFACE_BRIDGE, SURFACE_DCI, SURFACE_DIGEST):
            _record_dispatch(
                db,
                artifact_id=artifact_id,
                surface=s,
                parent_id=None,
                kid_id=None,
                status="failed",
                attempts=0,
                last_error=_ERR_ARTIFACT_NOT_FOUND,
            )
        return {
            SURFACE_BRIDGE: "failed",
            SURFACE_DCI: "failed",
            SURFACE_DIGEST: "failed",
        }

    state = (artifact.state or "").strip()
    if state not in {ArtifactState.APPROVED, ArtifactState.SELF_STUDY}:
        logger.warning(
            "cmcp.surface.dispatch skipped: state=%s not renderable "
            "artifact_id=%s",
            state,
            artifact_id,
        )
        for s in (SURFACE_BRIDGE, SURFACE_DCI, SURFACE_DIGEST):
            _record_dispatch(
                db,
                artifact_id=artifact_id,
                surface=s,
                parent_id=None,
                kid_id=None,
                status="failed",
                attempts=0,
                last_error=f"{_ERR_STATE_NOT_RENDERABLE}:{state}",
            )
        return {
            SURFACE_BRIDGE: "failed",
            SURFACE_DCI: "failed",
            SURFACE_DIGEST: "failed",
        }

    recipients = _resolve_recipients(db, artifact_id)

    # Per-surface "all recipients ok" outcome. Any failure on any
    # recipient downgrades the surface's outcome to "failed".
    outcomes: dict[str, str] = {
        SURFACE_BRIDGE: "ok",
        SURFACE_DCI: "ok",
        SURFACE_DIGEST: "ok",
    }
    for surface in (SURFACE_BRIDGE, SURFACE_DCI, SURFACE_DIGEST):
        emitter = _SURFACE_EMITTERS[surface]
        for parent_id, kid_id in recipients:
            call = partial(
                emitter,
                artifact_id=artifact_id,
                parent_id=parent_id,
                kid_id=kid_id,
                db=db,
            )
            success, attempts_used, last_exc = _retry(
                call, surface=surface, artifact_id=artifact_id
            )

            if success:
                elapsed_ms = max(
                    0,
                    int(
                        (time.monotonic_ns() - started_at_ns) // 1_000_000
                    ),
                )
                # Per-recipient telemetry: one log line per (artifact,
                # surface, recipient) triple. Co-parent families
                # generate N>1 lines per surface per artifact, so the
                # 24h-surface-rate metric in 3C-5 must dedupe by
                # ``artifact_id`` (NOT a naive count) when computing
                # rate-per-approval. Tracked as a docstring update
                # against ``surface_telemetry.log_dispatched``.
                try:
                    log_dispatched(
                        artifact_id=artifact_id,
                        surface=surface,
                        latency_ms_from_approve=elapsed_ms,
                    )
                except Exception as exc:  # pragma: no cover — telemetry never raises
                    logger.warning(
                        "cmcp.surface.dispatch telemetry emit failed "
                        "surface=%s artifact_id=%s error=%r",
                        surface,
                        artifact_id,
                        exc,
                    )
            else:
                outcomes[surface] = "failed"
                # Persist the terminal failure audit row. The
                # successful emitters above wrote their own ``ok``
                # audit row already; for the failed (recipient,
                # surface) pair the per-attempt emitter never reached
                # the audit-write line, so we write the failure row
                # here.
                _record_dispatch(
                    db,
                    artifact_id=artifact_id,
                    surface=surface,
                    parent_id=parent_id,
                    kid_id=kid_id,
                    status="failed",
                    attempts=attempts_used,
                    last_error=(
                        _truncate_error(last_exc) if last_exc else None
                    ),
                )
                logger.error(
                    "cmcp.surface.dispatch terminal failure surface=%s "
                    "artifact_id=%s parent_id=%s kid_id=%s attempts=%d "
                    "error=%r",
                    surface,
                    artifact_id,
                    parent_id,
                    kid_id,
                    attempts_used,
                    last_exc,
                )

    return outcomes


__all__ = [
    "dispatch_artifact_to_surfaces",
]
