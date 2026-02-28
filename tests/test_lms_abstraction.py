"""Tests for the LMS abstraction layer (#775, #776).

Tests the provider interface, Google Classroom adapter, registry, and
sync service using mocked Google API responses.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from conftest import PASSWORD

from app.services.lms.provider import (
    CanonicalAssignment,
    CanonicalCourse,
    CanonicalGrade,
    CanonicalMaterial,
    CanonicalStudent,
    CanonicalTeacher,
    LMSProvider,
)
from app.services.lms.google_classroom_adapter import GoogleClassroomAdapter
from app.services.lms import get_provider, list_providers


# ── Fixtures ─────────────────────────────────────────────────────────

MOCK_COURSES = [
    {
        "id": "course-001",
        "name": "Math 101",
        "description": "Intro to Math",
        "subject": "Mathematics",
        "section": "Section A",
    },
    {
        "id": "course-002",
        "name": "Science 201",
        "description": None,
        "section": "Section B",
    },
]

MOCK_COURSEWORK = [
    {
        "id": "cw-001",
        "title": "Homework 1",
        "description": "Do problems 1-10",
        "dueDate": {"year": 2026, "month": 3, "day": 15},
        "maxPoints": 100,
        "alternateLink": "https://classroom.google.com/cw/001",
    },
    {
        "id": "cw-002",
        "title": "Quiz 1",
        "description": None,
        "maxPoints": 50,
    },
]

MOCK_STUDENTS = [
    {
        "userId": "student-001",
        "profile": {
            "name": {"fullName": "Alice Student"},
            "emailAddress": "alice@school.edu",
        },
    },
    {
        "userId": "student-002",
        "profile": {
            "name": {"fullName": "Bob Student"},
            "emailAddress": "bob@school.edu",
        },
    },
]

MOCK_TEACHERS = [
    {
        "userId": "teacher-001",
        "profile": {
            "name": {"fullName": "Jane Teacher"},
            "emailAddress": "jane@school.edu",
        },
    },
]

MOCK_SUBMISSIONS = [
    {
        "userId": "student-001",
        "assignedGrade": 95.0,
        "state": "RETURNED",
        "maxPoints": 100,
    },
    {
        "userId": "student-002",
        "state": "TURNED_IN",
        "maxPoints": 100,
    },
]

MOCK_MATERIALS = [
    {
        "id": "mat-001",
        "title": "Lecture Notes",
        "description": "Week 1 notes",
        "alternateLink": "https://classroom.google.com/mat/001",
        "state": "PUBLISHED",
        "materials": [
            {"link": {"url": "https://example.com/notes.pdf"}},
        ],
    },
    {
        "id": "mat-002",
        "title": "Draft Material",
        "state": "DRAFT",
        "materials": [],
    },
]

MOCK_CREDENTIALS = MagicMock()
MOCK_CREDENTIALS.token = "refreshed-access-token"
MOCK_CREDENTIALS.refresh_token = "refreshed-refresh-token"


@pytest.fixture()
def lms_user(db_session):
    """Create a user with mock Google tokens for LMS testing."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "lms_test_user@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        user.google_access_token = "mock-access-token"
        user.google_refresh_token = "mock-refresh-token"
        db_session.commit()
        return user

    user = User(
        email=email,
        full_name="LMS Test User",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
        google_access_token="mock-access-token",
        google_refresh_token="mock-refresh-token",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Provider interface tests ─────────────────────────────────────────

class TestLMSProviderInterface:
    """Verify that LMSProvider cannot be instantiated directly."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            LMSProvider()

    def test_concrete_subclass_must_implement_all_methods(self):
        """Incomplete subclass should raise TypeError."""

        class IncompleteProvider(LMSProvider):
            def get_provider_name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteProvider()


# ── Registry tests ───────────────────────────────────────────────────

class TestLMSRegistry:
    def test_get_google_classroom_provider(self):
        provider = get_provider(
            "google_classroom",
            access_token="test-token",
            refresh_token="test-refresh",
        )
        assert isinstance(provider, GoogleClassroomAdapter)
        assert provider.get_provider_name() == "google_classroom"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LMS provider"):
            get_provider("canvas")

    def test_list_providers(self):
        providers = list_providers()
        assert "google_classroom" in providers

    def test_provider_is_lms_provider_instance(self):
        provider = get_provider(
            "google_classroom",
            access_token="test-token",
        )
        assert isinstance(provider, LMSProvider)


# ── Google Classroom Adapter tests ───────────────────────────────────

class TestGoogleClassroomAdapter:

    def _make_adapter(self):
        return GoogleClassroomAdapter(
            access_token="test-access-token",
            refresh_token="test-refresh-token",
        )

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_courses")
    def test_get_courses(self, mock_list_courses):
        mock_list_courses.return_value = (MOCK_COURSES, MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        courses = adapter.get_courses()

        assert len(courses) == 2
        assert all(isinstance(c, CanonicalCourse) for c in courses)

        c1 = courses[0]
        assert c1.external_id == "course-001"
        assert c1.name == "Math 101"
        assert c1.description == "Intro to Math"
        assert c1.subject == "Mathematics"
        assert c1.section == "Section A"

        c2 = courses[1]
        assert c2.external_id == "course-002"
        assert c2.name == "Science 201"
        assert c2.description is None
        # subject falls back to section when subject is missing
        assert c2.subject == "Section B"

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_courses")
    def test_get_courses_empty(self, mock_list_courses):
        mock_list_courses.return_value = ([], MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        courses = adapter.get_courses()
        assert courses == []

    @patch("app.services.lms.google_classroom_adapter.gc_service.get_course_work")
    def test_get_assignments(self, mock_get_course_work):
        mock_get_course_work.return_value = (MOCK_COURSEWORK, MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        assignments = adapter.get_assignments("course-001")

        assert len(assignments) == 2
        assert all(isinstance(a, CanonicalAssignment) for a in assignments)

        a1 = assignments[0]
        assert a1.external_id == "cw-001"
        assert a1.course_external_id == "course-001"
        assert a1.title == "Homework 1"
        assert a1.due_date == datetime(2026, 3, 15)
        assert a1.max_points == 100
        assert a1.link == "https://classroom.google.com/cw/001"

        a2 = assignments[1]
        assert a2.external_id == "cw-002"
        assert a2.due_date is None
        assert a2.max_points == 50

    @patch("app.services.lms.google_classroom_adapter.gc_service.get_student_submissions")
    def test_get_grades(self, mock_submissions):
        mock_submissions.return_value = (MOCK_SUBMISSIONS, MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        grades = adapter.get_grades("course-001", "cw-001")

        assert len(grades) == 2
        assert all(isinstance(g, CanonicalGrade) for g in grades)

        g1 = grades[0]
        assert g1.student_external_id == "student-001"
        assert g1.grade == 95.0
        assert g1.status == "graded"

        g2 = grades[1]
        assert g2.student_external_id == "student-002"
        assert g2.grade is None
        assert g2.status == "submitted"

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_course_students")
    def test_get_students(self, mock_list_students):
        mock_list_students.return_value = (MOCK_STUDENTS, MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        students = adapter.get_students("course-001")

        assert len(students) == 2
        assert all(isinstance(s, CanonicalStudent) for s in students)
        assert students[0].external_id == "student-001"
        assert students[0].email == "alice@school.edu"
        assert students[0].name == "Alice Student"

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_course_teachers")
    def test_get_teachers(self, mock_list_teachers):
        mock_list_teachers.return_value = (MOCK_TEACHERS, MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        teachers = adapter.get_teachers("course-001")

        assert len(teachers) == 1
        assert isinstance(teachers[0], CanonicalTeacher)
        assert teachers[0].external_id == "teacher-001"
        assert teachers[0].email == "jane@school.edu"
        assert teachers[0].name == "Jane Teacher"

    @patch("app.services.lms.google_classroom_adapter.gc_service.get_course_work_materials")
    def test_get_materials(self, mock_materials):
        mock_materials.return_value = (MOCK_MATERIALS, MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        materials = adapter.get_materials("course-001")

        assert len(materials) == 2
        assert all(isinstance(m, CanonicalMaterial) for m in materials)

        m1 = materials[0]
        assert m1.external_id == "mat-001"
        assert m1.title == "Lecture Notes"
        assert m1.reference_url == "https://example.com/notes.pdf"
        assert m1.state == "PUBLISHED"

        # Draft material is still returned by adapter (sync service filters)
        m2 = materials[1]
        assert m2.state == "DRAFT"

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_courses")
    def test_credentials_update_after_api_call(self, mock_list_courses):
        mock_list_courses.return_value = ([], MOCK_CREDENTIALS)
        adapter = self._make_adapter()

        assert adapter.access_token == "test-access-token"
        adapter.get_courses()
        assert adapter.access_token == "refreshed-access-token"
        assert adapter.refresh_token == "refreshed-refresh-token"
        assert adapter.last_credentials is MOCK_CREDENTIALS

    def test_parse_due_date_valid(self):
        result = GoogleClassroomAdapter._parse_due_date(
            {"year": 2026, "month": 6, "day": 15}
        )
        assert result == datetime(2026, 6, 15)

    def test_parse_due_date_none(self):
        assert GoogleClassroomAdapter._parse_due_date(None) is None

    def test_parse_due_date_invalid(self):
        assert GoogleClassroomAdapter._parse_due_date(
            {"year": 2026, "month": 13, "day": 1}
        ) is None

    def test_map_submission_state(self):
        assert GoogleClassroomAdapter._map_submission_state("NEW") == "pending"
        assert GoogleClassroomAdapter._map_submission_state("TURNED_IN") == "submitted"
        assert GoogleClassroomAdapter._map_submission_state("RETURNED") == "graded"
        assert GoogleClassroomAdapter._map_submission_state("UNKNOWN") == "pending"

    def test_extract_reference_url_link(self):
        items = [{"link": {"url": "https://example.com"}}]
        assert GoogleClassroomAdapter._extract_reference_url(items) == "https://example.com"

    def test_extract_reference_url_drive(self):
        items = [
            {"driveFile": {"driveFile": {"alternateLink": "https://drive.google.com/file"}}}
        ]
        assert GoogleClassroomAdapter._extract_reference_url(items) == "https://drive.google.com/file"

    def test_extract_reference_url_youtube(self):
        items = [
            {"youtubeVideo": {"alternateLink": "https://youtube.com/watch?v=123"}}
        ]
        assert GoogleClassroomAdapter._extract_reference_url(items) == "https://youtube.com/watch?v=123"

    def test_extract_reference_url_empty(self):
        assert GoogleClassroomAdapter._extract_reference_url([]) is None


# ── Sync Service tests ───────────────────────────────────────────────

class TestLMSSyncService:
    """Test the provider-agnostic sync service with mocked adapter."""

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_courses")
    def test_sync_courses_creates_new(self, mock_list_courses, db_session, lms_user):
        from app.models.course import Course
        from app.services.lms.sync_service import LMSSyncService

        mock_list_courses.return_value = (MOCK_COURSES, MOCK_CREDENTIALS)

        # Clean up any leftover courses from previous test runs
        db_session.query(Course).filter(
            Course.google_classroom_id.in_(["course-001", "course-002"])
        ).delete(synchronize_session=False)
        db_session.commit()

        adapter = GoogleClassroomAdapter(
            access_token="test-token", refresh_token="test-refresh",
        )
        sync = LMSSyncService(provider=adapter, db=db_session)

        courses = sync.sync_courses(user_id=lms_user.id)

        assert len(courses) == 2
        assert courses[0].name == "Math 101"
        assert courses[0].google_classroom_id == "course-001"
        assert courses[1].name == "Science 201"

        # Verify persisted
        db_course = db_session.query(Course).filter(
            Course.google_classroom_id == "course-001"
        ).first()
        assert db_course is not None
        assert db_course.name == "Math 101"

    @patch("app.services.lms.google_classroom_adapter.gc_service.list_courses")
    def test_sync_courses_updates_existing(self, mock_list_courses, db_session, lms_user):
        from app.models.course import Course
        from app.services.lms.sync_service import LMSSyncService

        # Pre-create course
        existing = db_session.query(Course).filter(
            Course.google_classroom_id == "course-001"
        ).first()
        if not existing:
            existing = Course(
                name="Old Name",
                google_classroom_id="course-001",
            )
            db_session.add(existing)
            db_session.commit()

        mock_list_courses.return_value = (MOCK_COURSES[:1], MOCK_CREDENTIALS)

        adapter = GoogleClassroomAdapter(
            access_token="test-token", refresh_token="test-refresh",
        )
        sync = LMSSyncService(provider=adapter, db=db_session)

        courses = sync.sync_courses(user_id=lms_user.id)

        assert len(courses) == 1
        assert courses[0].name == "Math 101"  # Updated from API

    @patch("app.services.lms.google_classroom_adapter.gc_service.get_course_work")
    def test_sync_assignments(self, mock_get_cw, db_session, lms_user):
        from app.models.assignment import Assignment
        from app.models.course import Course
        from app.services.lms.sync_service import LMSSyncService

        # Ensure course exists
        course = db_session.query(Course).filter(
            Course.google_classroom_id == "course-001"
        ).first()
        if not course:
            course = Course(name="Math 101", google_classroom_id="course-001")
            db_session.add(course)
            db_session.commit()
            db_session.refresh(course)

        # Clean up old assignments
        db_session.query(Assignment).filter(
            Assignment.google_classroom_id.in_(["cw-001", "cw-002"])
        ).delete(synchronize_session=False)
        db_session.commit()

        mock_get_cw.return_value = (MOCK_COURSEWORK, MOCK_CREDENTIALS)

        adapter = GoogleClassroomAdapter(
            access_token="test-token", refresh_token="test-refresh",
        )
        sync = LMSSyncService(provider=adapter, db=db_session)

        assignments = sync.sync_assignments(course.id, "course-001")

        assert len(assignments) == 2
        assert assignments[0].title == "Homework 1"
        assert assignments[0].due_date == datetime(2026, 3, 15)
        assert assignments[0].max_points == 100
        assert assignments[1].title == "Quiz 1"

    @patch("app.services.lms.google_classroom_adapter.gc_service.get_course_work_materials")
    def test_sync_materials_skips_drafts(self, mock_materials, db_session, lms_user):
        from app.models.course import Course
        from app.models.course_content import CourseContent
        from app.services.lms.sync_service import LMSSyncService

        course = db_session.query(Course).filter(
            Course.google_classroom_id == "course-001"
        ).first()
        if not course:
            course = Course(name="Math 101", google_classroom_id="course-001")
            db_session.add(course)
            db_session.commit()
            db_session.refresh(course)

        # Clean up
        db_session.query(CourseContent).filter(
            CourseContent.google_classroom_material_id.in_(["mat-001", "mat-002"])
        ).delete(synchronize_session=False)
        db_session.commit()

        mock_materials.return_value = (MOCK_MATERIALS, MOCK_CREDENTIALS)

        adapter = GoogleClassroomAdapter(
            access_token="test-token", refresh_token="test-refresh",
        )
        sync = LMSSyncService(provider=adapter, db=db_session)

        materials = sync.sync_materials(course.id, "course-001")

        # Should skip the DRAFT material
        assert len(materials) == 1
        assert materials[0].title == "Lecture Notes"
        assert materials[0].reference_url == "https://example.com/notes.pdf"

    @patch("app.services.lms.google_classroom_adapter.gc_service.get_course_work_materials")
    @patch("app.services.lms.google_classroom_adapter.gc_service.get_course_work")
    @patch("app.services.lms.google_classroom_adapter.gc_service.list_courses")
    def test_sync_all(self, mock_courses, mock_cw, mock_materials, db_session, lms_user):
        from app.models.assignment import Assignment
        from app.models.course import Course
        from app.models.course_content import CourseContent
        from app.services.lms.sync_service import LMSSyncService

        # Clean up
        db_session.query(CourseContent).filter(
            CourseContent.google_classroom_material_id.in_(["mat-001", "mat-002"])
        ).delete(synchronize_session=False)
        db_session.query(Assignment).filter(
            Assignment.google_classroom_id.in_(["cw-001", "cw-002"])
        ).delete(synchronize_session=False)
        db_session.query(Course).filter(
            Course.google_classroom_id.in_(["course-001", "course-002"])
        ).delete(synchronize_session=False)
        db_session.commit()

        mock_courses.return_value = (MOCK_COURSES[:1], MOCK_CREDENTIALS)
        mock_cw.return_value = (MOCK_COURSEWORK, MOCK_CREDENTIALS)
        mock_materials.return_value = (MOCK_MATERIALS, MOCK_CREDENTIALS)

        adapter = GoogleClassroomAdapter(
            access_token="test-token", refresh_token="test-refresh",
        )
        sync = LMSSyncService(provider=adapter, db=db_session)

        result = sync.sync_all(user_id=lms_user.id)

        assert result["provider"] == "google_classroom"
        assert result["courses_synced"] == 1
        assert result["assignments_synced"] == 2
        assert result["materials_synced"] == 1  # Draft excluded


# ── Canonical model tests ────────────────────────────────────────────

class TestCanonicalModels:
    """Verify canonical dataclass defaults and creation."""

    def test_canonical_course_defaults(self):
        c = CanonicalCourse(external_id="1", name="Test")
        assert c.description is None
        assert c.subject is None
        assert c.section is None
        assert c.teacher_name is None
        assert c.teacher_email is None

    def test_canonical_assignment_defaults(self):
        a = CanonicalAssignment(
            external_id="1", course_external_id="c1", title="HW"
        )
        assert a.due_date is None
        assert a.max_points is None
        assert a.link is None

    def test_canonical_grade_defaults(self):
        g = CanonicalGrade(
            assignment_external_id="a1",
            student_external_id="s1",
        )
        assert g.grade is None
        assert g.max_grade == 0.0
        assert g.status == "pending"

    def test_canonical_student(self):
        s = CanonicalStudent(external_id="1", email="a@b.com", name="Alice")
        assert s.external_id == "1"

    def test_canonical_material_defaults(self):
        m = CanonicalMaterial(
            external_id="1", course_external_id="c1", title="Notes"
        )
        assert m.description is None
        assert m.link is None
        assert m.reference_url is None
        assert m.state is None

    def test_canonical_teacher(self):
        t = CanonicalTeacher(external_id="1", email="t@b.com", name="Teacher")
        assert t.external_id == "1"
