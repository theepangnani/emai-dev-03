import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.course import Course
    from app.models.course_content import CourseContent

    user = db_session.query(User).filter(User.email == "notes_user@test.com").first()
    if user:
        parent = db_session.query(User).filter(User.email == "notes_parent@test.com").first()
        outsider = db_session.query(User).filter(User.email == "notes_outsider@test.com").first()
        cc = db_session.query(CourseContent).filter(CourseContent.title == "Notes Test Content").first()
        cc2 = db_session.query(CourseContent).filter(CourseContent.title == "Notes Test Content 2").first()
        student = db_session.query(Student).filter(Student.user_id == user.id).first()
        return {
            "user": user, "parent": parent, "outsider": outsider,
            "cc": cc, "cc2": cc2, "student": student,
        }

    hashed = get_password_hash(PASSWORD)
    user = User(email="notes_user@test.com", full_name="Notes User", role=UserRole.STUDENT, hashed_password=hashed)
    parent = User(email="notes_parent@test.com", full_name="Notes Parent", role=UserRole.PARENT, hashed_password=hashed)
    outsider = User(email="notes_outsider@test.com", full_name="Notes Outsider", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([user, parent, outsider])
    db_session.flush()

    student = Student(user_id=user.id)
    db_session.add(student)
    db_session.flush()

    # Link parent to student
    db_session.execute(parent_students.insert().values(
        parent_id=parent.id, student_id=student.id, relationship_type=RelationshipType.GUARDIAN
    ))

    course = Course(name="Notes Test Course", created_by_user_id=user.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(course_id=course.id, title="Notes Test Content", content_type="notes", created_by_user_id=user.id)
    cc2 = CourseContent(course_id=course.id, title="Notes Test Content 2", content_type="notes", created_by_user_id=user.id)
    db_session.add_all([cc, cc2])
    db_session.commit()

    return {
        "user": user, "parent": parent, "outsider": outsider,
        "cc": cc, "cc2": cc2, "student": student,
    }


class TestNoteUpsert:
    def test_create_note(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "<p>Hello world</p>",
            "plain_text": "Hello world",
            "has_images": False,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "<p>Hello world</p>"
        assert data["plain_text"] == "Hello world"
        assert data["course_content_id"] == setup["cc"].id
        assert data["course_content_title"] == "Notes Test Content"

    def test_update_existing_note(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        # First create
        client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "<p>Version 1</p>",
            "plain_text": "Version 1",
        }, headers=headers)
        # Then update (same course_content_id)
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "<p>Version 2</p>",
            "plain_text": "Version 2",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Version 2</p>"

    def test_upsert_invalid_course_content(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        resp = client.put("/api/notes/", json={
            "course_content_id": 99999,
            "content": "test",
            "plain_text": "test",
        }, headers=headers)
        assert resp.status_code == 404

    def test_upsert_requires_auth(self, client, setup):
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "test",
            "plain_text": "test",
        })
        assert resp.status_code == 401


class TestNoteList:
    def test_list_own_notes(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        # Ensure at least one note exists
        client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "<p>List test</p>",
            "plain_text": "List test",
        }, headers=headers)
        resp = client.get("/api/notes/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_filtered_by_course_content(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        # Create note on second content
        client.put("/api/notes/", json={
            "course_content_id": setup["cc2"].id,
            "content": "<p>CC2 note</p>",
            "plain_text": "CC2 note",
        }, headers=headers)
        resp = client.get(f"/api/notes/?course_content_id={setup['cc2'].id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(n["course_content_id"] == setup["cc2"].id for n in data)

    def test_list_empty_for_outsider(self, client, setup):
        headers = _auth(client, "notes_outsider@test.com")
        resp = client.get("/api/notes/", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestNoteGet:
    def test_get_own_note(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        # Ensure note exists
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "<p>Get test</p>",
            "plain_text": "Get test",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.get(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note_id

    def test_get_other_users_note_404(self, client, setup):
        headers_user = _auth(client, "notes_user@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "private",
            "plain_text": "private",
        }, headers=headers_user)
        note_id = put_resp.json()["id"]
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.get(f"/api/notes/{note_id}", headers=headers_outsider)
        assert resp.status_code == 404


class TestNoteDelete:
    def test_delete_own_note(self, client, setup):
        headers = _auth(client, "notes_user@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc2"].id,
            "content": "<p>To delete</p>",
            "plain_text": "To delete",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.delete(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 204
        # Verify gone
        resp2 = client.get(f"/api/notes/{note_id}", headers=headers)
        assert resp2.status_code == 404

    def test_delete_other_users_note_404(self, client, setup):
        headers_user = _auth(client, "notes_user@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "keep",
            "plain_text": "keep",
        }, headers=headers_user)
        note_id = put_resp.json()["id"]
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.delete(f"/api/notes/{note_id}", headers=headers_outsider)
        assert resp.status_code == 404


class TestChildNotes:
    def test_parent_can_view_child_notes(self, client, setup):
        # Student creates a note
        headers_student = _auth(client, "notes_user@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["cc"].id,
            "content": "<p>Child note</p>",
            "plain_text": "Child note",
        }, headers=headers_student)
        # Parent views child's notes
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(f"/api/notes/children/{setup['student'].id}", headers=headers_parent)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_outsider_cannot_view_child_notes(self, client, setup):
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.get(f"/api/notes/children/{setup['student'].id}", headers=headers_outsider)
        assert resp.status_code == 403
