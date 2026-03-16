"""Tests for multi-document management endpoints (§6.99, #993).

Covers:
  - POST /api/course-contents/{id}/add-files
  - PUT  /api/course-contents/{id}/reorder-subs
  - DELETE /api/course-contents/{id}/sub-materials/{sub_id}
"""
import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course

    parent = db_session.query(User).filter(User.email == "mdm_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "mdm_teacher@test.com").first()
        other = db_session.query(User).filter(User.email == "mdm_other@test.com").first()
        course = db_session.query(Course).filter(Course.name == "MDM Test Course").first()
        return {"parent": parent, "teacher": teacher, "other": other, "course": course}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="mdm_parent@test.com", full_name="MDM Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="mdm_teacher@test.com", full_name="MDM Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    other = User(email="mdm_other@test.com", full_name="MDM Other", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, teacher, other])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(name="MDM Test Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id, is_private=True)
    db_session.add(course)
    db_session.commit()

    for u in [parent, teacher, other]:
        db_session.refresh(u)
    db_session.refresh(course)
    return {"parent": parent, "teacher": teacher, "other": other, "course": course}


def _upload_single(client, headers, course_id, title="Single File"):
    """Upload a single file and return the response JSON."""
    resp = client.post(
        "/api/course-contents/upload",
        data={"course_id": str(course_id), "title": title},
        files={"file": ("test.txt", b"Hello world", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload_multi(client, headers, course_id, file_count=2, title="Multi File"):
    """Upload multiple files via upload-multi and return the response JSON (master)."""
    files = [
        ("files", (f"file{i}.txt", f"Content of file {i}".encode(), "text/plain"))
        for i in range(1, file_count + 1)
    ]
    resp = client.post(
        "/api/course-contents/upload-multi",
        data={"course_id": str(course_id), "title": title, "content_type": "notes"},
        files=files,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Add Files to Existing Material ───────────────────────────────


class TestAddFiles:
    def test_add_files_to_standalone_material(self, client, users):
        """Upload single file, then add 2 more → promotes to master."""
        headers = _auth(client, users["teacher"].email)
        original = _upload_single(client, headers, users["course"].id, "Standalone")
        assert original["is_master"] == "false"

        resp = client.post(
            f"/api/course-contents/{original['id']}/add-files",
            files=[
                ("files", ("extra1.txt", b"Extra content 1", "text/plain")),
                ("files", ("extra2.txt", b"Extra content 2", "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["is_master"] == "true"
        assert data["material_group_id"] is not None

        # Verify sub-materials were created
        linked = client.get(
            f"/api/course-contents/{original['id']}/linked-materials",
            headers=headers,
        )
        assert linked.status_code == 200
        linked_data = linked.json()
        assert len(linked_data) == 2
        for sub in linked_data:
            assert sub["is_master"] == "false"

    def test_add_files_to_master_material(self, client, users):
        """Create a multi-file upload (master+subs), then add 1 more file."""
        headers = _auth(client, users["teacher"].email)
        master = _upload_multi(client, headers, users["course"].id, 2, "Master Test")
        master_id = master["id"]
        assert master["is_master"] == "true"

        # Get existing subs count
        linked_before = client.get(
            f"/api/course-contents/{master_id}/linked-materials",
            headers=headers,
        )
        assert linked_before.status_code == 200
        subs_before = len(linked_before.json())

        # Add 1 more file
        resp = client.post(
            f"/api/course-contents/{master_id}/add-files",
            files=[("files", ("added.txt", b"Added content", "text/plain"))],
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

        linked_after = client.get(
            f"/api/course-contents/{master_id}/linked-materials",
            headers=headers,
        )
        assert linked_after.status_code == 200
        assert len(linked_after.json()) == subs_before + 1

    def test_add_files_exceeds_limit(self, client, users):
        """Try adding 11 files → expect 400."""
        headers = _auth(client, users["teacher"].email)
        original = _upload_single(client, headers, users["course"].id, "Limit Test")

        files = [
            ("files", (f"f{i}.txt", f"content {i}".encode(), "text/plain"))
            for i in range(11)
        ]
        resp = client.post(
            f"/api/course-contents/{original['id']}/add-files",
            files=files,
            headers=headers,
        )
        assert resp.status_code == 400

    def test_add_files_no_access(self, client, users):
        """User without course access → 403."""
        headers = _auth(client, users["teacher"].email)
        original = _upload_single(client, headers, users["course"].id, "No Access Test")

        other_headers = _auth(client, users["other"].email)
        resp = client.post(
            f"/api/course-contents/{original['id']}/add-files",
            files=[("files", ("x.txt", b"data", "text/plain"))],
            headers=other_headers,
        )
        assert resp.status_code == 403

    def test_add_files_not_found(self, client, users):
        """Nonexistent content_id → 404."""
        headers = _auth(client, users["teacher"].email)
        resp = client.post(
            "/api/course-contents/999999/add-files",
            files=[("files", ("x.txt", b"data", "text/plain"))],
            headers=headers,
        )
        assert resp.status_code == 404


# ── Reorder Sub-Materials ────────────────────────────────────────


class TestReorderSubs:
    def _create_master_with_subs(self, client, headers, course_id, sub_count=3):
        """Helper: create a master with N sub-materials via upload-multi."""
        master = _upload_multi(client, headers, course_id, sub_count, "Reorder Test")
        return master

    def test_reorder_subs_success(self, client, db_session, users):
        """Create master with subs, reorder, verify display_order."""
        headers = _auth(client, users["teacher"].email)
        # 4 files => 1 master + 3 subs (per §6.98 Rule 3)
        master = self._create_master_with_subs(client, headers, users["course"].id, 4)
        master_id = master["id"]

        # Get sub IDs
        linked = client.get(
            f"/api/course-contents/{master_id}/linked-materials",
            headers=headers,
        )
        assert linked.status_code == 200
        sub_ids = [s["id"] for s in linked.json()]
        assert len(sub_ids) == 3

        # Reverse the order
        reversed_ids = list(reversed(sub_ids))
        resp = client.put(
            f"/api/course-contents/{master_id}/reorder-subs",
            json={"sub_ids": reversed_ids},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["reordered"] == 3

        # Verify display_order in DB
        from app.models.course_content import CourseContent
        for expected_order, sid in enumerate(reversed_ids, 1):
            sub = db_session.query(CourseContent).filter(CourseContent.id == sid).first()
            db_session.refresh(sub)
            assert sub.display_order == expected_order

    def test_reorder_non_master(self, client, users):
        """Reorder on a non-master material → 400."""
        headers = _auth(client, users["teacher"].email)
        standalone = _upload_single(client, headers, users["course"].id, "Not Master")

        resp = client.put(
            f"/api/course-contents/{standalone['id']}/reorder-subs",
            json={"sub_ids": [1]},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_reorder_invalid_sub_ids(self, client, users):
        """Pass sub IDs that don't belong to this master → 400."""
        headers = _auth(client, users["teacher"].email)
        master = self._create_master_with_subs(client, headers, users["course"].id, 2)
        master_id = master["id"]

        resp = client.put(
            f"/api/course-contents/{master_id}/reorder-subs",
            json={"sub_ids": [999998, 999999]},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_reorder_not_found(self, client, users):
        """Nonexistent content_id → 404."""
        headers = _auth(client, users["teacher"].email)
        resp = client.put(
            "/api/course-contents/999999/reorder-subs",
            json={"sub_ids": [1]},
            headers=headers,
        )
        assert resp.status_code == 404


# ── Delete Sub-Material ──────────────────────────────────────────


class TestDeleteSubMaterial:
    def _create_master_with_subs(self, client, headers, course_id, sub_count=3):
        """Helper: create a master with N sub-materials via upload-multi."""
        master = _upload_multi(client, headers, course_id, sub_count, "Delete Test")
        master_id = master["id"]
        linked = client.get(
            f"/api/course-contents/{master_id}/linked-materials",
            headers=headers,
        )
        assert linked.status_code == 200
        sub_ids = [s["id"] for s in linked.json()]
        return master_id, sub_ids

    def test_delete_sub_material_success(self, client, users):
        """Delete one sub from a group, verify it's gone."""
        headers = _auth(client, users["teacher"].email)
        # 4 files => 1 master + 3 subs (per §6.98 Rule 3)
        master_id, sub_ids = self._create_master_with_subs(
            client, headers, users["course"].id, 4,
        )
        assert len(sub_ids) == 3
        to_delete = sub_ids[0]

        resp = client.delete(
            f"/api/course-contents/{master_id}/sub-materials/{to_delete}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_subs"] == 2
        assert data["is_master"] == "true"

        # Verify it's actually gone
        linked = client.get(
            f"/api/course-contents/{master_id}/linked-materials",
            headers=headers,
        )
        remaining_ids = [s["id"] for s in linked.json()]
        assert to_delete not in remaining_ids
        assert len(remaining_ids) == 2

    def test_delete_last_sub_demotes_master(self, client, users):
        """Delete the only sub in a group → master demotes to standalone."""
        headers = _auth(client, users["teacher"].email)
        # Use add-files to a standalone to get exactly 1 sub
        standalone = _upload_single(client, headers, users["course"].id, "Demote Test")
        standalone_id = standalone["id"]

        # Add 1 file → promotes to master with 1 sub
        resp = client.post(
            f"/api/course-contents/{standalone_id}/add-files",
            files=[("files", ("sub.txt", b"Sub content", "text/plain"))],
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["is_master"] == "true"

        # Get the sub ID
        linked = client.get(
            f"/api/course-contents/{standalone_id}/linked-materials",
            headers=headers,
        )
        assert linked.status_code == 200
        sub_ids = [s["id"] for s in linked.json()]
        assert len(sub_ids) == 1

        # Delete the only sub
        resp = client.delete(
            f"/api/course-contents/{standalone_id}/sub-materials/{sub_ids[0]}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_subs"] == 0
        assert data["is_master"] == "false"

    def test_delete_sub_not_in_group(self, client, users):
        """Try to delete a sub that doesn't belong to this master → 404."""
        headers = _auth(client, users["teacher"].email)
        master_id, sub_ids = self._create_master_with_subs(
            client, headers, users["course"].id, 2,
        )

        # Create another standalone material (not in this group)
        other = _upload_single(client, headers, users["course"].id, "Other Material")

        resp = client.delete(
            f"/api/course-contents/{master_id}/sub-materials/{other['id']}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_delete_from_non_master(self, client, users):
        """Try to delete from a non-master → 400."""
        headers = _auth(client, users["teacher"].email)
        standalone = _upload_single(client, headers, users["course"].id, "Not Master Delete")

        resp = client.delete(
            f"/api/course-contents/{standalone['id']}/sub-materials/999999",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_delete_sub_no_access(self, client, users):
        """User without course access → 403."""
        headers = _auth(client, users["teacher"].email)
        master_id, sub_ids = self._create_master_with_subs(
            client, headers, users["course"].id, 2,
        )

        other_headers = _auth(client, users["other"].email)
        resp = client.delete(
            f"/api/course-contents/{master_id}/sub-materials/{sub_ids[0]}",
            headers=other_headers,
        )
        assert resp.status_code == 403
