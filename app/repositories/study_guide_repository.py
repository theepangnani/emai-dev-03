"""Repository for StudyGuide data access operations.

Extracts SQLAlchemy query patterns from app/api/routes/study.py and
app/domains/study/services.py into named, reusable methods.

Note: Hashing logic (compute_content_hash) remains in StudyService since it is
pure business logic with no DB dependency.  This repository handles only the
database operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func as sa_func, or_, select
from sqlalchemy.orm import Session

from app.models.study_guide import StudyGuide
from app.models.student import Student, parent_students
from app.models.course import student_courses
from app.repositories.base import BaseRepository


class StudyGuideRepository(BaseRepository[StudyGuide]):
    """Data access layer for the StudyGuide model."""

    def __init__(self, db: Session) -> None:
        super().__init__(StudyGuide, db)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def list_for_user(
        self,
        user_id: int,
        *,
        course_id: int | None = None,
        guide_type: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[StudyGuide]:
        """Return study guides owned by ``user_id``.

        Optionally filtered by ``course_id`` and/or ``guide_type``.
        Archived guides are excluded by default.
        """
        stmt = select(StudyGuide).where(StudyGuide.user_id == user_id)

        if course_id is not None:
            stmt = stmt.where(StudyGuide.course_id == course_id)

        if guide_type is not None:
            stmt = stmt.where(StudyGuide.guide_type == guide_type)

        if not include_archived:
            stmt = stmt.where(StudyGuide.archived_at.is_(None))

        stmt = (
            stmt.order_by(StudyGuide.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return self.db.execute(stmt).scalars().all()

    def list_for_student_with_courses(
        self,
        student_user_id: int,
        *,
        enrolled_course_ids: list[int],
        include_archived: bool = False,
    ) -> Sequence[StudyGuide]:
        """Return study guides visible to a student.

        Includes:
        - Guides owned by the student
        - Guides tagged to any of the student's enrolled courses (when not archived)

        ``enrolled_course_ids`` must be resolved by the caller beforehand.
        This avoids the repository depending on the Student model's relationship
        loader while remaining a single efficient query.
        """
        conditions = [StudyGuide.user_id == student_user_id]
        if enrolled_course_ids:
            conditions.append(
                StudyGuide.course_id.in_(enrolled_course_ids)
                if enrolled_course_ids
                else False
            )

        stmt = select(StudyGuide).where(or_(*conditions))

        if not include_archived:
            stmt = stmt.where(StudyGuide.archived_at.is_(None))

        stmt = stmt.order_by(StudyGuide.created_at.desc())
        return self.db.execute(stmt).scalars().all()

    def list_for_parent(
        self,
        parent_user_id: int,
        *,
        student_user_id: int | None = None,
        include_archived: bool = False,
    ) -> Sequence[StudyGuide]:
        """Return study guides visible to a parent.

        Includes:
        - Guides owned by the parent
        - Guides owned by any linked child (or a specific child when
          ``student_user_id`` is provided)
        - Guides tagged to any of the children's enrolled courses

        Mirrors the parent branch of the ``list_study_guides`` route.
        """
        # Resolve linked child student IDs
        child_student_rows = self.db.execute(
            select(parent_students.c.student_id).where(
                parent_students.c.parent_id == parent_user_id
            )
        ).all()
        child_sids = [r[0] for r in child_student_rows]

        # Resolve children's course IDs
        if child_sids:
            enrolled_rows = self.db.execute(
                select(student_courses.c.course_id).where(
                    student_courses.c.student_id.in_(child_sids)
                )
            ).all()
            children_course_ids = [r[0] for r in enrolled_rows]
        else:
            children_course_ids = []

        # Resolve children user IDs
        if child_sids:
            child_user_rows = self.db.execute(
                select(Student.user_id).where(Student.id.in_(child_sids))
            ).all()
            child_user_ids = [r[0] for r in child_user_rows]
        else:
            child_user_ids = []

        # If a specific child is requested, filter to that child's user_id
        if student_user_id is not None and student_user_id in child_user_ids:
            target_uids = [student_user_id]
        else:
            target_uids = child_user_ids

        conditions = [StudyGuide.user_id == parent_user_id]
        if children_course_ids:
            conditions.append(StudyGuide.course_id.in_(children_course_ids))
        if target_uids:
            conditions.append(StudyGuide.user_id.in_(target_uids))

        stmt = select(StudyGuide).where(or_(*conditions))

        if not include_archived:
            stmt = stmt.where(StudyGuide.archived_at.is_(None))

        stmt = stmt.order_by(StudyGuide.created_at.desc())
        return self.db.execute(stmt).scalars().all()

    def find_by_content_hash(
        self,
        content_hash: str,
        user_id: int,
        *,
        seconds: int = 60,
    ) -> StudyGuide | None:
        """Return an existing guide if one with ``content_hash`` was created recently.

        The ``seconds`` window (default 60 s) prevents duplicate generation
        when the user double-submits.  This is the dedup detection query used
        by find_recent_duplicate in StudyService; the repository exposes it
        directly so callers can bypass the service when they only need the DB
        operation.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        stmt = (
            select(StudyGuide)
            .where(
                StudyGuide.user_id == user_id,
                StudyGuide.content_hash == content_hash,
                StudyGuide.created_at >= cutoff,
            )
            .order_by(StudyGuide.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def find_pool_guide(
        self,
        content_hash: str,
        guide_type: str,
        exclude_user_id: int,
    ) -> StudyGuide | None:
        """Search the cross-user content pool for a reusable guide.

        Finds the first non-archived guide with ``content_hash`` and
        ``guide_type`` belonging to any user OTHER than ``exclude_user_id``
        (the requesting user).  If found, the caller can clone the guide
        instead of invoking the AI service — saving the generation cost.

        Note: This intentionally searches across all users — the guide
        content itself is not user-private; only metadata (user_id) differs.
        """
        stmt = (
            select(StudyGuide)
            .where(
                StudyGuide.content_hash == content_hash,
                StudyGuide.guide_type == guide_type,
                StudyGuide.user_id != exclude_user_id,
                StudyGuide.archived_at.is_(None),
            )
            .order_by(StudyGuide.created_at.asc())
        )
        return self.db.execute(stmt).scalars().first()

    def count_reuses(self) -> int:
        """Count the number of guides that were reused from the content pool.

        Returns the count of rows where ``source_guide_id IS NOT NULL``.
        Used by the admin pool stats endpoint.
        """
        stmt = (
            select(sa_func.count())
            .select_from(StudyGuide)
            .where(StudyGuide.source_guide_id.isnot(None))
        )
        return self.db.execute(stmt).scalar_one()

    def count_total_and_unique(self) -> tuple[int, int]:
        """Return (total_guides, unique_content_hashes) for dedup stats.

        Used by GET /api/study-guides/pool to compute savings.
        """
        total = self.db.execute(
            select(sa_func.count()).select_from(StudyGuide)
        ).scalar_one()
        unique = self.db.execute(
            select(sa_func.count(StudyGuide.content_hash.distinct())).select_from(StudyGuide)
            .where(StudyGuide.content_hash.isnot(None))
        ).scalar_one()
        return total, unique

    def count_for_user(self, user_id: int, *, include_archived: bool = False) -> int:
        """Return the number of study guides owned by ``user_id``.

        Used for storage limit checks (enforce_study_guide_limit) before
        generating new material.  By default only active (non-archived) guides
        are counted.
        """
        stmt = select(sa_func.count()).select_from(StudyGuide).where(
            StudyGuide.user_id == user_id
        )
        if not include_archived:
            stmt = stmt.where(StudyGuide.archived_at.is_(None))
        return self.db.execute(stmt).scalar_one()

    def get_oldest_active(self, user_id: int, *, limit: int = 1) -> Sequence[StudyGuide]:
        """Return the oldest non-archived guides for ``user_id``.

        Used by enforce_study_guide_limit to find candidates for auto-archiving
        when the per-user quota is exceeded.
        """
        stmt = (
            select(StudyGuide)
            .where(
                StudyGuide.user_id == user_id,
                StudyGuide.archived_at.is_(None),
            )
            .order_by(StudyGuide.created_at.asc())
            .limit(limit)
        )
        return self.db.execute(stmt).scalars().all()

    def list_versions(
        self, root_guide_id: int, user_id: int
    ) -> Sequence[StudyGuide]:
        """Return all versions in a study guide chain for ``user_id``.

        A chain consists of the root guide (``id == root_guide_id``) and all
        child guides (``parent_guide_id == root_guide_id``).  Results are ordered
        newest-version-first, matching the ``list_study_guide_versions`` route.
        """
        stmt = (
            select(StudyGuide)
            .where(
                or_(
                    StudyGuide.id == root_guide_id,
                    StudyGuide.parent_guide_id == root_guide_id,
                ),
                StudyGuide.user_id == user_id,
            )
            .order_by(StudyGuide.version.desc())
        )
        return self.db.execute(stmt).scalars().all()

    def get_max_version_in_chain(self, root_guide_id: int) -> int:
        """Return the highest version number across the entire guide chain.

        Used when creating a new version to determine the next version number.
        Returns 1 as a safe default when no versions are found.
        """
        result = self.db.execute(
            select(sa_func.max(StudyGuide.version)).where(
                or_(
                    StudyGuide.id == root_guide_id,
                    StudyGuide.parent_guide_id == root_guide_id,
                )
            )
        ).scalar()
        return result if result is not None else 1

    def get_for_owner(self, guide_id: int, user_id: int) -> StudyGuide | None:
        """Fetch a study guide only if it is owned by ``user_id``.

        Used by routes that restrict edit/delete/restore to the guide owner.
        Returns ``None`` when not found or the guide belongs to a different user.
        """
        stmt = select(StudyGuide).where(
            StudyGuide.id == guide_id,
            StudyGuide.user_id == user_id,
        )
        return self.db.execute(stmt).scalars().first()

    def archive_guides_for_content(
        self, content_id: int, archived_at: datetime | None = None
    ) -> int:
        """Bulk-archive all active study guides linked to ``content_id``.

        Sets ``archived_at`` to ``archived_at`` (defaults to now UTC).
        Returns the count of guides that were archived.

        Used when course content text changes and linked guides become stale
        (update_course_content, replace_course_content_file routes).
        """
        now = archived_at or datetime.now(timezone.utc)
        guides = self.db.execute(
            select(StudyGuide).where(
                StudyGuide.course_content_id == content_id,
                StudyGuide.archived_at.is_(None),
            )
        ).scalars().all()

        for guide in guides:
            guide.archived_at = now

        return len(guides)
