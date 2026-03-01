"""Repository for Task data access operations.

Extracts all SQLAlchemy query patterns from app/api/routes/tasks.py into
named, reusable methods.  Route handlers should instantiate this class
(or use the get_task_repo FastAPI dependency) instead of writing inline queries.
"""

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.task import Task
from app.models.student import Student, parent_students
from app.repositories.base import BaseRepository


def _task_eager_options() -> list:
    """SQLAlchemy selectinload options to eager-load all Task relationships.

    Avoids N+1 queries when serialising tasks to response dicts.
    Mirrors the private helper that lived in tasks.py before the refactor.
    """
    return [
        selectinload(Task.creator),
        selectinload(Task.assignee),
        selectinload(Task.course),
        selectinload(Task.course_content),
        selectinload(Task.study_guide),
    ]


class TaskRepository(BaseRepository[Task]):
    """Data access layer for the Task model."""

    def __init__(self, db: Session) -> None:
        super().__init__(Task, db)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _child_user_ids_for_parent(self, parent_user_id: int) -> list[int]:
        """Return user_ids of all students linked to a parent.

        Helper used by several list methods that need parent-child visibility.
        Two queries: parent_students join table -> Student.user_id lookup.
        """
        child_student_ids = [
            r[0]
            for r in self.db.execute(
                select(parent_students.c.student_id).where(
                    parent_students.c.parent_id == parent_user_id
                )
            ).all()
        ]
        if not child_student_ids:
            return []
        child_user_ids = [
            r[0]
            for r in self.db.execute(
                select(Student.user_id).where(Student.id.in_(child_student_ids))
            ).all()
        ]
        return child_user_ids

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    def list_for_user(
        self,
        user_id: int,
        *,
        include_archived: bool = False,
        parent_user_id: int | None = None,
        assigned_to_user_id: int | None = None,
        is_completed: bool | None = None,
        priority: str | None = None,
        course_id: int | None = None,
        study_guide_id: int | None = None,
    ) -> Sequence[Task]:
        """Return tasks created by or directly assigned to ``user_id``.

        When ``parent_user_id`` is provided (i.e. the caller is a parent),
        tasks assigned to any of their linked children are included as well —
        matching the OR-filter logic in the original ``list_tasks`` route.

        Optional keyword filters mirror the query-string params on GET /tasks/.
        All relationships are eager-loaded to avoid N+1 queries.
        """
        # Build the base OR filter: creator OR direct assignee
        filters = [
            Task.created_by_user_id == user_id,
            Task.assigned_to_user_id == user_id,
        ]

        # Parents also see tasks assigned to any of their linked children
        if parent_user_id is not None:
            child_user_ids = self._child_user_ids_for_parent(parent_user_id)
            if child_user_ids:
                filters.append(Task.assigned_to_user_id.in_(child_user_ids))

        stmt = (
            select(Task)
            .options(*_task_eager_options())
            .where(or_(*filters))
        )

        if not include_archived:
            stmt = stmt.where(Task.archived_at.is_(None))

        if assigned_to_user_id is not None:
            stmt = stmt.where(Task.assigned_to_user_id == assigned_to_user_id)
        if is_completed is not None:
            stmt = stmt.where(Task.is_completed == is_completed)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if course_id is not None:
            stmt = stmt.where(Task.course_id == course_id)
        if study_guide_id is not None:
            stmt = stmt.where(Task.study_guide_id == study_guide_id)

        # Portable NULL handling: non-null due dates first, nulls last
        stmt = stmt.order_by(
            Task.due_date.is_(None).asc(),
            Task.due_date.asc(),
            Task.created_at.desc(),
        )

        return self.db.execute(stmt).scalars().all()

    def list_for_student(
        self,
        student_user_id: int,
        *,
        include_archived: bool = False,
    ) -> Sequence[Task]:
        """Return tasks assigned to a specific student user.

        Scoped to tasks where ``assigned_to_user_id == student_user_id``.
        Relationships are eager-loaded.
        """
        stmt = (
            select(Task)
            .options(*_task_eager_options())
            .where(Task.assigned_to_user_id == student_user_id)
        )
        if not include_archived:
            stmt = stmt.where(Task.archived_at.is_(None))
        stmt = stmt.order_by(
            Task.due_date.is_(None).asc(),
            Task.due_date.asc(),
            Task.created_at.desc(),
        )
        return self.db.execute(stmt).scalars().all()

    def list_for_parent_children(
        self,
        parent_user_id: int,
        child_ids: list[int],
    ) -> Sequence[Task]:
        """Return tasks assigned to any of a parent's linked children.

        ``child_ids`` should be a list of *user_id* values (not student_id).
        Caller is responsible for resolving student_id → user_id beforehand
        (see ``_child_user_ids_for_parent``).

        Relationships are eager-loaded.  Archived tasks are excluded.
        """
        if not child_ids:
            return []
        stmt = (
            select(Task)
            .options(*_task_eager_options())
            .where(
                Task.assigned_to_user_id.in_(child_ids),
                Task.archived_at.is_(None),
            )
            .order_by(
                Task.due_date.is_(None).asc(),
                Task.due_date.asc(),
                Task.created_at.desc(),
            )
        )
        return self.db.execute(stmt).scalars().all()

    def get_with_relations(self, task_id: int) -> Task | None:
        """Load a single task with all relationships eagerly loaded.

        Returns ``None`` when the task does not exist.  Use this whenever the
        route needs to serialise the task object (avoids lazy-load AttributeErrors
        after the session is closed).
        """
        stmt = (
            select(Task)
            .options(*_task_eager_options())
            .where(Task.id == task_id)
        )
        return self.db.execute(stmt).scalars().first()

    def get_by_creator(self, task_id: int, creator_user_id: int) -> Task | None:
        """Fetch a task only if it was created by ``creator_user_id``.

        Used by routes that restrict operations (delete, restore, permanent-delete)
        to the task creator.  Returns ``None`` when not found or wrong owner.
        """
        stmt = select(Task).where(
            Task.id == task_id,
            Task.created_by_user_id == creator_user_id,
        )
        return self.db.execute(stmt).scalars().first()

    def list_upcoming(
        self,
        user_id: int,
        days_ahead: int = 7,
    ) -> Sequence[Task]:
        """Return non-archived, incomplete tasks due within the next ``days_ahead`` days.

        Covers tasks created by OR assigned to ``user_id``.  Used by reminder jobs
        and dashboard widgets that surface upcoming deadlines.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        stmt = (
            select(Task)
            .where(
                or_(
                    Task.created_by_user_id == user_id,
                    Task.assigned_to_user_id == user_id,
                ),
                Task.archived_at.is_(None),
                Task.is_completed.is_(False),
                Task.due_date.isnot(None),
                Task.due_date >= now,
                Task.due_date <= cutoff,
            )
            .order_by(Task.due_date.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def get_overdue(self, student_user_id: int) -> Sequence[Task]:
        """Return incomplete tasks past their due date for a student.

        Looks at tasks assigned to ``student_user_id`` where
        ``due_date < now`` and ``is_completed`` is False.
        Archived tasks are excluded.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(Task)
            .where(
                Task.assigned_to_user_id == student_user_id,
                Task.archived_at.is_(None),
                Task.is_completed.is_(False),
                Task.due_date.isnot(None),
                Task.due_date < now,
            )
            .order_by(Task.due_date.asc())
        )
        return self.db.execute(stmt).scalars().all()
