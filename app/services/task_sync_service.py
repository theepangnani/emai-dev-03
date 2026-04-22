"""Task sync service — single source of truth for auto-created Tasks.

Implements CB-TASKSYNC-001 I3 (issue #3915). See `requirements/features-part1.md`
§6.13.1 for the authoritative spec (dedup key, lifecycle, assignee rules).

Public API
----------
- :func:`upsert_task_from_assignment` — deterministic source (one Task per enrolled student).
- :func:`upsert_task_from_digest_item` — probabilistic source (email-digest extraction).
- :func:`handle_assignment_deleted` — soft-cancel linked Tasks.
- :func:`handle_assignment_submitted` — auto-complete linked Task on submit.
- :func:`sync_all_upcoming_assignments` — batch orchestrator for the scheduled job.
- :func:`resolve_integration_child_user_id` — helper for the I6 digest wiring.

Design invariants
-----------------
- Idempotent: dedup on ``(source, source_ref, assigned_to_user_id)``.
- Sticky: ``source_status='user_deleted'`` is never resurrected.
- User-edit stickiness: after first user edit, subsequent upserts skip field updates.
- Preserves user completion: never overwrites ``is_completed=True`` / ``completed_at``.
- One transaction per source record; batch failures are isolated.
"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.assignment import Assignment
from app.models.course import student_courses
from app.models.parent_gmail_integration import ParentGmailIntegration
from app.models.student import Student, parent_students
from app.models.task import Task
from app.models.user import User
from app.services.parent_digest_ai_service import DigestTaskItem

logger = get_logger(__name__)

# Default IANA timezone used when an integration does not specify one. Matches
# the value used elsewhere for Canadian school boards.
_DEFAULT_TZ = "America/Toronto"

# Grace period (seconds) below which ``updated_at > created_at`` is treated as
# an ORM ``onupdate`` noise event, not a real user edit. Matches the
# §6.13.1 "sticky after first edit" definition.
_USER_EDIT_GRACE_SECONDS = 60

# Confidence thresholds for email_digest source (see §6.13.1).
_CONF_DROP_BELOW = 0.6
_CONF_TENTATIVE_BELOW = 0.8


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Collapse whitespace + casefold per §6.13.1 dedup-key recipe.

    ``re.sub(r'\\s+', ' ', title.casefold().strip())`` — load-bearing for
    cross-run idempotency of email-digest upserts.
    """
    return re.sub(r"\s+", " ", (title or "").casefold().strip())


def _resolve_tz(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or _DEFAULT_TZ)
    except ZoneInfoNotFoundError:
        return ZoneInfo(_DEFAULT_TZ)


def _digest_source_ref(title: str, due_date: datetime, tz_name: Optional[str]) -> str:
    """Compute the sha256 dedup key for an email_digest Task.

    ``sha256(normalized_title + '|' + iso_date_in_integration_tz)``.
    Date component is evaluated in the integration's timezone so that a 23:30
    EST email doesn't drift to the next UTC day.

    Naive datetimes are treated as already-in-``tz_name`` — we do NOT assume
    UTC, because that would silently flip the dedup key on the day boundary.
    """
    tz = _resolve_tz(tz_name)
    if due_date.tzinfo is None:
        local_date = due_date.date()
    else:
        local_date = due_date.astimezone(tz).date()
    payload = f"{_normalize_title(title)}|{local_date.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_user_edited(task: Task) -> bool:
    """§6.13.1 user-edit stickiness: updated > created + 60s AND updated > source_created + 60s."""
    if task.updated_at is None or task.created_at is None:
        return False
    grace = timedelta(seconds=_USER_EDIT_GRACE_SECONDS)
    if task.updated_at <= task.created_at + grace:
        return False
    # If source_created_at is set, also require the edit to post-date it by the
    # grace window — this prevents early-import upserts from being misread as
    # user edits when the auto-create itself bumps updated_at.
    if task.source_created_at is not None:
        if task.updated_at <= task.source_created_at + grace:
            return False
    return True


def _confidence_to_status(confidence: float) -> Optional[str]:
    """Map a raw confidence score to a ``source_status`` (or ``None`` to drop)."""
    if confidence < _CONF_DROP_BELOW:
        return None
    if confidence < _CONF_TENTATIVE_BELOW:
        return "tentative"
    return "active"


