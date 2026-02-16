import pytest

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from app.models.study_guide import StudyGuide
    from sqlalchemy import insert

    parent = db_session.query(User).filter(User.email == "sg_parent@test.com").first()
    if parent:
        student = db_session.query(User).filter(User.email == "sg_student@test.com").first()
        outsider = db_session.query(User).filter(User.email == "sg_outsider@test.com").first()
        parent2 = db_session.query(User).filter(User.email == "sg_parent2@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student.id).first()
        course = db_session.query(Course).filter(Course.name == "SG Test Course").first()
        parent_guide = db_session.query(StudyGuide).filter(
            StudyGuide.user_id == parent.id, StudyGuide.title == "Parent Guide"
        ).first()
        child_guide = db_session.query(StudyGuide).filter(
            StudyGuide.user_id == student.id, StudyGuide.title == "Child Guide"
        ).first()
        return {
            "parent": parent, "student": student, "outsider": outsider,
            "parent2": parent2, "student_rec": student_rec, "course": course,
            "parent_guide": parent_guide, "child_guide": child_guide,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="sg_parent@test.com", full_name="SG Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email="sg_student@test.com", full_name="SG Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="sg_outsider@test.com", full_name="SG Outsider", role=UserRole.PARENT, hashed_password=hashed)
    parent2 = User(email="sg_parent2@test.com", full_name="SG Parent2", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="sg_teacher@test.com", full_name="SG Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, student, outsider, parent2, teacher])
    db_session.flush()

    student_rec = Student(user_id=student.id)
    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add_all([student_rec, teacher_rec])
    db_session.flush()

    # Link parent → student
    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))
    # Link parent2 → same student (second parent scenario)
    db_session.execute(insert(parent_students).values(
        parent_id=parent2.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    # Create course, enroll student
    course = Course(name="SG Test Course", teacher_id=teacher_rec.id,
                    created_by_user_id=teacher.id, is_private=False)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(
        student_id=student_rec.id, course_id=course.id,
    ))

    # Insert study guides directly (bypass AI generation)
    parent_guide = StudyGuide(
        user_id=parent.id, title="Parent Guide", content="# Parent Content",
        guide_type="study_guide", version=1, course_id=course.id,
    )
    child_guide = StudyGuide(
        user_id=student.id, title="Child Guide", content="# Child Content",
        guide_type="study_guide", version=1, course_id=course.id,
    )
    quiz_guide = StudyGuide(
        user_id=parent.id, title="Parent Quiz", content='[{"q":"Q1","options":["A","B"],"answer":"A"}]',
        guide_type="quiz", version=1,
    )
    # Version 2 of parent guide (for version history tests)
    parent_guide_v2 = StudyGuide(
        user_id=parent.id, title="Parent Guide", content="# Parent Content v2",
        guide_type="study_guide", version=2,
        # parent_guide_id set after flush
    )
    db_session.add_all([parent_guide, child_guide, quiz_guide, parent_guide_v2])
    db_session.flush()

    # Set parent_guide_id for v2
    parent_guide_v2.parent_guide_id = parent_guide.id
    db_session.commit()

    for u in [parent, student, outsider, parent2]:
        db_session.refresh(u)
    db_session.refresh(student_rec)
    db_session.refresh(course)
    db_session.refresh(parent_guide)
    db_session.refresh(child_guide)

    return {
        "parent": parent, "student": student, "outsider": outsider,
        "parent2": parent2, "student_rec": student_rec, "course": course,
        "parent_guide": parent_guide, "child_guide": child_guide,
    }


# ── List study guides ────────────────────────────────────────

class TestListStudyGuides:
    def test_student_sees_own(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/study/guides", headers=headers)
        assert resp.status_code == 200
        titles = [g["title"] for g in resp.json()]
        assert "Child Guide" in titles

    def test_parent_sees_own_and_child_course_guides_by_default(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/study/guides", headers=headers)
        assert resp.status_code == 200
        titles = {g["title"] for g in resp.json()}
        # Parent sees own guides AND guides tagged to children's enrolled courses
        assert "Parent Guide" in titles
        assert "Child Guide" in titles  # tagged to child's enrolled course

    def test_second_parent_sees_first_parents_course_guides(self, client, users):
        """Second parent linked to same child sees guides tagged to that child's courses."""
        headers = _auth(client, users["parent2"].email)
        resp = client.get("/api/study/guides", headers=headers)
        assert resp.status_code == 200
        titles = {g["title"] for g in resp.json()}
        # Parent2 should see Parent1's guide tagged to the shared child's course
        assert "Parent Guide" in titles

    def test_parent_sees_childrens_with_include_children(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/study/guides?include_children=true", headers=headers)
        assert resp.status_code == 200
        user_ids = {g["user_id"] for g in resp.json()}
        assert users["student"].id in user_ids

    def test_filter_by_guide_type(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/study/guides?guide_type=quiz", headers=headers)
        assert resp.status_code == 200
        for g in resp.json():
            assert g["guide_type"] == "quiz"

    def test_filter_by_course_id(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(f"/api/study/guides?course_id={users['course'].id}", headers=headers)
        assert resp.status_code == 200
        for g in resp.json():
            assert g["course_id"] == users["course"].id


# ── Get study guide ──────────────────────────────────────────

class TestGetStudyGuide:
    def test_owner_gets_own(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(f"/api/study/guides/{users['parent_guide'].id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Parent Guide"

    def test_parent_gets_childs(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(f"/api/study/guides/{users['child_guide'].id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Child Guide"

    def test_outsider_gets_404(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.get(f"/api/study/guides/{users['parent_guide'].id}", headers=headers)
        assert resp.status_code == 404

    def test_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/study/guides/999999", headers=headers)
        assert resp.status_code == 404


# ── Update study guide ───────────────────────────────────────

class TestUpdateStudyGuide:
    def test_assign_course(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.patch(
            f"/api/study/guides/{users['parent_guide'].id}",
            json={"course_id": users["course"].id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["course_id"] == users["course"].id

    def test_non_owner_returns_404(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.patch(
            f"/api/study/guides/{users['parent_guide'].id}",
            json={"course_id": users["course"].id},
            headers=headers,
        )
        assert resp.status_code == 404


# ── Delete study guide ───────────────────────────────────────

class TestDeleteStudyGuide:
    def test_owner_deletes(self, client, users, db_session):
        from app.models.study_guide import StudyGuide

        # Create a disposable guide
        guide = StudyGuide(
            user_id=users["parent"].id, title="Disposable", content="# Delete Me",
            guide_type="study_guide", version=1,
        )
        db_session.add(guide)
        db_session.commit()
        db_session.refresh(guide)

        headers = _auth(client, users["parent"].email)
        resp = client.delete(f"/api/study/guides/{guide.id}", headers=headers)
        assert resp.status_code == 204

    def test_non_owner_returns_404(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.delete(f"/api/study/guides/{users['parent_guide'].id}", headers=headers)
        assert resp.status_code == 404


# ── Duplicate check ──────────────────────────────────────────

class TestDuplicateCheck:
    def test_duplicate_found_by_title(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/study/check-duplicate", json={
            "title": "Parent Guide", "guide_type": "study_guide",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["exists"] is True

    def test_no_duplicate(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/study/check-duplicate", json={
            "title": "Unique Title XYZ", "guide_type": "study_guide",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["exists"] is False


# ── Upload formats ───────────────────────────────────────────

class TestUploadFormats:
    def test_get_supported_formats(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/study/upload/formats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "supported_formats" in data or "formats" in data or isinstance(data, dict)


# ── Version history ──────────────────────────────────────────

class TestVersionHistory:
    def test_list_versions(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(
            f"/api/study/guides/{users['parent_guide'].id}/versions",
            headers=headers,
        )
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 2
        version_nums = [v["version"] for v in versions]
        assert 1 in version_nums
        assert 2 in version_nums


# ── Archive / Restore / Permanent Delete ─────────────────────

class TestArchiveLifecycle:
    def _make_guide(self, db_session, user_id):
        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=user_id, title="Lifecycle Guide",
            content="# Lifecycle", guide_type="study_guide", version=1,
        )
        db_session.add(guide)
        db_session.commit()
        db_session.refresh(guide)
        return guide

    def test_soft_delete_archives(self, client, users, db_session):
        guide = self._make_guide(db_session, users["parent"].id)
        headers = _auth(client, users["parent"].email)
        resp = client.delete(f"/api/study/guides/{guide.id}", headers=headers)
        assert resp.status_code == 204

        # Archived guide hidden from default listing
        list_resp = client.get("/api/study/guides", headers=headers)
        ids = [g["id"] for g in list_resp.json()]
        assert guide.id not in ids

        # Visible with include_archived
        list_resp2 = client.get("/api/study/guides?include_archived=true", headers=headers)
        ids2 = [g["id"] for g in list_resp2.json()]
        assert guide.id in ids2

    def test_restore_archived_guide(self, client, users, db_session):
        guide = self._make_guide(db_session, users["parent"].id)
        headers = _auth(client, users["parent"].email)

        # Archive first
        client.delete(f"/api/study/guides/{guide.id}", headers=headers)

        # Restore
        resp = client.patch(f"/api/study/guides/{guide.id}/restore", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == guide.id

        # Back in default listing
        list_resp = client.get("/api/study/guides", headers=headers)
        ids = [g["id"] for g in list_resp.json()]
        assert guide.id in ids

    def test_restore_non_archived_returns_400(self, client, users, db_session):
        guide = self._make_guide(db_session, users["parent"].id)
        headers = _auth(client, users["parent"].email)
        resp = client.patch(f"/api/study/guides/{guide.id}/restore", headers=headers)
        assert resp.status_code == 400

    def test_permanent_delete_requires_archive(self, client, users, db_session):
        guide = self._make_guide(db_session, users["parent"].id)
        headers = _auth(client, users["parent"].email)
        resp = client.delete(f"/api/study/guides/{guide.id}/permanent", headers=headers)
        assert resp.status_code == 400

    def test_permanent_delete_after_archive(self, client, users, db_session):
        guide = self._make_guide(db_session, users["parent"].id)
        headers = _auth(client, users["parent"].email)

        # Archive then permanently delete
        client.delete(f"/api/study/guides/{guide.id}", headers=headers)
        resp = client.delete(f"/api/study/guides/{guide.id}/permanent", headers=headers)
        assert resp.status_code == 204

        # Gone from all listings
        list_resp = client.get("/api/study/guides?include_archived=true", headers=headers)
        ids = [g["id"] for g in list_resp.json()]
        assert guide.id not in ids
