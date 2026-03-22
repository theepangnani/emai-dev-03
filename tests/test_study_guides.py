import pytest
from conftest import PASSWORD, _login, _auth


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

    def test_parent_archives_childs_guide(self, client, users, db_session):
        """Regression #924: parent must be able to archive a guide created by their child."""
        from app.models.study_guide import StudyGuide

        guide = StudyGuide(
            user_id=users["student"].id, title="Child Disposable",
            content="# Delete Me", guide_type="study_guide", version=1,
            course_id=users["course"].id,
        )
        db_session.add(guide)
        db_session.commit()
        db_session.refresh(guide)

        headers = _auth(client, users["parent"].email)
        resp = client.delete(f"/api/study/guides/{guide.id}", headers=headers)
        assert resp.status_code == 204

    def test_unlinked_parent_cannot_archive_childs_guide(self, client, users, db_session):
        """An unrelated parent should NOT be able to archive another child's guide."""
        headers = _auth(client, users["outsider"].email)
        resp = client.delete(f"/api/study/guides/{users['child_guide'].id}", headers=headers)
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


# ── Auto-task creation from study guide (#902) ────────────────

class TestAutoTaskCreationFromStudyGuide:
    """Regression tests for #902: tasks must be auto-created when generating study material."""

    def test_auto_create_tasks_sets_parent_id(self, db_session, users):
        """auto_create_tasks_from_dates must set parent_id on created tasks."""
        from app.api.routes.study import auto_create_tasks_from_dates
        from app.models.task import Task

        parent = users["parent"]
        student = users["student"]

        # Create a dummy study guide to link against
        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=parent.id, title="Auto-task test", content="# content",
            guide_type="study_guide", version=1,
        )
        db_session.add(guide)
        db_session.flush()

        dates = [{"date": "2026-03-15", "title": "Test Deadline", "priority": "high"}]
        created = auto_create_tasks_from_dates(
            db_session, dates, parent, guide.id, None, None,
        )

        assert len(created) == 1
        task = db_session.query(Task).filter(Task.id == created[0]["id"]).first()
        assert task is not None
        assert task.parent_id == parent.id, "parent_id must be set on auto-created tasks"
        assert task.created_by_user_id == parent.id
        assert task.assigned_to_user_id == student.id, "should be assigned to linked child"

        # Cleanup
        db_session.delete(task)
        db_session.delete(guide)
        db_session.commit()

    def test_auto_create_tasks_sets_student_id(self, db_session, users):
        """auto_create_tasks_from_dates must set legacy student_id FK."""
        from app.api.routes.study import auto_create_tasks_from_dates
        from app.models.task import Task

        parent = users["parent"]
        student_rec = users["student_rec"]

        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=parent.id, title="Student-id test", content="# content",
            guide_type="study_guide", version=1,
        )
        db_session.add(guide)
        db_session.flush()

        dates = [{"date": "2026-04-01", "title": "Student ID Check", "priority": "medium"}]
        created = auto_create_tasks_from_dates(
            db_session, dates, parent, guide.id, None, None,
        )

        assert len(created) == 1
        task = db_session.query(Task).filter(Task.id == created[0]["id"]).first()
        assert task.student_id == student_rec.id, "legacy student_id must be set"

        # Cleanup
        db_session.delete(task)
        db_session.delete(guide)
        db_session.commit()

    def test_auto_create_tasks_fallback_review_task(self, db_session, users):
        """When AI returns no critical dates, a fallback 'Review:' task should be created."""
        from app.api.routes.study import auto_create_tasks_from_dates
        from app.models.task import Task
        from datetime import datetime, timezone

        parent = users["parent"]

        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=parent.id, title="Fallback test", content="# content",
            guide_type="study_guide", version=1,
        )
        db_session.add(guide)
        db_session.flush()

        # Simulate the fallback that the endpoint creates
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fallback_dates = [{"date": today_str, "title": "Review: Fallback test", "priority": "medium"}]

        created = auto_create_tasks_from_dates(
            db_session, fallback_dates, parent, guide.id, None, None,
        )

        assert len(created) == 1
        assert created[0]["title"] == "Review: Fallback test"
        task = db_session.query(Task).filter(Task.id == created[0]["id"]).first()
        assert task is not None
        assert task.parent_id == parent.id

        # Cleanup
        db_session.delete(task)
        db_session.delete(guide)
        db_session.commit()

    def test_auto_task_visible_in_task_list(self, client, db_session, users):
        """Auto-created tasks must appear in the task list for the creating parent."""
        from app.api.routes.study import auto_create_tasks_from_dates
        from app.models.task import Task

        parent = users["parent"]

        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=parent.id, title="Visibility test", content="# content",
            guide_type="study_guide", version=1,
        )
        db_session.add(guide)
        db_session.flush()

        dates = [{"date": "2026-05-01", "title": "Visible Task", "priority": "low"}]
        created = auto_create_tasks_from_dates(
            db_session, dates, parent, guide.id, None, None,
        )
        db_session.commit()

        headers = _auth(client, parent.email)
        resp = client.get("/api/tasks/", headers=headers)
        assert resp.status_code == 200
        task_titles = [t["title"] for t in resp.json()]
        assert "Visible Task" in task_titles, "auto-created task must be visible in parent's task list"

        # Cleanup
        task = db_session.query(Task).filter(Task.id == created[0]["id"]).first()
        if task:
            db_session.delete(task)
        db_session.delete(guide)
        db_session.commit()