def _assignees_for_course(db: Session, course_id: int) -> list[int]:
    """Return user_ids for every student enrolled in ``course_id``.

    Mirrors the query used by `auto_create_tasks_from_dates` (study.py ~L491).
    Students whose ``user_id`` is NULL are skipped.
    """
    rows = (
        db.query(Student.user_id)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .filter(student_courses.c.course_id == course_id)
        .filter(Student.user_id.isnot(None))
        .all()
    )
    # Preserve order while de-duping.
    seen: set[int] = set()
    out: list[int] = []
    for (uid,) in rows:
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    return out


def _assignment_creator_user_id(assignment: Assignment) -> Optional[int]:
    """Best-effort resolution of the teacher behind an Assignment.

    Assignment rows do not carry ``created_by_user_id`` directly. Preference:
    1. course.teacher.user_id (if a real platform user; shadow teachers skipped)
    2. course.created_by_user_id
    3. None (caller falls back to the assignee)
    """
    course = getattr(assignment, "course", None)
    if course is None:
        return None
    teacher = getattr(course, "teacher", None)
    if teacher is not None and not getattr(teacher, "is_shadow", False):
        uid = getattr(teacher, "user_id", None)
        if uid:
            return uid
    return getattr(course, "created_by_user_id", None)


def _find_existing(
    db: Session,
    *,
    source: str,
    source_ref: str,
    assigned_to_user_id: Optional[int],
) -> Optional[Task]:
    q = db.query(Task).filter(
        Task.source == source,
        Task.source_ref == source_ref,
    )
    if assigned_to_user_id is None:
        q = q.filter(Task.assigned_to_user_id.is_(None))
    else:
        q = q.filter(Task.assigned_to_user_id == assigned_to_user_id)
    return q.first()


# ──────────────────────────────────────────────────────────────────────────
# Digest-item helper (used by I6, lives here so I3 owns the recipe)
# ──────────────────────────────────────────────────────────────────────────

def resolve_integration_child_user_id(
    db: Session,
    integration: ParentGmailIntegration,
) -> Optional[int]:
    """Return the student User.id for the child tied to ``integration`` — or None.

    Resolution preference:
    1. If ``integration.child_school_email`` matches a known student User, use that.
    2. Else if the parent has exactly one linked child, use that child.
    3. Else None (caller falls back to the parent as assignee — §6.13.1 rule).
    """
    if integration is None:
        return None

    # (1) Direct school-email match.
    email = (getattr(integration, "child_school_email", None) or "").strip().lower()
    if email:
        student_user = (
            db.query(User)
            .filter(User.email.is_not(None))
            .filter(User.email.ilike(email))
            .first()
        )
        if student_user is not None:
            # Confirm this user is actually one of the parent's linked students
            # — avoids grabbing a stranger who happens to share the email domain.
            link = (
                db.query(parent_students.c.id)
                .join(Student, Student.id == parent_students.c.student_id)
                .filter(parent_students.c.parent_id == integration.parent_id)
                .filter(Student.user_id == student_user.id)
                .first()
            )
            if link is not None:
                return student_user.id

    # (2) Fallback: parent has exactly one linked child.
    rows = (
        db.query(Student.user_id)
        .join(parent_students, Student.id == parent_students.c.student_id)
        .filter(parent_students.c.parent_id == integration.parent_id)
        .filter(Student.user_id.isnot(None))
        .all()
    )
    if len(rows) == 1:
        return rows[0][0]
    return None


# ──────────────────────────────────────────────────────────────────────────
# Single-record upserts
# ──────────────────────────────────────────────────────────────────────────

def _apply_field_updates(task: Task, *, title: str, due_date: Optional[datetime], description: Optional[str]) -> bool:
    """Apply allowed field updates to ``task``, respecting user-completion.

    Returns True if any field actually changed.
    """
    changed = False
    # Title / due / description are updatable only when the user hasn't edited.
    if title and task.title != title:
        task.title = title
        changed = True
    if due_date is not None and task.due_date != due_date:
        task.due_date = due_date
        changed = True
    if description is not None and task.description != description:
        task.description = description
        changed = True
    return changed


