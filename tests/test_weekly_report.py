"""Tests for the Weekly Family Report Card (#2228)."""

import pytest
from unittest.mock import patch, AsyncMock

from tests.conftest import PASSWORD, _auth


PARENT_EMAIL = "weekly_report_parent@test.com"
STUDENT_EMAIL = "weekly_report_student@test.com"


@pytest.fixture()
def setup_family(client, db_session):
    """Create a parent with a linked student for testing."""
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.core.security import get_password_hash
    from sqlalchemy import insert

    # Check if already exists
    existing = db_session.query(User).filter(User.email == PARENT_EMAIL).first()
    if existing:
        student_user = db_session.query(User).filter(User.email == STUDENT_EMAIL).first()
        student = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        return {"parent": existing, "student_user": student_user, "student": student}

    parent = User(
        email=PARENT_EMAIL,
        full_name="Report Parent",
        hashed_password=get_password_hash(PASSWORD),
        role=UserRole.PARENT,
        roles="parent",
        email_verified=True,
        is_active=True,
        email_notifications=True,
    )
    db_session.add(parent)
    db_session.flush()

    student_user = User(
        email=STUDENT_EMAIL,
        full_name="Report Student",
        hashed_password=get_password_hash(PASSWORD),
        role=UserRole.STUDENT,
        roles="student",
        email_verified=True,
        is_active=True,
    )
    db_session.add(student_user)
    db_session.flush()

    student = Student(user_id=student_user.id, grade_level=8)
    db_session.add(student)
    db_session.flush()

    db_session.execute(
        insert(parent_students).values(parent_id=parent.id, student_id=student.id)
    )
    db_session.commit()

    return {"parent": parent, "student_user": student_user, "student": student}


class TestWeeklyReportService:
    """Unit tests for the report generation service."""

    def test_generate_report_no_children(self, db_session, client):
        """Report for a parent with no children returns empty."""
        from app.models.user import User, UserRole
        from app.core.security import get_password_hash
        from app.services.weekly_report_service import generate_weekly_report

        # Create a lonely parent
        lonely = db_session.query(User).filter(User.email == "lonely_report@test.com").first()
        if not lonely:
            lonely = User(
                email="lonely_report@test.com",
                full_name="Lonely Parent",
                hashed_password=get_password_hash(PASSWORD),
                role=UserRole.PARENT,
                roles="parent",
                email_verified=True,
                is_active=True,
            )
            db_session.add(lonely)
            db_session.commit()

        report = generate_weekly_report(db_session, lonely.id)
        assert report.children == []
        assert "No children linked" in report.overall_summary

    def test_generate_report_with_child(self, db_session, setup_family, client):
        """Report includes child data."""
        from app.services.weekly_report_service import generate_weekly_report

        parent = setup_family["parent"]
        report = generate_weekly_report(db_session, parent.id)

        assert len(report.children) == 1
        child = report.children[0]
        assert child.full_name == "Report Student"
        assert child.grade_level == 8
        assert 0 <= child.engagement_score <= 100
        assert report.family_engagement_score >= 0
        assert report.share_url is not None
        assert "report/" in report.share_url

    def test_engagement_score_computation(self, client):
        """Engagement score produces expected values."""
        from app.services.weekly_report_service import _compute_engagement_score

        # Perfect engagement
        score = _compute_engagement_score(
            tasks_completed=5, tasks_total=5,
            assignments_submitted=3, assignments_due=3,
            study_guides=5, quiz_count=3, streak_days=7,
        )
        assert score == 100

        # Zero engagement
        score = _compute_engagement_score(
            tasks_completed=0, tasks_total=5,
            assignments_submitted=0, assignments_due=3,
            study_guides=0, quiz_count=0, streak_days=0,
        )
        assert score == 0

        # No tasks or assignments (100% by default) but no other activity
        score = _compute_engagement_score(
            tasks_completed=0, tasks_total=0,
            assignments_submitted=0, assignments_due=0,
            study_guides=0, quiz_count=0, streak_days=0,
        )
        assert score == 50  # 100% tasks + 100% assignments = 50 points, rest 0

    def test_share_token_deterministic(self, client):
        """Same inputs produce the same share token."""
        from app.services.weekly_report_service import generate_share_token

        token1 = generate_share_token(1, "2026-03-17")
        token2 = generate_share_token(1, "2026-03-17")
        assert token1 == token2
        assert len(token1) == 16

        # Different week = different token
        token3 = generate_share_token(1, "2026-03-24")
        assert token3 != token1


class TestWeeklyReportEndpoints:
    """Integration tests for the API endpoints."""

    def test_preview_requires_parent_role(self, client, db_session):
        """Non-parent users cannot access the preview endpoint."""
        resp = client.get("/api/parent/weekly-report")
        assert resp.status_code == 401

    def test_preview_returns_report(self, client, db_session, setup_family):
        """Parent can preview the weekly report."""
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get("/api/parent/weekly-report", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "week_start" in data
        assert "week_end" in data
        assert "children" in data
        assert "family_engagement_score" in data
        assert "share_url" in data

    @patch("app.services.weekly_report_service.send_email", new_callable=AsyncMock, return_value=True)
    def test_send_report_email(self, mock_send, client, db_session, setup_family):
        """Parent can trigger sending the report email."""
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post("/api/parent/weekly-report/send", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        mock_send.assert_called_once()


class TestWeeklyReportEmailRendering:
    """Tests for HTML email rendering."""

    def test_render_produces_html(self, db_session, setup_family, client):
        """Rendered email contains expected HTML structure."""
        from app.services.weekly_report_service import (
            generate_weekly_report,
            render_report_email_html,
        )

        parent = setup_family["parent"]
        report = generate_weekly_report(db_session, parent.id)
        html = render_report_email_html(report, unsubscribe_url="https://example.com/unsub")

        assert "Weekly Family Report Card" in html
        assert "Family Engagement Score" in html
        assert "Report Student" in html
        assert "classbridge-logo.png" in html
        assert "Unsubscribe" in html
        assert "Share this report" in html