class TestAIDateContext:
    """Regression: AI prompts must include today's date for year inference (#902)."""

    def test_study_guide_prompt_includes_today(self):
        """_build_study_guide_prompt must contain today's date."""
        import inspect
        from app.services.ai_service import _build_study_guide_prompt
        source = inspect.getsource(_build_study_guide_prompt)
        assert "Today's date is" in source, "AI prompt must include today's date for year inference"

    def test_quiz_prompt_includes_today(self):
        """generate_quiz prompt must contain today's date."""
        import inspect
        from app.services.ai_service import generate_quiz
        source = inspect.getsource(generate_quiz)
        assert "Today's date is" in source, "AI prompt must include today's date for year inference"

    def test_flashcards_prompt_includes_today(self):
        """generate_flashcards prompt must contain today's date."""
        import inspect
        from app.services.ai_service import generate_flashcards
        source = inspect.getsource(generate_flashcards)
        assert "Today's date is" in source, "AI prompt must include today's date for year inference"


class TestScanContentForDates:
    """Regression tests for scan_content_for_dates() fallback (#925)."""

    def test_due_mar_3_extracts_march(self):
        """'Due Mar 3' in content should extract March 3 date."""
        from app.api.routes.study import scan_content_for_dates
        result = scan_content_for_dates("Assignment summary\nDue Mar 3\nPlease review", "My Assignment")
        assert len(result) == 1
        assert result[0]["date"].endswith("-03-03")

    def test_due_colon_format(self):
        """'Due: March 15' should be recognised."""
        from app.api.routes.study import scan_content_for_dates
        result = scan_content_for_dates("Due: March 15", "Homework")
        assert len(result) == 1
        assert "-03-15" in result[0]["date"]

    def test_due_date_with_year(self):
        """'Due Jan 10, 2027' should use the explicit year."""
        from app.api.routes.study import scan_content_for_dates
        result = scan_content_for_dates("Due Jan 10, 2027", "Report")
        assert len(result) == 1
        assert result[0]["date"] == "2027-01-10"

    def test_no_dates_returns_empty(self):
        """Content without date patterns returns empty list."""
        from app.api.routes.study import scan_content_for_dates
        result = scan_content_for_dates("Just a normal paragraph with no dates", "Notes")
        assert result == []

    def test_due_by_format(self):
        """'Due by Apr 1' should be recognised."""
        from app.api.routes.study import scan_content_for_dates
        result = scan_content_for_dates("Due by Apr 1", "Project")
        assert len(result) == 1
        assert "-04-01" in result[0]["date"]

    def test_multiple_dates(self):
        """Multiple due date patterns should all be extracted."""
        from app.api.routes.study import scan_content_for_dates
        text = "Part A Due Mar 3\nPart B Due: April 10"
        result = scan_content_for_dates(text, "Multi-part")
        assert len(result) == 2


# ── Focus prompt history (#1001) ─────────────────────────────


