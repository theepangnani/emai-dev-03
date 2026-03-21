"""Tests for the Study Timeline API (GET /api/activity/timeline) (#2017)."""

import pytest
from datetime import datetime, timezone

from conftest import PASSWORD, _auth


@pytest.fixture()
def timeline_data(db_session):
    """Create a student with various activities for timeline testing."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide
    from app.models.quiz_result import QuizResult
    from app.models.xp import Badge, XpLedger, XpSummary

    hashed = get_password_hash(PASSWORD)

    # Check for existing rows (session-scoped DB)
    user = db_session.query(User).filter(User.email == "tlstudent@test.com").first()
    if user:
        course = db_session.query(Course).filter(Course.name == "Timeline Math").first()
        return {"user": user, "course": course}

    user = User(
        email="tlstudent@test.com",
        full_name="Timeline Student",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add(user)
    db_session.commit()

    student = Student(user_id=user.id, grade_level=10)
    db_session.add(student)
    db_session.commit()

    # Course
    course = Course(name="Timeline Math", created_by_user_id=user.id)
    db_session.add(course)
    db_session.commit()

    # Upload
    cc = CourseContent(
        course_id=course.id,
        title="Chapter 5 Notes",
        content_type="notes",
        created_by_user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(cc)
    db_session.commit()

    # Study guide
    sg = StudyGuide(
        user_id=user.id,
        course_id=course.id,
        title="Study Guide: Chapter 5",
        content="Test content",
        guide_type="study_guide",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sg)
    db_session.commit()

    # Quiz result
    qr = QuizResult(
        user_id=user.id,
        study_guide_id=sg.id,
        score=17,
        total_questions=20,
        percentage=85.0,
        answers_json='{"0":"A"}',
        attempt_number=1,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(qr)
    db_session.commit()

    # Badge
    badge = Badge(
        student_id=user.id,
        badge_id="first_upload",
        awarded_at=datetime.now(timezone.utc),
    )
    db_session.add(badge)
    db_session.commit()

    # XP ledger + summary (for level-up detection)
    xp_summary = XpSummary(student_id=user.id, total_xp=250, current_level=2)
    db_session.add(xp_summary)
    db_session.commit()

    xp1 = XpLedger(
        student_id=user.id,
        action_type="upload",
        xp_awarded=10,
        multiplier=1.0,
        created_at=datetime.now(timezone.utc),
    )
    xp2 = XpLedger(
        student_id=user.id,
        action_type="study_guide",
        xp_awarded=240,
        multiplier=1.0,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([xp1, xp2])
    db_session.commit()

    return {"user": user, "course": course}


class TestTimelineEndpoint:
    """Tests for GET /api/activity/timeline."""

    def test_timeline_returns_all_types(self, client, timeline_data):
        """Timeline returns uploads, study guides, quizzes, badges, and level-ups."""
        headers = _auth(client, "tlstudent@test.com")
        resp = client.get("/api/activity/timeline?days=30", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        types_found = {item["type"] for item in data["items"]}
        # Should have at least upload, study_guide, quiz, badge
        assert "upload" in types_found
        assert "study_guide" in types_found
        assert "quiz" in types_found
        assert "badge" in types_found

    def test_timeline_filter_by_type(self, client, timeline_data):
        """Filtering by type returns only that type."""
        headers = _auth(client, "tlstudent@test.com")
        resp = client.get("/api/activity/timeline?days=30&type=upload", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["type"] == "upload"

    def test_timeline_filter_by_course(self, client, timeline_data):
        """Filtering by course_id returns only items from that course."""
        headers = _auth(client, "tlstudent@test.com")
        course_id = timeline_data["course"].id
        resp = client.get(
            f"/api/activity/timeline?days=30&course_id={course_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # All items with a course should match
        for item in data["items"]:
            if item["course"]:
                assert item["course"] == "Timeline Math"

    def test_timeline_pagination(self, client, timeline_data):
        """Limit and offset work correctly."""
        headers = _auth(client, "tlstudent@test.com")
        resp = client.get(
            "/api/activity/timeline?days=30&limit=2&offset=0",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= len(data["items"])

    def test_timeline_requires_auth(self, client, timeline_data):
        """Endpoint requires authentication."""
        resp = client.get("/api/activity/timeline?days=30")
        assert resp.status_code == 401

    def test_timeline_level_up_detected(self, client, timeline_data):
        """Level-up events are detected from XP ledger crossings."""
        headers = _auth(client, "tlstudent@test.com")
        resp = client.get("/api/activity/timeline?days=30&type=level_up", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # With 250 total XP (10+240), should cross level 2 threshold (200)
        level_ups = [i for i in data["items"] if i["type"] == "level_up"]
        assert len(level_ups) >= 1
        assert "Level 2" in level_ups[0]["title"]
