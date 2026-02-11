"""Tests for global search endpoint (GET /api/search)."""

import pytest

PASSWORD = "password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


@pytest.fixture()
def search_data(db_session):
    """Create test data: parent, child, courses, tasks, study guides, course content."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.course import Course, student_courses
    from app.models.task import Task
    from app.models.study_guide import StudyGuide
    from app.models.course_content import CourseContent

    # Check if already created
    parent = db_session.query(User).filter(User.email == "searchparent@test.com").first()
    if parent:
        child = db_session.query(User).filter(User.email == "searchchild@test.com").first()
        outsider = db_session.query(User).filter(User.email == "searchoutsider@test.com").first()
        admin = db_session.query(User).filter(User.email == "searchadmin@test.com").first()
        return {"parent": parent, "child": child, "outsider": outsider, "admin": admin}

    hashed = get_password_hash(PASSWORD)

    parent = User(email="searchparent@test.com", full_name="Search Parent", role=UserRole.PARENT, hashed_password=hashed)
    child = User(email="searchchild@test.com", full_name="Search Child", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="searchoutsider@test.com", full_name="Search Outsider", role=UserRole.PARENT, hashed_password=hashed)
    admin = User(email="searchadmin@test.com", full_name="Search Admin", role=UserRole.ADMIN, hashed_password=hashed)
    db_session.add_all([parent, child, outsider, admin])
    db_session.commit()

    student = Student(user_id=child.id, grade_level=7)
    db_session.add(student)
    db_session.commit()

    # Link parent-child
    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student.id, relationship_type="guardian"))
    db_session.commit()

    # Course created by parent
    course = Course(name="Algebra Basics", description="Intro to algebra", created_by_user_id=parent.id)
    db_session.add(course)
    db_session.commit()

    # Enroll child
    db_session.execute(student_courses.insert().values(student_id=student.id, course_id=course.id))
    db_session.commit()

    # Course content
    cc = CourseContent(title="Algebra Chapter 1", description="Variables and equations", course_id=course.id, created_by_user_id=parent.id)
    db_session.add(cc)
    db_session.commit()

    # Study guide by parent
    sg = StudyGuide(title="Algebra Study Guide", content="Study notes for algebra", guide_type="study_guide", user_id=parent.id, course_id=course.id, course_content_id=cc.id)
    db_session.add(sg)
    db_session.commit()

    # Task by parent
    task = Task(title="Review Algebra Homework", description="Complete chapter 1 exercises", created_by_user_id=parent.id, assigned_to_user_id=child.id, priority="high")
    db_session.add(task)
    db_session.commit()

    # Outsider's private course (should not appear in parent's results)
    outsider_course = Course(name="Outsider Algebra Course", description="Not visible", created_by_user_id=outsider.id, is_private=True)
    db_session.add(outsider_course)
    db_session.commit()

    # Outsider's task
    outsider_task = Task(title="Outsider Algebra Task", description="Not visible", created_by_user_id=outsider.id, priority="low")
    db_session.add(outsider_task)
    db_session.commit()

    return {"parent": parent, "child": child, "outsider": outsider, "admin": admin}


class TestGlobalSearch:
    """Test GET /api/search endpoint."""

    def test_search_requires_auth(self, client):
        resp = client.get("/api/search", params={"q": "algebra"})
        assert resp.status_code == 401

    def test_search_too_short_query(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "a"}, headers=headers)
        assert resp.status_code == 422  # validation error: min_length=2

    def test_search_returns_grouped_results(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "algebra"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "algebra"
        assert data["total"] > 0
        assert len(data["groups"]) > 0

        # Check that we get results from multiple types
        types_found = {g["entity_type"] for g in data["groups"] if g["total"] > 0}
        assert "course" in types_found
        assert "study_guide" in types_found
        assert "task" in types_found
        assert "course_content" in types_found

    def test_search_result_structure(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "algebra"}, headers=headers)
        data = resp.json()

        for group in data["groups"]:
            assert "entity_type" in group
            assert "label" in group
            assert "items" in group
            assert "total" in group
            for item in group["items"]:
                assert "id" in item
                assert "title" in item
                assert "entity_type" in item
                assert "url" in item

    def test_search_filter_by_type(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "algebra", "types": "task"}, headers=headers)
        data = resp.json()
        # Should only have task group
        assert len(data["groups"]) == 1
        assert data["groups"][0]["entity_type"] == "task"

    def test_search_filter_multiple_types(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "algebra", "types": "course,task"}, headers=headers)
        data = resp.json()
        types_found = {g["entity_type"] for g in data["groups"]}
        assert types_found == {"course", "task"}

    def test_search_respects_access_control(self, client, search_data):
        """Parent should not see outsider's private course or tasks."""
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "outsider"}, headers=headers)
        data = resp.json()
        # Parent should not find outsider's resources
        all_titles = [item["title"] for g in data["groups"] for item in g["items"]]
        assert "Outsider Algebra Task" not in all_titles

    def test_search_outsider_sees_own_data(self, client, search_data):
        """Outsider should see their own task and course."""
        headers = _auth(client, "searchoutsider@test.com")
        resp = client.get("/api/search", params={"q": "outsider"}, headers=headers)
        data = resp.json()
        all_titles = [item["title"] for g in data["groups"] for item in g["items"]]
        assert "Outsider Algebra Task" in all_titles
        assert "Outsider Algebra Course" in all_titles

    def test_search_admin_sees_all(self, client, search_data):
        """Admin should see results from all users."""
        headers = _auth(client, "searchadmin@test.com")
        resp = client.get("/api/search", params={"q": "algebra"}, headers=headers)
        data = resp.json()
        all_titles = [item["title"] for g in data["groups"] for item in g["items"]]
        # Admin should see both parent's and outsider's data
        assert "Algebra Basics" in all_titles
        assert "Outsider Algebra Course" in all_titles

    def test_search_no_results(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "xyznonexistent"}, headers=headers)
        data = resp.json()
        assert data["total"] == 0
        # All groups should be empty
        for group in data["groups"]:
            assert group["total"] == 0

    def test_search_limit_parameter(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "algebra", "limit": 1}, headers=headers)
        data = resp.json()
        for group in data["groups"]:
            assert len(group["items"]) <= 1

    def test_search_case_insensitive(self, client, search_data):
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "ALGEBRA"}, headers=headers)
        data = resp.json()
        assert data["total"] > 0

    def test_search_urls_correct(self, client, search_data):
        """Verify that result URLs point to correct routes."""
        headers = _auth(client, "searchparent@test.com")
        resp = client.get("/api/search", params={"q": "algebra"}, headers=headers)
        data = resp.json()

        for group in data["groups"]:
            for item in group["items"]:
                if item["entity_type"] == "course":
                    assert item["url"].startswith("/courses/")
                elif item["entity_type"] == "study_guide":
                    assert item["url"].startswith("/study/")
                elif item["entity_type"] == "task":
                    assert item["url"].startswith("/tasks/")
                elif item["entity_type"] == "course_content":
                    assert item["url"].startswith("/study-guides/")
