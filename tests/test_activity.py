"""Tests for the Recent Activity API endpoint (GET /api/activity/recent)."""

import pytest
from datetime import datetime, timezone, timedelta
from conftest import PASSWORD, _login, _auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def family(db_session):
    """Create parent, child (student), a course, and an outsider parent."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses

    hashed = get_password_hash(PASSWORD)

    # Check for existing rows (session-scoped DB)
    parent = db_session.query(User).filter(User.email == "actparent@test.com").first()
    if parent:
        child_user = db_session.query(User).filter(User.email == "actchild@test.com").first()
        student = db_session.query(Student).filter(Student.user_id == child_user.id).first()
        outsider = db_session.query(User).filter(User.email == "actoutsider@test.com").first()
        teacher_user = db_session.query(User).filter(User.email == "actteacher@test.com").first()
        teacher = db_session.query(Teacher).filter(Teacher.user_id == teacher_user.id).first()
        course = db_session.query(Course).filter(Course.name == "Act Math").first()

        # second child
        child2_user = db_session.query(User).filter(User.email == "actchild2@test.com").first()
        student2 = db_session.query(Student).filter(Student.user_id == child2_user.id).first()

        return {
            "parent": parent,
            "child_user": child_user,
            "student": student,
            "child2_user": child2_user,
            "student2": student2,
            "outsider": outsider,
            "teacher_user": teacher_user,
            "teacher": teacher,
            "course": course,
        }

    parent = User(email="actparent@test.com", full_name="Act Parent", role=UserRole.PARENT, hashed_password=hashed)
    child_user = User(email="actchild@test.com", full_name="Act Child", role=UserRole.STUDENT, hashed_password=hashed)
    child2_user = User(email="actchild2@test.com", full_name="Act Child2", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="actoutsider@test.com", full_name="Act Outsider", role=UserRole.PARENT, hashed_password=hashed)
    teacher_user = User(email="actteacher@test.com", full_name="Act Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, child_user, child2_user, outsider, teacher_user])
    db_session.commit()

    student = Student(user_id=child_user.id, grade_level=7)
    student2 = Student(user_id=child2_user.id, grade_level=9)
    db_session.add_all([student, student2])
    db_session.commit()

    # Link both children to parent
    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student.id))
    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student2.id))
    db_session.commit()

    teacher = Teacher(user_id=teacher_user.id)
    db_session.add(teacher)
    db_session.commit()

    course = Course(name="Act Math", teacher_id=teacher.id, created_by_user_id=parent.id)
    db_session.add(course)
    db_session.commit()

    db_session.execute(student_courses.insert().values(student_id=student.id, course_id=course.id))
    db_session.commit()

    return {
        "parent": parent,
        "child_user": child_user,
        "student": student,
        "child2_user": child2_user,
        "student2": student2,
        "outsider": outsider,
        "teacher_user": teacher_user,
        "teacher": teacher,
        "course": course,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_activity_for_outsider(client, family):
    """Outsider parent with no linked children gets empty list."""
    headers = _auth(client, "actoutsider@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_course_created_activity(client, family):
    """Courses linked to parent's child appear as course_created."""
    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    course_items = [i for i in data if i["activity_type"] == "course_created"]
    assert len(course_items) >= 1
    assert course_items[0]["resource_type"] == "course"
    assert course_items[0]["title"] == "Act Math"
    assert course_items[0]["student_id"] == family["student"].id


def test_task_created_activity(client, db_session, family):
    """Tasks created by parent show as task_created."""
    from app.models.task import Task

    task = Task(
        title="Act Homework",
        created_by_user_id=family["parent"].id,
        assigned_to_user_id=family["child_user"].id,
    )
    db_session.add(task)
    db_session.commit()

    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    data = resp.json()
    task_items = [i for i in data if i["activity_type"] == "task_created" and i["title"] == "Act Homework"]
    assert len(task_items) >= 1
    assert task_items[0]["resource_type"] == "task"


def test_material_uploaded_activity(client, db_session, family):
    """Course materials linked to child's course appear."""
    from app.models.course_content import CourseContent

    cc = CourseContent(
        title="Act Notes Ch1",
        course_id=family["course"].id,
        content_type="notes",
        created_by_user_id=family["teacher_user"].id,
    )
    db_session.add(cc)
    db_session.commit()

    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    data = resp.json()
    mat_items = [i for i in data if i["activity_type"] == "material_uploaded" and i["title"] == "Act Notes Ch1"]
    assert len(mat_items) >= 1
    assert mat_items[0]["resource_type"] == "course_content"


def test_task_completed_activity(client, db_session, family):
    """Completed tasks show as task_completed with completed_at timestamp."""
    from app.models.task import Task

    now = datetime.now(timezone.utc)
    task = Task(
        title="Act Done Task",
        created_by_user_id=family["parent"].id,
        assigned_to_user_id=family["child_user"].id,
        is_completed=True,
        completed_at=now,
    )
    db_session.add(task)
    db_session.commit()

    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    data = resp.json()
    done_items = [i for i in data if i["activity_type"] == "task_completed" and i["title"] == "Act Done Task"]
    assert len(done_items) >= 1
    assert done_items[0]["resource_type"] == "task"


