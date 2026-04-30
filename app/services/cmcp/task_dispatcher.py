"""CB-CMCP-001 M3-D 3D-1 (#4652) — Tasks emit on approve.

When a teacher-distributed CMCP artifact is APPROVED via
``POST /api/cmcp/review/{id}/approve`` and has a ``course_id`` set,
this dispatcher emits one :class:`app.models.task.Task` row per
enrolled student in the artifact's class — reusing CB-TASKSYNC-001's
existing Task model + dedup pattern.

What this stripe writes
-----------------------
For each (artifact, enrolled-student) pair, the dispatcher writes one
``tasks`` row keyed on ``source='cmcp_artifact'`` /
``source_ref=str(artifact_id)`` / ``assigned_to_user_id=<student>``.
The unique partial index ``uq_tasks_source_upsert`` (defined on
:class:`app.models.task.Task`) makes repeat calls idempotent — a
re-approve / re-dispatch updates the existing row in place rather than
inserting a duplicate.

What this stripe does NOT do
----------------------------
* Run for SELF_STUDY-derived artifacts (no ``course_id`` →
  no enrollment fan-out → 0 events).
* Run for non-APPROVED states (PENDING_REVIEW, REJECTED, DRAFT — the
  approve endpoint already gates on PENDING_REVIEW → APPROVED, but
  the dispatcher itself is defensive and short-circuits when called
  on a non-APPROVED row).
* Stamp XP eligibility — handled by parallel stripe 3D-2.
* Notify students of the new Task — Tasks page polling surfaces them.

Best-effort guarantee
---------------------
The approve endpoint catches any exception this dispatcher raises and
swallows it (matches the surface dispatcher's contract). A failure to
emit Tasks therefore never blocks an approve from returning 200 — the
dispatcher logs at WARNING / ERROR for ops and returns the count of
Tasks it managed to emit.

Coordination with CB-TASKSYNC-001
---------------------------------
We use a NEW ``source='cmcp_artifact'`` value rather than reusing
``'assignment'`` because the artifact is a CMCP-generated study
artifact, not a Google Classroom assignment. CB-TASKSYNC's
``handle_assignment_deleted`` / ``handle_assignment_submitted``
lifecycle handlers therefore do not affect these rows — that's the
correct behavior because a CMCP artifact's lifecycle (REJECTED /
ARCHIVED) is independent of an assignment's. The shared
``Task`` model + sticky ``user_deleted`` semantics still apply: once
a student deletes an auto-emitted CMCP Task, a re-approve will not
resurrect it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.services.cmcp.artifact_state import ArtifactState

logger = logging.getLogger(__name__)


# Stable source value persisted on every Task this dispatcher emits.
# Keep it distinct from CB-TASKSYNC's ``'assignment'`` / ``'email_digest'``
# so future per-source ops queries (and lifecycle handlers) don't
# cross-contaminate.
TASK_SOURCE_CMCP_ARTIFACT = "cmcp_artifact"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _enrolled_student_user_ids(db: Session, course_id: int) -> list[int]:
    """Return user_ids for every student enrolled in ``course_id``.

    Mirrors :func:`app.services.task_sync_service._assignees_for_course`
    so the contract with CB-TASKSYNC stays consistent: students whose
    ``user_id`` is NULL are skipped (shadow / un-onboarded students),
    and the returned list is deduped while preserving order.
    """
    # Lazy import — match the rest of the CMCP service layer's pattern
    # for ORM models. Avoids import-cycle risk under conftest reloads.
    from app.models.student import Student  # noqa: PLC0415
    from app.models.course import student_courses  # noqa: PLC0415

    rows = (
        db.query(Student.user_id)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .filter(student_courses.c.course_id == course_id)
        .filter(Student.user_id.isnot(None))
        .all()
    )
    seen: set[int] = set()
    out: list[int] = []
    for (uid,) in rows:
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    return out


def _find_existing_task(
    db: Session,
    *,
    source_ref: str,
    assigned_to_user_id: int,
):
    """Return the existing Task for the (source, source_ref, assignee) tuple.

    Mirrors :func:`app.services.task_sync_service._find_existing` but
    pinned to ``source='cmcp_artifact'``. Used to short-circuit when a
    re-approve hits the same (artifact, student) pair so we update in
    place rather than inserting a duplicate.
    """
    from app.models.task import Task  # noqa: PLC0415

    return (
        db.query(Task)
        .filter(Task.source == TASK_SOURCE_CMCP_ARTIFACT)
        .filter(Task.source_ref == source_ref)
        .filter(Task.assigned_to_user_id == assigned_to_user_id)
        .first()
    )


def emit_tasks_for_approved_artifact(
    artifact_id: int,
    db: Session,
) -> int:
    """Emit one Task per enrolled student for an APPROVED CMCP artifact.

    Args:
        artifact_id: ``study_guides.id`` of the artifact whose
            APPROVED state was just persisted by the approve endpoint.
        db: SQLAlchemy session (caller-managed lifecycle).

    Returns:
        The number of Tasks created OR updated by this call. Returns 0
        for any of the documented short-circuit paths:

        * Artifact missing → 0
        * Artifact state is not APPROVED → 0
        * Artifact has no ``course_id`` (SELF_STUDY-derived /
          parent-self generated) → 0
        * Course has zero enrolled students with non-NULL
          ``user_id`` → 0

    Side effects:
        * One ``tasks`` row per enrolled student (insert OR update on
          the unique tuple ``(source, source_ref, assigned_to_user_id)``).
        * One ``cmcp.tasks.emitted`` INFO log per artifact + per Task
          (so ops can grep for fan-out volume).
        * Per-student WARNING log on commit failure; the caller's loop
          isolates the failure so other students' Tasks still emit.

    Best-effort guarantee:
        Per-student exceptions are caught + logged; this function only
        propagates errors that occur BEFORE the per-student loop (e.g.,
        a failed enrollment query). The approve endpoint's outer
        try/except still catches those for ops-only logging.
    """
    # Lazy import — match the rest of the CMCP service layer's pattern.
    from app.models.student import Student  # noqa: PLC0415
    from app.models.study_guide import StudyGuide  # noqa: PLC0415
    from app.models.task import Task  # noqa: PLC0415

    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
    )
    if artifact is None:
        logger.warning(
            "cmcp.tasks.emit skipped: artifact missing artifact_id=%s",
            artifact_id,
        )
        return 0

    state = (artifact.state or "").strip()
    if state != ArtifactState.APPROVED:
        # Defence-in-depth — the approve endpoint already gates on
        # PENDING_REVIEW → APPROVED, so this branch only fires when the
        # dispatcher is invoked directly (e.g., a future cross-process
        # worker re-running emit).
        logger.warning(
            "cmcp.tasks.emit skipped: state=%s not APPROVED artifact_id=%s",
            state,
            artifact_id,
        )
        return 0

    course_id: Optional[int] = getattr(artifact, "course_id", None)
    if course_id is None:
        # SELF_STUDY-derived / parent-self generated artifacts have no
        # class context — there's nothing to fan out to.
        logger.info(
            "cmcp.tasks.emit skipped: no course_id artifact_id=%s",
            artifact_id,
        )
        return 0

    student_user_ids = _enrolled_student_user_ids(db, course_id)
    if not student_user_ids:
        logger.info(
            "cmcp.tasks.emit skipped: no enrolled students artifact_id=%s "
            "course_id=%s",
            artifact_id,
            course_id,
        )
        return 0

    source_ref = str(artifact_id)
    title = (artifact.title or f"Study task {artifact_id}").strip()
    description = (artifact.content or "")[:1000] or None
    creator_id = artifact.user_id  # the teacher / admin who owns the artifact
    now = _now_utc()
    emitted = 0

    for student_user_id in student_user_ids:
        try:
            existing = _find_existing_task(
                db,
                source_ref=source_ref,
                assigned_to_user_id=student_user_id,
            )

            # Sticky user_deleted — once a student deletes an auto-emitted
            # CMCP Task, a re-approve must not resurrect it (matches
            # CB-TASKSYNC §6.13.1 stickiness).
            if existing is not None and existing.source_status == "user_deleted":
                logger.info(
                    "cmcp.tasks.emit skipped_user_deleted artifact_id=%s "
                    "task_id=%s assigned_to_user_id=%s",
                    artifact_id,
                    existing.id,
                    student_user_id,
                )
                continue

            if existing is None:
                # Resolve legacy student_id (NOT-NULL-ish in some
                # historical rows). Lookup is best-effort — None is fine
                # if the student row is unresolvable.
                student_rec = (
                    db.query(Student)
                    .filter(Student.user_id == student_user_id)
                    .first()
                )
                task = Task(
                    created_by_user_id=creator_id or student_user_id,
                    assigned_to_user_id=student_user_id,
                    title=title,
                    description=description,
                    course_id=course_id,
                    study_guide_id=artifact_id,
                    student_id=student_rec.id if student_rec else None,
                    source=TASK_SOURCE_CMCP_ARTIFACT,
                    source_ref=source_ref,
                    source_status="active",
                    source_created_at=now,
                )
                db.add(task)
                db.commit()
                db.refresh(task)
                emitted += 1
                logger.info(
                    "cmcp.tasks.emit created artifact_id=%s task_id=%s "
                    "assigned_to_user_id=%s",
                    artifact_id,
                    task.id,
                    student_user_id,
                )
            else:
                # Update path — light-touch refresh of the server-owned
                # fields. Don't touch ``is_completed`` / ``completed_at``
                # — those are user-owned (matches CB-TASKSYNC §6.13.1
                # "preserve user completion" rule).
                changed = False
                if title and existing.title != title:
                    existing.title = title
                    changed = True
                if description is not None and existing.description != description:
                    existing.description = description
                    changed = True
                if existing.source_status in ("source_deleted", None):
                    existing.source_status = "active"
                    existing.archived_at = None
                    changed = True
                # Refresh the "last server touch" baseline so the next
                # run's user-edit heuristic doesn't misread this server
                # write as a user edit once the 60s grace window elapses.
                existing.source_created_at = now
                db.commit()
                db.refresh(existing)
                emitted += 1
                if changed:
                    logger.info(
                        "cmcp.tasks.emit updated artifact_id=%s task_id=%s "
                        "assigned_to_user_id=%s",
                        artifact_id,
                        existing.id,
                        student_user_id,
                    )
        except Exception:
            # Per-student isolation: a single failed commit must not
            # block other students' Tasks. ``db.rollback()`` clears the
            # session so the next iteration's ``db.query`` doesn't
            # choke on a poisoned transaction.
            db.rollback()
            logger.exception(
                "cmcp.tasks.emit error artifact_id=%s assigned_to_user_id=%s",
                artifact_id,
                student_user_id,
            )
            continue

    logger.info(
        "cmcp.tasks.emit summary artifact_id=%s course_id=%s enrolled=%d "
        "emitted=%d",
        artifact_id,
        course_id,
        len(student_user_ids),
        emitted,
    )
    return emitted


__all__ = [
    "TASK_SOURCE_CMCP_ARTIFACT",
    "emit_tasks_for_approved_artifact",
]
