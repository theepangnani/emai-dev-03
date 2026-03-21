"""Tests for material hierarchy feature (#1740).

Tests cover:
- generate_sub_title() utility
- create_material_hierarchy() service function
- get_linked_materials() service function
- POST /upload-multi hierarchy creation (integration)
- GET /linked-materials endpoint (integration)
"""
import pytest
from conftest import PASSWORD, _auth


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture()
def hierarchy_users(db_session):
    """Create teacher + course for hierarchy tests (idempotent)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course

    teacher = db_session.query(User).filter(User.email == "mh_teacher@test.com").first()
    if teacher:
        course = db_session.query(Course).filter(Course.name == "MH Test Course").first()
        return {"teacher": teacher, "course": course}

    hashed = get_password_hash(PASSWORD)
    teacher = User(
        email="mh_teacher@test.com",
        full_name="MH Teacher",
        role=UserRole.TEACHER,
        hashed_password=hashed,
    )
    db_session.add(teacher)
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(
        name="MH Test Course",
        teacher_id=teacher_rec.id,
        created_by_user_id=teacher.id,
    )
    db_session.add(course)
    db_session.commit()

    db_session.refresh(teacher)
    db_session.refresh(course)
    return {"teacher": teacher, "course": course}


# ── Unit tests: generate_sub_title ───────────────────────────


class TestGenerateSubTitle:
    def test_basic(self):
        from app.services.material_hierarchy import generate_sub_title
        assert generate_sub_title("Math Notes", 1) == "Math Notes \u2014 Part 1"
        assert generate_sub_title("Math Notes", 3) == "Math Notes \u2014 Part 3"

    def test_with_large_index(self):
        from app.services.material_hierarchy import generate_sub_title
        assert generate_sub_title("Lecture", 10) == "Lecture \u2014 Part 10"

    def test_preserves_title(self):
        from app.services.material_hierarchy import generate_sub_title
        title = "  Physics Lab Report  "
        result = generate_sub_title(title, 2)
        assert "Part 2" in result


# ── Unit tests: hierarchy service ────────────────────────────


class TestMaterialHierarchyService:
    def test_create_hierarchy(self, db_session, hierarchy_users):
        """create_material_hierarchy should link master + N sub-materials."""
        from app.models.course_content import CourseContent
        from app.services.material_hierarchy import create_material_hierarchy

        course = hierarchy_users["course"]
        teacher = hierarchy_users["teacher"]

        master = CourseContent(
            course_id=course.id,
            title="Combined Notes",
            content_type="notes",
            created_by_user_id=teacher.id,
        )
        db_session.add(master)
        db_session.flush()

        subs = []
        for i in range(1, 4):
            cc = CourseContent(
                course_id=course.id,
                title=f"File {i}",
                content_type="notes",
                created_by_user_id=teacher.id,
            )
            db_session.add(cc)
            db_session.flush()
            subs.append(cc)

        group_id = create_material_hierarchy(db_session, master, subs)
        db_session.commit()

        db_session.refresh(master)
        assert master.title == "Combined Notes"
        assert master.material_group_id == group_id
        assert master.is_master is True

        for sub in subs:
            db_session.refresh(sub)
            assert sub.material_group_id == group_id
            assert sub.parent_content_id == master.id

    def test_get_linked_from_master(self, db_session, hierarchy_users):
        """get_linked_materials from master returns master + sub-materials."""
        from app.models.course_content import CourseContent
        from app.services.material_hierarchy import create_material_hierarchy, get_linked_materials

        course = hierarchy_users["course"]
        teacher = hierarchy_users["teacher"]

        master = CourseContent(
            course_id=course.id,
            title="Linked Master",
            content_type="notes",
            created_by_user_id=teacher.id,
        )
        db_session.add(master)
        db_session.flush()

        subs = []
        for i in range(1, 3):
            cc = CourseContent(
                course_id=course.id,
                title=f"Linked Sub {i}",
                content_type="notes",
                created_by_user_id=teacher.id,
            )
            db_session.add(cc)
            db_session.flush()
            subs.append(cc)

        create_material_hierarchy(db_session, master, subs)
        db_session.commit()

        linked = get_linked_materials(db_session, master.id)
        linked_ids = {m.id for m in linked}
        assert master.id in linked_ids
        for sub in subs:
            assert sub.id in linked_ids

    def test_get_linked_from_sub(self, db_session, hierarchy_users):
        """get_linked_materials from a sub returns master + all siblings including self."""
        from app.models.course_content import CourseContent
        from app.services.material_hierarchy import create_material_hierarchy, get_linked_materials

        course = hierarchy_users["course"]
        teacher = hierarchy_users["teacher"]

        master = CourseContent(
            course_id=course.id,
            title="Sibling Master",
            content_type="notes",
            created_by_user_id=teacher.id,
        )
        db_session.add(master)
        db_session.flush()

        subs = []
        for i in range(1, 4):
            cc = CourseContent(
                course_id=course.id,
                title=f"Sibling {i}",
                content_type="notes",
                created_by_user_id=teacher.id,
            )
            db_session.add(cc)
            db_session.flush()
            subs.append(cc)

        create_material_hierarchy(db_session, master, subs)
        db_session.commit()

        linked = get_linked_materials(db_session, subs[0].id)
        linked_ids = {m.id for m in linked}
        assert master.id in linked_ids
        assert subs[0].id in linked_ids
        assert subs[1].id in linked_ids
        assert subs[2].id in linked_ids

    def test_get_linked_standalone(self, db_session, hierarchy_users):
        """get_linked_materials on non-grouped material returns empty list."""
        from app.models.course_content import CourseContent
        from app.services.material_hierarchy import get_linked_materials

        course = hierarchy_users["course"]
        teacher = hierarchy_users["teacher"]

        standalone = CourseContent(
            course_id=course.id,
            title="Standalone Material",
            content_type="notes",
            created_by_user_id=teacher.id,
        )
        db_session.add(standalone)
        db_session.commit()
        db_session.refresh(standalone)

        linked = get_linked_materials(db_session, standalone.id)
        assert linked == []


# ── Integration tests: upload-multi hierarchy ────────────────


class TestUploadMultiHierarchy:
    def _make_files(self, count: int):
        """Create list of (field_name, (filename, content, mime)) tuples."""
        return [
            ("files", (f"file{i}.txt", f"Content of file {i}".encode(), "text/plain"))
            for i in range(1, count + 1)
        ]

    def test_upload_multi_creates_hierarchy(self, client, hierarchy_users):
        """Upload 3 files => 1 master + 3 sub-materials with hierarchy."""
        headers = _auth(client, hierarchy_users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload-multi",
            data={
                "course_id": str(hierarchy_users["course"].id),
                "title": "Multi Upload Test",
            },
            files=self._make_files(3),
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["title"] == "Multi Upload Test"
        assert data.get("material_group_id") is not None

    def test_upload_multi_single_file_no_hierarchy(self, client, hierarchy_users):
        """Upload 1 file => no hierarchy created (backward compatible)."""
        headers = _auth(client, hierarchy_users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload-multi",
            data={
                "course_id": str(hierarchy_users["course"].id),
                "title": "Single File Upload",
            },
            files=self._make_files(1),
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("material_group_id") is None

    def test_upload_multi_max_10_files(self, client, hierarchy_users):
        """Upload 11 files => 400 error (max 10 enforced)."""
        headers = _auth(client, hierarchy_users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload-multi",
            data={
                "course_id": str(hierarchy_users["course"].id),
                "title": "Too Many Files",
            },
            files=self._make_files(11),
            headers=headers,
        )
        assert resp.status_code == 400

    def test_sub_material_naming(self, client, db_session, hierarchy_users):
        """Sub-materials should be named after their original filenames (without extension)."""
        from app.models.course_content import CourseContent

        headers = _auth(client, hierarchy_users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload-multi",
            data={
                "course_id": str(hierarchy_users["course"].id),
                "title": "Naming Test",
            },
            files=self._make_files(3),
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        group_id = data.get("material_group_id")
        assert group_id is not None

        materials = (
            db_session.query(CourseContent)
            .filter(CourseContent.material_group_id == group_id)
            .order_by(CourseContent.id)
            .all()
        )
        # 3 files => 1 master + 2 subs (per §6.98 Rule 3)
        sub_titles = [m.title for m in materials if m.id != data["id"]]
        assert len(sub_titles) == 2
        # Sub-materials use their original filenames (without extension)
        assert sub_titles[0] == "file2"
        assert sub_titles[1] == "file3"


# ── Integration tests: linked-materials endpoint ─────────────


class TestLinkedMaterialsEndpoint:
    def _create_hierarchy_via_api(self, client, hierarchy_users):
        """Helper: upload 3 files to create hierarchy, return master response."""
        headers = _auth(client, hierarchy_users["teacher"].email)
        files = [
            ("files", (f"linked{i}.txt", f"Linked content {i}".encode(), "text/plain"))
            for i in range(1, 4)
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            data={
                "course_id": str(hierarchy_users["course"].id),
                "title": "Linked Test",
            },
            files=files,
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_linked_materials_from_master(self, client, hierarchy_users):
        """GET /linked-materials from master returns sub-materials."""
        headers = _auth(client, hierarchy_users["teacher"].email)
        master = self._create_hierarchy_via_api(client, hierarchy_users)

        resp = client.get(
            f"/api/course-contents/{master['id']}/linked-materials",
            headers=headers,
        )
        assert resp.status_code == 200
        linked = resp.json()
        assert len(linked) >= 3  # 3 files => master + 2 subs; includes self

    def test_linked_materials_from_sub(self, client, db_session, hierarchy_users):
        """GET /linked-materials from sub returns master + siblings."""
        from app.models.course_content import CourseContent

        headers = _auth(client, hierarchy_users["teacher"].email)
        master = self._create_hierarchy_via_api(client, hierarchy_users)
        group_id = master["material_group_id"]

        sub = (
            db_session.query(CourseContent)
            .filter(
                CourseContent.material_group_id == group_id,
                CourseContent.id != master["id"],
            )
            .first()
        )
        assert sub is not None

        resp = client.get(
            f"/api/course-contents/{sub.id}/linked-materials",
            headers=headers,
        )
        assert resp.status_code == 200
        linked = resp.json()
        linked_ids = {item["id"] for item in linked}
        assert master["id"] in linked_ids
        assert sub.id in linked_ids

    def test_linked_materials_standalone(self, client, hierarchy_users):
        """GET /linked-materials on non-grouped material returns empty list."""
        headers = _auth(client, hierarchy_users["teacher"].email)
        resp = client.post(
            "/api/course-contents/",
            json={
                "course_id": hierarchy_users["course"].id,
                "title": "Standalone Item",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["id"]

        resp = client.get(
            f"/api/course-contents/{cid}/linked-materials",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []
