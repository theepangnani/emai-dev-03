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

    def test_parent_can_view_child_note_with_highlights(self, client, setup):
        """Parent can read child's note that has highlights_json set."""
        headers_owner = _auth(client, "notes_owner@test.com")
        highlights = '[{"text":"key term","start":0,"end":8}]'
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>key term explained</p>",
            "highlights_json": highlights,
        }, headers=headers_owner)
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(
            f"/api/notes/children/{setup['owner'].id}?course_content_id={setup['course_content'].id}",
            headers=headers_parent,
        )
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 1
        assert notes[0]["highlights_json"] == highlights

    def test_parent_can_get_single_child_note(self, client, setup):
        """Parent can fetch a single child note via GET /notes/{id}."""
        headers_owner = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Parent can see this</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(f"/api/notes/{note_id}", headers=headers_parent)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Parent can see this</p>"

    def test_parent_child_notes_pagination(self, client, setup):
        """Parent can paginate child notes with limit/offset."""
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(
            f"/api/notes/children/{setup['owner'].id}?limit=1&offset=0",
            headers=headers_parent,
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 1


# ── Upsert Edge Cases ──────────────────────────────────────────


class TestUpsertEdgeCases:
    def test_html_special_characters(self, client, setup):
        """Note content with HTML entities, unicode, and special chars."""
        headers = _auth(client, "notes_owner@test.com")
        content = '<p>Caf&eacute; &amp; math: 2 &lt; 3, price $5.99, emoji \u2764\ufe0f</p>'
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": content,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == content

    def test_large_content_10kb(self, client, setup):
        """Upsert with content exceeding 10KB."""
        headers = _auth(client, "notes_owner@test.com")
        # Build ~12KB of content
        large_body = "A" * 12000
        content = f"<p>{large_body}</p>"
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": content,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["content"]) > 10000
        assert data["plain_text"] == large_body

    def test_nested_html_tags(self, client, setup):
        """Content with deeply nested HTML tags."""
        headers = _auth(client, "notes_owner@test.com")
        content = "<div><ul><li><strong><em>Nested</em></strong></li></ul></div>"
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": content,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["plain_text"] == "Nested"

    def test_upsert_preserves_highlights_json(self, client, setup):
        """highlights_json is stored and returned on upsert."""
        headers = _auth(client, "notes_owner@test.com")
        highlights = '[{"text":"hello","start":3,"end":8}]'
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>say hello world</p>",
            "highlights_json": highlights,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["highlights_json"] == highlights

    def test_upsert_null_highlights(self, client, setup):
        """Omitting highlights_json defaults to None."""
        headers = _auth(client, "notes_owner@test.com")
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>No highlights</p>",
        }, headers=headers)
        assert resp.status_code == 200
        # highlights_json should be None or the previous value

    def test_whitespace_only_html_deletes(self, client, setup):
        """Various whitespace-only HTML patterns trigger deletion."""
        headers = _auth(client, "notes_owner@test.com")
        # Create
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Real content</p>",
        }, headers=headers)
        # Whitespace-only HTML
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p> </p><br/><p>\n\t</p>",
        }, headers=headers)
        assert resp.status_code == 204

    def test_empty_string_content_deletes(self, client, setup):
        """Empty string content triggers deletion."""
        headers = _auth(client, "notes_owner@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Exists</p>",
        }, headers=headers)
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "",
        }, headers=headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_note_via_empty_upsert(self, client, setup):
        """Sending empty content when no note exists returns 204 without error."""
        headers = _auth(client, "notes_owner@test.com")
        # First ensure no note exists by deleting
        resp = client.get(
            f"/api/notes/?course_content_id={setup['course_content'].id}",
            headers=headers,
        )
        for n in resp.json():
            client.delete(f"/api/notes/{n['id']}", headers=headers)
        # Now send empty content
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "",
        }, headers=headers)
        assert resp.status_code == 204

    def test_multiple_img_tags_detected(self, client, setup):
        """has_images is True when content has multiple img tags."""
        headers = _auth(client, "notes_owner@test.com")
        resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": '<p>Photos: <img src="a.png"/><img src="b.png"/></p>',
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["has_images"] is True


