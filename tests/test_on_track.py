"""
Tests for the "Is My Child On Track?" signal (#2020).
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from conftest import PASSWORD, _auth


@pytest.fixture()
def on_track_users(db_session):
    """Create parent, student, course for on-track tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.course import Course, student_courses
    from sqlalchemy import insert

    hashed = get_password_hash(PASSWORD)

    parent = db_session.query(User).filter(User.email == "ot_parent@test.com").first()
    if parent:
        student_user = db_session.query(User).filter(User.email == "ot_student@test.com").first()
        outsider = db_session.query(User).filter(User.email == "ot_outsider@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        course = db_session.query(Course).filter(Course.name == "OT Test Course").first()
        return {
            "parent": parent, "student_user": student_user, "outsider": outsider,
            "student_rec": student_rec, "course": course,
        }

    parent = User(email="ot_parent@test.com", full_name="OT Parent", role=UserRole.PARENT, hashed_password=hashed)
    student_user = User(email="ot_student@test.com", full_name="OT Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="ot_outsider@test.com", full_name="OT Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, student_user, outsider])
    db_session.flush()

    student_rec = Student(user_id=student_user.id)
    db_session.add(student_rec)
    db_session.flush()

    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    course = Course(name="OT Test Course", created_by_user_id=parent.id, is_private=False)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(
        student_id=student_rec.id, course_id=course.id,
    ))
    db_session.commit()

    for u in [parent, student_user, outsider]:
        db_session.refresh(u)
    db_session.refresh(student_rec)
    db_session.refresh(course)

    return {
        "parent": parent, "student_user": student_user, "outsider": outsider,
        "student_rec": student_rec, "course": course,
    }


# ── Service unit tests ──


class TestOnTrackSignalCalculation:
    def test_green_recent_activity(self, db_session, on_track_users):
        """Student with activity today -> green."""
        from app.models.xp import XpSummary
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]

        # Clean up prior summary
        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.add(XpSummary(
            student_id=student_user.id,
            total_xp=100,
            current_level=1,
            current_streak=1,
            longest_streak=1,
            last_qualifying_action_date=date.today(),
        ))
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "green"
        assert result["last_activity_days"] == 0

    def test_green_two_days_ago(self, db_session, on_track_users):
        """Student with activity 2 days ago -> green."""
        from app.models.xp import XpSummary
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]

        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.add(XpSummary(
            student_id=student_user.id,
            total_xp=100,
            current_level=1,
            current_streak=1,
            longest_streak=1,
            last_qualifying_action_date=date.today() - timedelta(days=2),
        ))
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "green"
        assert result["last_activity_days"] == 2

    def test_yellow_five_days(self, db_session, on_track_users):
        """Student with activity 5 days ago, no upcoming work -> yellow."""
        from app.models.xp import XpSummary
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]

        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.add(XpSummary(
            student_id=student_user.id,
            total_xp=100,
            current_level=1,
            current_streak=0,
            longest_streak=1,
            last_qualifying_action_date=date.today() - timedelta(days=5),
        ))
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "yellow"
        assert result["last_activity_days"] == 5

    def test_red_eight_days(self, db_session, on_track_users):
        """Student with activity 8 days ago -> red."""
        from app.models.xp import XpSummary
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]

        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.add(XpSummary(
            student_id=student_user.id,
            total_xp=100,
            current_level=1,
            current_streak=0,
            longest_streak=1,
            last_qualifying_action_date=date.today() - timedelta(days=8),
        ))
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "red"
        assert result["last_activity_days"] == 8

    def test_red_no_activity_ever(self, db_session, on_track_users):
        """Student with no XP summary at all -> red."""
        from app.models.xp import XpSummary
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]

        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "red"
        assert result["last_activity_days"] is None

    def test_escalation_upcoming_and_inactive(self, db_session, on_track_users):
        """4 days inactive + upcoming assignment -> escalate to red."""
        from app.models.xp import XpSummary
        from app.models.assignment import Assignment
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]
        course = on_track_users["course"]

        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.add(XpSummary(
            student_id=student_user.id,
            total_xp=100,
            current_level=1,
            current_streak=0,
            longest_streak=1,
            last_qualifying_action_date=date.today() - timedelta(days=4),
        ))

        # Add an upcoming assignment
        assignment = Assignment(
            title="OT Test Assignment",
            course_id=course.id,
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
        )
        db_session.add(assignment)
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "red"
        assert result["upcoming_count"] >= 1

        # Clean up
        db_session.delete(assignment)
        db_session.commit()

    def test_green_with_upcoming_but_active(self, db_session, on_track_users):
        """Recent activity + upcoming work -> still green."""
        from app.models.xp import XpSummary
        from app.models.assignment import Assignment
        from app.services.on_track_service import OnTrackService

        student_user = on_track_users["student_user"]
        student_rec = on_track_users["student_rec"]
        course = on_track_users["course"]

        db_session.query(XpSummary).filter(XpSummary.student_id == student_user.id).delete()
        db_session.add(XpSummary(
            student_id=student_user.id,
            total_xp=100,
            current_level=1,
            current_streak=3,
            longest_streak=3,
            last_qualifying_action_date=date.today() - timedelta(days=1),
        ))

        assignment = Assignment(
            title="OT Test Assignment Green",
            course_id=course.id,
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
        )
        db_session.add(assignment)
        db_session.commit()

        result = OnTrackService.get_signal(db_session, student_rec.id, student_user.id)
        assert result["signal"] == "green"
        assert result["upcoming_count"] >= 1

        # Clean up
        db_session.delete(assignment)
        db_session.commit()


# ── API endpoint tests ──


class TestOnTrackEndpoint:
    def test_parent_gets_signal(self, client, on_track_users):
        """Parent can fetch on-track signal for linked child."""
        headers = _auth(client, on_track_users["parent"].email)
        student_id = on_track_users["student_rec"].id
        resp = client.get(f"/api/parent/children/{student_id}/on-track", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal"] in ("green", "yellow", "red")
        assert "reason" in data
        assert "last_activity_days" in data
        assert "upcoming_count" in data

    def test_outsider_cannot_access(self, client, on_track_users):
        """Non-linked parent gets 404."""
        headers = _auth(client, on_track_users["outsider"].email)
        student_id = on_track_users["student_rec"].id
        resp = client.get(f"/api/parent/children/{student_id}/on-track", headers=headers)
        assert resp.status_code == 404

    def test_student_cannot_access(self, client, on_track_users):
        """Student role cannot access parent endpoint."""
        headers = _auth(client, on_track_users["student_user"].email)
        student_id = on_track_users["student_rec"].id
        resp = client.get(f"/api/parent/children/{student_id}/on-track", headers=headers)
        assert resp.status_code == 403

    def test_nonexistent_student(self, client, on_track_users):
        """Requesting signal for non-existent student returns 404."""
        headers = _auth(client, on_track_users["parent"].email)
        resp = client.get("/api/parent/children/99999/on-track", headers=headers)
        assert resp.status_code == 404
