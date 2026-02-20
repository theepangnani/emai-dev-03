"""Tests for Stream C: Google Classroom + Teacher Features (#550, #551, #552)."""
import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def gc_users(db_session):
    """Create users, teacher records, student records, and courses for GC tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher, TeacherType
    from app.models.student import Student, parent_students
    from app.models.course import Course, student_courses
    from sqlalchemy import insert

    # Check if already created (session-scoped db)
    existing = db_session.query(User).filter(User.email == "gc_school_teacher@test.com").first()
    if existing:
        school_teacher_user = existing
        private_teacher_user = db_session.query(User).filter(User.email == "gc_private_teacher@test.com").first()
        student_user = db_session.query(User).filter(User.email == "gc_student@test.com").first()
        parent_user = db_session.query(User).filter(User.email == "gc_parent@test.com").first()

        school_teacher = db_session.query(Teacher).filter(Teacher.user_id == school_teacher_user.id).first()
        private_teacher = db_session.query(Teacher).filter(Teacher.user_id == private_teacher_user.id).first()
        student = db_session.query(Student).filter(Student.user_id == student_user.id).first()

        school_course = db_session.query(Course).filter(Course.name == "GC School Course").first()
        private_course = db_session.query(Course).filter(Course.name == "GC Private Course").first()

        return {
            "school_teacher_user": school_teacher_user,
            "private_teacher_user": private_teacher_user,
            "student_user": student_user,
            "parent_user": parent_user,
            "school_teacher": school_teacher,
            "private_teacher": private_teacher,
            "student": student,
            "school_course": school_course,
            "private_course": private_course,
        }

    hashed = get_password_hash(PASSWORD)

    school_teacher_user = User(email="gc_school_teacher@test.com", full_name="School Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    private_teacher_user = User(email="gc_private_teacher@test.com", full_name="Private Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    student_user = User(email="gc_student@test.com", full_name="GC Student", role=UserRole.STUDENT, hashed_password=hashed)
    parent_user = User(email="gc_parent@test.com", full_name="GC Parent", role=UserRole.PARENT, hashed_password=hashed)

    db_session.add_all([school_teacher_user, private_teacher_user, student_user, parent_user])
    db_session.flush()

    school_teacher = Teacher(user_id=school_teacher_user.id, teacher_type=TeacherType.SCHOOL_TEACHER, is_shadow=False, is_platform_user=True)
    private_teacher = Teacher(user_id=private_teacher_user.id, teacher_type=TeacherType.PRIVATE_TUTOR, is_shadow=False, is_platform_user=True)
    db_session.add_all([school_teacher, private_teacher])
    db_session.flush()

    student = Student(user_id=student_user.id, grade_level=5)
    db_session.add(student)
    db_session.flush()

    # Link parent to student
    db_session.execute(insert(parent_students).values(parent_id=parent_user.id, student_id=student.id))

    # Create courses
    school_course = Course(
        name="GC School Course",
        teacher_id=school_teacher.id,
        classroom_type="school",
        google_classroom_id="gc_school_123",
        created_by_user_id=school_teacher_user.id,
    )
    private_course = Course(
        name="GC Private Course",
        teacher_id=private_teacher.id,
        classroom_type="private",
        google_classroom_id="gc_private_456",
        created_by_user_id=private_teacher_user.id,
    )
    db_session.add_all([school_course, private_course])
    db_session.flush()

    # Enroll student in both courses
    db_session.execute(insert(student_courses).values(student_id=student.id, course_id=school_course.id))
    db_session.execute(insert(student_courses).values(student_id=student.id, course_id=private_course.id))

    db_session.commit()

    for obj in [school_teacher_user, private_teacher_user, student_user, parent_user,
                school_teacher, private_teacher, student, school_course, private_course]:
        db_session.refresh(obj)

    return {
        "school_teacher_user": school_teacher_user,
        "private_teacher_user": private_teacher_user,
        "student_user": student_user,
        "parent_user": parent_user,
        "school_teacher": school_teacher,
        "private_teacher": private_teacher,
        "student": student,
        "school_course": school_course,
        "private_course": private_course,
    }


# ── #550: Google Classroom School vs Private Type ─────────────────


class TestClassroomTypeSync:
    def test_set_classroom_type_school_teacher(self, db_session, gc_users):
        """School teacher's course should get classroom_type='school'."""
        from app.api.routes.google_classroom import _set_classroom_type
        from app.models.course import Course

        course = Course(name="Test School", teacher_id=gc_users["school_teacher"].id)
        db_session.add(course)
        db_session.flush()

        _set_classroom_type(course, db_session)
        assert course.classroom_type == "school"

        db_session.rollback()

    def test_set_classroom_type_private_tutor(self, db_session, gc_users):
        """Private tutor's course should get classroom_type='private'."""
        from app.api.routes.google_classroom import _set_classroom_type
        from app.models.course import Course

        course = Course(name="Test Private", teacher_id=gc_users["private_teacher"].id)
        db_session.add(course)
        db_session.flush()

        _set_classroom_type(course, db_session)
        assert course.classroom_type == "private"

        db_session.rollback()

    def test_set_classroom_type_no_teacher(self, db_session):
        """Course with no teacher should default to 'private'."""
        from app.api.routes.google_classroom import _set_classroom_type
        from app.models.course import Course

        course = Course(name="Test NoTeacher")
        db_session.add(course)
        db_session.flush()

        _set_classroom_type(course, db_session)
        assert course.classroom_type == "private"

        db_session.rollback()

    def test_does_not_override_existing(self, db_session, gc_users):
        """Should not override if classroom_type is already set."""
        from app.api.routes.google_classroom import _set_classroom_type
        from app.models.course import Course

        course = Course(name="Test Existing", teacher_id=gc_users["school_teacher"].id, classroom_type="private")
        db_session.add(course)
        db_session.flush()

        _set_classroom_type(course, db_session)
        assert course.classroom_type == "private"  # unchanged

        db_session.rollback()


