"""Tests for Notes system (CRUD + parent read-only access to child notes)."""

import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def users(db_session):
    """Create test users: parent, child (student), second child, outsider."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.course import Course
    from app.models.course_content import CourseContent

    parent = db_session.query(User).filter(User.email == "noteparent@test.com").first()
    if parent:
        child_user = db_session.query(User).filter(User.email == "notechild@test.com").first()
        student = db_session.query(Student).filter(Student.user_id == child_user.id).first()
        outsider = db_session.query(User).filter(User.email == "noteoutsider@test.com").first()
        course = db_session.query(Course).filter(Course.name == "Note Test Course").first()
        cc = db_session.query(CourseContent).filter(CourseContent.course_id == course.id).first()
        return {
            "parent": parent, "child_user": child_user, "student": student,
            "outsider": outsider, "course": course, "course_content": cc,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="noteparent@test.com", full_name="Note Parent", role=UserRole.PARENT, hashed_password=hashed)
    child_user = User(email="notechild@test.com", full_name="Note Child", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="noteoutsider@test.com", full_name="Note Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, child_user, outsider])
    db_session.commit()

    student = Student(user_id=child_user.id, grade_level=7)
    db_session.add(student)
    db_session.commit()

    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student.id))
    db_session.commit()

    course = Course(name="Note Test Course", created_by_user_id=parent.id)
    db_session.add(course)
    db_session.commit()

    cc = CourseContent(
        course_id=course.id,
        title="Chapter 1 Notes",
        description="Chapter 1 material",
        content_type="notes",
        created_by_user_id=parent.id,
    )
    db_session.add(cc)
    db_session.commit()

    return {
        "parent": parent, "child_user": child_user, "student": student,
        "outsider": outsider, "course": course, "course_content": cc,
    }


# ── CRUD Tests ─────────────────────────────────────────────────────────────────

class TestNotesCRUD:
    def test_upsert_creates_note(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        resp = client.put(f"/api/notes/{cc_id}", json={"content": "Hello world"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Hello world"
        assert data["plain_text"] == "Hello world"
        assert data["course_content_id"] == cc_id
        assert data["has_images"] is False

    def test_upsert_updates_existing(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "First"}, headers=h)
        resp = client.put(f"/api/notes/{cc_id}", json={"content": "Updated"}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated"

    def test_upsert_strips_html(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        resp = client.put(f"/api/notes/{cc_id}", json={"content": "<p>Bold <b>text</b></p>"}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["plain_text"] == "Bold text"

    def test_upsert_detects_images(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        resp = client.put(
            f"/api/notes/{cc_id}",
            json={"content": '<p>Look: <img src="data:image/png;base64,abc"/></p>'},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["has_images"] is True

    def test_upsert_empty_content_deletes(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        # Create a note first
        client.put(f"/api/notes/{cc_id}", json={"content": "Something"}, headers=h)
        # Now send empty
        resp = client.put(f"/api/notes/{cc_id}", json={"content": "   "}, headers=h)
        assert resp.status_code == 204
        # Verify it's gone
        resp = client.get(f"/api/notes/{cc_id}", headers=h)
        assert resp.status_code == 404

    def test_get_note(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "My note"}, headers=h)
        resp = client.get(f"/api/notes/{cc_id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["content"] == "My note"

    def test_get_note_not_found(self, client, users):
        h = _auth(client, "notechild@test.com")
        resp = client.get("/api/notes/99999", headers=h)
        assert resp.status_code == 404

    def test_list_notes(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "List test"}, headers=h)
        resp = client.get("/api/notes/", headers=h)
        assert resp.status_code == 200
        notes = resp.json()
        assert any(n["course_content_id"] == cc_id for n in notes)

    def test_list_notes_filtered(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "Filter test"}, headers=h)
        resp = client.get(f"/api/notes/?course_content_id={cc_id}", headers=h)
        assert resp.status_code == 200
        notes = resp.json()
        assert all(n["course_content_id"] == cc_id for n in notes)

    def test_delete_note(self, client, users):
        h = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "To delete"}, headers=h)
        resp = client.delete(f"/api/notes/{cc_id}", headers=h)
        assert resp.status_code == 204
        resp = client.get(f"/api/notes/{cc_id}", headers=h)
        assert resp.status_code == 404

    def test_delete_note_not_found(self, client, users):
        h = _auth(client, "notechild@test.com")
        resp = client.delete("/api/notes/99999", headers=h)
        assert resp.status_code == 404


# ── Parent Read-Only Access Tests ──────────────────────────────────────────────

class TestParentChildNotes:
    def test_parent_can_view_child_notes(self, client, users):
        """Parent can see their linked child's notes."""
        # Child creates a note
        h_child = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "Child's study notes"}, headers=h_child)

        # Parent reads child's notes
        h_parent = _auth(client, "noteparent@test.com")
        student_id = users["student"].id
        resp = client.get(f"/api/notes/children/{student_id}", headers=h_parent)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 1
        note = next(n for n in notes if n["course_content_id"] == cc_id)
        assert note["read_only"] is True
        assert note["student_name"] == "Note Child"
        assert "study notes" in note["content"]

    def test_parent_can_filter_by_content_id(self, client, users):
        """Parent can filter child's notes by course_content_id."""
        h_child = _auth(client, "notechild@test.com")
        cc_id = users["course_content"].id
        client.put(f"/api/notes/{cc_id}", json={"content": "Filtered note"}, headers=h_child)

        h_parent = _auth(client, "noteparent@test.com")
        student_id = users["student"].id
        resp = client.get(
            f"/api/notes/children/{student_id}?course_content_id={cc_id}",
            headers=h_parent,
        )
        assert resp.status_code == 200
        notes = resp.json()
        assert all(n["course_content_id"] == cc_id for n in notes)

    def test_outsider_parent_cannot_view_child_notes(self, client, users):
        """A parent not linked to the child cannot see their notes."""
        h = _auth(client, "noteoutsider@test.com")
        student_id = users["student"].id
        resp = client.get(f"/api/notes/children/{student_id}", headers=h)
        assert resp.status_code == 403

    def test_student_cannot_view_other_notes(self, client, users):
        """Students cannot use the children endpoint."""
        h = _auth(client, "notechild@test.com")
        student_id = users["student"].id
        resp = client.get(f"/api/notes/children/{student_id}", headers=h)
        assert resp.status_code == 403

    def test_child_no_notes_returns_empty(self, client, users, db_session):
        """When child has no notes, endpoint returns empty list."""
        from app.models.note import Note
        # Clear any existing notes for this child
        db_session.query(Note).filter(Note.user_id == users["child_user"].id).delete()
        db_session.commit()

        h_parent = _auth(client, "noteparent@test.com")
        student_id = users["student"].id
        resp = client.get(f"/api/notes/children/{student_id}", headers=h_parent)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_nonexistent_student(self, client, users):
        """Requesting notes for a non-existent student returns 403 (no link)."""
        h_parent = _auth(client, "noteparent@test.com")
        resp = client.get("/api/notes/children/99999", headers=h_parent)
        assert resp.status_code == 403