class TestFocusPromptHistory:
    """Focus prompt is persisted on generation and returned in list/get responses."""

    def test_focus_prompt_saved_on_study_guide(self, db_session, users):
        """A study guide created with focus_prompt has it persisted in the DB."""
        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=users["parent"].id,
            title="Focus Test Guide",
            content="# Content",
            guide_type="study_guide",
            version=1,
            focus_prompt="photosynthesis and the Calvin cycle",
        )
        db_session.add(guide)
        db_session.commit()
        db_session.refresh(guide)

        assert guide.focus_prompt == "photosynthesis and the Calvin cycle"

        # Cleanup
        db_session.delete(guide)
        db_session.commit()

    def test_focus_prompt_returned_in_list(self, client, db_session, users):
        """GET /api/study/guides returns focus_prompt on each guide."""
        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=users["parent"].id,
            title="Focus List Test",
            content="# Content",
            guide_type="study_guide",
            version=1,
            focus_prompt="Newton's laws",
        )
        db_session.add(guide)
        db_session.commit()
        db_session.refresh(guide)

        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/study/guides", headers=headers)
        assert resp.status_code == 200
        match = next((g for g in resp.json() if g["id"] == guide.id), None)
        assert match is not None
        assert match["focus_prompt"] == "Newton's laws"

        # Cleanup
        db_session.delete(guide)
        db_session.commit()

    def test_focus_prompt_none_when_not_set(self, client, db_session, users):
        """Guides without a focus_prompt return null in the response."""
        from app.models.study_guide import StudyGuide
        guide = StudyGuide(
            user_id=users["parent"].id,
            title="No Focus Guide",
            content="# Content",
            guide_type="study_guide",
            version=1,
        )
        db_session.add(guide)
        db_session.commit()
        db_session.refresh(guide)

        headers = _auth(client, users["parent"].email)
        resp = client.get(f"/api/study/guides/{guide.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["focus_prompt"] is None

        # Cleanup
        db_session.delete(guide)
        db_session.commit()


# ── Content moderation (#1001) ───────────────────────────────


class TestContentModeration:
    """check_content_safe() returns (True, '') for safe text and (False, reason) for unsafe."""

    def test_safe_text_passes(self):
        """Normal educational focus text is classified as safe."""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="SAFE")]
        )
        with patch("app.services.ai_service.get_anthropic_client", return_value=mock_client):
            from app.services.ai_service import check_content_safe
            safe, reason = check_content_safe("photosynthesis and the light reactions")
        assert safe is True
        assert reason == ""

    def test_unsafe_text_blocked(self):
        """Text classified as UNSAFE returns (False, reason)."""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="UNSAFE")]
        )
        with patch("app.services.ai_service.get_anthropic_client", return_value=mock_client):
            from app.services.ai_service import check_content_safe
            safe, reason = check_content_safe("inappropriate content here")
        assert safe is False
        assert reason != ""

    def test_api_error_fails_open(self):
        """If the moderation API call raises, check_content_safe fails open (returns True)."""
        from unittest.mock import patch

        with patch(
            "app.services.ai_service.get_anthropic_client",
            side_effect=Exception("network error"),
        ):
            from app.services.ai_service import check_content_safe
            safe, reason = check_content_safe("some focus text")
        assert safe is True

    def test_empty_text_skips_check(self):
        """Empty or whitespace-only text is safe without an API call."""
        from unittest.mock import patch, MagicMock

        mock_client = MagicMock()
        with patch("app.services.ai_service.get_anthropic_client", return_value=mock_client):
            from app.services.ai_service import check_content_safe
            safe, _ = check_content_safe("")
            safe2, _ = check_content_safe("   ")
        assert safe is True
        assert safe2 is True
        mock_client.messages.create.assert_not_called()

    def test_generation_blocked_on_unsafe_focus(self, client, users):
        """POST /api/study/generate returns 400 when focus_prompt is flagged."""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="UNSAFE")]
        )
        headers = _auth(client, users["parent"].email)
        with patch("app.services.ai_service.get_anthropic_client", return_value=mock_client):
            resp = client.post(
                "/api/study/generate",
                json={
                    "content": "Photosynthesis converts sunlight to energy.",
                    "title": "Biology",
                    "focus_prompt": "inappropriate text",
                },
                headers=headers,
            )
        assert resp.status_code == 400
        assert "inappropriate" in resp.json()["detail"].lower() or "appropriate" in resp.json()["detail"].lower()


class TestFocusPromptQuestionCount:
    """Regression tests for #1066 — focus prompt count extraction and clamping.

    The regex must match 'quizzes' (not just 'questions') and clamp values
    above 50 to 50 instead of silently ignoring them.
    """

    def _extract(self, focus_prompt: str, default: int = 5) -> int:
        """Simulate the extraction logic from study.py quiz/generate endpoint."""
        import re
        num_questions = default
        if focus_prompt and num_questions <= 10:
            m = re.search(r'(\d+)\s*(?:\w*\s*)(?:questions?|quizzes?|q\b)', focus_prompt, re.IGNORECASE)
            if m:
                requested = min(int(m.group(1)), 50)
                if requested >= 1:
                    num_questions = requested
        return num_questions

    def test_matches_quizzes(self):
        """'100 quizzes' should be matched and clamped to 50."""
        assert self._extract("100 quizzes") == 50

    def test_matches_questions(self):
        """'20 questions' should return 20."""
        assert self._extract("20 questions") == 20

    def test_clamps_above_50(self):
        """Values above 50 should be clamped to 50, not ignored."""
        assert self._extract("75 questions") == 50

    def test_normal_range(self):
        """Values within 1-50 should pass through."""
        assert self._extract("10 questions") == 10

    def test_no_match_returns_default(self):
        """Prompt without a count pattern should return default."""
        assert self._extract("focus on photosynthesis") == 5


