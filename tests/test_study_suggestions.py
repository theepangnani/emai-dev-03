"""Tests for Smart Study Time Suggestions (#2227)."""
import pytest
from datetime import datetime, timezone, timedelta

from conftest import PASSWORD, _auth


@pytest.fixture()
def suggestion_student(db_session):
    """Create a test student for study suggestions tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)
    student = db_session.query(User).filter(User.email == "suggest_student@test.com").first()
    if not student:
        student = User(
            email="suggest_student@test.com",
            username="suggest_student",
            hashed_password=hashed,
            full_name="Suggest Student",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(student)
        db_session.commit()
    return student


@pytest.fixture()
def suggestion_parent(db_session):
    """Create a test parent for study suggestions tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)
    parent = db_session.query(User).filter(User.email == "suggest_parent@test.com").first()
    if not parent:
        parent = User(
            email="suggest_parent@test.com",
            username="suggest_parent",
            hashed_password=hashed,
            full_name="Suggest Parent",
            role=UserRole.PARENT,
            roles="parent",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(parent)
        db_session.commit()
    return parent


@pytest.fixture()
def linked_student(db_session, suggestion_student, suggestion_parent):
    """Create a Student record linked to the parent."""
    from app.models.student import Student, parent_students

    student_record = db_session.query(Student).filter(Student.user_id == suggestion_student.id).first()
    if not student_record:
        student_record = Student(user_id=suggestion_student.id, grade_level=10)
        db_session.add(student_record)
        db_session.commit()

    # Link parent to student
    link = db_session.query(parent_students).filter(
        parent_students.c.parent_id == suggestion_parent.id,
        parent_students.c.student_id == student_record.id,
    ).first()
    if not link:
        db_session.execute(parent_students.insert().values(
            parent_id=suggestion_parent.id,
            student_id=student_record.id,
        ))
        db_session.commit()

    return student_record


class TestStudentSelfSuggestions:
    def test_get_own_suggestions_empty(self, client, suggestion_student):
        """Student with no activity gets empty suggestions."""
        headers = _auth(client, suggestion_student.email)
        resp = client.get("/api/students/me/study-suggestions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["top_slots"] == []
        assert len(data["weekly_chart"]) == 7
        assert data["current_week_minutes"] == 0
        assert data["weekly_trend"] == "steady"

    def test_get_suggestions_with_sessions(self, client, suggestion_student, db_session):
        """Student with study sessions gets meaningful suggestions."""
        from app.models.study_session import StudySession

        now = datetime.now(timezone.utc)
        # Create a few sessions at evening time
        for i in range(3):
            session = StudySession(
                student_id=suggestion_student.id,
                subject="Math",
                duration_seconds=1800,
                target_duration=1800,
                completed=True,
                created_at=now - timedelta(days=i, hours=2),
            )
            db_session.add(session)
        db_session.commit()

        headers = _auth(client, suggestion_student.email)
        resp = client.get("/api/students/me/study-suggestions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["top_slots"]) > 0
        assert data["top_slots"][0]["score"] > 0
        assert data["weekly_chart"] is not None


class TestParentAccessSuggestions:
    def test_parent_gets_child_suggestions(
        self, client, suggestion_parent, linked_student,
    ):
        """Parent can access linked child's study suggestions."""
        headers = _auth(client, suggestion_parent.email)
        resp = client.get(
            f"/api/students/{linked_student.id}/study-suggestions",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "top_slots" in data
        assert "weekly_chart" in data

    def test_parent_cannot_access_unlinked_student(
        self, client, suggestion_parent, db_session,
    ):
        """Parent cannot access a student they are not linked to."""
        from app.models.user import User, UserRole
        from app.models.student import Student
        from app.core.security import get_password_hash

        # Create an unlinked student
        other_user = db_session.query(User).filter(User.email == "other_suggest@test.com").first()
        if not other_user:
            other_user = User(
                email="other_suggest@test.com",
                username="other_suggest",
                hashed_password=get_password_hash(PASSWORD),
                full_name="Other Student",
                role=UserRole.STUDENT,
                roles="student",
                onboarding_completed=True,
                email_verified=True,
            )
            db_session.add(other_user)
            db_session.commit()

        other_student = db_session.query(Student).filter(Student.user_id == other_user.id).first()
        if not other_student:
            other_student = Student(user_id=other_user.id, grade_level=9)
            db_session.add(other_student)
            db_session.commit()

        headers = _auth(client, suggestion_parent.email)
        resp = client.get(
            f"/api/students/{other_student.id}/study-suggestions",
            headers=headers,
        )
        assert resp.status_code == 403


class TestSuggestionsServiceUnit:
    def test_build_time_slots_empty(self):
        from app.services.study_suggestions_service import _build_time_slots
        assert _build_time_slots([]) == []

    def test_build_time_slots_grouped(self):
        from app.services.study_suggestions_service import _build_time_slots

        now = datetime(2026, 3, 24, 19, 30, tzinfo=timezone.utc)  # Tuesday evening
        timestamps = [now - timedelta(hours=i * 24) for i in range(5)]
        slots = _build_time_slots(timestamps)
        assert len(slots) > 0
        assert slots[0].score == 100.0

    def test_suggest_next_session(self):
        from app.services.study_suggestions_service import _suggest_next_session
        from app.schemas.study_suggestions import StudyTimeSlot

        slot = StudyTimeSlot(
            day_of_week="Weekdays",
            time_of_day="Evening (5 - 10 PM)",
            period="evening",
            score=100.0,
            label="test",
        )
        # Tuesday morning
        now = datetime(2026, 3, 24, 9, 0, tzinfo=timezone.utc)
        result = _suggest_next_session([slot], now)
        assert result is not None
        assert "5 PM" in result