class TestURLStripping:
    def _create_content(self, client, headers, course_id, title="Test Content"):
        resp = client.post("/api/course-contents/", json={
            "course_id": course_id,
            "title": title,
            "reference_url": "https://example.com/doc",
            "google_classroom_url": "https://classroom.google.com/doc",
        }, headers=headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_student_sees_no_urls_on_school_course(self, client, gc_users):
        """Student should not see reference_url or google_classroom_url on school courses."""
        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        content = self._create_content(client, teacher_headers, gc_users["school_course"].id, "School Material")

        student_headers = _auth(client, gc_users["student_user"].email)
        resp = client.get(f"/api/course-contents/{content['id']}", headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reference_url"] is None
        assert data["google_classroom_url"] is None

    def test_student_sees_urls_on_private_course(self, client, gc_users):
        """Student should see URLs on private courses."""
        teacher_headers = _auth(client, gc_users["private_teacher_user"].email)
        content = self._create_content(client, teacher_headers, gc_users["private_course"].id, "Private Material")

        student_headers = _auth(client, gc_users["student_user"].email)
        resp = client.get(f"/api/course-contents/{content['id']}", headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reference_url"] == "https://example.com/doc"
        assert data["google_classroom_url"] == "https://classroom.google.com/doc"

    def test_teacher_sees_urls_on_school_course(self, client, gc_users):
        """Teacher should always see URLs even on school courses."""
        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        content = self._create_content(client, teacher_headers, gc_users["school_course"].id, "Teacher Visible")

        resp = client.get(f"/api/course-contents/{content['id']}", headers=teacher_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reference_url"] == "https://example.com/doc"
        assert data["google_classroom_url"] == "https://classroom.google.com/doc"

    def test_parent_sees_urls_on_school_course(self, client, gc_users):
        """Parent should always see URLs even on school courses."""
        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        content = self._create_content(client, teacher_headers, gc_users["school_course"].id, "Parent Visible")

        parent_headers = _auth(client, gc_users["parent_user"].email)
        resp = client.get(f"/api/course-contents/{content['id']}", headers=parent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reference_url"] == "https://example.com/doc"
        assert data["google_classroom_url"] == "https://classroom.google.com/doc"

    def test_list_strips_urls_for_student_school_course(self, client, gc_users):
        """List endpoint should also strip URLs for students on school courses."""
        student_headers = _auth(client, gc_users["student_user"].email)
        resp = client.get(
            f"/api/course-contents/?course_id={gc_users['school_course'].id}",
            headers=student_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert item["reference_url"] is None
            assert item["google_classroom_url"] is None


# ── #551: Student/Teacher Invites + Course Enrollment ─────────────


class TestInviteTeacher:
    def test_student_invites_new_teacher(self, client, gc_users):
        """Student should be able to invite a new teacher by email."""
        student_headers = _auth(client, gc_users["student_user"].email)
        resp = client.post("/api/invites/invite-teacher", json={
            "teacher_email": "gc_new_teacher_invite@test.com",
        }, headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("email") == "gc_new_teacher_invite@test.com" or data.get("action") == "message_sent"

    def test_student_invites_existing_teacher(self, client, gc_users):
        """Student inviting existing teacher should send a message."""
        student_headers = _auth(client, gc_users["student_user"].email)
        resp = client.post("/api/invites/invite-teacher", json={
            "teacher_email": gc_users["school_teacher_user"].email,
        }, headers=student_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "message_sent"

    def test_parent_cannot_invite_teacher_via_student_endpoint(self, client, gc_users):
        """Parent should get 403 on the student-only invite-teacher endpoint."""
        parent_headers = _auth(client, gc_users["parent_user"].email)
        resp = client.post("/api/invites/invite-teacher", json={
            "teacher_email": "gc_someone@test.com",
        }, headers=parent_headers)
        assert resp.status_code == 403

    def test_duplicate_pending_invite_rejected(self, client, gc_users):
        """Duplicate pending invite should return 400."""
        student_headers = _auth(client, gc_users["student_user"].email)
        # First invite should succeed (or already exist)
        resp1 = client.post("/api/invites/invite-teacher", json={
            "teacher_email": "gc_dup_teacher@test.com",
        }, headers=student_headers)
        assert resp1.status_code == 200

        # Second invite should fail
        resp2 = client.post("/api/invites/invite-teacher", json={
            "teacher_email": "gc_dup_teacher@test.com",
        }, headers=student_headers)
        assert resp2.status_code == 400


class TestInviteStudentAlias:
    def test_invite_student_to_course(self, client, gc_users):
        """POST /api/courses/{id}/invite-student should work like add student."""
        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        resp = client.post(
            f"/api/courses/{gc_users['school_course'].id}/invite-student",
            json={"email": "gc_invited_student@test.com"},
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("invited") is True or "student_id" in data


class TestInviteParentWithStudentId:
    def test_invite_parent_with_student_context(self, client, gc_users, db_session):
        """invite-parent with student_id should include metadata."""
        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        resp = client.post("/api/invites/invite-parent", json={
            "parent_email": "gc_new_parent@test.com",
            "student_id": gc_users["student"].id,
        }, headers=teacher_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Check metadata on the invite
        if "metadata_json" in data and data["metadata_json"]:
            assert data["metadata_json"].get("student_id") == gc_users["student"].id


# ── #552: Custom Prompt + Parent Notification ─────────────────────


class TestCustomPrompt:
    def test_schema_accepts_custom_prompt(self):
        """StudyGuideCreate schema should accept custom_prompt."""
        from app.schemas.study import StudyGuideCreate
        body = StudyGuideCreate(content="test content", custom_prompt="Summarize this")
        assert body.custom_prompt == "Summarize this"

    def test_schema_custom_prompt_optional(self):
        """StudyGuideCreate schema should allow omitting custom_prompt."""
        from app.schemas.study import StudyGuideCreate
        body = StudyGuideCreate(content="test content")
        assert body.custom_prompt is None


class TestParentNotificationOnUpload:
    def test_student_upload_notifies_parents(self, client, gc_users, db_session):
        """When a student creates course content, parents should be notified."""
        from app.models.notification import Notification, NotificationType

        student_headers = _auth(client, gc_users["student_user"].email)

        # Count existing notifications for parent
        parent_id = gc_users["parent_user"].id
        before_count = db_session.query(Notification).filter(
            Notification.user_id == parent_id,
            Notification.type == NotificationType.MATERIAL_UPLOADED,
        ).count()

        resp = client.post("/api/course-contents/", json={
            "course_id": gc_users["private_course"].id,
            "title": "Student Upload Test",
            "content_type": "notes",
        }, headers=student_headers)
        assert resp.status_code == 201

        db_session.expire_all()
        after_count = db_session.query(Notification).filter(
            Notification.user_id == parent_id,
            Notification.type == NotificationType.MATERIAL_UPLOADED,
        ).count()
        assert after_count > before_count

    def test_teacher_upload_does_not_notify_parents(self, client, gc_users, db_session):
        """When a teacher creates course content, parents should NOT be notified."""
        from app.models.notification import Notification, NotificationType

        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        parent_id = gc_users["parent_user"].id

        before_count = db_session.query(Notification).filter(
            Notification.user_id == parent_id,
            Notification.type == NotificationType.MATERIAL_UPLOADED,
        ).count()

        resp = client.post("/api/course-contents/", json={
            "course_id": gc_users["school_course"].id,
            "title": "Teacher Upload Test",
            "content_type": "notes",
        }, headers=teacher_headers)
        assert resp.status_code == 201

        db_session.expire_all()
        after_count = db_session.query(Notification).filter(
            Notification.user_id == parent_id,
            Notification.type == NotificationType.MATERIAL_UPLOADED,
        ).count()
        assert after_count == before_count


class TestCourseResponseIncludesClassroomType:
    def test_course_detail_includes_classroom_type(self, client, gc_users):
        """GET /api/courses/{id} should include classroom_type in response."""
        teacher_headers = _auth(client, gc_users["school_teacher_user"].email)
        resp = client.get(f"/api/courses/{gc_users['school_course'].id}", headers=teacher_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("classroom_type") == "school"
