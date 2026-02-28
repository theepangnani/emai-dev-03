"""Provider-agnostic LMS sync service.

Consumes canonical models from any ``LMSProvider`` implementation and
persists them into the ClassBridge database.  This service owns the
upsert logic (create-or-update) for courses, assignments, and materials
so that individual adapters remain stateless data-fetchers.

The existing Google Classroom sync in ``app/api/routes/google_classroom.py``
continues to work unchanged.  This service is intended for **new** code
paths and for gradual migration.

Part of #775 / #776.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.services.lms.provider import (
    CanonicalAssignment,
    CanonicalCourse,
    CanonicalMaterial,
    LMSProvider,
)

logger = logging.getLogger(__name__)


class LMSSyncService:
    """Orchestrates syncing data from an LMS provider into the local DB.

    Parameters
    ----------
    provider : LMSProvider
        An authenticated provider instance.
    db : Session
        Active SQLAlchemy database session.
    """

    def __init__(self, provider: LMSProvider, db: Session):
        self.provider = provider
        self.db = db

    # ── Course sync ──────────────────────────────────────────────────

    def sync_courses(self, user_id: int) -> list[Course]:
        """Fetch courses from the provider and upsert into the DB.

        Parameters
        ----------
        user_id : int
            The ClassBridge user performing the sync (used for
            ``created_by_user_id`` on newly created courses).

        Returns
        -------
        list[Course]
            All synced (created or updated) Course ORM instances.
        """
        provider_name = self.provider.get_provider_name()
        canonical_courses = self.provider.get_courses()

        synced: list[Course] = []

        for cc in canonical_courses:
            course = self._upsert_course(cc, user_id, provider_name)
            synced.append(course)

        self.db.commit()
        logger.info(
            "LMS sync_courses: provider=%s, user=%s, count=%d",
            provider_name, user_id, len(synced),
        )
        return synced

    def _upsert_course(
        self,
        cc: CanonicalCourse,
        user_id: int,
        provider_name: str,
    ) -> Course:
        """Create or update a single Course from a canonical model."""
        # Look up by the provider's external ID.
        # Currently only google_classroom_id exists on the model; future
        # providers can use a generic ``lms_external_id`` column.
        existing = (
            self.db.query(Course)
            .filter(Course.google_classroom_id == cc.external_id)
            .first()
        )

        if existing:
            existing.name = cc.name or existing.name
            existing.description = cc.description
            if cc.subject and not existing.subject:
                existing.subject = cc.subject
            return existing

        course = Course(
            name=cc.name or "Untitled Course",
            description=cc.description,
            subject=cc.subject,
            google_classroom_id=cc.external_id,
            created_by_user_id=user_id,
        )
        self.db.add(course)
        self.db.flush()
        return course

    # ── Assignment sync ──────────────────────────────────────────────

    def sync_assignments(self, course_id: int, course_external_id: str) -> list[Assignment]:
        """Fetch assignments for a course and upsert into the DB.

        Parameters
        ----------
        course_id : int
            Local DB course ID.
        course_external_id : str
            The provider's external course ID.

        Returns
        -------
        list[Assignment]
            All synced Assignment ORM instances.
        """
        canonical_assignments = self.provider.get_assignments(course_external_id)

        synced: list[Assignment] = []

        for ca in canonical_assignments:
            assignment = self._upsert_assignment(ca, course_id)
            synced.append(assignment)

        self.db.commit()
        logger.info(
            "LMS sync_assignments: provider=%s, course=%d, count=%d",
            self.provider.get_provider_name(), course_id, len(synced),
        )
        return synced

    def _upsert_assignment(self, ca: CanonicalAssignment, course_id: int) -> Assignment:
        """Create or update a single Assignment from a canonical model."""
        existing = (
            self.db.query(Assignment)
            .filter(Assignment.google_classroom_id == ca.external_id)
            .first()
        )

        if existing:
            existing.title = ca.title or existing.title
            existing.description = ca.description
            if ca.due_date:
                existing.due_date = ca.due_date
            if ca.max_points is not None:
                existing.max_points = ca.max_points
            return existing

        assignment = Assignment(
            title=ca.title or "Untitled Assignment",
            description=ca.description,
            course_id=course_id,
            google_classroom_id=ca.external_id,
            due_date=ca.due_date,
            max_points=ca.max_points,
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    # ── Materials sync ───────────────────────────────────────────────

    def sync_materials(self, course_id: int, course_external_id: str) -> list[CourseContent]:
        """Fetch course materials and upsert into the DB.

        Parameters
        ----------
        course_id : int
            Local DB course ID.
        course_external_id : str
            The provider's external course ID.

        Returns
        -------
        list[CourseContent]
            All synced CourseContent ORM instances.
        """
        canonical_materials = self.provider.get_materials(course_external_id)

        synced: list[CourseContent] = []

        for cm in canonical_materials:
            # Skip drafts / deleted items
            if cm.state in ("DRAFT", "DELETED"):
                continue
            content = self._upsert_material(cm, course_id)
            synced.append(content)

        self.db.commit()
        logger.info(
            "LMS sync_materials: provider=%s, course=%d, count=%d",
            self.provider.get_provider_name(), course_id, len(synced),
        )
        return synced

    def _upsert_material(self, cm: CanonicalMaterial, course_id: int) -> CourseContent:
        """Create or update a single CourseContent from a canonical model."""
        existing = (
            self.db.query(CourseContent)
            .filter(CourseContent.google_classroom_material_id == cm.external_id)
            .first()
        )

        if existing:
            existing.title = cm.title or existing.title
            existing.description = cm.description or existing.description
            existing.google_classroom_url = cm.link or existing.google_classroom_url
            existing.reference_url = cm.reference_url or existing.reference_url
            return existing

        content = CourseContent(
            course_id=course_id,
            title=cm.title or "Untitled Material",
            description=cm.description or "",
            content_type="resources",
            google_classroom_url=cm.link,
            google_classroom_material_id=cm.external_id,
            reference_url=cm.reference_url,
        )
        self.db.add(content)
        self.db.flush()
        return content

    # ── Full sync (courses + assignments + materials) ────────────────

    def sync_all(self, user_id: int) -> dict:
        """Convenience method: sync courses, then assignments and materials
        for each synced course.

        Returns
        -------
        dict
            Summary with ``courses``, ``assignments_synced``, and
            ``materials_synced`` counts.
        """
        courses = self.sync_courses(user_id)

        total_assignments = 0
        total_materials = 0

        for course in courses:
            if not course.google_classroom_id:
                continue

            assignments = self.sync_assignments(
                course.id, course.google_classroom_id,
            )
            total_assignments += len(assignments)

            materials = self.sync_materials(
                course.id, course.google_classroom_id,
            )
            total_materials += len(materials)

        return {
            "provider": self.provider.get_provider_name(),
            "courses": [
                {
                    "id": c.id,
                    "name": c.name,
                    "external_id": c.google_classroom_id,
                }
                for c in courses
            ],
            "courses_synced": len(courses),
            "assignments_synced": total_assignments,
            "materials_synced": total_materials,
        }
