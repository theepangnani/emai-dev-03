import pytest
from unittest.mock import patch, AsyncMock

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


@pytest.fixture()
def analytics_data(db_session):
    """Create parent, student, courses, assignments, GradeRecords + StudentAssignments."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment, StudentAssignment
    from app.models.analytics import GradeRecord
    from sqlalchemy import insert
    from datetime import datetime, timedelta

    # Check if already created (fixture reuse across test module)
    parent = db_session.query(User).filter(User.email == "ana_parent@test.com").first()
    if parent:
        student_user = db_session.query(User).filter(User.email == "ana_student@test.com").first()
        outsider = db_session.query(User).filter(User.email == "ana_outsider@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        courses = db_session.query(Course).filter(Course.name.like("Analytics%")).all()
        return {
            "parent": parent, "student_user": student_user, "outsider": outsider,
            "student_rec": student_rec, "courses": courses,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="ana_parent@test.com", full_name="Analytics Parent", role=UserRole.PARENT, hashed_password=hashed)
    student_user = User(email="ana_student@test.com", full_name="Analytics Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="ana_outsider@test.com", full_name="Analytics Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, student_user, outsider])
    db_session.flush()

    student_rec = Student(user_id=student_user.id)
    db_session.add(student_rec)
    db_session.flush()

    # Link parent → student
    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    # Create two courses with assignments
    course1 = Course(name="Analytics Math", created_by_user_id=parent.id)
    course2 = Course(name="Analytics Science", created_by_user_id=parent.id)
    db_session.add_all([course1, course2])
    db_session.flush()

    # Enroll student
    db_session.execute(student_courses.insert().values(student_id=student_rec.id, course_id=course1.id))
    db_session.execute(student_courses.insert().values(student_id=student_rec.id, course_id=course2.id))

    now = datetime.utcnow()

    # Create assignments
    assignments = []
    for i in range(5):
        a = Assignment(
            title=f"Math HW {i+1}", course_id=course1.id,
            max_points=100.0, due_date=now - timedelta(days=30 - i * 6),
        )
        assignments.append(a)
    for i in range(3):
        a = Assignment(
            title=f"Sci Lab {i+1}", course_id=course2.id,
            max_points=50.0, due_date=now - timedelta(days=20 - i * 7),
        )
        assignments.append(a)

    db_session.add_all(assignments)
    db_session.flush()

    # Grade math assignments (improving trend: 70, 75, 80, 85, 90)
    math_grades = [70, 75, 80, 85, 90]
    for i, a in enumerate(assignments[:5]):
        recorded_at = now - timedelta(days=30 - i * 6)
        sa = StudentAssignment(
            student_id=student_rec.id, assignment_id=a.id,
            grade=math_grades[i], status="graded",
            submitted_at=recorded_at,
        )
        db_session.add(sa)
        # GradeRecord (analytics source of truth)
        gr = GradeRecord(
            student_id=student_rec.id, course_id=course1.id,
            assignment_id=a.id, grade=math_grades[i], max_grade=100.0,
            percentage=math_grades[i],  # max=100, so pct == grade
            source="seed", recorded_at=recorded_at,
        )
        db_session.add(gr)

    # Science: 40, 35, 45 (out of 50)
    sci_grades = [40, 35, 45]
    for i, a in enumerate(assignments[5:]):
        recorded_at = now - timedelta(days=20 - i * 7)
        sa = StudentAssignment(
            student_id=student_rec.id, assignment_id=a.id,
            grade=sci_grades[i], status="graded",
            submitted_at=recorded_at,
        )
        db_session.add(sa)
        gr = GradeRecord(
            student_id=student_rec.id, course_id=course2.id,
            assignment_id=a.id, grade=sci_grades[i], max_grade=50.0,
            percentage=round((sci_grades[i] / 50.0) * 100, 2),
            source="seed", recorded_at=recorded_at,
        )
        db_session.add(gr)

    db_session.commit()

    for obj in [parent, student_user, outsider, student_rec, course1, course2]:
        db_session.refresh(obj)

    return {
        "parent": parent, "student_user": student_user, "outsider": outsider,
        "student_rec": student_rec, "courses": [course1, course2],
    }


# ── Grades list ─────────────────────────────────────────────────

def test_grades_list_as_parent(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/grades?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8
    assert len(data["grades"]) == 8
    # Check grade item structure
    g = data["grades"][0]
    assert "student_assignment_id" in g
    assert "percentage" in g
    assert "course_name" in g


def test_grades_list_as_student(client, analytics_data):
    headers = _auth(client, "ana_student@test.com")
    resp = client.get("/api/analytics/grades", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 8


def test_grades_list_unauthorized(client, analytics_data):
    headers = _auth(client, "ana_outsider@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/grades?student_id={sid}", headers=headers)
    assert resp.status_code == 403


def test_grades_filter_by_course(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    cid = analytics_data["courses"][0].id  # Math
    resp = client.get(f"/api/analytics/grades?student_id={sid}&course_id={cid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 5


# ── Summary ─────────────────────────────────────────────────────

def test_summary_endpoint(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/summary?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_graded"] == 8
    assert data["overall_average"] > 0
    assert len(data["course_averages"]) == 2
    assert data["trend"] in ("improving", "declining", "stable")
    # Check course average structure
    ca = data["course_averages"][0]
    assert "average_percentage" in ca
    assert "completion_rate" in ca


def test_summary_empty_student(client, db_session):
    """Student with no grades gets sensible defaults."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_empty@test.com", full_name="Empty Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.commit()

    headers = _auth(client, "ana_empty@test.com")
    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_average"] == 0.0
    assert data["total_graded"] == 0
    assert data["trend"] == "stable"
    assert data["course_averages"] == []


