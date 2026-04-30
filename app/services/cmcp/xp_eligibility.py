"""CB-CMCP-001 M3-D 3D-2 (#4659) — XP eligibility for completed assigned artifacts.

When a STUDENT completes a Task that was emitted by 3D-1's
:func:`app.services.cmcp.task_dispatcher.emit_tasks_for_approved_artifact`
fan-out, this module awards XP via the existing dev-03 XP infrastructure
(``XpLedger`` + ``XpSummary``) — keyed off the artifact's ``guide_type``
to match the per-content-type XP table locked in #4659.

XP table (per-content-type, in XP points)
-----------------------------------------
- ``study_guide``       → 5
- ``quiz``              → 10
- ``worksheet``         → 8
- ``sample_test``       → 20
- ``assignment``        → 15
- ``parent_companion``  → 0  (parent-facing — no student XP)

Eligibility gates (all must pass)
---------------------------------
1. The Task's ``source`` must be ``'cmcp_artifact'`` — i.e. it was
   created by 3D-1 fan-out, not a manual or LMS-sourced row.
   *SELF_STUDY artifacts skip 3D-1 entirely (no ``course_id``), so
   they have no Task with this source and naturally award 0 XP.*
2. The linked artifact must exist and be in state ``APPROVED``.
   Defence-in-depth: 3D-1 only emits Tasks on APPROVED, but a
   future state machine refactor (e.g. APPROVED → REJECTED) must
   not retroactively grant XP.
3. The artifact's ``guide_type`` must map to a positive XP amount
   in :data:`CMCP_CONTENT_TYPE_XP`.
4. No existing :class:`app.models.xp.XpLedger` row with
   ``context_id=cmcp_artifact_{artifact_id}`` for this student
   (lifetime dedup → idempotent re-completion).

Idempotency contract
--------------------
Same (artifact_id, student_user_id) pair → at most one XP award,
ever. Re-completing a Task (toggle complete → uncomplete → complete
again), or a future re-fan-out of the same artifact, must not
double-award. We enforce this with lifetime dedup on
``XpLedger.context_id`` rather than the 60-second window in
:func:`app.services.xp_service.award_xp`, mirroring the
``_award_cycle_xp`` lifetime-dedup pattern from CB-TUTOR-002 Phase 2.

Best-effort guarantee
---------------------
Like 3D-1's ``emit_tasks_for_approved_artifact``, this dispatcher
**never** raises out to its caller. It logs at WARNING / EXCEPTION
and returns 0 on any internal error so that the Task PATCH endpoint
(which surfaces task completion to the UI) never returns 500 due to
a gamification-side failure.

Out of scope (explicitly NOT done here)
---------------------------------------
- Streak multipliers — applied via the shared XP path below.
- Daily caps — bypassed for CMCP completions (they're rare ops
  events, not a grindable surface; the upstream Task fan-out
  itself caps how often these fire).
- Badge awards — left to a future stripe; not in #4659 scope.
- PARENT_COMPANION artifacts — return 0 XP (parents don't earn XP,
  and a parent companion is parent-facing context, not a student
  task).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)


# Per-content-type XP table from #4659. Keys match
# ``StudyGuide.guide_type`` (lowercase). PARENT_COMPANION maps to 0
# explicitly so the gate-check short-circuits without an XP award.
CMCP_CONTENT_TYPE_XP: dict[str, int] = {
    "study_guide": 5,
    "quiz": 10,
    "worksheet": 8,
    "sample_test": 20,
    "assignment": 15,
    "parent_companion": 0,
}

# Single action_type value persisted on every CMCP completion XP entry.
# Stable so dashboards / audit queries can group "all CMCP completion
# XP" without enumerating every content_type.
XP_ACTION_CMCP_ARTIFACT_COMPLETED = "cmcp_artifact_completed"


def _context_id_for(artifact_id: int) -> str:
    """Stable lifetime-dedup key for the (student, artifact) pair.

    Centralised here so tests + future audit tooling don't drift
    from the production write path.
    """
    return f"cmcp_artifact_{artifact_id}"


def _existing_award(
    db: Session,
    *,
    student_user_id: int,
    context_id: str,
):
    """Return the existing XpLedger row for (student, artifact), or None.

    Lazy-imports :class:`app.models.xp.XpLedger` to match the rest of
    the CMCP service layer's pattern (avoids import-cycle risk under
    conftest reloads).
    """
    from app.models.xp import XpLedger  # noqa: PLC0415

    return (
        db.query(XpLedger)
        .filter(XpLedger.student_id == student_user_id)
        .filter(XpLedger.context_id == context_id)
        .first()
    )


def award_xp_for_completed_artifact(
    *,
    artifact_id: int,
    student_user_id: int,
    task_source: Optional[str],
    db: Session,
) -> int:
    """Award XP to ``student_user_id`` for completing CMCP ``artifact_id``.

    Args:
        artifact_id: ``study_guides.id`` of the completed artifact.
        student_user_id: ``users.id`` of the student who completed the
            Task. Must be the assignee — caller is responsible for
            verifying ownership before invoking.
        task_source: ``Task.source`` string from the row whose
            ``is_completed`` just flipped to True. Must equal
            ``'cmcp_artifact'`` for an award to fire — any other
            value (None, 'assignment', 'email_digest', ...) returns 0
            because the Task was not created by 3D-1's fan-out.
        db: SQLAlchemy session (caller-managed lifecycle).

    Returns:
        The XP awarded (positive int). Returns 0 for any short-circuit:

        * ``task_source != 'cmcp_artifact'`` (not 3D-1 emitted) → 0
        * Artifact missing → 0
        * Artifact state != APPROVED → 0
        * Artifact ``guide_type`` not in :data:`CMCP_CONTENT_TYPE_XP` → 0
        * ``guide_type`` maps to 0 XP (e.g. parent_companion) → 0
        * ``settings.xp_enabled`` is False → 0
        * Already-awarded for this (student, artifact) — idempotent → 0

    Side effects:
        * One ``xp_ledger`` row + ``xp_summary`` total bump on success.
        * One ``cmcp.xp.awarded`` INFO log on success; WARNING / DEBUG
          for skip paths so ops can grep skip reasons.

    Best-effort guarantee:
        Any unexpected exception is caught, logged, and 0 is returned.
        The Task PATCH endpoint must never 500 because of an XP write
        failure.
    """
    try:
        # Gate 1: feature-flag style global XP toggle. If a deploy ever
        # disables the gamification surface, this path must yield 0
        # (matches xp_service.award_xp's first check).
        from app.core.config import settings  # noqa: PLC0415

        if not settings.xp_enabled:
            return 0

        # Gate 2: only Tasks created by 3D-1's fan-out are eligible.
        # SELF_STUDY artifacts have no Task at all (3D-1 short-circuits
        # on missing course_id), and non-CMCP tasks (Assignment imports,
        # email-digest follow-ups) have their own XP paths.
        if (task_source or "") != "cmcp_artifact":
            logger.debug(
                "cmcp.xp.skipped non_cmcp_source artifact_id=%s "
                "student_user_id=%s task_source=%r",
                artifact_id,
                student_user_id,
                task_source,
                extra={
                    "event": "cmcp.xp.skipped_self_study",
                    "artifact_id": artifact_id,
                    "student_user_id": student_user_id,
                    "task_source": task_source,
                },
            )
            return 0

        # Lazy imports — match the CMCP service-layer pattern.
        from app.models.study_guide import StudyGuide  # noqa: PLC0415
        from app.models.xp import XpLedger  # noqa: PLC0415

        artifact = (
            db.query(StudyGuide)
            .filter(StudyGuide.id == artifact_id)
            .first()
        )
        if artifact is None:
            logger.warning(
                "cmcp.xp.skipped missing_artifact artifact_id=%s "
                "student_user_id=%s",
                artifact_id,
                student_user_id,
            )
            return 0

        # Gate 3: defence-in-depth — only APPROVED artifacts award XP.
        # 3D-1's fan-out already requires APPROVED, but a future state
        # transition (APPROVED → ARCHIVED, or REJECTED clawback) must
        # not retroactively grant XP on a stale Task.
        state = (artifact.state or "").strip()
        if state != ArtifactState.APPROVED:
            logger.debug(
                "cmcp.xp.skipped state_not_approved artifact_id=%s "
                "student_user_id=%s state=%s",
                artifact_id,
                student_user_id,
                state,
            )
            return 0

        # Gate 4: per-content-type XP lookup. Unknown / unmapped types
        # (a future ``guide_type`` we haven't priced) return 0 rather
        # than guessing — that's auditable and fail-safe.
        content_type = (artifact.guide_type or "").strip().lower()
        amount = CMCP_CONTENT_TYPE_XP.get(content_type, 0)
        if amount <= 0:
            logger.debug(
                "cmcp.xp.skipped zero_amount artifact_id=%s "
                "student_user_id=%s content_type=%s",
                artifact_id,
                student_user_id,
                content_type,
            )
            return 0

        # Gate 5: lifetime dedup — at most one award per
        # (student, artifact). Idempotent across re-completions and
        # any future re-fan-out of the same artifact.
        context_id = _context_id_for(artifact_id)
        if _existing_award(
            db, student_user_id=student_user_id, context_id=context_id,
        ) is not None:
            logger.debug(
                "cmcp.xp.skipped already_awarded artifact_id=%s "
                "student_user_id=%s",
                artifact_id,
                student_user_id,
                extra={
                    "event": "cmcp.xp.skipped_already_claimed",
                    "artifact_id": artifact_id,
                    "student_user_id": student_user_id,
                },
            )
            return 0

        # Award path — write XpLedger + bump XpSummary in the same
        # transaction. We bypass ``xp_service.award_xp``'s 60s dedup
        # window (irrelevant for lifetime-deduped events) and its
        # daily-cap clamp (CMCP completions are rare ops events, not
        # a grindable surface — fan-out volume is the natural cap).
        # Streak multiplier IS applied so a student on a 7-day streak
        # still gets the 1.25× bump on a CMCP completion.
        from app.services.xp_service import (  # noqa: PLC0415
            _get_or_create_summary,
            get_level_for_xp,
            get_streak_multiplier,
        )

        summary = _get_or_create_summary(db, student_user_id)
        multiplier = get_streak_multiplier(summary.current_streak or 0)
        final_xp = int(amount * multiplier)
        if final_xp <= 0:
            # Defensive — a future negative multiplier or zero amount
            # path must not write a 0-XP row.
            return 0

        entry = XpLedger(
            student_id=student_user_id,
            action_type=XP_ACTION_CMCP_ARTIFACT_COMPLETED,
            xp_awarded=final_xp,
            multiplier=multiplier,
            context_id=context_id,
            reason=f"Completed CMCP {content_type} artifact #{artifact_id}",
        )
        db.add(entry)
        db.flush()

        summary.total_xp = (summary.total_xp or 0) + final_xp
        level_info = get_level_for_xp(summary.total_xp)
        summary.current_level = level_info["level"]
        summary.last_qualifying_action_date = date.today()
        db.flush()
        db.commit()

        logger.info(
            "cmcp.xp.awarded artifact_id=%s student_user_id=%s "
            "content_type=%s xp=%d multiplier=%.2f total=%d",
            artifact_id,
            student_user_id,
            content_type,
            final_xp,
            multiplier,
            summary.total_xp,
            extra={
                "event": "cmcp.xp.awarded",
                "artifact_id": artifact_id,
                "student_user_id": student_user_id,
                "content_type": content_type,
                "xp_awarded": final_xp,
                "multiplier": multiplier,
                "total_xp": summary.total_xp,
            },
        )
        return final_xp

    except Exception:
        # Best-effort: any failure here must not surface to the Task
        # PATCH endpoint. Roll back the half-written row so the next
        # iteration's session is clean.
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception(
            "cmcp.xp.error artifact_id=%s student_user_id=%s",
            artifact_id,
            student_user_id,
        )
        return 0


__all__ = [
    "CMCP_CONTENT_TYPE_XP",
    "XP_ACTION_CMCP_ARTIFACT_COMPLETED",
    "award_xp_for_completed_artifact",
]
