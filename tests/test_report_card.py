"""Tests for the Report Card API (GET /api/report-card) (#2018)."""

import pytest
from datetime import datetime, timezone

from conftest import PASSWORD, _auth


@pytest.fixture()
def report_card_data(db_session):
    """Create a student with study data for report card testing."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide
    from app.models.quiz_result import QuizResult
    from app.models.xp import Badge, XpLedger, XpSummary
    from app.models.study_session import StudySession

    hashed = get_password_hash(PASSWORD)

    user = db_session.query(User).filter(User.email == "rcstudent@test.com").first()
    if user:
        return {"user": user}

    user = User(
        email="rcstudent@test.com",
        full_name="Report Card Student",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add(user)
    db_session.commit()

    student = Student(user_id=user.id, grade_level=10)
    db_session.add(student)
    db_session.commit()

    course = Course(name="RC Math", created_by_user_id=user.id)
    db_session.add(course)
    db_session.commit()

    cc = CourseContent(
        course_id=course.id,
        title="Chapter 1 Notes",
        content_type="notes",
        created_by_user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(cc)
    db_session.commit()

    sg = StudyGuide(
        user_id=user.id,
        course_id=course.id,
        title="Guide: Chapter 1",
        content="Test content",
        guide_type="study_guide",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sg)
    db_session.commit()

    qr = QuizResult(
        user_id=user.id,
        study_guide_id=sg.id,
        score=8,
        total_questions=10,
        percentage=80.0,
        answers_json='{"0":"A"}',
        attempt_number=1,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(qr)
    db_session.commit()

    badge = Badge(
        student_id=user.id,
        badge_id="first_upload",
        awarded_at=datetime.now(timezone.utc),
    )
    db_session.add(badge)
    db_session.commit()

    xp_summary = XpSummary(
        student_id=user.id,
        total_xp=300,
        current_level=2,
        longest_streak=7,
    )
    db_session.add(xp_summary)
    db_session.commit()

    xp = XpLedger(
        student_id=user.id,
        action_type="upload",
        xp_awarded=10,
        multiplier=1.0,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(xp)
    db_session.commit()

    session = StudySession(
        student_id=user.id,
        duration_seconds=1500,
        target_duration=1500,
        completed=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(session)
    db_session.commit()

    return {"user": user}


class TestReportCardEndpoint:
    """Tests for GET /api/report-card."""

    def test_report_card_returns_data(self, client, report_card_data):
        """Report card returns all expected fields."""
        headers = _auth(client, "rcstudent@test.com")
        resp = client.get("/api/report-card", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_name"] == "Report Card Student"
        assert "term" in data
        assert isinstance(data["subjects_studied"], list)
        assert data["total_uploads"] >= 1
        assert data["total_guides"] >= 1
        assert data["total_quizzes"] >= 1
        assert data["total_xp"] >= 10
        assert data["level_reached"]["level"] >= 1
        assert len(data["badges_earned"]) >= 1
        assert data["longest_streak"] >= 7
        assert data["study_sessions"] >= 1
        assert data["total_study_minutes"] >= 25

    def test_report_card_with_term_param(self, client, report_card_data):
        """Report card accepts a term parameter."""
        headers = _auth(client, "rcstudent@test.com")
        resp = client.get("/api/report-card?term=winter2026", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["term"] == "Winter 2026"

    def test_report_card_requires_auth(self, client, report_card_data):
        """Endpoint requires authentication."""
        resp = client.get("/api/report-card")
        assert resp.status_code == 401

    def test_report_card_subjects_have_course_info(self, client, report_card_data):
        """Subjects studied include course name, guide count, quiz count."""
        headers = _auth(client, "rcstudent@test.com")
        resp = client.get("/api/report-card", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        if data["subjects_studied"]:
            subject = data["subjects_studied"][0]
            assert "name" in subject
            assert "guides" in subject
            assert "quizzes" in subject
