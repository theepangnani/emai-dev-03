import pytest

PASSWORD = "password123!"


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
    from app.models.teacher import Teacher
    from app.models.student import Student
    from app.models.course import Course, student_courses

    # Check-or-create
    parent = db_session.query(User).filter(User.email == "course_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "course_teacher@test.com").first()
        student = db_session.query(User).filter(User.email == "course_student@test.com").first()
        outsider = db_session.query(User).filter(User.email == "course_outsider@test.com").first()
        admin = db_session.query(User).filter(User.email == "course_admin@test.com").first()
        teacher_rec = db_session.query(Teacher).filter(Teacher.user_id == teacher.id).first()
        student_rec = db_session.query(Student).filter(Student.user_id == student.id).first()
        course = db_session.query(Course).filter(Course.name == "Course Test Class").first()
        return {
            "parent": parent, "teacher": teacher, "student": student,
            "outsider": outsider, "admin": admin,
            "teacher_rec": teacher_rec, "student_rec": student_rec,
            "course": course,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="course_parent@test.com", full_name="Course Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="course_teacher@test.com", full_name="Course Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    student = User(email="course_student@test.com", full_name="Course Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="course_outsider@test.com", full_name="Course Outsider", role=UserRole.PARENT, hashed_password=hashed)
    admin = User(email="course_admin@test.com", full_name="Course Admin", role=UserRole.ADMIN, hashed_password=hashed)
    db_session.add_all([parent, teacher, student, outsider, admin])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    student_rec = Student(user_id=student.id)
    db_session.add_all([teacher_rec, student_rec])
    db_session.flush()

    # Create a course owned by teacher, with student enrolled
    course = Course(name="Course Test Class", description="Test", teacher_id=teacher_rec.id,
                    created_by_user_id=teacher.id, is_private=False)
    db_session.add(course)
    db_session.flush()

    # Enroll student
    db_session.execute(student_courses.insert().values(student_id=student_rec.id, course_id=course.id))
    db_session.commit()

    for u in [parent, teacher, student, outsider, admin]:
        db_session.refresh(u)
    db_session.refresh(teacher_rec)
    db_session.refresh(student_rec)
    db_session.refresh(course)

    return {
        "parent": parent, "teacher": teacher, "student": student,
        "outsider": outsider, "admin": admin,
        "teacher_rec": teacher_rec, "student_rec": student_rec,
        "course": course,
    }


# ── Course creation ───────────────────────────────────────────

class TestCourseCreation:
    def test_teacher_creates_public_course(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/courses/", json={"name": "Physics 101"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Physics 101"
        assert data["is_private"] is False
        assert data["created_by_user_id"] == users["teacher"].id

    def test_parent_creates_private_course(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/courses/", json={"name": "Parent Math"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_private"] is True

    def test_student_creates_private_course(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/courses/", json={"name": "Student Study"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_private"] is True

    def test_create_with_all_fields(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/courses/", json={
            "name": "Full Course", "description": "All fields", "subject": "Science",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "All fields"
        assert data["subject"] == "Science"

    def test_missing_name_rejected(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/courses/", json={}, headers=headers)
        assert resp.status_code == 422

    def test_unauthenticated_rejected(self, client):
        resp = client.post("/api/courses/", json={"name": "No Auth"})
        assert resp.status_code == 401


# ── Course listing ────────────────────────────────────────────

class TestCourseList:
    def test_teacher_sees_public_courses(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/courses/", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Course Test Class" in names

    def test_student_sees_enrolled_courses(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/courses/", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Course Test Class" in names

    def test_admin_sees_all(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/courses/", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/api/courses/")
        assert resp.status_code == 401


# ── Get course ────────────────────────────────────────────────

class TestCourseGet:
    def test_get_by_id(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/courses/{users['course'].id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Course Test Class"

    def test_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/courses/999999", headers=headers)
        assert resp.status_code == 404


# ── Enrollment ────────────────────────────────────────────────

class TestCourseEnrollment:
    def _create_enroll_course(self, client, users):
        """Helper: teacher creates a fresh course for enrollment tests."""
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/courses/", json={"name": "Enroll Target"}, headers=headers)
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_student_enrolls(self, client, users):
        course_id = self._create_enroll_course(client, users)
        headers = _auth(client, users["student"].email)
        resp = client.post(f"/api/courses/{course_id}/enroll", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["course_id"] == course_id

    def test_double_enroll_rejected(self, client, users):
        """Student is already enrolled in the fixture course."""
        headers = _auth(client, users["student"].email)
        resp = client.post(f"/api/courses/{users['course'].id}/enroll", headers=headers)
        assert resp.status_code == 400
        assert "already enrolled" in resp.json()["detail"].lower()

    def test_enroll_nonexistent_course(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/courses/999999/enroll", headers=headers)
        assert resp.status_code == 404

    def test_unenroll(self, client, users):
        headers = _auth(client, users["student"].email)
        # Student is enrolled in fixture course
        resp = client.delete(f"/api/courses/{users['course'].id}/enroll", headers=headers)
        assert resp.status_code == 200

        # Re-enroll for other tests
        client.post(f"/api/courses/{users['course'].id}/enroll", headers=headers)

    def test_unenroll_when_not_enrolled(self, client, users):
        headers = _auth(client, users["student"].email)
        # Create a new course student is not enrolled in
        course_id = self._create_enroll_course(client, users)
        resp = client.delete(f"/api/courses/{course_id}/enroll", headers=headers)
        assert resp.status_code == 400
        assert "not enrolled" in resp.json()["detail"].lower()

    def test_parent_cannot_enroll(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(f"/api/courses/{users['course'].id}/enroll", headers=headers)
        assert resp.status_code == 403


# ── Teacher course routes ─────────────────────────────────────

class TestTeacherCourseRoutes:
    def test_list_teaching_courses(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/courses/teaching", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Course Test Class" in names

    def test_non_teacher_cannot_list_teaching(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/courses/teaching", headers=headers)
        assert resp.status_code == 403

    def test_list_course_students(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/courses/{users['course'].id}/students", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Created/enrolled routes ───────────────────────────────────

class TestCreatedCoursesRoute:
    def test_list_created_me(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/courses/created/me", headers=headers)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Course Test Class" in names

    def test_student_enrolled_me(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/courses/enrolled/me", headers=headers)
        assert resp.status_code == 200
        # Student is enrolled in fixture course
        assert isinstance(resp.json(), list)

    def test_non_student_cannot_use_enrolled_me(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/courses/enrolled/me", headers=headers)
        assert resp.status_code == 403