def _notify_task_upgraded(db: Session, task: Task) -> None:
    """Send an in-app notification when an email_digest Task is upgraded to an Assignment.

    Per §6.13.1 notifications rule ("'{title}' now linked to class assignment").
    Best-effort: failures are logged but never propagate — a notification
    failure must not roll back the upgrade itself. Added for CB-TASKSYNC-001 I6
    as a surgical addition to the I3 service (single-responsibility break
    accepted for MVP-1 simplicity).
    """
    if task is None or task.assigned_to_user_id is None:
        return
    try:
        from app.models.notification import NotificationType
        from app.models.user import User
        from app.services.notification_service import (
            send_multi_channel_notification,
        )

        recipient = db.query(User).filter(User.id == task.assigned_to_user_id).first()
        if recipient is None:
            return
        title_preview = (task.title or "")[:80]
        send_multi_channel_notification(
            db=db,
            recipient=recipient,
            sender=None,
            title="Task linked to class assignment",
            content=f"'{title_preview}' is now linked to a class assignment",
            notification_type=NotificationType.TASK_DUE,
            link="/tasks",
            channels=["app_notification"],
        )
    except Exception:
        logger.exception(
            "task_sync.notify_upgraded.error | task_id=%s",
            getattr(task, "id", None),
        )


def _try_upgrade_digest_to_assignment(
    db: Session,
    assignment: Assignment,
    assignee_user_id: int,
    assignment_due: datetime,
) -> Optional[Task]:
    """Find an email_digest Task that matches this assignment and upgrade it.

    Match rule (§6.13.1 upgrade path): same assignee, non-user_deleted,
    fuzzy title match (normalized equal), abs(due_date diff) ≤ 1 day.

    If matched, flip source → 'assignment', update source_ref + source_status,
    and return the upgraded Task so the caller can skip the create path.
    """
    norm_title = _normalize_title(assignment.title)
    lower = assignment_due - timedelta(days=1)
    upper = assignment_due + timedelta(days=1)

    candidates = (
        db.query(Task)
        .filter(Task.source == "email_digest")
        .filter(Task.assigned_to_user_id == assignee_user_id)
        .filter(or_(
            Task.source_status.is_(None),
            ~Task.source_status.in_(("user_deleted", "source_deleted")),
        ))
        .filter(Task.due_date >= lower)
        .filter(Task.due_date <= upper)
        # Deterministic "first match" so behaviour is reproducible across runs.
        .order_by(Task.id.asc())
        .all()
    )
    for cand in candidates:
        if _normalize_title(cand.title) == norm_title:
            cand.source = "assignment"
            cand.source_ref = str(assignment.id)
            cand.source_status = "upgraded"
            cand.source_created_at = _now_utc()
            # archived_at carry-over is intentional — if the user archived it
            # we wouldn't be here (filter above).
            logger.info(
                "task_sync.assignment.upgraded",
                extra={
                    "task_id": cand.id,
                    "source_ref": cand.source_ref,
                    "assigned_to_user_id": assignee_user_id,
                },
            )
            return cand
    return None


