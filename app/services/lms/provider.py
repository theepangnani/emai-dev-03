"""LMS Provider abstract interface and canonical data models.

Defines the contract that all LMS integrations (Google Classroom, Canvas,
Schoology, etc.) must implement. Canonical models are plain dataclasses
used as DTOs between the provider layer and the sync service -- they are
intentionally NOT SQLAlchemy models.

Part of #775 / #776.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


# ── Canonical data models ────────────────────────────────────────────


@dataclass
class CanonicalCourse:
    """Provider-agnostic representation of a course / class."""

    external_id: str
    name: str
    description: str | None = None
    subject: str | None = None
    section: str | None = None
    teacher_name: str | None = None
    teacher_email: str | None = None


@dataclass
class CanonicalAssignment:
    """Provider-agnostic representation of an assignment / coursework."""

    external_id: str
    course_external_id: str
    title: str
    description: str | None = None
    due_date: datetime | None = None
    max_points: float | None = None
    link: str | None = None


@dataclass
class CanonicalGrade:
    """Provider-agnostic representation of a student submission / grade."""

    assignment_external_id: str
    student_external_id: str
    grade: float | None = None
    max_grade: float = 0.0
    status: str = "pending"  # pending, submitted, graded


@dataclass
class CanonicalStudent:
    """Provider-agnostic representation of a student enrolled in a course."""

    external_id: str
    email: str
    name: str


@dataclass
class CanonicalMaterial:
    """Provider-agnostic representation of course material / resource."""

    external_id: str
    course_external_id: str
    title: str
    description: str | None = None
    link: str | None = None
    reference_url: str | None = None
    state: str | None = None  # e.g. "PUBLISHED", "DRAFT"


@dataclass
class CanonicalTeacher:
    """Provider-agnostic representation of a teacher for a course."""

    external_id: str
    email: str
    name: str


# ── Abstract provider interface ──────────────────────────────────────


class LMSProvider(ABC):
    """Abstract interface for Learning Management System integrations.

    Each concrete implementation wraps a specific LMS API (Google Classroom,
    Canvas, Schoology, etc.) and translates its domain objects into the
    canonical models above.

    Implementations are expected to handle their own authentication and
    token refresh internally.
    """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the unique provider identifier (e.g. ``"google_classroom"``)."""
        ...

    @abstractmethod
    def get_courses(self) -> list[CanonicalCourse]:
        """List all courses visible to the authenticated user."""
        ...

    @abstractmethod
    def get_assignments(self, course_external_id: str) -> list[CanonicalAssignment]:
        """List assignments for a specific course."""
        ...

    @abstractmethod
    def get_grades(self, course_external_id: str, assignment_external_id: str) -> list[CanonicalGrade]:
        """List student grades / submissions for a specific assignment in a course."""
        ...

    @abstractmethod
    def get_students(self, course_external_id: str) -> list[CanonicalStudent]:
        """List students enrolled in a specific course."""
        ...

    @abstractmethod
    def get_teachers(self, course_external_id: str) -> list[CanonicalTeacher]:
        """List teachers / instructors for a specific course."""
        ...

    @abstractmethod
    def get_materials(self, course_external_id: str) -> list[CanonicalMaterial]:
        """List course materials / resources for a specific course."""
        ...
