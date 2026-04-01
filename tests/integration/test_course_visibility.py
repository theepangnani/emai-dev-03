"""Integration test: course visibility by role.

Create users with different roles -> create courses -> verify each role
sees exactly the courses they should.
"""

import secrets

import pytest
from conftest import PASSWORD, _auth


def _hex():
    return secrets.token_hex(4)


@pytest.fixture()
def visibility_users(db_session):
    """Create a self-contained set of users, courses, and enrollments."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.student import Student
    from app.models.course import Course, student_courses

    tag = _hex()
    hashed = get_password_hash(PASSWORD)

    teacher_user = User(
        email=f"vis_teacher_{tag}@test.com", full_name="Vis Teacher",
        role=UserRole.TEACHER, hashed_password=hashed,
    )
    student_user = User(
        email=f"vis_student_{tag}@test.com", full_name="Vis Student",
        role=UserRole.STUDENT, hashed_password=hashed,
    )
    other_student_user = User(
        email=f"vis_other_student_{tag}@test.com", full_name="Vis Other Student",
        role=UserRole.STUDENT, hashed_password=hashed,
    )
    parent_user = User(
        email=f"vis_parent_{tag}@test.com", full_name="Vis Parent",
        role=UserRole.PARENT, hashed_password=hashed,
    )
    admin_user = User(
        email=f"vis_admin_{tag}@test.com", full_name="Vis Admin",
        role=UserRole.ADMIN, hashed_password=hashed,
    )
    db_session.add_all([teacher_user, student_user, other_student_user, parent_user, admin_user])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher_user.id)
    student_rec = Student(user_id=student_user.id)
    other_student_rec = Student(user_id=other_student_user.id)
    db_session.add_all([teacher_rec, student_rec, other_student_rec])
    db_session.flush()

    # Public course owned by teacher — student enrolled
    public_course = Course(
        name=f"Vis Public {tag}", teacher_id=teacher_rec.id,
        created_by_user_id=teacher_user.id, is_private=False,
    )
    # Private course created by parent — only creator sees it
    private_course = Course(
        name=f"Vis Private {tag}", created_by_user_id=parent_user.id,
        is_private=True,
    )
    db_session.add_all([public_course, private_course])
    db_session.flush()

    # Enroll student in public course
    db_session.execute(
        student_courses.insert().values(student_id=student_rec.id, course_id=public_course.id)
    )
    db_session.commit()

    for obj in [teacher_user, student_user, other_student_user, parent_user, admin_user,
                teacher_rec, student_rec, other_student_rec, public_course, private_course]:
        db_session.refresh(obj)

    return {
        "teacher": teacher_user,
        "student": student_user,
        "other_student": other_student_user,
        "parent": parent_user,
        "admin": admin_user,
        "teacher_rec": teacher_rec,
        "student_rec": student_rec,
        "public_course": public_course,
        "private_course": private_course,
        "tag": tag,
    }


class TestCourseVisibilityByRole:
    """Each role should see only the courses appropriate to their access level."""

    def test_teacher_sees_own_public_courses(self, client, visibility_users):
        headers = _auth(client, visibility_users["teacher"].email)
        resp = client.get("/api/courses/teaching", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert visibility_users["public_course"].name in names

    def test_student_sees_enrolled_course(self, client, visibility_users):
        headers = _auth(client, visibility_users["student"].email)
        resp = client.get("/api/courses/enrolled/me", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert visibility_users["public_course"].name in names

    def test_other_student_does_not_see_unenrolled_course(self, client, visibility_users):
        """A student who is NOT enrolled should not see the course in enrolled/me."""
        headers = _auth(client, visibility_users["other_student"].email)
        resp = client.get("/api/courses/enrolled/me", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert visibility_users["public_course"].name not in names

    def test_parent_sees_own_private_course(self, client, visibility_users):
        """Parent should see their own private course in the general listing."""
        headers = _auth(client, visibility_users["parent"].email)
        resp = client.get("/api/courses/created/me", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert visibility_users["private_course"].name in names

    def test_admin_sees_all_courses(self, client, visibility_users):
        headers = _auth(client, visibility_users["admin"].email)
        resp = client.get("/api/courses/", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        # Admin should see both the public and private courses
        assert visibility_users["public_course"].name in names
        assert visibility_users["private_course"].name in names

    def test_student_enroll_then_see_course(self, client, visibility_users):
        """Student enrolls in a new course via API and immediately sees it."""
        # Teacher creates a new course
        teacher_headers = _auth(client, visibility_users["teacher"].email)
        create_resp = client.post("/api/courses/", json={
            "name": f"Vis New Enroll {visibility_users['tag']}",
        }, headers=teacher_headers)
        assert create_resp.status_code == 200
        new_course_id = create_resp.json()["id"]

        # Other student enrolls
        student_headers = _auth(client, visibility_users["other_student"].email)
        enroll_resp = client.post(f"/api/courses/{new_course_id}/enroll", headers=student_headers)
        assert enroll_resp.status_code == 200

        # Now the student should see it in enrolled/me
        enrolled = client.get("/api/courses/enrolled/me", headers=student_headers)
        assert enrolled.status_code == 200
        names = [c["name"] for c in enrolled.json()]
        assert f"Vis New Enroll {visibility_users['tag']}" in names