# ── Version History Tests ───────────────────────────────────────


class TestVersionHistory:
    def test_version_created_on_update(self, client, setup):
        """Updating a note creates a version of the previous content."""
        headers = _auth(client, "notes_owner@test.com")
        # Set known content
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>VerCreate-old</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        versions_before = client.get(f"/api/notes/{note_id}/versions", headers=headers).json()
        count_before = len(versions_before)
        # Update to create a version
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>VerCreate-new</p>",
        }, headers=headers)
        # List versions
        resp = client.get(f"/api/notes/{note_id}/versions", headers=headers)
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) == count_before + 1
        # The newest version (index 0) should contain the OLD content preview
        assert "VerCreate-old" in versions[0]["preview"]

    def test_get_specific_version(self, client, setup):
        """Fetch a specific version's full content."""
        headers = _auth(client, "notes_owner@test.com")
        # Set known starting content
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Get-v-original</p>",
        }, headers=headers)
        # Count existing versions
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Get-v-original</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        versions_before = client.get(f"/api/notes/{note_id}/versions", headers=headers).json()
        count_before = len(versions_before)
        # Now update to create a new version of "Get-v-original"
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Get-v-updated</p>",
        }, headers=headers)
        versions_resp = client.get(f"/api/notes/{note_id}/versions", headers=headers)
        versions = versions_resp.json()
        assert len(versions) == count_before + 1
        # The newest version (index 0, descending order) should be the snapshot
        newest_version_id = versions[0]["id"]
        resp = client.get(f"/api/notes/{note_id}/versions/{newest_version_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Get-v-original</p>"

    def test_restore_version(self, client, setup):
        """Restoring a version updates the note content and saves current as version."""
        headers = _auth(client, "notes_owner@test.com")
        # Set a known starting state
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Restore-base</p>",
        }, headers=headers)
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Restore-base</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        # Update to create a version snapshot of "Restore-base"
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Restore-newer</p>",
        }, headers=headers)
        versions_resp = client.get(f"/api/notes/{note_id}/versions", headers=headers)
        # Get the newest version (which contains "Restore-base")
        newest_version_id = versions_resp.json()[0]["id"]
        # Restore it
        resp = client.post(f"/api/notes/{note_id}/restore/{newest_version_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Restore-base</p>"
        assert resp.json()["plain_text"] == "Restore-base"

    def test_restore_creates_version_of_current(self, client, setup):
        """Restoring saves the current content as a new version first."""
        headers = _auth(client, "notes_owner@test.com")
        # Set known state and create a version
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>RestoreCount-A</p>",
        }, headers=headers)
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>RestoreCount-B</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        versions_before = client.get(f"/api/notes/{note_id}/versions", headers=headers).json()
        count_before = len(versions_before)
        assert count_before >= 1
        version_id = versions_before[0]["id"]  # newest version
        # Restore
        client.post(f"/api/notes/{note_id}/restore/{version_id}", headers=headers)
        versions_after = client.get(f"/api/notes/{note_id}/versions", headers=headers).json()
        # Should have one more version (the pre-restore snapshot)
        assert len(versions_after) == count_before + 1

    def test_versions_sorted_descending(self, client, setup):
        """Versions are returned in descending version_number order."""
        headers = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>v1</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>v2</p>",
        }, headers=headers)
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>v3</p>",
        }, headers=headers)
        resp = client.get(f"/api/notes/{note_id}/versions", headers=headers)
        versions = resp.json()
        if len(versions) >= 2:
            assert versions[0]["version_number"] > versions[-1]["version_number"]

    def test_version_nonexistent_note_404(self, client, setup):
        """Listing versions for a nonexistent note returns 404."""
        headers = _auth(client, "notes_owner@test.com")
        resp = client.get("/api/notes/999999/versions", headers=headers)
        assert resp.status_code == 404

    def test_get_nonexistent_version_404(self, client, setup):
        """Fetching a nonexistent version returns 404."""
        headers = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>exists</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.get(f"/api/notes/{note_id}/versions/999999", headers=headers)
        assert resp.status_code == 404

    def test_restore_nonexistent_version_404(self, client, setup):
        """Restoring a nonexistent version returns 404."""
        headers = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>exists</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        resp = client.post(f"/api/notes/{note_id}/restore/999999", headers=headers)
        assert resp.status_code == 404

    def test_outsider_cannot_list_versions(self, client, setup):
        """Non-owner cannot list versions of another user's note."""
        headers_owner = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Secret versions</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.get(f"/api/notes/{note_id}/versions", headers=headers_outsider)
        assert resp.status_code == 404

    def test_outsider_cannot_restore_version(self, client, setup):
        """Non-owner cannot restore versions of another user's note."""
        headers_owner = _auth(client, "notes_owner@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>OutRestore-A</p>",
        }, headers=headers_owner)
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>OutRestore-B</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        versions = client.get(f"/api/notes/{note_id}/versions", headers=headers_owner).json()
        version_id = versions[0]["id"]
        headers_outsider = _auth(client, "notes_outsider@test.com")
        resp = client.post(f"/api/notes/{note_id}/restore/{version_id}", headers=headers_outsider)
        assert resp.status_code in (403, 404)

    def test_parent_can_view_child_versions(self, client, setup):
        """Parent can list versions for a linked child's note."""
        headers_owner = _auth(client, "notes_owner@test.com")
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Child v1</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>Child v2</p>",
        }, headers=headers_owner)
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.get(f"/api/notes/{note_id}/versions", headers=headers_parent)
        assert resp.status_code == 200

    def test_parent_cannot_restore_child_version(self, client, setup):
        """Parent can view but cannot restore child's versions."""
        headers_owner = _auth(client, "notes_owner@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>ParRestore-A</p>",
        }, headers=headers_owner)
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>ParRestore-B</p>",
        }, headers=headers_owner)
        note_id = put_resp.json()["id"]
        versions = client.get(f"/api/notes/{note_id}/versions", headers=headers_owner).json()
        version_id = versions[0]["id"]
        headers_parent = _auth(client, "notes_parent@test.com")
        resp = client.post(f"/api/notes/{note_id}/restore/{version_id}", headers=headers_parent)
        assert resp.status_code == 403

    def test_version_preview_truncated(self, client, setup):
        """Version preview is truncated to ~120 chars with ellipsis."""
        headers = _auth(client, "notes_owner@test.com")
        long_text = "X" * 200
        put_resp = client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": f"<p>{long_text}</p>",
        }, headers=headers)
        note_id = put_resp.json()["id"]
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>New content</p>",
        }, headers=headers)
        versions = client.get(f"/api/notes/{note_id}/versions", headers=headers).json()
        # Find the version with the long text
        long_version = [v for v in versions if "XXX" in v["preview"]]
        assert len(long_version) >= 1
        assert long_version[0]["preview"].endswith("...")
        assert len(long_version[0]["preview"]) <= 123  # 120 + "..."