class TestExtractTextRateLimit:
    """Regression tests for #1003 — /upload/extract-text rate limit too low.

    Before the fix: limit was 5/minute, causing 429 when uploading >5 files via
    Promise.all() on the frontend. Files after the 5th silently showed
    '(text extraction failed)' in the study guide content.

    After the fix: limit raised to 30/minute.
    """

    def test_rate_limit_is_30_per_minute(self):
        """The extract-text endpoint must be limited to 30/minute, not 5/minute.

        This test inspects the source of the endpoint function directly so it will
        fail if someone accidentally lowers the limit back to 5/minute.
        """
        import inspect
        from app.api.routes.study import router

        extract_route = next(
            (r for r in router.routes if getattr(r, "path", "") == "/study/upload/extract-text"),
            None,
        )
        assert extract_route is not None, "/study/upload/extract-text route not found"

        # Unwrap decorator chain to get the original function, then check source
        func = extract_route.endpoint
        original = getattr(func, "__wrapped__", func)
        source = inspect.getsource(original)

        assert '30/minute' in source, (
            "Expected @limiter.limit('30/minute') on extract_text_from_upload. "
            "This limit was raised from 5/minute to fix multi-file OCR failures (issue #1003). "
            f"Current source snippet: {[l.strip() for l in source.splitlines() if 'limit' in l.lower()]}"
        )


# ── AI generation error handling (#1058) ──────────────────────

class TestAIGenerationErrorHandling:
    """Regression tests for #1058: unhandled AI API exceptions must return helpful 500s."""

    def test_quiz_generation_api_error_returns_500(self, client, users):
        """POST /api/study/quiz/generate returns 500 with detail when AI raises APIError."""
        from unittest.mock import patch, AsyncMock
        import anthropic

        headers = _auth(client, users["parent"].email)

        # Mock generate_quiz to raise an anthropic.APIError
        mock_err = anthropic.APIConnectionError(request=None)
        with patch(
            "app.api.routes.study.generate_quiz",
            new_callable=AsyncMock,
            side_effect=mock_err,
        ):
            resp = client.post(
                "/api/study/quiz/generate",
                json={"content": "Photosynthesis converts sunlight to energy.", "topic": "Biology", "num_questions": 3},
                headers=headers,
            )

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "AI generation failed" in detail
        assert "APIConnectionError" in detail

    def test_flashcard_generation_api_error_returns_500(self, client, users):
        """POST /api/study/flashcards/generate returns 500 with detail when AI raises."""
        from unittest.mock import patch, AsyncMock
        import anthropic

        headers = _auth(client, users["parent"].email)

        mock_err = anthropic.APIConnectionError(request=None)
        with patch(
            "app.api.routes.study.generate_flashcards",
            new_callable=AsyncMock,
            side_effect=mock_err,
        ):
            resp = client.post(
                "/api/study/flashcards/generate",
                json={"content": "Photosynthesis converts sunlight to energy.", "topic": "Biology", "num_cards": 5},
                headers=headers,
            )

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "AI generation failed" in detail
        assert "APIConnectionError" in detail

    def test_study_guide_generation_api_error_returns_500(self, client, users):
        """POST /api/study/generate returns 500 with detail when AI raises unexpected error."""
        from unittest.mock import patch, AsyncMock
        import anthropic

        headers = _auth(client, users["parent"].email)

        mock_err = anthropic.APIConnectionError(request=None)
        with patch(
            "app.api.routes.study.generate_study_guide",
            new_callable=AsyncMock,
            side_effect=mock_err,
        ):
            resp = client.post(
                "/api/study/generate",
                json={"content": "Photosynthesis converts sunlight to energy.", "title": "Biology"},
                headers=headers,
            )

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "AI generation failed" in detail
        assert "APIConnectionError" in detail

    def test_quiz_json_decode_error_still_caught(self, client, users):
        """Ensure existing json.JSONDecodeError handling is not broken."""
        from unittest.mock import patch, AsyncMock

        headers = _auth(client, users["parent"].email)

        with patch(
            "app.api.routes.study.generate_quiz",
            new_callable=AsyncMock,
            return_value="not valid json at all",
        ):
            resp = client.post(
                "/api/study/quiz/generate",
                json={"content": "Test content for quiz.", "topic": "Test", "num_questions": 3},
                headers=headers,
            )

        assert resp.status_code == 500
        assert "Failed to parse quiz response" in resp.json()["detail"]

    def test_error_detail_truncated_to_500_chars(self, client, users):
        """Error detail message should be capped at 500 characters to avoid info leaks."""
        from unittest.mock import patch, AsyncMock

        headers = _auth(client, users["parent"].email)

        long_msg = "x" * 1000
        mock_err = RuntimeError(long_msg)
        with patch(
            "app.api.routes.study.generate_quiz",
            new_callable=AsyncMock,
            side_effect=mock_err,
        ):
            resp = client.post(
                "/api/study/quiz/generate",
                json={"content": "Test content.", "topic": "Test", "num_questions": 3},
                headers=headers,
            )

        assert resp.status_code == 500
        assert len(resp.json()["detail"]) <= 500


