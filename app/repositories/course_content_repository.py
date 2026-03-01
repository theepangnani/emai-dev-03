"""Repository for CourseContent data access operations.

Extracts SQLAlchemy query patterns from app/api/routes/course_contents.py
into named, reusable methods.  The visibility logic (which courses a user
can see) lives in the route helpers (_get_visible_course_ids) for now;
this repository focuses on the content-level queries.
"""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.course_content import CourseContent
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.repositories.base import BaseRepository


class CourseContentRepository(BaseRepository[CourseContent]):
    """Data access layer for the CourseContent model."""

    def __init__(self, db: Session) -> None:
        super().__init__(CourseContent, db)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def list_for_course(
        self,
        course_id: int,
        *,
        content_type: str | None = None,
        include_archived: bool = False,
    ) -> Sequence[CourseContent]:
        """Return all content items belonging to a specific course.

        Mirrors the scoped branch of the ``list_course_contents`` route when
        ``course_id`` is provided.  Access control (can_access_course) must
        be checked by the caller before invoking this method.
        """
        stmt = select(CourseContent).where(CourseContent.course_id == course_id)

        if not include_archived:
            stmt = stmt.where(CourseContent.archived_at.is_(None))

        if content_type is not None:
            stmt = stmt.where(CourseContent.content_type == content_type.strip().lower())

        stmt = stmt.order_by(CourseContent.created_at.desc())
        return self.db.execute(stmt).scalars().all()

    def list_for_user(
        self,
        user_id: int,
        *,
        course_id: int | None = None,
        content_type: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CourseContent]:
        """Return content created by ``user_id``, optionally scoped to a course.

        This covers the teacher / admin use-case where the user sees their own
        uploaded content.  For cross-user visibility (parent seeing children's
        content) use ``list_for_visible_courses`` instead.
        """
        stmt = select(CourseContent).where(
            CourseContent.created_by_user_id == user_id
        )

        if course_id is not None:
            stmt = stmt.where(CourseContent.course_id == course_id)

        if not include_archived:
            stmt = stmt.where(CourseContent.archived_at.is_(None))

        if content_type is not None:
            stmt = stmt.where(CourseContent.content_type == content_type.strip().lower())

        stmt = stmt.order_by(CourseContent.created_at.desc()).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def list_for_student(
        self,
        student_user_id: int,
        *,
        course_id: int | None = None,
        include_archived: bool = False,
    ) -> Sequence[CourseContent]:
        """Return content visible to a student.

        A student can see content they created themselves, plus content from
        courses they are enrolled in.  Access is resolved via the student's
        course enrollments.

        ``course_id`` scopes results to a single course when provided.
        """
        # Resolve the student's enrolled course IDs
        student = self.db.execute(
            select(Student).where(Student.user_id == student_user_id)
        ).scalars().first()

        if student:
            enrolled_ids = [c.id for c in student.courses]
        else:
            enrolled_ids = []

        # Content created by the student OR in their enrolled courses
        from sqlalchemy import or_
        conditions = [CourseContent.created_by_user_id == student_user_id]
        if enrolled_ids:
            conditions.append(CourseContent.course_id.in_(enrolled_ids))

        stmt = select(CourseContent).where(or_(*conditions))

        if course_id is not None:
            stmt = stmt.where(CourseContent.course_id == course_id)

        if not include_archived:
            stmt = stmt.where(CourseContent.archived_at.is_(None))

        stmt = stmt.order_by(CourseContent.created_at.desc())
        return self.db.execute(stmt).scalars().all()

    def list_for_visible_courses(
        self,
        course_ids: list[int],
        *,
        content_type: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[CourseContent]:
        """Return content belonging to any of the supplied ``course_ids``.

        The caller is responsible for computing which course IDs are visible
        to the requesting user (see ``_get_visible_course_ids`` in routes).
        This keeps the repository free of role-specific visibility logic.
        """
        if not course_ids:
            return []

        stmt = select(CourseContent).where(
            CourseContent.course_id.in_(course_ids)
        )

        if not include_archived:
            stmt = stmt.where(CourseContent.archived_at.is_(None))

        if content_type is not None:
            stmt = stmt.where(CourseContent.content_type == content_type.strip().lower())

        stmt = stmt.order_by(CourseContent.created_at.desc()).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def list_for_parent_children(
        self,
        parent_user_id: int,
        *,
        course_id: int | None = None,
        content_type: str | None = None,
        include_archived: bool = False,
    ) -> Sequence[CourseContent]:
        """Return content visible to a parent via their linked children.

        Resolves the parent → student → course chain and returns content from
        any course that at least one child is enrolled in.

        ``course_id`` scopes to a single course when provided.
        """
        # Resolve child student IDs
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

        # Resolve course IDs via the student_courses join table
        enrolled_course_ids = [
            r[0]
            for r in self.db.execute(
                select(student_courses.c.course_id).where(
                    student_courses.c.student_id.in_(child_student_ids)
                )
            ).all()
        ]
        if not enrolled_course_ids:
            return []

        stmt = select(CourseContent).where(
            CourseContent.course_id.in_(enrolled_course_ids)
        )

        if course_id is not None:
            stmt = stmt.where(CourseContent.course_id == course_id)

        if not include_archived:
            stmt = stmt.where(CourseContent.archived_at.is_(None))

        if content_type is not None:
            stmt = stmt.where(CourseContent.content_type == content_type.strip().lower())

        stmt = stmt.order_by(CourseContent.created_at.desc())
        return self.db.execute(stmt).scalars().all()

    def get_with_study_guide(self, content_id: int) -> CourseContent | None:
        """Load a single CourseContent with its linked study guides eagerly loaded.

        Uses selectinload on the ``study_guides`` backref so that accessing
        ``content.study_guides`` does not trigger additional lazy queries.
        Returns ``None`` when the content item does not exist.
        """
        stmt = (
            select(CourseContent)
            .options(selectinload(CourseContent.study_guides))
            .where(CourseContent.id == content_id)
        )
        return self.db.execute(stmt).scalars().first()

    def get_active_study_guides_for_content(
        self, content_id: int
    ) -> Sequence[StudyGuide]:
        """Return all non-archived study guides linked to a content item.

        Used when archiving linked guides after the source content text changes
        (see update_course_content and replace_course_content_file routes).
        """
        stmt = select(StudyGuide).where(
            StudyGuide.course_content_id == content_id,
            StudyGuide.archived_at.is_(None),
        )
        return self.db.execute(stmt).scalars().all()

    def search_in_courses(
        self,
        course_ids: list[int],
        search: str,
        *,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CourseContent]:
        """Full-text search on title and description within a set of courses.

        Performs a case-insensitive LIKE match against ``title`` and
        ``description``.  ``course_ids`` must be pre-filtered by the caller for
        access control.
        """
        if not course_ids:
            return []

        from app.core.utils import escape_like
        pattern = f"%{escape_like(search.strip())}%"

        from sqlalchemy import or_
        stmt = (
            select(CourseContent)
            .where(
                CourseContent.course_id.in_(course_ids),
                or_(
                    CourseContent.title.ilike(pattern),
                    CourseContent.description.ilike(pattern),
                ),
            )
        )

        if not include_archived:
            stmt = stmt.where(CourseContent.archived_at.is_(None))

        stmt = stmt.order_by(CourseContent.created_at.desc()).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()