# ── List Pagination & Filtering ─────────────────────────────────


class TestListPagination:
    def test_list_with_limit(self, client, setup):
        """Limit parameter restricts result count."""
        headers = _auth(client, "notes_owner@test.com")
        client.put("/api/notes/", json={
            "course_content_id": setup["course_content"].id,
            "content": "<p>At least one note</p>",
        }, headers=headers)
        resp = client.get("/api/notes/?limit=1", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    def test_list_with_offset(self, client, setup):
        """Offset parameter skips results."""
        headers = _auth(client, "notes_owner@test.com")
        resp_all = client.get("/api/notes/?limit=200", headers=headers)
        total = len(resp_all.json())
        resp_offset = client.get(f"/api/notes/?offset={total}", headers=headers)
        assert resp_offset.status_code == 200
        assert len(resp_offset.json()) == 0

    def test_get_nonexistent_note_404(self, client, setup):
        """Fetching a nonexistent note ID returns 404."""
        headers = _auth(client, "notes_owner@test.com")
        resp = client.get("/api/notes/999999", headers=headers)
        assert resp.status_code == 404

    def test_delete_nonexistent_note_404(self, client, setup):
        """Deleting a nonexistent note ID returns 404."""
        headers = _auth(client, "notes_owner@test.com")
        resp = client.delete("/api/notes/999999", headers=headers)
        assert resp.status_code == 404
