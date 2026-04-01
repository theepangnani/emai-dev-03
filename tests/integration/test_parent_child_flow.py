"""Integration test: parent-child linking and course visibility.

Create parent + student -> link them -> enroll student in course ->
verify parent sees child's courses via the parent API.
"""

import secrets

import pytest
from conftest import PASSWORD, _auth
from sqlalchemy import insert


def _hex():
    return secrets.token_hex(4)


@pytest.fixture()
def family(db_session):
    """Create a parent, student, teacher, course, and link/enroll them."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.course import Course, student_courses

    tag = _hex()
    hashed = get_password_hash(PASSWORD)

    parent = User(
        email=f"fam_parent_{tag}@test.com", full_name="Family Parent",
        role=UserRole.PARENT, hashed_password=hashed,
    )
    student_user = User(
        email=f"fam_student_{tag}@test.com", full_name="Family Student",
        role=UserRole.STUDENT, hashed_password=hashed,
    )
    teacher_user = User(
        email=f"fam_teacher_{tag}@test.com", full_name="Family Teacher",
        role=UserRole.TEACHER, hashed_password=hashed,
    )
    outsider_parent = User(
        email=f"fam_outsider_{tag}@test.com", full_name="Outsider Parent",
        role=UserRole.PARENT, hashed_password=hashed,
    )
    db_session.add_all([parent, student_user, teacher_user, outsider_parent])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher_user.id)
    student_rec = Student(user_id=student_user.id)
    db_session.add_all([teacher_rec, student_rec])
    db_session.flush()

    # Link parent -> student
    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    # Create course and enroll student
    course = Course(
        name=f"Family Course {tag}", teacher_id=teacher_rec.id,
        created_by_user_id=teacher_user.id, is_private=False,
    )
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(
        student_id=student_rec.id, course_id=course.id,
    ))
    db_session.commit()

    for obj in [parent, student_user, teacher_user, outsider_parent,
                teacher_rec, student_rec, course]:
        db_session.refresh(obj)

    return {
        "parent": parent,
        "student_user": student_user,
        "student_rec": student_rec,
        "teacher": teacher_user,
        "outsider": outsider_parent,
        "course": course,
        "tag": tag,
    }


class TestParentChildFlow:
    """Parent links to child and sees child's courses and data."""

    def test_parent_sees_linked_child(self, client, family):
        headers = _auth(client, family["parent"].email)
        resp = client.get("/api/parent/children", headers=headers)
        assert resp.status_code == 200
        children = resp.json()
        child_names = [c["full_name"] for c in children]
        assert "Family Student" in child_names

    def test_parent_sees_child_courses(self, client, family):
        """Parent can view the courses their linked child is enrolled in."""
        headers = _auth(client, family["parent"].email)
        student_id = family["student_rec"].id
        resp = client.get(f"/api/parent/children/{student_id}/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        course_names = [c["name"] for c in data.get("courses", [])]
        assert family["course"].name in course_names

    def test_outsider_parent_cannot_see_child(self, client, family):
        """A parent not linked to the student should not see them."""
        headers = _auth(client, family["outsider"].email)
        resp = client.get("/api/parent/children", headers=headers)
        assert resp.status_code == 200
        children = resp.json()
        child_names = [c["full_name"] for c in children]
        assert "Family Student" not in child_names

    def test_outsider_parent_cannot_access_child_overview(self, client, family):
        """A parent not linked to the student should get 404 on overview."""
        headers = _auth(client, family["outsider"].email)
        student_id = family["student_rec"].id
        resp = client.get(f"/api/parent/children/{student_id}/overview", headers=headers)
        assert resp.status_code == 404

    def test_student_role_cannot_access_parent_api(self, client, family):
        """Students should be rejected from parent-only endpoints."""
        headers = _auth(client, family["student_user"].email)
        resp = client.get("/api/parent/children", headers=headers)
        assert resp.status_code == 403

    def test_parent_child_course_enrollment_updates_live(self, client, family, db_session):
        """When a child enrolls in a new course, parent sees it immediately."""
        from app.models.course import Course, student_courses

        # Teacher creates a second course
        teacher_headers = _auth(client, family["teacher"].email)
        create_resp = client.post("/api/courses/", json={
            "name": f"Family New Course {family['tag']}",
        }, headers=teacher_headers)
        assert create_resp.status_code == 200
        new_course_id = create_resp.json()["id"]

        # Student enrolls in the new course
        student_headers = _auth(client, family["student_user"].email)
        enroll_resp = client.post(f"/api/courses/{new_course_id}/enroll", headers=student_headers)
        assert enroll_resp.status_code == 200

        # Parent should now see both courses in child's overview
        parent_headers = _auth(client, family["parent"].email)
        overview = client.get(
            f"/api/parent/children/{family['student_rec'].id}/overview",
            headers=parent_headers,
        )
        assert overview.status_code == 200
        course_names = [c["name"] for c in overview.json().get("courses", [])]
        assert family["course"].name in course_names
        assert f"Family New Course {family['tag']}" in course_names