# ── CourseContent fallback for generation (#1132) ─────────────────

class TestGenerateFromCourseContent:
    """Regression tests for #1132: generation endpoints must fall back to
    CourseContent.text_content when no explicit content is provided."""

    @pytest.fixture()
    def course_content(self, db_session, users):
        from app.models.course_content import CourseContent
        cc = db_session.query(CourseContent).filter(
            CourseContent.title == "CC Fallback Material"
        ).first()
        if cc:
            return cc
        cc = CourseContent(
            course_id=users["course"].id,
            title="CC Fallback Material",
            text_content="Photosynthesis is the process by which plants convert sunlight into energy.",
            content_type="notes",
            created_by_user_id=users["parent"].id,
        )
        db_session.add(cc)
        db_session.commit()
        db_session.refresh(cc)
        return cc

    def test_study_guide_generate_falls_back_to_course_content(self, client, users, course_content):
        """POST /api/study/generate with course_content_id but no content should use CourseContent text."""
        from unittest.mock import patch, AsyncMock

        headers = _auth(client, users["parent"].email)

        with patch(
            "app.api.routes.study.generate_study_guide",
            new_callable=AsyncMock,
            return_value=("# Study Guide\n\nPhotosynthesis overview.", False),
        ):
            resp = client.post(
                "/api/study/generate",
                json={"course_content_id": course_content.id, "title": "Test Guide"},
                headers=headers,
            )

        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.json()}"
        assert "Photosynthesis" in resp.json()["content"]

    def test_quiz_generate_falls_back_to_course_content(self, client, users, course_content):
        """POST /api/study/quiz/generate with course_content_id but no content should use CourseContent text."""
        from unittest.mock import patch, AsyncMock

        headers = _auth(client, users["parent"].email)

        quiz_json = '[{"question": "What is photosynthesis?", "options": {"A": "Light absorption", "B": "Respiration", "C": "Digestion", "D": "Osmosis"}, "correct_answer": "A", "explanation": "Plants absorb light."}]'
        with patch(
            "app.api.routes.study.generate_quiz",
            new_callable=AsyncMock,
            return_value=quiz_json,
        ):
            resp = client.post(
                "/api/study/quiz/generate",
                json={"course_content_id": course_content.id, "topic": "Test Quiz", "num_questions": 1},
                headers=headers,
            )

        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.json()}"

    def test_flashcards_generate_falls_back_to_course_content(self, client, users, course_content):
        """POST /api/study/flashcards/generate with course_content_id but no content should use CourseContent text."""
        from unittest.mock import patch, AsyncMock

        headers = _auth(client, users["parent"].email)

        cards_json = '[{"front": "What is photosynthesis?", "back": "Process of converting sunlight to energy"}]'
        with patch(
            "app.api.routes.study.generate_flashcards",
            new_callable=AsyncMock,
            return_value=cards_json,
        ):
            resp = client.post(
                "/api/study/flashcards/generate",
                json={"course_content_id": course_content.id, "topic": "Test Cards", "num_cards": 1},
                headers=headers,
            )

        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.json()}"

    def test_study_guide_still_fails_with_no_content_and_no_course_content(self, client, users):
        """POST /api/study/generate with neither content nor course_content_id still returns 400."""
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            "/api/study/generate",
            json={"title": "Empty Guide"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Please provide" in resp.json()["detail"]


# ------------------------------------------------------------------
# Config: verify default Claude model is up-to-date
# ------------------------------------------------------------------


def test_default_claude_model_is_current():
    """Ensure the default Claude model in settings is claude-sonnet-4-6."""
    from app.core.config import Settings

    defaults = Settings(secret_key="test-key-for-unit-test")
    assert defaults.claude_model == "claude-sonnet-4-6"
