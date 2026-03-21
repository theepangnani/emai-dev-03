"""Tests for assessment date detection regex and API endpoints."""
import pytest
from datetime import date, timedelta

from app.services.assessment_detector import detect_assessments
from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Unit tests: detect_assessments regex
# ---------------------------------------------------------------------------

class TestDetectAssessments:
    def test_empty_text(self):
        assert detect_assessments("", "test.pdf") == []

    def test_no_dates(self):
        assert detect_assessments("This is a regular document with no dates", "doc.pdf") == []

    def test_month_day_format(self):
        ref = date(2026, 3, 1)
        text = "Math test on March 25"
        results = detect_assessments(text, "syllabus.pdf", reference_date=ref)
        assert len(results) == 1
        assert results[0]["event_type"] == "test"
        assert results[0]["event_date"] == date(2026, 3, 25)
        assert results[0]["source"] == "document_parse"

    def test_iso_date_format(self):
        ref = date(2026, 3, 1)
        text = "Final exam: 2026-04-10"
        results = detect_assessments(text, "schedule.pdf", reference_date=ref)
        assert len(results) == 1
        assert results[0]["event_type"] == "exam"
        assert results[0]["event_date"] == date(2026, 4, 10)

    def test_quiz_keyword(self):
        ref = date(2026, 3, 1)
        text = "quiz on April 3"
        results = detect_assessments(text, "notes.pdf", reference_date=ref)
        assert len(results) == 1
        assert results[0]["event_type"] == "quiz"

    def test_day_name(self):
        ref = date(2026, 3, 16)  # Monday
        text = "quiz Friday"
        results = detect_assessments(text, "class.pdf", reference_date=ref)
        assert len(results) == 1
        assert results[0]["event_date"] == date(2026, 3, 20)  # next Friday

    def test_multiple_events(self):
        ref = date(2026, 3, 1)
        text = "test on March 25\nmidterm April 5"
        results = detect_assessments(text, "syllabus.pdf", reference_date=ref)
        assert len(results) == 2

    def test_past_dates_excluded(self):
        ref = date(2026, 3, 20)
        text = "test on March 10"
        results = detect_assessments(text, "old.pdf", reference_date=ref)
        assert len(results) == 0

    def test_far_future_excluded(self):
        ref = date(2026, 3, 1)
        text = "exam on December 25"
        results = detect_assessments(text, "future.pdf", reference_date=ref)
        assert len(results) == 0  # >90 days away

    def test_no_keyword_no_match(self):
        ref = date(2026, 3, 1)
        text = "Meeting on March 25"
        results = detect_assessments(text, "notes.pdf", reference_date=ref)
        assert len(results) == 0

    def test_us_date_format(self):
        ref = date(2026, 3, 1)
        text = "due date: 04/15/2026"
        results = detect_assessments(text, "hw.pdf", reference_date=ref)
        assert len(results) == 1
        assert results[0]["event_date"] == date(2026, 4, 15)

    def test_deduplication(self):
        ref = date(2026, 3, 1)
        text = "test on March 25\ntest on March 25"
        results = detect_assessments(text, "dup.pdf", reference_date=ref)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def event_users(db_session):
    """Create users for event tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students

    hashed = get_password_hash(PASSWORD)

    student_user = db_session.query(User).filter(User.email == "evtstudent@test.com").first()
    if student_user:
        parent = db_session.query(User).filter(User.email == "evtparent@test.com").first()
        student = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        return {"student_user": student_user, "parent": parent, "student": student}

    student_user = User(email="evtstudent@test.com", full_name="Evt Student", role=UserRole.STUDENT, hashed_password=hashed)
    parent = User(email="evtparent@test.com", full_name="Evt Parent", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([student_user, parent])
    db_session.commit()

    student = Student(user_id=student_user.id, grade_level=9)
    db_session.add(student)
    db_session.commit()

    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student.id))
    db_session.commit()

    return {"student_user": student_user, "parent": parent, "student": student}


def test_create_event(client, event_users):
    headers = _auth(client, "evtstudent@test.com")
    resp = client.post("/api/events", json={
        "event_type": "test",
        "event_title": "Math Unit Test",
        "event_date": (date.today() + timedelta(days=5)).isoformat(),
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["event_title"] == "Math Unit Test"
    assert data["event_type"] == "test"
    assert data["days_remaining"] == 5


def test_get_upcoming_events(client, event_users):
    headers = _auth(client, "evtstudent@test.com")
    resp = client.get("/api/events/upcoming", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_dismiss_event(client, event_users):
    headers = _auth(client, "evtstudent@test.com")
    # Create first
    resp = client.post("/api/events", json={
        "event_type": "quiz",
        "event_title": "Science Quiz",
        "event_date": (date.today() + timedelta(days=3)).isoformat(),
    }, headers=headers)
    event_id = resp.json()["id"]

    # Dismiss
    resp = client.delete(f"/api/events/{event_id}", headers=headers)
    assert resp.status_code == 200

    # Should not appear in upcoming
    resp = client.get("/api/events/upcoming", headers=headers)
    ids = [e["id"] for e in resp.json()]
    assert event_id not in ids


def test_parent_sees_child_events(client, event_users):
    # Student creates event
    student_headers = _auth(client, "evtstudent@test.com")
    client.post("/api/events", json={
        "event_type": "exam",
        "event_title": "Final Exam - visible to parent",
        "event_date": (date.today() + timedelta(days=7)).isoformat(),
    }, headers=student_headers)

    # Parent should see it
    parent_headers = _auth(client, "evtparent@test.com")
    resp = client.get("/api/events/upcoming", headers=parent_headers)
    assert resp.status_code == 200
    titles = [e["event_title"] for e in resp.json()]
    assert "Final Exam - visible to parent" in titles


def test_unauthenticated_rejected(client):
    resp = client.get("/api/events/upcoming")
    assert resp.status_code == 401