def test_filter_by_student_id(client, db_session, family):
    """Filtering by student_id returns only that child's activities."""
    headers = _auth(client, "actparent@test.com")

    # student2 has no courses/tasks, so filtering to student2 should exclude course items
    resp = client.get(f"/api/activity/recent?student_id={family['student2'].id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # No course_created for student2 (they aren't enrolled)
    course_items = [i for i in data if i["activity_type"] == "course_created"]
    assert len(course_items) == 0


def test_task_filter_excludes_other_childs_tasks(client, db_session, family):
    """Tasks for child1 must NOT appear when filtering by child2 (#2914)."""
    from app.models.task import Task

    task = Task(
        title="Child1 Only Task",
        created_by_user_id=family["parent"].id,
        assigned_to_user_id=family["child_user"].id,
        student_id=family["student"].id,
    )
    db_session.add(task)
    db_session.commit()

    headers = _auth(client, "actparent@test.com")

    # Filtering to student2 should NOT show child1's task
    resp = client.get(f"/api/activity/recent?student_id={family['student2'].id}", headers=headers)
    data = resp.json()
    task_items = [i for i in data if i["title"] == "Child1 Only Task"]
    assert len(task_items) == 0

    # Filtering to student1 SHOULD show it
    resp = client.get(f"/api/activity/recent?student_id={family['student'].id}", headers=headers)
    data = resp.json()
    task_items = [i for i in data if i["title"] == "Child1 Only Task"]
    assert len(task_items) >= 1


def test_limit_parameter(client, db_session, family):
    """The limit parameter caps the number of results."""
    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent?limit=2", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 2


def test_sorted_by_created_at_desc(client, family):
    """Items are returned in descending created_at order."""
    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent?limit=50", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    if len(data) >= 2:
        timestamps = [i["created_at"] for i in data]
        assert timestamps == sorted(timestamps, reverse=True)


def test_only_own_children(client, family):
    """Outsider parent cannot see activities of another parent's children."""
    headers = _auth(client, "actoutsider@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # Outsider has no linked children, so nothing should appear
    assert data == []


def test_non_parent_forbidden(client, family):
    """A student user gets 403 when calling the parent endpoint."""
    headers = _auth(client, "actchild@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    assert resp.status_code == 403


def test_study_guide_uses_course_content_id(client, db_session, family):
    """Study guide activity resource_id must be the CourseContent ID, not StudyGuide ID (#1550)."""
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide

    # #4573 — force ID divergence. course_content and study_guide are
    # separate tables with independent auto-increment sequences, both starting
    # at 1 in a fresh DB. If pytest's collection order means the first row
    # inserted into each table happens during this test, both rows get id=1
    # and the precondition assertion below fails before the real contract is
    # validated. Inserting a filler CourseContent advances its sequence past
    # whatever the StudyGuide is going to land on.
    filler = CourseContent(
        title="filler — #4573 ID-divergence guard",
        course_id=family["course"].id,
        content_type="notes",
        created_by_user_id=family["parent"].id,
    )
    db_session.add(filler)
    db_session.commit()

    cc = CourseContent(
        title="Act Guide Content",
        course_id=family["course"].id,
        content_type="notes",
        created_by_user_id=family["parent"].id,
    )
    db_session.add(cc)
    db_session.commit()

    guide = StudyGuide(
        user_id=family["parent"].id,
        course_content_id=cc.id,
        course_id=family["course"].id,
        title="Act Guide Content",
        content="guide content",
        guide_type="study_guide",
    )
    db_session.add(guide)
    db_session.commit()

    # resource_id must equal the CourseContent ID, not the StudyGuide ID
    assert guide.id != cc.id, "IDs must differ to validate the fix"

    headers = _auth(client, "actparent@test.com")
    resp = client.get("/api/activity/recent", headers=headers)
    data = resp.json()
    guide_items = [i for i in data if i["activity_type"] == "study_guide_generated" and i["title"] == "Act Guide Content"]
    assert len(guide_items) >= 1
    assert guide_items[0]["resource_id"] == cc.id


def test_study_guide_filtered_by_child(client, db_session, family):
    """Study guide activities must respect the student_id filter (#1550)."""
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide

    cc = CourseContent(
        title="Act Filtered Guide",
        course_id=family["course"].id,
        content_type="notes",
        created_by_user_id=family["parent"].id,
    )
    db_session.add(cc)
    db_session.commit()

    guide = StudyGuide(
        user_id=family["parent"].id,
        course_content_id=cc.id,
        course_id=family["course"].id,
        title="Act Filtered Guide",
        content="guide content",
        guide_type="quiz",
    )
    db_session.add(guide)
    db_session.commit()

    headers = _auth(client, "actparent@test.com")

    # Guide is linked to course enrolled by student (child 1), not student2
    # Filtering to student2 should NOT show this guide
    resp = client.get(f"/api/activity/recent?student_id={family['student2'].id}", headers=headers)
    data = resp.json()
    guide_items = [i for i in data if i["activity_type"] == "study_guide_generated" and i["title"] == "Act Filtered Guide"]
    assert len(guide_items) == 0

    # Filtering to student (child 1) SHOULD show this guide
    resp = client.get(f"/api/activity/recent?student_id={family['student'].id}", headers=headers)
    data = resp.json()
    guide_items = [i for i in data if i["activity_type"] == "study_guide_generated" and i["title"] == "Act Filtered Guide"]
    assert len(guide_items) >= 1