def upsert_task_from_assignment(db: Session, assignment: Assignment) -> list[Task]:
    """Upsert one Task per enrolled student for ``assignment``.

    Returns the list of Tasks created or updated. Skips the assignment
    silently (with a log) when ``due_date`` is NULL — §6.13.1 requires a
    non-null due date for task creation.
    """
    if assignment is None:
        return []
    if assignment.due_date is None:
        logger.info(
            "task_sync.assignment.skipped_no_due",
            extra={"source_ref": str(assignment.id)},
        )
        return []

    assignees = _assignees_for_course(db, assignment.course_id)
    if not assignees:
        return []

    source_ref = str(assignment.id)
    creator_fallback = _assignment_creator_user_id(assignment)
    now = _now_utc()
    results: list[Task] = []

    for student_user_id in assignees:
        try:
            # Sticky user_deleted check (on the assignment-keyed row).
            existing = _find_existing(
                db,
                source="assignment",
                source_ref=source_ref,
                assigned_to_user_id=student_user_id,
            )
            if existing is not None and existing.source_status == "user_deleted":
                # No state to commit — the existing row is sticky.
                logger.info(
                    "task_sync.assignment.skipped_user_deleted",
                    extra={
                        "task_id": existing.id,
                        "source_ref": source_ref,
                        "assigned_to_user_id": student_user_id,
                    },
                )
                continue

            if existing is None:
                # Try the upgrade path before creating a new Task.
                upgraded = _try_upgrade_digest_to_assignment(
                    db, assignment, student_user_id, assignment.due_date
                )
                if upgraded is not None:
                    # Keep description/title in sync with the authoritative
                    # assignment, respecting user-edit stickiness.
                    if not _is_user_edited(upgraded):
                        _apply_field_updates(
                            upgraded,
                            title=assignment.title,
                            due_date=assignment.due_date,
                            description=assignment.description,
                        )
                    # Refresh the "last server touch" baseline so the next
                    # run's user-edit heuristic compares against this write,
                    # not the original creation timestamp.
                    upgraded.source_created_at = now
                    db.commit()
                    db.refresh(upgraded)
                    # §6.13.1: notify assignee on email_digest → assignment
                    # upgrade. Fire after commit so a notification failure
                    # cannot roll back the upgrade itself.
                    _notify_task_upgraded(db, upgraded)
                    results.append(upgraded)
                    continue

                created_by = creator_fallback or student_user_id
                # Legacy columns (parent_id/student_id) are required in prod by
                # existing NOT-NULL-ish constraints on some rows; populate
                # student_id if we can resolve it.
                student_rec = (
                    db.query(Student).filter(Student.user_id == student_user_id).first()
                )
                task = Task(
                    created_by_user_id=created_by,
                    assigned_to_user_id=student_user_id,
                    title=assignment.title,
                    description=assignment.description,
                    due_date=assignment.due_date,
                    course_id=assignment.course_id,
                    student_id=student_rec.id if student_rec else None,
                    source="assignment",
                    source_ref=source_ref,
                    source_status="active",
                    source_created_at=now,
                )
                db.add(task)
                db.commit()
                db.refresh(task)
                logger.info(
                    "task_sync.assignment.created",
                    extra={
                        "task_id": task.id,
                        "source_ref": source_ref,
                        "assigned_to_user_id": student_user_id,
                    },
                )
                results.append(task)
            else:
                # Update path — respect user edits + preserve completion.
                if _is_user_edited(existing):
                    # Status may still flip (e.g., reactivate from source_deleted).
                    if existing.source_status in ("source_deleted", None) and existing.archived_at is None:
                        existing.source_status = "active"
                    db.commit()
                    db.refresh(existing)
                    results.append(existing)
                    logger.info(
                        "task_sync.assignment.skipped_user_edited",
                        extra={
                            "task_id": existing.id,
                            "source_ref": source_ref,
                            "assigned_to_user_id": student_user_id,
                        },
                    )
                    continue

                changed = _apply_field_updates(
                    existing,
                    title=assignment.title,
                    due_date=assignment.due_date,
                    description=assignment.description,
                )
                # Reactivate if previously source_deleted.
                if existing.source_status == "source_deleted":
                    existing.source_status = "active"
                    existing.archived_at = None
                    changed = True
                # Refresh the "last server touch" baseline so the next run's
                # user-edit heuristic doesn't misread this server write as a
                # user edit once the 60s grace window elapses.
                existing.source_created_at = now
                # Preserve user completion — never overwrite.
                db.commit()
                db.refresh(existing)
                if changed:
                    logger.info(
                        "task_sync.assignment.updated",
                        extra={
                            "task_id": existing.id,
                            "source_ref": source_ref,
                            "assigned_to_user_id": student_user_id,
                        },
                    )
                results.append(existing)
        except Exception:
            db.rollback()
            logger.exception(
                "task_sync.assignment.error | source_ref=%s assigned_to_user_id=%s",
                source_ref, student_user_id,
            )
            continue

    return results


