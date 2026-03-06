import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def note_users(db_session):
    """Create parent, student, teacher, and unlinked parent for notes tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher
    from app.models.course import Course
    from app.models.course_content import CourseContent
    from sqlalchemy import insert

    # Check if already created (session-scoped DB)
    existing = db_session.query(User).filter(User.email == "notes_parent@test.com").first()
    if existing:
        parent = existing
        student_user = db_session.query(User).filter(User.email == "notes_student@test.com").first()
        teacher_user = db_session.query(User).filter(User.email == "notes_teacher@test.com").first()
        other_parent = db_session.query(User).filter(User.email == "notes_other_parent@test.com").first()
        student = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        course = db_session.query(Course).filter(Course.name == "Notes Test Course").first()
        cc = db_session.query(CourseContent).filter(CourseContent.title == "Notes Test Content").first()
        return {
            "parent": parent,
            "student_user": student_user,
            "student": student,
            "teacher": teacher_user,
            "other_parent": other_parent,
            "course": course,
            "course_content": cc,
        }

    hashed = get_password_hash(PASSWORD)

    parent = User(email="notes_parent@test.com", full_name="Notes Parent", role=UserRole.PARENT, hashed_password=hashed)
    student_user = User(email="notes_student@test.com", full_name="Notes Student", role=UserRole.STUDENT, hashed_password=hashed)
    teacher_user = User(email="notes_teacher@test.com", full_name="Notes Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    other_parent = User(email="notes_other_parent@test.com", full_name="Other Parent", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, student_user, teacher_user, other_parent])
    db_session.flush()

    student = Student(user_id=student_user.id, grade_level=8, school_name="Test School")
    db_session.add(student)
    db_session.flush()

    # Link parent to student
    db_session.execute(insert(parent_students).values(parent_id=parent.id, student_id=student.id))

    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.flush()

    course = Course(name="Notes Test Course", teacher_id=teacher.id, created_by_user_id=teacher_user.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(course_id=course.id, title="Notes Test Content", created_by_user_id=teacher_user.id)
    db_session.add(cc)
    db_session.commit()

    for u in [parent, student_user, teacher_user, other_parent]:
        db_session.refresh(u)
    db_session.refresh(student)
    db_session.refresh(course)
    db_session.refresh(cc)

    return {
        "parent": parent,
        "student_user": student_user,
        "student": student,
        "teacher": teacher_user,
        "other_parent": other_parent,
        "course": course,
        "course_content": cc,
    }


# ── Own Notes CRUD ──────────────────────────────────────────────


class TestNotesCRUD:
    def test_upsert_creates_note(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        cc_id = note_users["course_content"].id
        resp = client.put("/api/notes/", json={
            "course_content_id": cc_id,
            "content": "My first note",
            "plain_text": "My first note",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "My first note"
        assert data["course_content_id"] == cc_id
        assert data["user_id"] == note_users["student_user"].id

    def test_upsert_updates_existing(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        cc_id = note_users["course_content"].id
        # Create
        client.put("/api/notes/", json={
            "course_content_id": cc_id,
            "content": "Initial note",
            "plain_text": "Initial note",
        }, headers=headers)
        # Update
        resp = client.put("/api/notes/", json={
            "course_content_id": cc_id,
            "content": "Updated note",
            "plain_text": "Updated note",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated note"

    def test_list_my_notes(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        resp = client.get("/api/notes/", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_filter_by_course_content(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        cc_id = note_users["course_content"].id
        resp = client.get(f"/api/notes/?course_content_id={cc_id}", headers=headers)
        assert resp.status_code == 200
        for note in resp.json():
            assert note["course_content_id"] == cc_id

    def test_get_single_note(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        cc_id = note_users["course_content"].id
        # Ensure note exists
        put_resp = client.put("/api/notes/", json={
            "course_content_id": cc_id,
            "content": "Get me",
            "plain_text": "Get me",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.get(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note_id

    def test_get_other_users_note_returns_404(self, client, note_users):
        """A user cannot GET another user's note by ID."""
        headers = _auth(client, note_users["teacher"].email)
        # Student's note
        student_headers = _auth(client, note_users["student_user"].email)
        put_resp = client.put("/api/notes/", json={
            "course_content_id": note_users["course_content"].id,
            "content": "Student only",
            "plain_text": "Student only",
        }, headers=student_headers)
        note_id = put_resp.json()["id"]
        # Teacher tries to access
        resp = client.get(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 404

    def test_delete_note(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        cc_id = note_users["course_content"].id
        put_resp = client.put("/api/notes/", json={
            "course_content_id": cc_id,
            "content": "Delete me",
            "plain_text": "Delete me",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.delete(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 204
        # Verify deleted
        get_resp = client.get(f"/api/notes/{note_id}", headers=headers)
        assert get_resp.status_code == 404

    def test_delete_other_users_note_returns_404(self, client, note_users):
        student_headers = _auth(client, note_users["student_user"].email)
        put_resp = client.put("/api/notes/", json={
            "course_content_id": note_users["course_content"].id,
            "content": "Cannot delete",
            "plain_text": "Cannot delete",
        }, headers=student_headers)
        note_id = put_resp.json()["id"]
        teacher_headers = _auth(client, note_users["teacher"].email)
        resp = client.delete(f"/api/notes/{note_id}", headers=teacher_headers)
        assert resp.status_code == 404

    def test_upsert_nonexistent_course_content(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        resp = client.put("/api/notes/", json={
            "course_content_id": 999999,
            "content": "Nope",
            "plain_text": "Nope",
        }, headers=headers)
        assert resp.status_code == 404

    def test_upsert_has_images_flag(self, client, note_users):
        headers = _auth(client, note_users["student_user"].email)
        resp = client.put("/api/notes/", json={
            "course_content_id": note_users["course_content"].id,
            "content": "<p>With image</p>",
            "plain_text": "With image",
            "has_images": True,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["has_images"] is True


# ── Parent Access to Child Notes ─────────────────────────────────


class TestParentChildNotes:
    def _ensure_student_note(self, client, note_users, content="Child note content"):
        """Helper: make sure the student has a note on the test content."""
        headers = _auth(client, note_users["student_user"].email)
        client.put("/api/notes/", json={
            "course_content_id": note_users["course_content"].id,
            "content": content,
            "plain_text": content,
        }, headers=headers)

    def test_parent_can_read_child_notes(self, client, note_users):
        self._ensure_student_note(client, note_users, "Visible to parent")
        headers = _auth(client, note_users["parent"].email)
        resp = client.get(f"/api/notes/children/{note_users['student'].id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["child_name"] == "Notes Student"
        assert data[0]["student_id"] == note_users["student"].id

    def test_parent_child_notes_filter_by_content(self, client, note_users):
        self._ensure_student_note(client, note_users)
        headers = _auth(client, note_users["parent"].email)
        cc_id = note_users["course_content"].id
        resp = client.get(
            f"/api/notes/children/{note_users['student'].id}?course_content_id={cc_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        for note in resp.json():
            assert note["course_content_id"] == cc_id

    def test_unlinked_parent_cannot_read_child_notes(self, client, note_users):
        """A parent not linked to the child gets 403."""
        self._ensure_student_note(client, note_users)
        headers = _auth(client, note_users["other_parent"].email)
        resp = client.get(f"/api/notes/children/{note_users['student'].id}", headers=headers)
        assert resp.status_code == 403

    def test_student_cannot_access_children_endpoint(self, client, note_users):
        """Students should get 403 (not a parent)."""
        headers = _auth(client, note_users["student_user"].email)
        resp = client.get(f"/api/notes/children/{note_users['student'].id}", headers=headers)
        assert resp.status_code == 403

    def test_teacher_cannot_access_children_endpoint(self, client, note_users):
        """Teachers should get 403 (not a parent)."""
        headers = _auth(client, note_users["teacher"].email)
        resp = client.get(f"/api/notes/children/{note_users['student'].id}", headers=headers)
        assert resp.status_code == 403

    def test_parent_gets_empty_list_when_child_has_no_notes(self, client, note_users, db_session):
        """If child has no notes, return empty list (not error)."""
        from app.models.note import Note
        # Clear any existing notes for the student
        db_session.query(Note).filter(Note.user_id == note_users["student_user"].id).delete()
        db_session.commit()
        headers = _auth(client, note_users["parent"].email)
        resp = client.get(f"/api/notes/children/{note_users['student'].id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthenticated_access_rejected(self, client, note_users):
        """No auth header should get 401."""
        resp = client.get("/api/notes/")
        assert resp.status_code == 401

    def test_parent_child_notes_are_readonly(self, client, note_users):
        """Verify there's no PUT/DELETE on the children endpoint (read-only by design).
        Trying to PUT or DELETE should return 405 Method Not Allowed."""
        headers = _auth(client, note_users["parent"].email)
        student_id = note_users["student"].id
        resp_put = client.put(f"/api/notes/children/{student_id}", json={
            "course_content_id": note_users["course_content"].id,
            "content": "Hack",
            "plain_text": "Hack",
        }, headers=headers)
        assert resp_put.status_code == 405

        resp_delete = client.delete(f"/api/notes/children/{student_id}", headers=headers)
        assert resp_delete.status_code == 405
