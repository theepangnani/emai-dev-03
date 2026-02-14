"""Tests for critical date parsing and auto-task creation from AI-generated content."""

import pytest
from datetime import datetime

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


class TestParseCriticalDates:
    """Test the parse_critical_dates helper function."""

    def test_no_dates_section(self):
        from app.api.routes.study import parse_critical_dates

        content = "# Study Guide\n\nHere is some content about algebra."
        clean, dates = parse_critical_dates(content)
        assert clean == content
        assert dates == []

    def test_valid_dates_section(self):
        from app.api.routes.study import parse_critical_dates

        content = (
            "# Study Guide\n\nHere is content.\n\n"
            "--- CRITICAL_DATES ---\n"
            '[{"date": "2026-03-15", "title": "Biology Exam", "priority": "high"}]'
        )
        clean, dates = parse_critical_dates(content)
        assert "CRITICAL_DATES" not in clean
        assert clean.strip() == "# Study Guide\n\nHere is content."
        assert len(dates) == 1
        assert dates[0]["date"] == "2026-03-15"
        assert dates[0]["title"] == "Biology Exam"
        assert dates[0]["priority"] == "high"

    def test_multiple_dates(self):
        from app.api.routes.study import parse_critical_dates

        content = (
            "Some content\n\n"
            "--- CRITICAL_DATES ---\n"
            '[{"date": "2026-03-15", "title": "Exam", "priority": "high"}, '
            '{"date": "2026-03-10", "title": "Homework", "priority": "medium"}]'
        )
        clean, dates = parse_critical_dates(content)
        assert len(dates) == 2
        assert dates[0]["title"] == "Exam"
        assert dates[1]["title"] == "Homework"

    def test_malformed_json(self):
        from app.api.routes.study import parse_critical_dates

        content = "Some content\n\n--- CRITICAL_DATES ---\nnot valid json"
        clean, dates = parse_critical_dates(content)
        assert clean == "Some content"
        assert dates == []

    def test_missing_required_fields(self):
        from app.api.routes.study import parse_critical_dates

        content = (
            "Content\n\n"
            "--- CRITICAL_DATES ---\n"
            '[{"date": "2026-03-15"}, {"title": "No date"}, '
            '{"date": "2026-04-01", "title": "Valid", "priority": "medium"}]'
        )
        clean, dates = parse_critical_dates(content)
        # Only the entry with both date and title should be included
        assert len(dates) == 1
        assert dates[0]["title"] == "Valid"

    def test_default_priority(self):
        from app.api.routes.study import parse_critical_dates

        content = (
            "Content\n\n"
            "--- CRITICAL_DATES ---\n"
            '[{"date": "2026-03-15", "title": "Task without priority"}]'
        )
        clean, dates = parse_critical_dates(content)
        assert len(dates) == 1
        assert dates[0]["priority"] == "medium"

    def test_dates_with_json_fences(self):
        from app.api.routes.study import parse_critical_dates

        content = (
            "Content\n\n"
            "--- CRITICAL_DATES ---\n"
            "```json\n"
            '[{"date": "2026-03-15", "title": "Exam", "priority": "high"}]\n'
            "```"
        )
        clean, dates = parse_critical_dates(content)
        assert len(dates) == 1
        assert dates[0]["title"] == "Exam"

    def test_empty_dates_array(self):
        from app.api.routes.study import parse_critical_dates

        content = "Content\n\n--- CRITICAL_DATES ---\n[]"
        clean, dates = parse_critical_dates(content)
        assert clean == "Content"
        assert dates == []

    def test_not_a_list(self):
        from app.api.routes.study import parse_critical_dates

        content = 'Content\n\n--- CRITICAL_DATES ---\n{"date": "2026-03-15"}'
        clean, dates = parse_critical_dates(content)
        assert clean == "Content"
        assert dates == []


class TestAutoCreateTasksFromDates:
    """Test auto_create_tasks_from_dates helper."""

    @pytest.fixture()
    def task_data(self, db_session):
        """Create test user for task creation."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        parent = db_session.query(User).filter(User.email == "taskdatesparent@test.com").first()
        if parent:
            return {"parent": parent}

        hashed = get_password_hash(PASSWORD)
        parent = User(
            email="taskdatesparent@test.com",
            full_name="Task Dates Parent",
            role=UserRole.PARENT,
            hashed_password=hashed,
        )
        db_session.add(parent)
        db_session.commit()
        return {"parent": parent}

    def test_creates_tasks_from_dates(self, db_session, task_data):
        from app.api.routes.study import auto_create_tasks_from_dates
        from app.models.task import Task

        parent = task_data["parent"]
        dates = [
            {"date": "2026-04-15", "title": "Biology Exam", "priority": "high"},
            {"date": "2026-04-10", "title": "Homework Due", "priority": "medium"},
        ]
        created = auto_create_tasks_from_dates(
            db_session, dates, parent,
            study_guide_id=None, course_id=None, course_content_id=None,
        )
        db_session.commit()

        assert len(created) == 2
        assert created[0]["title"] == "Biology Exam"
        assert created[0]["priority"] == "high"
        assert created[1]["title"] == "Homework Due"

        # Verify tasks in DB
        tasks = db_session.query(Task).filter(Task.created_by_user_id == parent.id).all()
        assert len(tasks) >= 2

    def test_skips_invalid_dates(self, db_session, task_data):
        from app.api.routes.study import auto_create_tasks_from_dates

        parent = task_data["parent"]
        dates = [
            {"date": "not-a-date", "title": "Bad Date Task", "priority": "medium"},
            {"date": "2026-05-01", "title": "Good Date Task", "priority": "low"},
        ]
        created = auto_create_tasks_from_dates(
            db_session, dates, parent,
            study_guide_id=None, course_id=None, course_content_id=None,
        )
        db_session.commit()

        # Only the valid date should create a task
        assert len(created) == 1
        assert created[0]["title"] == "Good Date Task"

    def test_normalizes_invalid_priority(self, db_session, task_data):
        from app.api.routes.study import auto_create_tasks_from_dates

        parent = task_data["parent"]
        dates = [
            {"date": "2026-06-01", "title": "Weird Priority", "priority": "urgent"},
        ]
        created = auto_create_tasks_from_dates(
            db_session, dates, parent,
            study_guide_id=None, course_id=None, course_content_id=None,
        )
        db_session.commit()

        assert len(created) == 1
        assert created[0]["priority"] == "medium"

    def test_empty_dates_list(self, db_session, task_data):
        from app.api.routes.study import auto_create_tasks_from_dates

        parent = task_data["parent"]
        created = auto_create_tasks_from_dates(
            db_session, [], parent,
            study_guide_id=None, course_id=None, course_content_id=None,
        )
        assert created == []