def upsert_task_from_digest_item(
    db: Session,
    parent_user: User,
    child_user_id: Optional[int],
    item: DigestTaskItem,
    *,
    tz_name: Optional[str] = None,
) -> Optional[Task]:
    """Upsert a single email_digest Task from an AI-extracted item.

    Args:
        db: Active SQLAlchemy session.
        parent_user: The parent who owns the Gmail integration; used as
            ``created_by_user_id`` and as the fallback assignee.
        child_user_id: Preferred assignee (the student). If ``None``, the
            parent is used as assignee (§6.13.1 fallback rule).
        item: AI-extracted :class:`DigestTaskItem`. Its ``due_date`` must be
            timezone-aware.
        tz_name: IANA timezone name for dedup-key date normalization. Defaults
            to ``America/Toronto`` when falsy.

    Returns:
        The Task (created or updated) or None if the item was dropped
        (low confidence, sticky user_deleted, bad input).
    """
    if item is None or not item.title or item.due_date is None:
        return None

    status = _confidence_to_status(float(item.confidence))
    if status is None:
        logger.info(
            "task_sync.digest.dropped_low_confidence",
            extra={"confidence": item.confidence, "title": item.title[:60]},
        )
        return None

    assignee_id = child_user_id or (parent_user.id if parent_user else None)
    if assignee_id is None:
        return None

    source_ref = _digest_source_ref(item.title, item.due_date, tz_name)
    now = _now_utc()

    try:
        existing = _find_existing(
            db,
            source="email_digest",
            source_ref=source_ref,
            assigned_to_user_id=assignee_id,
        )
        if existing is not None and existing.source_status == "user_deleted":
            logger.info(
                "task_sync.digest.skipped_user_deleted",
                extra={
                    "task_id": existing.id,
                    "source_ref": source_ref,
                    "assigned_to_user_id": assignee_id,
                },
            )
            return None

        if existing is None:
            task = Task(
                created_by_user_id=parent_user.id,
                assigned_to_user_id=assignee_id,
                title=item.title,
                due_date=item.due_date,
                source="email_digest",
                source_ref=source_ref,
                source_confidence=float(item.confidence),
                source_status=status,
                source_message_id=item.gmail_message_id,
                source_created_at=now,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            logger.info(
                "task_sync.digest.created",
                extra={
                    "task_id": task.id,
                    "source_ref": source_ref,
                    "assigned_to_user_id": assignee_id,
                },
            )
            return task

        # Update path.
        if _is_user_edited(existing):
            db.commit()
            db.refresh(existing)
            logger.info(
                "task_sync.digest.skipped_user_edited",
                extra={
                    "task_id": existing.id,
                    "source_ref": source_ref,
                    "assigned_to_user_id": assignee_id,
                },
            )
            return existing

        changed = _apply_field_updates(
            existing,
            title=item.title,
            due_date=item.due_date,
            description=None,  # digest items don't carry description
        )
        # Refresh confidence + status if they changed (e.g., upgraded tentative→active).
        new_conf = float(item.confidence)
        if existing.source_confidence != new_conf:
            existing.source_confidence = new_conf
            changed = True
        # Never demote an 'upgraded' status back to active/tentative — once
        # an email_digest Task was linked to an assignment, it stays there.
        if existing.source_status not in ("upgraded",) and existing.source_status != status:
            existing.source_status = status
            changed = True
        # Keep the audit trail pointing at the most-recent Gmail message.
        if item.gmail_message_id and existing.source_message_id != item.gmail_message_id:
            existing.source_message_id = item.gmail_message_id
            changed = True
        # Refresh the "last server touch" baseline so the next run's user-edit
        # heuristic doesn't misread this server write as a user edit once the
        # 60s grace window elapses.
        existing.source_created_at = now
        db.commit()
        db.refresh(existing)
        if changed:
            logger.info(
                "task_sync.digest.updated",
                extra={
                    "task_id": existing.id,
                    "source_ref": source_ref,
                    "assigned_to_user_id": assignee_id,
                },
            )
        return existing
    except Exception:
        db.rollback()
        logger.exception(
            "task_sync.digest.error | source_ref=%s assigned_to_user_id=%s",
            source_ref, assignee_id,
        )
        return None


# ──────────────────────────────────────────────────────────────────────────
# Lifecycle handlers
# ──────────────────────────────────────────────────────────────────────────

def handle_assignment_deleted(db: Session, assignment_id: int) -> int:
    """Soft-cancel every Task linked to ``assignment_id``.

    Returns the count of Tasks transitioned by *this* call (not the total
    number of ``source_deleted`` rows for the assignment). A repeat call with
    no new tasks to cancel returns 0 — already-deleted tasks are skipped.
    Each transitioned Task gets ``archived_at=now,
    source_status='source_deleted'``. Already ``user_deleted`` rows are
    untouched (sticky per §6.13.1).
    """
    source_ref = str(assignment_id)
    now = _now_utc()
    count = 0

    tasks = (
        db.query(Task)
        .filter(Task.source == "assignment")
        .filter(Task.source_ref == source_ref)
        .all()
    )
    for task in tasks:
        try:
            if task.source_status == "user_deleted":
                continue
            task.archived_at = now
            task.source_status = "source_deleted"
            db.commit()
            db.refresh(task)
            count += 1
            logger.info(
                "task_sync.assignment.cancelled",
                extra={
                    "task_id": task.id,
                    "source_ref": source_ref,
                    "assigned_to_user_id": task.assigned_to_user_id,
                },
            )
        except Exception:
            db.rollback()
            logger.exception(
                "task_sync.assignment.cancel_error | source_ref=%s task_id=%s",
                source_ref, task.id,
            )
    return count


def handle_assignment_submitted(
    db: Session,
    assignment_id: int,
    student_user_id: int,
    submitted_at: datetime,
) -> Optional[Task]:
    """Auto-complete the Task for ``(assignment_id, student_user_id)`` on submit.

    Never overwrites an existing user completion timestamp (§6.13.1). Returns
    the Task, or None if no matching auto-Task exists.
    """
    task = _find_existing(
        db,
        source="assignment",
        source_ref=str(assignment_id),
        assigned_to_user_id=student_user_id,
    )
    if task is None:
        return None

    try:
        if task.source_status == "user_deleted":
            return None
        if not task.is_completed:
            task.is_completed = True
            task.completed_at = submitted_at or _now_utc()
        # Regardless, mark source_status for auditability.
        task.source_status = "source_submitted"
        db.commit()
        db.refresh(task)
        logger.info(
            "task_sync.assignment.submitted",
            extra={
                "task_id": task.id,
                "source_ref": str(assignment_id),
                "assigned_to_user_id": student_user_id,
            },
        )
        return task
    except Exception:
        db.rollback()
        logger.exception(
            "task_sync.assignment.submit_error | assignment_id=%s user_id=%s",
            assignment_id, student_user_id,
        )
        return None


# ──────────────────────────────────────────────────────────────────────────
# Batch orchestrator
# ──────────────────────────────────────────────────────────────────────────

def sync_all_upcoming_assignments(
    db: Session,
    *,
    window_days_past: int = 2,
    window_days_future: int = 30,
) -> dict:
    """Scan assignments in the rolling window and run per-record upserts.

    Implements the §6.13.1 "no backfill — rolling window" rule
    (``due_date BETWEEN now - window_days_past AND now + window_days_future``).
    Failures on individual assignments do NOT abort the batch.

    Returns a summary dict with keys: ``scanned``, ``created``, ``updated``,
    ``skipped``, ``errors``, ``duration_ms``.
    """
    start = time.time()
    now = _now_utc()
    lower = now - timedelta(days=window_days_past)
    upper = now + timedelta(days=window_days_future)

    assignments = (
        db.query(Assignment)
        .filter(Assignment.due_date.isnot(None))
        .filter(Assignment.due_date >= lower)
        .filter(Assignment.due_date <= upper)
        .all()
    )

    scanned = 0
    created = 0
    updated = 0
    skipped = 0
    errors = 0

    for assignment in assignments:
        scanned += 1
        try:
            # Snapshot existing Task ids for this assignment so we can classify
            # created vs updated post-upsert.
            existing_ids = set(
                row[0]
                for row in (
                    db.query(Task.id)
                    .filter(Task.source == "assignment")
                    .filter(Task.source_ref == str(assignment.id))
                    .all()
                )
            )
            tasks = upsert_task_from_assignment(db, assignment)
            if not tasks:
                skipped += 1
                continue
            for t in tasks:
                if t.id in existing_ids:
                    updated += 1
                else:
                    created += 1
        except Exception:
            errors += 1
            logger.exception(
                "task_sync_summary.item_error | assignment_id=%s", assignment.id,
            )

    duration_ms = int((time.time() - start) * 1000)
    summary = {
        "scanned": scanned,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "duration_ms": duration_ms,
    }
    logger.info(
        "task_sync_summary | source=assignment created=%d updated=%d cancelled=0 "
        "skipped=%d errors=%d duration_ms=%d",
        created, updated, skipped, errors, duration_ms,
    )
    return summary
