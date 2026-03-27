"""Tests for can_access_material() trust-circle access control (#2269)."""

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def trust_circle_data(db_session):
    """Create users with all trust-circle roles and a course with content."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from app.models.student import Student, parent_students
    from app.models.course_content import CourseContent

    hashed = get_password_hash(PASSWORD)

    # Check if already created (session-scoped db may persist)
    existing = db_session.query(User).filter(User.email == "tc_teacher@test.com").first()
    if existing:
        teacher_user = existing
        student_user = db_session.query(User).filter(User.email == "tc_student@test.com").first()
        parent_user = db_session.query(User).filter(User.email == "tc_parent@test.com").first()
        admin_user = db_session.query(User).filter(User.email == "tc_admin@test.com").first()
        outsider_user = db_session.query(User).filter(User.email == "tc_outsider@test.com").first()
        course = db_session.query(Course).filter(Course.name == "TC Trust Circle Course").first()
        content = db_session.query(CourseContent).filter(CourseContent.title == "TC Material").first()
        return {
            "teacher": teacher_user,
            "student": student_user,
            "parent": parent_user,
            "admin": admin_user,
            "outsider": outsider_user,
            "course": course,
            "content": content,
        }

    # Teacher user + Teacher record
    teacher_user = User(
        email="tc_teacher@test.com", full_name="TC Teacher",
        role=UserRole.TEACHER, hashed_password=hashed,
    )
    # Student user + Student record
    student_user = User(
        email="tc_student@test.com", full_name="TC Student",
        role=UserRole.STUDENT, hashed_password=hashed,
    )
    # Parent user
    parent_user = User(
        email="tc_parent@test.com", full_name="TC Parent",
        role=UserRole.PARENT, hashed_password=hashed,
    )
    # Admin user
    admin_user = User(
        email="tc_admin@test.com", full_name="TC Admin",
        role=UserRole.ADMIN, hashed_password=hashed,
    )
    # Outsider (unrelated teacher, not enrolled)
    outsider_user = User(
        email="tc_outsider@test.com", full_name="TC Outsider",
        role=UserRole.TEACHER, hashed_password=hashed,
    )
    db_session.add_all([teacher_user, student_user, parent_user, admin_user, outsider_user])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher_user.id)
    db_session.add(teacher_rec)
    db_session.flush()

    student_rec = Student(user_id=student_user.id)
    db_session.add(student_rec)
    db_session.flush()

    # Course owned by teacher (private — trust-circle tests need restricted access)
    course = Course(
        name="TC Trust Circle Course",
        teacher_id=teacher_rec.id,
        created_by_user_id=teacher_user.id,
        is_private=True,
    )
    db_session.add(course)
    db_session.flush()

    # Enroll student in course
    db_session.execute(
        student_courses.insert().values(student_id=student_rec.id, course_id=course.id)
    )

    # Link parent to student
    db_session.execute(
        parent_students.insert().values(parent_id=parent_user.id, student_id=student_rec.id)
    )

    # Create a course content item
    content = CourseContent(
        course_id=course.id,
        title="TC Material",
        text_content="Secret study material content",
        content_type="notes",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(content)
    db_session.commit()

    for u in [teacher_user, student_user, parent_user, admin_user, outsider_user]:
        db_session.refresh(u)
    db_session.refresh(course)
    db_session.refresh(content)

    return {
        "teacher": teacher_user,
        "student": student_user,
        "parent": parent_user,
        "admin": admin_user,
        "outsider": outsider_user,
        "course": course,
        "content": content,
    }


class TestCanAccessMaterial:
    """Unit tests for can_access_material() function."""

    def test_teacher_can_access_own_material(self, db_session, trust_circle_data):
        from app.api.deps import can_access_material
        assert can_access_material(
            db_session, trust_circle_data["teacher"], trust_circle_data["content"]
        ) is True

    def test_enrolled_student_can_access(self, db_session, trust_circle_data):
        from app.api.deps import can_access_material
        assert can_access_material(
            db_session, trust_circle_data["student"], trust_circle_data["content"]
        ) is True

    def test_parent_of_enrolled_student_can_access(self, db_session, trust_circle_data):
        from app.api.deps import can_access_material
        assert can_access_material(
            db_session, trust_circle_data["parent"], trust_circle_data["content"]
        ) is True

    def test_admin_cannot_access(self, db_session, trust_circle_data):
        from app.api.deps import can_access_material
        assert can_access_material(
            db_session, trust_circle_data["admin"], trust_circle_data["content"]
        ) is False

    def test_outsider_cannot_access(self, db_session, trust_circle_data):
        from app.api.deps import can_access_material
        assert can_access_material(
            db_session, trust_circle_data["outsider"], trust_circle_data["content"]
        ) is False

    def test_outsider_can_access_public_course_material(self, db_session, trust_circle_data):
        """Outsider should access materials on public (non-private) courses."""
        from app.api.deps import can_access_material
        course = trust_circle_data["course"]
        course.is_private = False
        db_session.commit()
        assert can_access_material(
            db_session, trust_circle_data["outsider"], trust_circle_data["content"]
        ) is True
        course.is_private = True
        db_session.commit()

    def test_admin_still_denied_on_public_course(self, db_session, trust_circle_data):
        """Admin exclusion applies even on public courses."""
        from app.api.deps import can_access_material
        course = trust_circle_data["course"]
        course.is_private = False
        db_session.commit()
        assert can_access_material(
            db_session, trust_circle_data["admin"], trust_circle_data["content"]
        ) is False
        course.is_private = True
        db_session.commit()


class TestMaterialEndpointAccess:
    """Integration tests for trust-circle enforcement on API endpoints."""

    def test_teacher_can_view_material(self, client, trust_circle_data):
        headers = _auth(client, trust_circle_data["teacher"].email)
        resp = client.get(
            f"/api/course-contents/{trust_circle_data['content'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["text_content"] is not None

    def test_enrolled_student_can_view_material(self, client, trust_circle_data):
        headers = _auth(client, trust_circle_data["student"].email)
        resp = client.get(
            f"/api/course-contents/{trust_circle_data['content'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["text_content"] is not None

    def test_parent_can_view_material(self, client, trust_circle_data):
        headers = _auth(client, trust_circle_data["parent"].email)
        resp = client.get(
            f"/api/course-contents/{trust_circle_data['content'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["text_content"] is not None

    def test_admin_gets_403_on_view(self, client, trust_circle_data):
        headers = _auth(client, trust_circle_data["admin"].email)
        resp = client.get(
            f"/api/course-contents/{trust_circle_data['content'].id}",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_outsider_gets_403_on_view(self, client, trust_circle_data):
        headers = _auth(client, trust_circle_data["outsider"].email)
        resp = client.get(
            f"/api/course-contents/{trust_circle_data['content'].id}",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_admin_gets_403_on_download(self, client, trust_circle_data):
        headers = _auth(client, trust_circle_data["admin"].email)
        resp = client.get(
            f"/api/course-contents/{trust_circle_data['content'].id}/download",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_admin_list_strips_text_content(self, client, trust_circle_data):
        """Admin listing materials should get text_content=null."""
        headers = _auth(client, trust_circle_data["admin"].email)
        resp = client.get(
            f"/api/course-contents/?course_id={trust_circle_data['course'].id}",
            headers=headers,
        )
        # Admin can still list (via can_access_course) but text_content is stripped
        # Since admin has can_access_course but NOT can_access_material,
        # the list endpoint should strip text_content
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                assert item["text_content"] is None

    def test_teacher_list_preserves_text_content(self, client, trust_circle_data):
        """Teacher listing materials should get text_content preserved."""
        headers = _auth(client, trust_circle_data["teacher"].email)
        resp = client.get(
            f"/api/course-contents/?course_id={trust_circle_data['course'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) > 0
        # Teacher is in trust circle, text_content should be preserved
        found = [i for i in items if i["title"] == "TC Material"]
        assert len(found) == 1
        assert found[0]["text_content"] is not None
