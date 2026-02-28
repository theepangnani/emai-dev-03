"""Google Classroom adapter implementing the LMSProvider interface.

Wraps the existing ``app.services.google_classroom`` module -- all Google
API calls are delegated to that module so the adapter is a thin translation
layer.  This keeps the existing endpoints and sync logic untouched while
enabling provider-agnostic workflows through the LMS abstraction.

Part of #775 / #776.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.services import google_classroom as gc_service
from app.services.lms.provider import (
    CanonicalAssignment,
    CanonicalCourse,
    CanonicalGrade,
    CanonicalMaterial,
    CanonicalStudent,
    CanonicalTeacher,
    LMSProvider,
)

logger = logging.getLogger(__name__)


class GoogleClassroomAdapter(LMSProvider):
    """Translates Google Classroom API responses into canonical LMS models.

    Parameters
    ----------
    access_token : str
        Valid Google OAuth2 access token.
    refresh_token : str | None
        Optional refresh token for automatic credential renewal.
    """

    def __init__(self, access_token: str, refresh_token: str | None = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        # Updated credentials after API calls (caller can read these to
        # persist refreshed tokens).
        self.last_credentials = None

    # ── Provider identity ────────────────────────────────────────────

    def get_provider_name(self) -> str:
        return "google_classroom"

    # ── Courses ──────────────────────────────────────────────────────

    def get_courses(self) -> list[CanonicalCourse]:
        """Fetch all courses visible to the authenticated user."""
        courses, credentials = gc_service.list_courses(
            self.access_token, self.refresh_token,
        )
        self._update_credentials(credentials)

        return [
            CanonicalCourse(
                external_id=str(c["id"]),
                name=c.get("name", ""),
                description=c.get("description"),
                subject=c.get("subject") or c.get("section"),
                section=c.get("section"),
            )
            for c in courses
        ]

    # ── Assignments ──────────────────────────────────────────────────

    def get_assignments(self, course_external_id: str) -> list[CanonicalAssignment]:
        """Fetch all coursework for a given course."""
        coursework, credentials = gc_service.get_course_work(
            self.access_token, course_external_id, self.refresh_token,
        )
        self._update_credentials(credentials)

        result: list[CanonicalAssignment] = []
        for cw in coursework:
            due_date = self._parse_due_date(cw.get("dueDate"))
            result.append(
                CanonicalAssignment(
                    external_id=str(cw["id"]),
                    course_external_id=course_external_id,
                    title=cw.get("title", "Untitled Assignment"),
                    description=cw.get("description"),
                    due_date=due_date,
                    max_points=cw.get("maxPoints"),
                    link=cw.get("alternateLink"),
                )
            )
        return result

    # ── Grades / submissions ─────────────────────────────────────────

    def get_grades(self, course_external_id: str, assignment_external_id: str) -> list[CanonicalGrade]:
        """Fetch student submissions for a specific assignment."""
        submissions, credentials = gc_service.get_student_submissions(
            self.access_token,
            course_external_id,
            assignment_external_id,
            self.refresh_token,
        )
        self._update_credentials(credentials)

        result: list[CanonicalGrade] = []
        for sub in submissions:
            grade = sub.get("assignedGrade") or sub.get("draftGrade")
            state = sub.get("state", "NEW")
            status = self._map_submission_state(state)
            max_points = sub.get("maxPoints", 0)

            student_id = sub.get("userId", "")
            if not student_id:
                continue

            result.append(
                CanonicalGrade(
                    assignment_external_id=assignment_external_id,
                    student_external_id=str(student_id),
                    grade=grade,
                    max_grade=max_points,
                    status=status,
                )
            )
        return result

    # ── Students ─────────────────────────────────────────────────────

    def get_students(self, course_external_id: str) -> list[CanonicalStudent]:
        """Fetch students enrolled in a course."""
        students, credentials = gc_service.list_course_students(
            self.access_token, course_external_id, self.refresh_token,
        )
        self._update_credentials(credentials)

        result: list[CanonicalStudent] = []
        for s in students:
            profile = s.get("profile", {})
            name_obj = profile.get("name", {})
            email = profile.get("emailAddress", "")
            full_name = name_obj.get("fullName", "")
            user_id = s.get("userId", "")

            if not user_id:
                continue

            result.append(
                CanonicalStudent(
                    external_id=str(user_id),
                    email=email,
                    name=full_name,
                )
            )
        return result

    # ── Teachers ─────────────────────────────────────────────────────

    def get_teachers(self, course_external_id: str) -> list[CanonicalTeacher]:
        """Fetch teachers for a course."""
        teachers, credentials = gc_service.list_course_teachers(
            self.access_token, course_external_id, self.refresh_token,
        )
        self._update_credentials(credentials)

        result: list[CanonicalTeacher] = []
        for t in teachers:
            profile = t.get("profile", {})
            name_obj = profile.get("name", {})
            email = profile.get("emailAddress", "")
            full_name = name_obj.get("fullName", "")
            user_id = t.get("userId", "")

            if not user_id:
                continue

            result.append(
                CanonicalTeacher(
                    external_id=str(user_id),
                    email=email,
                    name=full_name,
                )
            )
        return result

    # ── Materials ────────────────────────────────────────────────────

    def get_materials(self, course_external_id: str) -> list[CanonicalMaterial]:
        """Fetch course materials / resources."""
        materials, credentials = gc_service.get_course_work_materials(
            self.access_token, course_external_id, self.refresh_token,
        )
        self._update_credentials(credentials)

        result: list[CanonicalMaterial] = []
        for mat in materials:
            material_id = mat.get("id")
            if not material_id:
                continue

            # Extract the first useful link from the materials array
            reference_url = self._extract_reference_url(mat.get("materials", []))

            result.append(
                CanonicalMaterial(
                    external_id=str(material_id),
                    course_external_id=course_external_id,
                    title=mat.get("title", "Untitled Material"),
                    description=mat.get("description"),
                    link=mat.get("alternateLink"),
                    reference_url=reference_url,
                    state=mat.get("state"),
                )
            )
        return result

    # ── Internal helpers ─────────────────────────────────────────────

    def _update_credentials(self, credentials) -> None:
        """Stash refreshed credentials so the caller can persist them."""
        self.last_credentials = credentials
        if credentials and credentials.token:
            self.access_token = credentials.token
            if credentials.refresh_token:
                self.refresh_token = credentials.refresh_token

    @staticmethod
    def _parse_due_date(due_date_obj: dict | None) -> datetime | None:
        """Convert Google Classroom dueDate dict to a datetime."""
        if not due_date_obj:
            return None
        try:
            return datetime(
                due_date_obj.get("year", 2024),
                due_date_obj.get("month", 1),
                due_date_obj.get("day", 1),
            )
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _map_submission_state(state: str) -> str:
        """Map Google Classroom submission state to our canonical status."""
        mapping = {
            "NEW": "pending",
            "CREATED": "pending",
            "TURNED_IN": "submitted",
            "RETURNED": "graded",
            "RECLAIMED_BY_STUDENT": "submitted",
        }
        return mapping.get(state, "pending")

    @staticmethod
    def _extract_reference_url(materials_list: list[dict]) -> str | None:
        """Extract the first link URL from a Google Classroom materials array."""
        for item in materials_list:
            if "link" in item:
                return item["link"].get("url")
            if "driveFile" in item:
                return item["driveFile"].get("driveFile", {}).get("alternateLink")
            if "youtubeVideo" in item:
                return item["youtubeVideo"].get("alternateLink")
        return None
