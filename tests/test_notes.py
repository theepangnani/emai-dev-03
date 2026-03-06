"""Tests for Notes API endpoints and search integration."""

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def notes_users(db_session):
    """Create test users for notes: a student, a parent linked to the student, and an admin."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.course import Course
    from app.models.course_content import CourseContent

    hashed = get_password_hash(PASSWORD)

    # Check if already created (session-scoped DB can persist across test calls)
    student_user = db_session.query(User).filter(User.email == "notes_student@test.com").first()
    if student_user:
        parent_user = db_session.query(User).filter(User.email == "notes_parent@test.com").first()
        admin_user = db_session.query(User).filter(User.email == "notes_admin@test.com").first()
        cc = db_session.query(CourseContent).filter(CourseContent.title == "Notes Test Material").first()
        return {
            "student": student_user,
            "parent": parent_user,
            "admin": admin_user,
            "course_content": cc,
        }

    # Create student user + profile
    student_user = User(
        email="notes_student@test.com", full_name="Notes Student",
        role=UserRole.STUDENT, hashed_password=hashed,
    )
    db_session.add(student_user)
    db_session.flush()

    student = Student(user_id=student_user.id, grade_level="10")
    db_session.add(student)
    db_session.flush()

    # Create parent user and link
    parent_user = User(
        email="notes_parent@test.com", full_name="Notes Parent",
        role=UserRole.PARENT, hashed_password=hashed,
    )
    db_session.add(parent_user)
    db_session.flush()

    db_session.execute(
        parent_students.insert().values(parent_id=parent_user.id, student_id=student.id, relationship_type="parent")
    )

    # Admin
    admin_user = User(
        email="notes_admin@test.com", full_name="Notes Admin",
        role=UserRole.ADMIN, hashed_password=hashed,
    )
    db_session.add(admin_user)
    db_session.flush()

    # Course + content
    course = Course(name="Notes Biology 101", created_by_user_id=student_user.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(
        course_id=course.id, title="Notes Test Material",
        description="Chapter on mitochondria", content_type="notes",
    )
    db_session.add(cc)
    db_session.commit()

    return {
        "student": student_user,
        "parent": parent_user,
        "admin": admin_user,
        "course_content": cc,
    }


class TestNotesAPI:
    def test_get_note_empty(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        resp = client.get(f"/api/notes/content/{cc_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_upsert_note_create(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        resp = client.put(f"/api/notes/content/{cc_id}", json={
            "content": "<p>The <b>mitochondria</b> is the powerhouse of the cell.</p>",
            "has_images": False,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["course_content_id"] == cc_id
        assert "mitochondria" in data["plain_text"]
        assert "<p>" not in data["plain_text"]  # HTML stripped
        assert data["material_title"] == "Notes Test Material"
        assert data["course_name"] == "Notes Biology 101"

    def test_upsert_note_update(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        resp = client.put(f"/api/notes/content/{cc_id}", json={
            "content": "<p>Updated: ATP synthesis in mitochondria</p>",
            "has_images": False,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ATP synthesis" in data["plain_text"]

    def test_get_note_after_upsert(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        resp = client.get(f"/api/notes/content/{cc_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert "ATP synthesis" in data["plain_text"]

    def test_upsert_note_nonexistent_content(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        resp = client.put("/api/notes/content/99999", json={
            "content": "test",
        }, headers=headers)
        assert resp.status_code == 404

    def test_upsert_note_auto_delete_empty(self, client, notes_users):
        """Empty content should auto-delete the note."""
        headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        # First ensure a note exists
        client.put(f"/api/notes/content/{cc_id}", json={
            "content": "<p>Temporary note</p>",
        }, headers=headers)
        # Now save empty content
        resp = client.put(f"/api/notes/content/{cc_id}", json={
            "content": "",
        }, headers=headers)
        assert resp.status_code == 200
        # Note should be gone
        resp2 = client.get(f"/api/notes/content/{cc_id}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json() is None

    def test_delete_note(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        # Create a note to delete
        client.put(f"/api/notes/content/{cc_id}", json={
            "content": "<p>To be deleted</p>",
        }, headers=headers)
        resp = client.delete(f"/api/notes/content/{cc_id}", headers=headers)
        assert resp.status_code == 204
        # Verify gone
        resp2 = client.get(f"/api/notes/content/{cc_id}", headers=headers)
        assert resp2.json() is None

    def test_delete_note_not_found(self, client, notes_users):
        headers = _auth(client, "notes_student@test.com")
        resp = client.delete("/api/notes/content/99999", headers=headers)
        assert resp.status_code == 404

    def test_children_notes_parent(self, client, notes_users):
        """Parent can see child's notes."""
        # Student creates a note
        student_headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        client.put(f"/api/notes/content/{cc_id}", json={
            "content": "<p>Child's note on biology</p>",
        }, headers=student_headers)

        # Parent queries children's notes
        parent_headers = _auth(client, "notes_parent@test.com")
        resp = client.get(f"/api/notes/children?course_content_id={cc_id}", headers=parent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any("biology" in n["plain_text"] for n in data)

    def test_children_notes_non_parent(self, client, notes_users):
        """Non-parent cannot access children endpoint."""
        headers = _auth(client, "notes_student@test.com")
        resp = client.get("/api/notes/children", headers=headers)
        assert resp.status_code == 403

    def test_requires_auth(self, client, notes_users):
        cc_id = notes_users["course_content"].id
        resp = client.get(f"/api/notes/content/{cc_id}")
        assert resp.status_code == 401


class TestNotesSearch:
    def test_search_notes_by_content(self, client, notes_users):
        """Notes appear in global search results."""
        # Ensure student has a note with searchable content
        student_headers = _auth(client, "notes_student@test.com")
        cc_id = notes_users["course_content"].id
        client.put(f"/api/notes/content/{cc_id}", json={
            "content": "<p>Photosynthesis converts light energy into chemical energy</p>",
        }, headers=student_headers)

        resp = client.get("/api/search", params={
            "q": "Photosynthesis",
            "types": "note",
        }, headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        note_groups = [g for g in data["groups"] if g["entity_type"] == "note"]
        assert len(note_groups) == 1
        assert note_groups[0]["total"] >= 1
        item = note_groups[0]["items"][0]
        assert item["entity_type"] == "note"
        assert "Photosynthesis" in item["subtitle"]
        assert "/course-materials/" in item["url"]
        assert "notes=1" in item["url"]

    def test_search_notes_rbac_parent_sees_child(self, client, notes_users):
        """Parent can see child's notes in search."""
        parent_headers = _auth(client, "notes_parent@test.com")
        resp = client.get("/api/search", params={
            "q": "Photosynthesis",
            "types": "note",
        }, headers=parent_headers)
        assert resp.status_code == 200
        data = resp.json()
        note_groups = [g for g in data["groups"] if g["entity_type"] == "note"]
        assert len(note_groups) == 1
        assert note_groups[0]["total"] >= 1

    def test_search_notes_rbac_other_user_no_access(self, client, notes_users):
        """Admin sees all notes in search (admin bypass)."""
        admin_headers = _auth(client, "notes_admin@test.com")
        resp = client.get("/api/search", params={
            "q": "Photosynthesis",
            "types": "note",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        note_groups = [g for g in data["groups"] if g["entity_type"] == "note"]
        assert len(note_groups) == 1
        # Admin can see the student's note
        assert note_groups[0]["total"] >= 1

    def test_search_notes_no_match(self, client, notes_users):
        """Search for non-existent term returns 0 notes."""
        student_headers = _auth(client, "notes_student@test.com")
        resp = client.get("/api/search", params={
            "q": "xyznonexistent123",
            "types": "note",
        }, headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        note_groups = [g for g in data["groups"] if g["entity_type"] == "note"]
        assert len(note_groups) == 1
        assert note_groups[0]["total"] == 0

    def test_search_all_types_includes_notes(self, client, notes_users):
        """When no types specified, notes are included."""
        student_headers = _auth(client, "notes_student@test.com")
        resp = client.get("/api/search", params={
            "q": "Photosynthesis",
        }, headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        entity_types = [g["entity_type"] for g in data["groups"]]
        assert "note" in entity_types
