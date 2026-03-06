"""Tests for Notes API — CRUD, upsert semantics, image detection, permissions."""

import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from app.models.course_content import CourseContent

    parent = db_session.query(User).filter(User.email == "note_parent@test.com").first()
    if parent:
        student_user = db_session.query(User).filter(User.email == "note_student@test.com").first()
        teacher_user = db_session.query(User).filter(User.email == "note_teacher@test.com").first()
        outsider = db_session.query(User).filter(User.email == "note_outsider@test.com").first()
        course = db_session.query(Course).filter(Course.name == "Notes Test Course").first()
        cc = db_session.query(CourseContent).filter(CourseContent.title == "Notes Test Content").first()
        return {
            "parent": parent, "student_user": student_user,
            "teacher_user": teacher_user, "outsider": outsider,
            "course": course, "cc": cc,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="note_parent@test.com", full_name="Note Parent", role=UserRole.PARENT, hashed_password=hashed)
    student_user = User(email="note_student@test.com", full_name="Note Student", role=UserRole.STUDENT, hashed_password=hashed)
    teacher_user = User(email="note_teacher@test.com", full_name="Note Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    outsider = User(email="note_outsider@test.com", full_name="Note Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, student_user, teacher_user, outsider])
    db_session.commit()

    student = Student(user_id=student_user.id, grade_level=9)
    db_session.add(student)
    db_session.commit()

    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student.id))
    db_session.commit()

    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.commit()

    course = Course(name="Notes Test Course", teacher_id=teacher.id, created_by_user_id=teacher_user.id)
    db_session.add(course)
    db_session.commit()

    db_session.execute(student_courses.insert().values(student_id=student.id, course_id=course.id))
    db_session.commit()

    cc = CourseContent(
        course_id=course.id,
        title="Notes Test Content",
        content_type="notes",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(cc)
    db_session.commit()
    db_session.refresh(cc)

    for u in [parent, student_user, teacher_user, outsider]:
        db_session.refresh(u)
    db_session.refresh(course)

    return {
        "parent": parent, "student_user": student_user,
        "teacher_user": teacher_user, "outsider": outsider,
        "course": course, "cc": cc,
    }


class TestNoteUpsert:
    def test_create_note(self, client, users):
        """PUT creates a new note when none exists."""
        headers = _auth(client, users["student_user"].email)
        resp = client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>Hello world</p>", "plain_text": "Hello world"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "<p>Hello world</p>"
        assert data["plain_text"] == "Hello world"
        assert data["has_images"] is False
        assert data["user_id"] == users["student_user"].id
        assert data["course_content_id"] == users["cc"].id

    def test_update_note_upsert(self, client, users):
        """PUT updates existing note (upsert semantics)."""
        headers = _auth(client, users["student_user"].email)
        resp = client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>Updated</p>", "plain_text": "Updated"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Updated</p>"

    def test_has_images_auto_detected(self, client, users):
        """has_images is auto-set when content contains <img tags."""
        headers = _auth(client, users["teacher_user"].email)
        content_with_img = '<p>Look at this:</p><img src="data:image/png;base64,abc123" />'
        resp = client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": content_with_img, "plain_text": "Look at this:"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["has_images"] is True

    def test_has_images_false_when_no_img(self, client, users):
        """has_images is False when content has no <img tags."""
        headers = _auth(client, users["teacher_user"].email)
        resp = client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>No images here</p>", "plain_text": "No images here"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["has_images"] is False

    def test_content_size_limit(self, client, users):
        """Content exceeding 50 MB is rejected."""
        headers = _auth(client, users["student_user"].email)
        # Create content just over the limit (50 MB + 1)
        huge_content = "x" * (50 * 1024 * 1024 + 1)
        resp = client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": huge_content, "plain_text": "big"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_image_count_limit(self, client, users):
        """Content with more than 10 images is rejected."""
        headers = _auth(client, users["student_user"].email)
        img_tags = '<img src="data:image/png;base64,a" />' * 11
        resp = client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": f"<p>{img_tags}</p>", "plain_text": "images"},
            headers=headers,
        )
        assert resp.status_code == 422


class TestNoteGet:
    def test_get_own_note(self, client, users):
        """User can get their own note."""
        headers = _auth(client, users["student_user"].email)
        # Ensure note exists
        client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>My note</p>", "plain_text": "My note"},
            headers=headers,
        )
        resp = client.get(f"/api/notes/content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>My note</p>"

    def test_get_nonexistent_note(self, client, users):
        """Getting a note that doesn't exist returns 404."""
        headers = _auth(client, users["outsider"].email)
        resp = client.get(f"/api/notes/content/{users['cc'].id}", headers=headers)
        # outsider has no access to the course
        assert resp.status_code in (403, 404)

    def test_get_note_no_access(self, client, users):
        """User without course access gets 403 or 404."""
        headers = _auth(client, users["outsider"].email)
        resp = client.get(f"/api/notes/content/{users['cc'].id}", headers=headers)
        assert resp.status_code in (403, 404)


class TestNoteDelete:
    def test_delete_own_note(self, client, users):
        """User can delete their own note."""
        headers = _auth(client, users["student_user"].email)
        # Ensure note exists
        client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>To delete</p>", "plain_text": "To delete"},
            headers=headers,
        )
        resp = client.delete(f"/api/notes/content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_note(self, client, users):
        """Deleting a nonexistent note returns 404."""
        headers = _auth(client, users["teacher_user"].email)
        # Delete first to ensure clean state
        client.delete(f"/api/notes/content/{users['cc'].id}", headers=headers)
        resp = client.delete(f"/api/notes/content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 404


class TestNoteList:
    def test_list_my_notes(self, client, users):
        """User can list their own notes."""
        headers = _auth(client, users["student_user"].email)
        # Ensure at least one note exists
        client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>Listed note</p>", "plain_text": "Listed note"},
            headers=headers,
        )
        resp = client.get("/api/notes/mine", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(n["course_content_id"] == users["cc"].id for n in data)

    def test_list_children_notes_parent(self, client, users):
        """Parent can list children's notes for a content item."""
        # Student creates a note
        student_headers = _auth(client, users["student_user"].email)
        client.put(
            f"/api/notes/content/{users['cc'].id}",
            json={"content": "<p>Student note</p>", "plain_text": "Student note"},
            headers=student_headers,
        )
        # Parent lists children's notes
        parent_headers = _auth(client, users["parent"].email)
        resp = client.get(
            f"/api/notes/content/{users['cc'].id}/children",
            headers=parent_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(n["user_id"] == users["student_user"].id for n in data)

    def test_list_children_notes_non_parent_forbidden(self, client, users):
        """Non-parent users cannot list children's notes."""
        headers = _auth(client, users["student_user"].email)
        resp = client.get(
            f"/api/notes/content/{users['cc'].id}/children",
            headers=headers,
        )
        assert resp.status_code == 403


class TestNoteContentNotFound:
    def test_upsert_nonexistent_content(self, client, users):
        """Upserting for a nonexistent course content returns 404."""
        headers = _auth(client, users["student_user"].email)
        resp = client.put(
            "/api/notes/content/999999",
            json={"content": "<p>Test</p>", "plain_text": "Test"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_get_nonexistent_content(self, client, users):
        """Getting a note for nonexistent course content returns 404."""
        headers = _auth(client, users["student_user"].email)
        resp = client.get("/api/notes/content/999999", headers=headers)
        assert resp.status_code == 404
