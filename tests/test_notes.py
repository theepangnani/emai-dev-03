import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.course import Course
    from app.models.course_content import CourseContent

    owner = db_session.query(User).filter(User.email == "notes_owner@test.com").first()
    if owner:
        parent = db_session.query(User).filter(User.email == "notes_parent@test.com").first()
        outsider = db_session.query(User).filter(User.email == "notes_outsider@test.com").first()
        cc = db_session.query(CourseContent).join(Course).filter(Course.name == "Notes Test Course").first()
        return {"owner": owner, "parent": parent, "outsider": outsider, "course_content": cc}

    hashed = get_password_hash(PASSWORD)
    owner = User(email="notes_owner@test.com", full_name="Notes Owner", role=UserRole.STUDENT, hashed_password=hashed)
    parent = User(email="notes_parent@test.com", full_name="Notes Parent", role=UserRole.PARENT, hashed_password=hashed)
    outsider = User(email="notes_outsider@test.com", full_name="Notes Outsider", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([owner, parent, outsider])
    db_session.flush()

    student_rec = Student(user_id=owner.id)
    db_session.add(student_rec)
    db_session.flush()

    # Link parent to student
    db_session.execute(parent_students.insert().values(
        parent_id=parent.id, student_id=student_rec.id
    ))

    course = Course(name="Notes Test Course")
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(course_id=course.id, title="Lesson 1", content_type="notes")
    db_session.add(cc)
    db_session.commit()

    return {"owner": owner, "parent": parent, "outsider": outsider, "course_content": cc}


# ── Upsert Tests ─────────────────────────────────────────────────


class TestUpsertNote:
    def test_create_note(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Hello <b>world</b></p>",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == setup["owner"].id
        assert data["course_content_id"] == setup["course_content"].id
        assert data["content"] == "<p>Hello <b>world</b></p>"
        assert data["plain_text"] == "Hello world"
        assert data["has_images"] is False

    def test_update_existing_note(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        # Create
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>First version</p>",
        }, headers=headers)
        # Update
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Second version</p>",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["plain_text"] == "Second version"

    def test_empty_content_deletes(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        # Create a note first
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Will be deleted</p>",
        }, headers=headers)
        # Send empty content → auto-delete
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>  </p>",
        }, headers=headers)
        assert resp.status_code == 204

    def test_has_images_detected(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": '<p>Look: <img src="data:image/png;base64,abc" /></p>',
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["has_images"] is True

    def test_unauthenticated(self, client, setup):
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Nope</p>",
        })
        assert resp.status_code == 401


# ── List Tests ───────────────────────────────────────────────────


class TestListNotes:
    def test_list_own_notes(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        # Ensure a note exists
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Listed note</p>",
        }, headers=headers)
        resp = client.get("/api/notes/", headers=headers)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 1
        assert all(n["user_id"] == setup["owner"].id for n in notes)

    def test_list_filtered_by_content(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Filtered note</p>",
        }, headers=headers)
        resp = client.get(
            f"/api/notes/?course_content_id={setup['course_content'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        notes = resp.json()
        assert all(n["course_content_id"] == setup["course_content"].id for n in notes)

    def test_outsider_cannot_see_others_notes(self, client, setup):
        headers = _auth(client, "notes_outsider@test.com")
        resp = client.get("/api/notes/", headers=headers)
        assert resp.status_code == 200
        notes = resp.json()
        # Outsider should not see owner's notes
        assert all(n["user_id"] == setup["outsider"].id for n in notes)


# ── Get Single Note ──────────────────────────────────────────────


class TestGetNote:
    def test_get_own_note(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Get me</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.get(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Get me</p>"

    def test_outsider_cannot_get(self, client, setup):
        headers_owner = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Secret</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.get(f"/api/notes/{note_id}", headers=headers_outsider)
        assert resp.status_code == 404


# ── Delete Tests ─────────────────────────────────────────────────


class TestDeleteNote:
    def test_delete_own_note(self, client, setup):
        headers = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Delete me</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.delete(f"/api/notes/{note_id}", headers=headers)
        assert resp.status_code == 204

    def test_cannot_delete_others_note(self, client, setup):
        headers_owner = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Mine</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.delete(f"/api/notes/{note_id}", headers=headers_outsider)
        assert resp.status_code == 404


# ── Parent (children) Tests ──────────────────────────────────────


class TestParentChildNotes:
    def test_parent_can_list_child_notes(self, client, setup):
        # Owner creates a note
        headers_owner = _auth(client, "notes_owner@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Child note</p>",
        }, headers=headers_owner)
        # Parent reads child's notes
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(
            f"/api/notes/children/{setup['owner'].id}",
            headers=headers_parent,
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_parent_cannot_access_unlinked_child(self, client, setup):
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(
            f"/api/notes/children/{setup['outsider'].id}",
            headers=headers_parent,
        )
        assert resp.status_code == 403

    def test_non_parent_cannot_use_children_endpoint(self, client, setup):
        headers_owner = _auth(client, "notes_owner@test.com")
        resp = client.get(
            f"/api/notes/children/{setup['outsider'].id}",
            headers=headers_owner,
        )
        assert resp.status_code == 403
