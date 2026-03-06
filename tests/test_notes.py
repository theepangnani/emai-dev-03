"""Tests for Notes system — CRUD, task creation from notes (#1087)."""

import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def users(db_session):
    """Create test users: a parent and a course with content."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.course import Course
    from app.models.course_content import CourseContent

    parent = db_session.query(User).filter(User.email == "noteparent@test.com").first()
    if parent:
        course = db_session.query(Course).filter(Course.name == "Notes Test Course").first()
        cc = db_session.query(CourseContent).filter(CourseContent.course_id == course.id).first()
        other = db_session.query(User).filter(User.email == "noteother@test.com").first()
        return {"parent": parent, "course": course, "cc": cc, "other": other}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="noteparent@test.com", full_name="Note Parent", role=UserRole.PARENT, hashed_password=hashed)
    other = User(email="noteother@test.com", full_name="Other User", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, other])
    db_session.commit()

    course = Course(name="Notes Test Course", created_by_user_id=parent.id)
    db_session.add(course)
    db_session.commit()

    cc = CourseContent(
        course_id=course.id,
        title="Test Material",
        description="Test description",
        text_content="Some test content for notes",
        content_type="notes",
        created_by_user_id=parent.id,
    )
    db_session.add(cc)
    db_session.commit()

    return {"parent": parent, "course": course, "cc": cc, "other": other}


class TestNotesUpsert:
    """Test PUT /api/notes/by-content/{course_content_id}"""

    def test_create_note(self, client, users):
        h = _auth(client, "noteparent@test.com")
        resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>My study notes</p>", "has_images": False},
            headers=h,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["course_content_id"] == users["cc"].id
        assert data["plain_text"] == "My study notes"
        assert data["has_images"] is False

    def test_update_note(self, client, users):
        h = _auth(client, "noteparent@test.com")
        # Create first
        client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>First version</p>"},
            headers=h,
        )
        # Update
        resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Updated version</p>"},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["plain_text"] == "Updated version"

    def test_auto_delete_empty_note(self, client, users):
        h = _auth(client, "noteparent@test.com")
        # Create note first
        client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Something</p>"},
            headers=h,
        )
        # Send empty content -> auto-delete
        resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": ""},
            headers=h,
        )
        assert resp.status_code == 204

    def test_create_note_nonexistent_content(self, client, users):
        h = _auth(client, "noteparent@test.com")
        resp = client.put(
            "/api/notes/by-content/99999",
            json={"content": "<p>Test</p>"},
            headers=h,
        )
        assert resp.status_code == 404


class TestNotesGet:
    """Test GET /api/notes/by-content/{course_content_id}"""

    def test_get_note(self, client, users):
        h = _auth(client, "noteparent@test.com")
        # Create first
        client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<b>Bold notes</b>"},
            headers=h,
        )
        resp = client.get(f"/api/notes/by-content/{users['cc'].id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["plain_text"] == "Bold notes"

    def test_get_note_not_found(self, client, users):
        h = _auth(client, "noteother@test.com")
        resp = client.get(f"/api/notes/by-content/{users['cc'].id}", headers=h)
        assert resp.status_code == 404


class TestNotesDelete:
    """Test DELETE /api/notes/by-content/{course_content_id}"""

    def test_delete_note(self, client, users):
        h = _auth(client, "noteparent@test.com")
        # Create first
        client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>To delete</p>"},
            headers=h,
        )
        resp = client.delete(f"/api/notes/by-content/{users['cc'].id}", headers=h)
        assert resp.status_code == 204

    def test_delete_note_not_found(self, client, users):
        h = _auth(client, "noteother@test.com")
        resp = client.delete(f"/api/notes/by-content/{users['cc'].id}", headers=h)
        assert resp.status_code == 404


class TestNotesList:
    """Test GET /api/notes/"""

    def test_list_notes(self, client, users):
        h = _auth(client, "noteparent@test.com")
        # Create a note first
        client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Listed note</p>"},
            headers=h,
        )
        resp = client.get("/api/notes/", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(n["course_content_id"] == users["cc"].id for n in data)


class TestNoteCreateTask:
    """Test POST /api/notes/{note_id}/create-task"""

    def test_create_linked_task_from_note(self, client, users, db_session):
        h = _auth(client, "noteparent@test.com")
        # Create a note first
        note_resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Task from this note</p>"},
            headers=h,
        )
        note_id = note_resp.json()["id"]

        resp = client.post(
            f"/api/notes/{note_id}/create-task",
            json={
                "title": "Review material",
                "priority": "high",
                "linked": True,
            },
            headers=h,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Review material"
        assert data["priority"] == "high"
        assert data["course_content_id"] == users["cc"].id
        assert data["note_id"] == note_id
        assert "Task from this note" in (data["description"] or "")

    def test_create_unlinked_task_from_note(self, client, users):
        h = _auth(client, "noteparent@test.com")
        note_resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Standalone task note</p>"},
            headers=h,
        )
        note_id = note_resp.json()["id"]

        resp = client.post(
            f"/api/notes/{note_id}/create-task",
            json={
                "title": "Quick standalone task",
                "linked": False,
            },
            headers=h,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Quick standalone task"
        assert data["course_content_id"] is None
        assert data["note_id"] == note_id

    def test_create_task_note_not_found(self, client, users):
        h = _auth(client, "noteparent@test.com")
        resp = client.post(
            "/api/notes/99999/create-task",
            json={"title": "Test", "linked": True},
            headers=h,
        )
        assert resp.status_code == 404

    def test_create_task_invalid_priority(self, client, users):
        h = _auth(client, "noteparent@test.com")
        note_resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Note for priority test</p>"},
            headers=h,
        )
        note_id = note_resp.json()["id"]

        resp = client.post(
            f"/api/notes/{note_id}/create-task",
            json={"title": "Test", "priority": "urgent", "linked": True},
            headers=h,
        )
        assert resp.status_code == 400

    def test_other_user_cannot_create_task_from_note(self, client, users):
        """Another user should not be able to create a task from someone else's note."""
        h_parent = _auth(client, "noteparent@test.com")
        note_resp = client.put(
            f"/api/notes/by-content/{users['cc'].id}",
            json={"content": "<p>Private note</p>"},
            headers=h_parent,
        )
        note_id = note_resp.json()["id"]

        h_other = _auth(client, "noteother@test.com")
        resp = client.post(
            f"/api/notes/{note_id}/create-task",
            json={"title": "Hack", "linked": True},
            headers=h_other,
        )
        assert resp.status_code == 404