# ── Trends ──────────────────────────────────────────────────────

def test_trends_endpoint(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/trends?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data
    assert "trend" in data
    assert len(data["points"]) > 0
    pt = data["points"][0]
    assert "date" in pt
    assert "percentage" in pt
    assert "course_name" in pt


def test_trends_with_course_filter(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    cid = analytics_data["courses"][1].id  # Science
    resp = client.get(f"/api/analytics/trends?student_id={sid}&course_id={cid}", headers=headers)
    assert resp.status_code == 200
    points = resp.json()["points"]
    for pt in points:
        assert pt["course_name"] == "Analytics Science"


# ── Weekly report ───────────────────────────────────────────────

def test_weekly_report(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/reports/weekly?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_type"] == "weekly"
    assert "data" in data
    assert "overall_average" in data["data"]


def test_weekly_report_caching(client, analytics_data):
    """Second call returns cached report (same id)."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp1 = client.get(f"/api/analytics/reports/weekly?student_id={sid}", headers=headers)
    resp2 = client.get(f"/api/analytics/reports/weekly?student_id={sid}", headers=headers)
    assert resp1.json()["id"] == resp2.json()["id"]


# ── AI Insights ─────────────────────────────────────────────────

def test_ai_insights_unauthorized(client):
    resp = client.post("/api/analytics/ai-insights", json={"student_id": 999})
    assert resp.status_code == 401


def test_ai_insights_success(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    with patch(
        "app.services.ai_service.generate_content",
        new_callable=AsyncMock,
        return_value="## Performance Summary\nDoing well!",
    ):
        resp = client.post(
            "/api/analytics/ai-insights",
            json={"student_id": sid},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "insight" in data
    assert "generated_at" in data
    assert "Performance Summary" in data["insight"]


# ── Sync grades ─────────────────────────────────────────────────

def test_sync_grades_no_google(client, analytics_data):
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.post(f"/api/analytics/sync-grades?student_id={sid}", headers=headers)
    assert resp.status_code == 400
    assert "Google" in resp.json()["detail"]


# ── determine_trend unit test ───────────────────────────────────

def test_determine_trend():
    from app.services.analytics_service import determine_trend

    assert determine_trend([70, 75, 80, 85, 90]) == "improving"
    assert determine_trend([90, 85, 80, 75, 70]) == "declining"
    assert determine_trend([80, 81, 80, 79, 80]) == "stable"
    assert determine_trend([50, 60]) == "stable"  # too few
    assert determine_trend([]) == "stable"
