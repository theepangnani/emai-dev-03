import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def ct_users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher, TeacherType
    from app.models.student import Student

    hashed = get_password_hash(PASSWORD)
    parent = db_session.query(User).filter(User.email == 'ct_parent@test.com').first()
    if parent:
        teacher = db_session.query(User).filter(User.email == 'ct_teacher@test.com').first()
        student = db_session.query(User).filter(User.email == 'ct_student@test.com').first()
        admin = db_session.query(User).filter(User.email == 'ct_admin@test.com').first()
        teacher_rec = db_session.query(Teacher).filter(Teacher.user_id == teacher.id).first()
        student_rec = db_session.query(Student).filter(Student.user_id == student.id).first()
        return dict(parent=parent, teacher=teacher, student=student, admin=admin,
                    teacher_rec=teacher_rec, student_rec=student_rec)

    parent = User(email='ct_parent@test.com', full_name='CT Parent',
                  role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email='ct_teacher@test.com', full_name='CT Teacher',
                   role=UserRole.TEACHER, hashed_password=hashed)
    student = User(email='ct_student@test.com', full_name='CT Student',
                   role=UserRole.STUDENT, hashed_password=hashed)
    admin = User(email='ct_admin@test.com', full_name='CT Admin',
                 role=UserRole.ADMIN, hashed_password=hashed)
    db_session.add_all([parent, teacher, student, admin])
    db_session.flush()
    teacher_rec = Teacher(user_id=teacher.id, teacher_type=TeacherType.SCHOOL_TEACHER)
    student_rec = Student(user_id=student.id)
    db_session.add_all([teacher_rec, student_rec])
    db_session.commit()
    for u in [parent, teacher, student, admin]:
        db_session.refresh(u)
    db_session.refresh(teacher_rec)
    db_session.refresh(student_rec)
    return dict(parent=parent, teacher=teacher, student=student, admin=admin,
                teacher_rec=teacher_rec, student_rec=student_rec)


class TestClassroomTypeDefaults:
    def test_new_course_defaults_to_manual(self, client, ct_users):
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.post('/api/courses/', json={'name': 'CT Default Test'}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()['classroom_type'] == 'manual'

    def test_parent_created_course_is_manual(self, client, ct_users):
        headers = _auth(client, ct_users['parent'].email)
        resp = client.post('/api/courses/', json={'name': 'CT Parent Manual'}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()['classroom_type'] == 'manual'


class TestClassroomTypeInResponse:
    def test_get_course_includes_classroom_type(self, client, ct_users):
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.post('/api/courses/', json={'name': 'CT Response Test'}, headers=headers)
        course_id = resp.json()['id']
        resp = client.get(f'/api/courses/{course_id}', headers=headers)
        assert resp.status_code == 200
        assert 'classroom_type' in resp.json()

    def test_list_courses_includes_classroom_type(self, client, ct_users):
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.get('/api/courses/', headers=headers)
        assert resp.status_code == 200
        for course in resp.json():
            assert 'classroom_type' in course


class TestClassroomTypeFilter:
    def test_filter_by_manual(self, client, ct_users):
        headers = _auth(client, ct_users['teacher'].email)
        client.post('/api/courses/', json={'name': 'CT Filter Manual'}, headers=headers)
        resp = client.get('/api/courses/?classroom_type=manual', headers=headers)
        assert resp.status_code == 200
        for course in resp.json():
            assert course['classroom_type'] == 'manual'

    def test_filter_by_school(self, client, ct_users, db_session):
        from app.models.course import Course
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.post('/api/courses/', json={'name': 'CT Filter School'}, headers=headers)
        course_id = resp.json()['id']
        course = db_session.query(Course).filter(Course.id == course_id).first()
        course.classroom_type = 'school'
        db_session.commit()
        resp = client.get('/api/courses/?classroom_type=school', headers=headers)
        assert resp.status_code == 200
        names = [c['name'] for c in resp.json()]
        assert 'CT Filter School' in names
        for course in resp.json():
            assert course['classroom_type'] == 'school'

    def test_filter_by_private(self, client, ct_users, db_session):
        from app.models.course import Course
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.post('/api/courses/', json={'name': 'CT Filter Private'}, headers=headers)
        course_id = resp.json()['id']
        course = db_session.query(Course).filter(Course.id == course_id).first()
        course.classroom_type = 'private'
        db_session.commit()
        resp = client.get('/api/courses/?classroom_type=private', headers=headers)
        assert resp.status_code == 200
        names = [c['name'] for c in resp.json()]
        assert 'CT Filter Private' in names

    def test_filter_invalid_type_returns_400(self, client, ct_users):
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.get('/api/courses/?classroom_type=invalid', headers=headers)
        assert resp.status_code == 400

    def test_no_filter_returns_all(self, client, ct_users):
        headers = _auth(client, ct_users['teacher'].email)
        resp = client.get('/api/courses/', headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestDomainDetection:
    def test_gmail_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('teacher@gmail.com') == 'private'

    def test_yahoo_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('teacher@yahoo.com') == 'private'

    def test_outlook_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('teacher@outlook.com') == 'private'

    def test_hotmail_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('teacher@hotmail.com') == 'private'

    def test_school_domain_is_school(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('teacher@springfield.edu') == 'school'

    def test_k12_domain_is_school(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('admin@district.k12.ca.us') == 'school'

    def test_org_domain_is_school(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('teacher@myschool.org') == 'school'

    def test_none_email_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain(None) == 'private'

    def test_empty_email_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('') == 'private'

    def test_no_at_sign_is_private(self):
        from app.api.routes.google_classroom import _detect_classroom_type_from_domain
        assert _detect_classroom_type_from_domain('nodomain') == 'private'


class TestIsSchoolCourseProperty:
    def test_school_course_property(self, db_session):
        from app.models.course import Course
        course = Course(name='School Test', classroom_type='school')
        assert course.is_school_course is True

    def test_private_course_property(self, db_session):
        from app.models.course import Course
        course = Course(name='Private Test', classroom_type='private')
        assert course.is_school_course is False

    def test_manual_course_property(self, db_session):
        from app.models.course import Course
        course = Course(name='Manual Test', classroom_type='manual')
        assert course.is_school_course is False
