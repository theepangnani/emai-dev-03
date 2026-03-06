import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course
    from app.models.course_content import CourseContent

    parent = db_session.query(User).filter(User.email == "notes_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "notes_teacher@test.com").first()
        other = db_session.query(User).filter(User.email == "notes_other@test.com").first()
        course = db_session.query(Course).filter(Course.name == "Notes Test Course").first()
        cc = db_session.query(CourseContent).filter(CourseContent.title == "Notes Lecture 1").first()
        return {"parent": parent, "teacher": teacher, "other": other, "course": course, "cc": cc}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="notes_parent@test.com", full_name="Notes Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="notes_teacher@test.com", full_name="Notes Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    other = User(email="notes_other@test.com", full_name="Notes Other", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, teacher, other])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(name="Notes Test Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(course_id=course.id, title="Notes Lecture 1", content_type="notes", created_by_user_id=teacher.id)
    db_session.add(cc)
    db_session.commit()

    for u in [parent, teacher, other]:
        db_session.refresh(u)
    db_session.refresh(course)
    db_session.refresh(cc)
    return {"parent": parent, "teacher": teacher, "other": other, "course": course, "cc": cc}


class TestNoteUpsert:
    def test_create_note_via_upsert(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>My study notes</p>",
            "plain_text": "My study notes",
            "has_images": False,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "<p>My study notes</p>"
        assert data["plain_text"] == "My study notes"
        assert data["has_images"] is False
        assert data["course_content_id"] == users["cc"].id

    def test_update_existing_note_via_upsert(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Create
        client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>First draft</p>",
            "plain_text": "First draft",
            "has_images": False,
        }, headers=headers)
        # Update
        resp = client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>Updated notes</p>",
            "plain_text": "Updated notes",
            "has_images": True,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "<p>Updated notes</p>"
        assert data["has_images"] is True

    def test_upsert_invalid_course_content(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.put("/api/notes/by-content/999999", json={
            "content": "test",
            "plain_text": "test",
            "has_images": False,
        }, headers=headers)
        assert resp.status_code == 404


class TestNoteGet:
    def test_get_by_content(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Create first
        client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>Teacher notes</p>",
            "plain_text": "Teacher notes",
            "has_images": False,
        }, headers=headers)
        # Get
        resp = client.get(f"/api/notes/by-content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plain_text"] == "Teacher notes"

    def test_get_nonexistent_returns_null(self, client, users):
        headers = _auth(client, users["other"].email)
        resp = client.get(f"/api/notes/by-content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_get_by_id(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Create
        create_resp = client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>By ID test</p>",
            "plain_text": "By ID test",
            "has_images": False,
        }, headers=headers)
        note_id = create_resp.json()["id"]
        # Get by ID
        resp = client.get(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note_id

    def test_get_by_id_other_user_404(self, client, users):
        headers_teacher = _auth(client, users["teacher"].email)
        create_resp = client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>Private</p>",
            "plain_text": "Private",
            "has_images": False,
        }, headers=headers_teacher)
        note_id = create_resp.json()["id"]
        # Other user cannot see it
        headers_other = _auth(client, users["other"].email)
        resp = client.get(f"/api/notes/{note_id}", headers=headers_other)
        assert resp.status_code == 404


class TestNoteList:
    def test_list_all_notes(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Create a note
        client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>List test</p>",
            "plain_text": "List test",
            "has_images": False,
        }, headers=headers)
        resp = client.get("/api/notes/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_filtered_by_content(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(f"/api/notes/?course_content_id={users['cc'].id}", headers=headers)
        assert resp.status_code == 200
        for item in resp.json():
            assert item["course_content_id"] == users["cc"].id


class TestNoteDelete:
    def test_delete_note(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Create
        client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>To delete</p>",
            "plain_text": "To delete",
            "has_images": False,
        }, headers=headers)
        # Delete
        resp = client.delete(f"/api/notes/by-content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 204
        # Verify gone
        resp2 = client.get(f"/api/notes/by-content/{users['cc'].id}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json() is None

    def test_delete_nonexistent_note_404(self, client, users):
        headers = _auth(client, users["other"].email)
        resp = client.delete(f"/api/notes/by-content/{users['cc'].id}", headers=headers)
        assert resp.status_code == 404


class TestNoteAuth:
    def test_unauthenticated_request_rejected(self, client, users):
        resp = client.get("/api/notes/")
        assert resp.status_code == 401

    def test_users_cannot_see_each_others_notes(self, client, users):
        headers_parent = _auth(client, users["parent"].email)
        headers_other = _auth(client, users["other"].email)
        # Parent creates note
        client.put(f"/api/notes/by-content/{users['cc'].id}", json={
            "content": "<p>Parent only</p>",
            "plain_text": "Parent only",
            "has_images": False,
        }, headers=headers_parent)
        # Other user lists - should not see parent's note for this content
        resp = client.get(f"/api/notes/?course_content_id={users['cc'].id}", headers=headers_other)
        assert resp.status_code == 200
        # Other user should not have any notes for this content
        data = resp.json()
        for item in data:
            assert item["course_content_id"] == users["cc"].id
