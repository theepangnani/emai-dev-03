"""Tests for Study Sessions (Pomodoro) (#2021)."""
import pytest
from unittest.mock import patch

from conftest import PASSWORD, _auth


@pytest.fixture()
def study_student(db_session):
    """Create or retrieve a test student for study session tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)

    student = db_session.query(User).filter(User.email == "study_session_student@test.com").first()
    if not student:
        student = User(
            email="study_session_student@test.com",
            username="study_session_student",
            hashed_password=hashed,
            full_name="Study Student",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(student)
        db_session.commit()
    return student


class TestStartSession:
    def test_start_session(self, client, study_student):
        headers = _auth(client, study_student.email)
        resp = client.post(
            "/api/study-sessions/start",
            json={"subject": "Math", "target_duration": 1500},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Math"
        assert data["duration_seconds"] == 0
        assert data["completed"] is False

    def test_start_session_with_course(self, client, study_student):
        headers = _auth(client, study_student.email)
        resp = client.post(
            "/api/study-sessions/start",
            json={"subject": "Science", "course_id": None},
            headers=headers,
        )
        assert resp.status_code == 201


class TestCompleteSession:
    def test_complete_under_20_min_no_xp(self, client, study_student):
        headers = _auth(client, study_student.email)
        # Start
        start_resp = client.post(
            "/api/study-sessions/start",
            json={"subject": "English"},
            headers=headers,
        )
        session_id = start_resp.json()["id"]

        # Complete with < 20 min (600 seconds = 10 min) — should not award XP
        resp = client.post(
            f"/api/study-sessions/{session_id}/complete",
            json={"duration_seconds": 600},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] is False
        assert data["xp_awarded"] is None

    def test_complete_over_20_min_awards_xp(self, client, study_student, db_session):
        headers = _auth(client, study_student.email)

        # Clean up prior XP data
        from app.models.xp import XpLedger, XpSummary
        db_session.query(XpLedger).filter(XpLedger.student_id == study_student.id).delete()
        db_session.query(XpSummary).filter(XpSummary.student_id == study_student.id).delete()
        db_session.commit()

        # Start
        start_resp = client.post(
            "/api/study-sessions/start",
            json={"subject": "History"},
            headers=headers,
        )
        session_id = start_resp.json()["id"]

        # Complete with >= 20 min (1500 seconds = 25 min)
        with patch("app.api.routes.study_sessions._generate_ai_recap", return_value="Great job!"):
            resp = client.post(
                f"/api/study-sessions/{session_id}/complete",
                json={"duration_seconds": 1500},
                headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] is True
        assert data["xp_awarded"] is not None
        assert data["xp_awarded"] > 0
        assert data["ai_recap"] == "Great job!"

    def test_complete_already_completed_returns_400(self, client, study_student):
        headers = _auth(client, study_student.email)
        start_resp = client.post(
            "/api/study-sessions/start",
            json={"subject": "Art"},
            headers=headers,
        )
        session_id = start_resp.json()["id"]

        # Complete first time
        with patch("app.api.routes.study_sessions._generate_ai_recap", return_value=None):
            client.post(
                f"/api/study-sessions/{session_id}/complete",
                json={"duration_seconds": 1500},
                headers=headers,
            )

        # Try completing again
        resp = client.post(
            f"/api/study-sessions/{session_id}/complete",
            json={"duration_seconds": 1500},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_complete_nonexistent_returns_404(self, client, study_student):
        headers = _auth(client, study_student.email)
        resp = client.post(
            "/api/study-sessions/99999/complete",
            json={"duration_seconds": 1500},
            headers=headers,
        )
        assert resp.status_code == 404


class TestListSessions:
    def test_list_sessions(self, client, study_student):
        headers = _auth(client, study_student.email)
        resp = client.get("/api/study-sessions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestStats:
    def test_stats(self, client, study_student):
        headers = _auth(client, study_student.email)
        resp = client.get("/api/study-sessions/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions" in data
        assert "total_minutes" in data
        assert "xp_earned" in data
