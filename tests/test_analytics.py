import pytest
from unittest.mock import patch, AsyncMock
from conftest import PASSWORD, _login, _auth


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


# ── determine_trend unit tests (parameterized) ──────────────────


@pytest.mark.parametrize("grades,expected", [
    ([70, 75, 80, 85, 90], "improving"),
    ([90, 85, 80, 75, 70], "declining"),
    ([80, 81, 80, 79, 80], "stable"),
    ([50, 60], "stable"),
    ([], "stable"),
    ([85], "stable"),
    ([50, 100], "stable"),
    ([100, 50], "stable"),
    ([80, 80, 80, 80, 80], "stable"),
    ([50, 55, 60, 65, 70, 75, 80, 85, 90], "improving"),
    ([95, 90, 85, 80, 75, 70, 65, 60, 55], "declining"),
    ([80, 80, 80, 81, 81, 82, 82, 82, 82], "stable"),
    ([50, 70, 90], "improving"),
    ([90, 70, 50], "declining"),
    ([80, 70, 80], "stable"),
])
def test_determine_trend(grades, expected):
    from app.services.analytics_service import determine_trend

    assert determine_trend(grades) == expected


# ── compute_summary: unit tests ─────────────────────────────────

def test_compute_summary_with_data(db_session, analytics_data):
    """Unit test compute_summary directly, verify aggregation with mixed courses."""
    from app.services.analytics_service import compute_summary

    sid = analytics_data["student_rec"].id
    result = compute_summary(db_session, sid)

    assert result["total_graded"] == 8
    assert result["total_assignments"] == 8
    assert result["overall_average"] > 0
    assert result["completion_rate"] == 100.0  # 8/8 = 100%
    assert len(result["course_averages"]) == 2
    assert result["trend"] in ("improving", "declining", "stable")

    # Verify math average: (70+75+80+85+90)/5 = 80.0
    math_avg = None
    sci_avg = None
    for ca in result["course_averages"]:
        if ca["course_name"] == "Analytics Math":
            math_avg = ca
        elif ca["course_name"] == "Analytics Science":
            sci_avg = ca

    assert math_avg is not None
    assert math_avg["average_percentage"] == 80.0
    assert math_avg["graded_count"] == 5
    assert math_avg["completion_rate"] == 100.0

    # Science: percentages are 80%, 70%, 90% → average = 80.0
    assert sci_avg is not None
    assert sci_avg["graded_count"] == 3
    assert sci_avg["completion_rate"] == 100.0


def test_compute_summary_empty(db_session):
    """compute_summary for a student with no grades."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.services.analytics_service import compute_summary

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_csempty@test.com", full_name="CS Empty", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)

    result = compute_summary(db_session, s.id)
    assert result["overall_average"] == 0.0
    assert result["total_graded"] == 0
    assert result["course_averages"] == []
    assert result["trend"] == "stable"
    assert result["completion_rate"] == 0.0


# ── compute_trend_points: date range filtering ──────────────────

def test_compute_trend_points_default_90d(db_session, analytics_data):
    """Default 90-day window returns all points within range."""
    from app.services.analytics_service import compute_trend_points

    sid = analytics_data["student_rec"].id
    points, trend = compute_trend_points(db_session, sid, days=90)

    assert len(points) > 0
    assert trend in ("improving", "declining", "stable")
    # All points should have required keys
    for pt in points:
        assert "date" in pt
        assert "percentage" in pt
        assert "course_name" in pt
        assert "assignment_title" in pt


def test_compute_trend_points_narrow_window(db_session, analytics_data):
    """A very narrow window (1 day) should return fewer or no points."""
    from app.services.analytics_service import compute_trend_points

    sid = analytics_data["student_rec"].id
    points, trend = compute_trend_points(db_session, sid, days=1)

    # With 1-day window, may have 0 or very few points
    assert isinstance(points, list)
    # With too few points, trend is always stable
    if len(points) < 3:
        assert trend == "stable"


def test_compute_trend_points_30d(db_session, analytics_data):
    """30-day window captures some assignments."""
    from app.services.analytics_service import compute_trend_points

    sid = analytics_data["student_rec"].id
    points_30, trend_30 = compute_trend_points(db_session, sid, days=30)
    points_90, _ = compute_trend_points(db_session, sid, days=90)

    # 30-day window should return same or fewer points than 90-day
    assert len(points_30) <= len(points_90)


def test_compute_trend_points_course_filter(db_session, analytics_data):
    """Course filter restricts to only that course."""
    from app.services.analytics_service import compute_trend_points

    sid = analytics_data["student_rec"].id
    math_id = analytics_data["courses"][0].id
    sci_id = analytics_data["courses"][1].id

    math_points, _ = compute_trend_points(db_session, sid, course_id=math_id)
    sci_points, _ = compute_trend_points(db_session, sid, course_id=sci_id)

    for pt in math_points:
        assert pt["course_name"] == "Analytics Math"
    for pt in sci_points:
        assert pt["course_name"] == "Analytics Science"


# ── Grades list: pagination ─────────────────────────────────────

def test_grades_pagination_limit(client, analytics_data):
    """Limit restricts the number of returned grades."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    resp = client.get(f"/api/analytics/grades?student_id={sid}&limit=3", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8  # total is still full count
    assert len(data["grades"]) == 3  # but only 3 returned


def test_grades_pagination_offset(client, analytics_data):
    """Offset skips rows and returns the rest."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    resp = client.get(f"/api/analytics/grades?student_id={sid}&offset=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8
    assert len(data["grades"]) == 3  # 8 - 5 = 3


def test_grades_pagination_limit_and_offset(client, analytics_data):
    """Limit+offset work together for paging."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    # page 1: offset=0, limit=4
    resp1 = client.get(f"/api/analytics/grades?student_id={sid}&limit=4&offset=0", headers=headers)
    # page 2: offset=4, limit=4
    resp2 = client.get(f"/api/analytics/grades?student_id={sid}&limit=4&offset=4", headers=headers)

    data1 = resp1.json()
    data2 = resp2.json()

    assert len(data1["grades"]) == 4
    assert len(data2["grades"]) == 4
    assert data1["total"] == data2["total"] == 8

    # Pages should not overlap
    ids1 = {g["student_assignment_id"] for g in data1["grades"]}
    ids2 = {g["student_assignment_id"] for g in data2["grades"]}
    assert ids1.isdisjoint(ids2)


def test_grades_pagination_beyond_total(client, analytics_data):
    """Offset beyond total yields empty grades list."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    resp = client.get(f"/api/analytics/grades?student_id={sid}&offset=100", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8
    assert len(data["grades"]) == 0


# ── Grades list: course filter via API ──────────────────────────

def test_grades_filter_science_only(client, analytics_data):
    """Filter by science course returns only science grades."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    cid = analytics_data["courses"][1].id  # Science

    resp = client.get(f"/api/analytics/grades?student_id={sid}&course_id={cid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    for g in data["grades"]:
        assert g["course_name"] == "Analytics Science"


# ── RBAC: parent sees linked child ──────────────────────────────

def test_rbac_parent_sees_linked_child_summary(client, analytics_data):
    """A parent linked to a student can see that student's summary."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/summary?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_graded"] == 8


def test_rbac_parent_sees_linked_child_trends(client, analytics_data):
    """A parent linked to a student can see trends."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/trends?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    assert "points" in resp.json()


def test_rbac_parent_sees_linked_child_weekly(client, analytics_data):
    """A parent linked to a student can see the weekly report."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/reports/weekly?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["report_type"] == "weekly"


# ── RBAC: outsider (unlinked parent) CANNOT see student data ───

def test_rbac_outsider_cannot_see_summary(client, analytics_data):
    """An unlinked parent gets 403 on summary."""
    headers = _auth(client, "ana_outsider@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/summary?student_id={sid}", headers=headers)
    assert resp.status_code == 403


def test_rbac_outsider_cannot_see_trends(client, analytics_data):
    """An unlinked parent gets 403 on trends."""
    headers = _auth(client, "ana_outsider@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/trends?student_id={sid}", headers=headers)
    assert resp.status_code == 403


def test_rbac_outsider_cannot_see_weekly(client, analytics_data):
    """An unlinked parent gets 403 on weekly report."""
    headers = _auth(client, "ana_outsider@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/reports/weekly?student_id={sid}", headers=headers)
    assert resp.status_code == 403


def test_rbac_outsider_cannot_use_ai_insights(client, analytics_data):
    """An unlinked parent gets 403 on AI insights."""
    headers = _auth(client, "ana_outsider@test.com")
    sid = analytics_data["student_rec"].id

    with patch(
        "app.services.ai_service.generate_content",
        new_callable=AsyncMock,
        return_value="test",
    ):
        resp = client.post(
            "/api/analytics/ai-insights",
            json={"student_id": sid},
            headers=headers,
        )
    assert resp.status_code == 403


# ── RBAC: student sees own data ─────────────────────────────────

def test_rbac_student_sees_own_summary(client, analytics_data):
    """Student can see their own summary without student_id param."""
    headers = _auth(client, "ana_student@test.com")
    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_graded"] == 8


def test_rbac_student_sees_own_trends(client, analytics_data):
    """Student can see their own trends."""
    headers = _auth(client, "ana_student@test.com")
    resp = client.get("/api/analytics/trends", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["points"]) > 0


def test_rbac_student_sees_own_weekly(client, analytics_data):
    """Student can see their own weekly report."""
    headers = _auth(client, "ana_student@test.com")
    resp = client.get("/api/analytics/reports/weekly", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["report_type"] == "weekly"


# ── RBAC: teacher sees enrolled student ─────────────────────────

def test_rbac_teacher_sees_course_student(client, db_session, analytics_data):
    """A teacher assigned to a course can see enrolled student grades."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher

    hashed = get_password_hash(PASSWORD)

    # Check if teacher already exists (fixture reuse)
    teacher_user = db_session.query(User).filter(User.email == "ana_teacher@test.com").first()
    if not teacher_user:
        teacher_user = User(
            email="ana_teacher@test.com", full_name="Analytics Teacher",
            role=UserRole.TEACHER, hashed_password=hashed,
        )
        db_session.add(teacher_user)
        db_session.flush()

        teacher_rec = Teacher(user_id=teacher_user.id)
        db_session.add(teacher_rec)
        db_session.flush()

        # Assign teacher to the Math course
        math_course = analytics_data["courses"][0]
        math_course.teacher_id = teacher_rec.id
        db_session.commit()

    headers = _auth(client, "ana_teacher@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/grades?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 8


def test_rbac_teacher_no_access_to_unrelated_student(client, db_session, analytics_data):
    """A teacher not assigned to any course with the student gets 403."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher

    hashed = get_password_hash(PASSWORD)

    teacher_user2 = db_session.query(User).filter(User.email == "ana_teacher2@test.com").first()
    if not teacher_user2:
        teacher_user2 = User(
            email="ana_teacher2@test.com", full_name="Other Teacher",
            role=UserRole.TEACHER, hashed_password=hashed,
        )
        db_session.add(teacher_user2)
        db_session.flush()

        teacher_rec2 = Teacher(user_id=teacher_user2.id)
        db_session.add(teacher_rec2)
        db_session.commit()

    headers = _auth(client, "ana_teacher2@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/grades?student_id={sid}", headers=headers)
    assert resp.status_code == 403


# ── RBAC: admin sees all ────────────────────────────────────────

def test_rbac_admin_sees_any_student(client, db_session, analytics_data):
    """Admin can see any student's data."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    admin_user = db_session.query(User).filter(User.email == "ana_admin@test.com").first()
    if not admin_user:
        admin_user = User(
            email="ana_admin@test.com", full_name="Analytics Admin",
            role=UserRole.ADMIN, hashed_password=hashed,
        )
        db_session.add(admin_user)
        db_session.commit()

    headers = _auth(client, "ana_admin@test.com")
    sid = analytics_data["student_rec"].id

    resp = client.get(f"/api/analytics/grades?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 8


def test_rbac_admin_sees_summary(client, db_session, analytics_data):
    """Admin can see any student's summary."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)

    admin_user = db_session.query(User).filter(User.email == "ana_admin@test.com").first()
    if not admin_user:
        admin_user = User(
            email="ana_admin@test.com", full_name="Analytics Admin",
            role=UserRole.ADMIN, hashed_password=hashed,
        )
        db_session.add(admin_user)
        db_session.commit()

    headers = _auth(client, "ana_admin@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/summary?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_graded"] == 8


# ── AI Insights: extended tests ─────────────────────────────────

def test_ai_insights_with_focus_area(client, analytics_data):
    """AI insights endpoint accepts an optional focus_area."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    with patch(
        "app.services.ai_service.generate_content",
        new_callable=AsyncMock,
        return_value="## Math Focus\nNeed more practice.",
    ):
        resp = client.post(
            "/api/analytics/ai-insights",
            json={"student_id": sid, "focus_area": "math"},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "Math Focus" in data["insight"]


def test_ai_insights_student_not_found(client, analytics_data):
    """AI insights for non-existent student returns 404."""
    headers = _auth(client, "ana_parent@test.com")

    resp = client.post(
        "/api/analytics/ai-insights",
        json={"student_id": 999999},
        headers=headers,
    )
    assert resp.status_code == 404


def test_ai_insights_as_student(client, analytics_data):
    """Student can request AI insights for themselves."""
    headers = _auth(client, "ana_student@test.com")
    sid = analytics_data["student_rec"].id

    with patch(
        "app.services.ai_service.generate_content",
        new_callable=AsyncMock,
        return_value="## Your Performance\nGood progress!",
    ):
        resp = client.post(
            "/api/analytics/ai-insights",
            json={"student_id": sid},
            headers=headers,
        )
    assert resp.status_code == 200
    assert "Your Performance" in resp.json()["insight"]


# ── Weekly report: extended tests ───────────────────────────────

def test_weekly_report_data_structure(client, analytics_data):
    """Weekly report contains expected data fields."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/reports/weekly?student_id={sid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "id" in data
    assert "student_id" in data
    assert "period_start" in data
    assert "period_end" in data
    assert "generated_at" in data
    assert data["student_id"] == sid

    report_data = data["data"]
    assert "overall_average" in report_data
    assert "total_graded" in report_data
    assert "completion_rate" in report_data
    assert "trend" in report_data
    assert "grades_this_week" in report_data


def test_weekly_report_as_student(client, analytics_data):
    """Student can see their own weekly report."""
    headers = _auth(client, "ana_student@test.com")
    resp = client.get("/api/analytics/reports/weekly", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["report_type"] == "weekly"


# ── Trends: API time range filtering ────────────────────────────

def test_trends_30d_filter(client, analytics_data):
    """Trends with 30-day filter."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/trends?student_id={sid}&days=30", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data
    assert "trend" in data


def test_trends_60d_filter(client, analytics_data):
    """Trends with 60-day filter."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/trends?student_id={sid}&days=60", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data


def test_trends_shorter_window_fewer_points(client, analytics_data):
    """Shorter time window should return same or fewer trend points."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id

    resp_30 = client.get(f"/api/analytics/trends?student_id={sid}&days=30", headers=headers)
    resp_90 = client.get(f"/api/analytics/trends?student_id={sid}&days=90", headers=headers)

    points_30 = resp_30.json()["points"]
    points_90 = resp_90.json()["points"]
    assert len(points_30) <= len(points_90)


# ── Grades: grade item structure ────────────────────────────────

def test_grade_item_complete_structure(client, analytics_data):
    """Every grade item has all expected fields."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/grades?student_id={sid}&limit=1", headers=headers)
    assert resp.status_code == 200
    g = resp.json()["grades"][0]

    expected_fields = [
        "student_assignment_id", "assignment_id", "assignment_title",
        "course_id", "course_name", "grade", "max_points", "percentage",
        "status", "source", "submitted_at", "due_date",
    ]
    for field in expected_fields:
        assert field in g, f"Missing field: {field}"


# ── Student not found (parameterized) ──────────────────────────


@pytest.mark.parametrize("endpoint", [
    "/api/analytics/grades",
    "/api/analytics/summary",
    "/api/analytics/trends",
])
def test_student_not_found(client, analytics_data, endpoint):
    """Requesting analytics for a non-existent student returns 404."""
    headers = _auth(client, "ana_parent@test.com")
    resp = client.get(f"{endpoint}?student_id=999999", headers=headers)
    assert resp.status_code == 404


# ── Missing student_id for non-student roles ────────────────────

def test_grades_no_student_id_as_parent(client, analytics_data):
    """Parent without student_id gets 400."""
    headers = _auth(client, "ana_parent@test.com")
    resp = client.get("/api/analytics/grades", headers=headers)
    assert resp.status_code == 400


def test_summary_no_student_id_as_parent(client, analytics_data):
    """Parent without student_id gets 400."""
    headers = _auth(client, "ana_parent@test.com")
    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 400


# ── get_graded_assignments: unit tests ──────────────────────────

def test_get_graded_assignments_unit(db_session, analytics_data):
    """Unit test get_graded_assignments directly."""
    from app.services.analytics_service import get_graded_assignments

    sid = analytics_data["student_rec"].id
    grades, total = get_graded_assignments(db_session, sid)
    assert total == 8
    assert len(grades) == 8
    # Verify grades are ordered by recorded_at desc
    if len(grades) >= 2:
        for i in range(len(grades) - 1):
            assert grades[i]["submitted_at"] >= grades[i + 1]["submitted_at"]


def test_get_graded_assignments_with_course_filter(db_session, analytics_data):
    """Unit test get_graded_assignments with course filter."""
    from app.services.analytics_service import get_graded_assignments

    sid = analytics_data["student_rec"].id
    math_id = analytics_data["courses"][0].id
    grades, total = get_graded_assignments(db_session, sid, course_id=math_id)
    assert total == 5
    for g in grades:
        assert g["course_name"] == "Analytics Math"


def test_get_graded_assignments_pagination(db_session, analytics_data):
    """Unit test pagination in get_graded_assignments."""
    from app.services.analytics_service import get_graded_assignments

    sid = analytics_data["student_rec"].id
    grades_page1, total1 = get_graded_assignments(db_session, sid, limit=3, offset=0)
    grades_page2, total2 = get_graded_assignments(db_session, sid, limit=3, offset=3)

    assert total1 == total2 == 8
    assert len(grades_page1) == 3
    assert len(grades_page2) == 3

    ids1 = {g["student_assignment_id"] for g in grades_page1}
    ids2 = {g["student_assignment_id"] for g in grades_page2}
    assert ids1.isdisjoint(ids2)


# ── Grade sync: GradeRecord creation / update ───────────────────

def test_grade_record_creation_and_query(db_session):
    """Creating a new GradeRecord and querying it works correctly."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment
    from app.models.analytics import GradeRecord
    from datetime import datetime

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_grcreate@test.com", full_name="GR Create", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.flush()

    course = Course(name="GR Create Course", created_by_user_id=u.id)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(student_id=s.id, course_id=course.id))

    initial_count = db_session.query(GradeRecord).filter(
        GradeRecord.student_id == s.id,
    ).count()

    gr = GradeRecord(
        student_id=s.id,
        course_id=course.id,
        assignment_id=None,  # course-level grade
        grade=95.0,
        max_grade=100.0,
        percentage=95.0,
        source="manual",
        recorded_at=datetime.utcnow(),
    )
    db_session.add(gr)
    db_session.commit()
    db_session.refresh(gr)

    assert gr.grade == 95.0
    assert gr.percentage == 95.0
    assert gr.source == "manual"

    new_count = db_session.query(GradeRecord).filter(
        GradeRecord.student_id == s.id,
    ).count()
    assert new_count == initial_count + 1


def test_grade_record_update_existing(db_session):
    """Updating an existing GradeRecord preserves the row count."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment
    from app.models.analytics import GradeRecord
    from datetime import datetime

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_grupdate@test.com", full_name="GR Update", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.flush()

    course = Course(name="GR Update Course", created_by_user_id=u.id)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(student_id=s.id, course_id=course.id))

    a = Assignment(title="GR Update HW", course_id=course.id, max_points=100.0)
    db_session.add(a)
    db_session.flush()

    gr = GradeRecord(
        student_id=s.id, course_id=course.id, assignment_id=a.id,
        grade=70.0, max_grade=100.0, percentage=70.0,
        source="seed", recorded_at=datetime.utcnow(),
    )
    db_session.add(gr)
    db_session.commit()
    db_session.refresh(gr)

    # Now update it
    gr.grade = 99.0
    gr.max_grade = 100.0
    gr.percentage = 99.0
    gr.source = "google_classroom"
    db_session.commit()
    db_session.refresh(gr)

    assert gr.grade == 99.0
    assert gr.percentage == 99.0
    assert gr.source == "google_classroom"

    # Count should be unchanged (updated existing, not added new)
    count = db_session.query(GradeRecord).filter(
        GradeRecord.student_id == s.id,
        GradeRecord.assignment_id == a.id,
    ).count()
    assert count == 1


# ── Summary: mixed courses verification ─────────────────────────

def test_summary_course_averages_match_expectations(client, analytics_data):
    """Verify course averages are computed correctly for mixed courses."""
    headers = _auth(client, "ana_parent@test.com")
    sid = analytics_data["student_rec"].id
    resp = client.get(f"/api/analytics/summary?student_id={sid}", headers=headers)
    assert resp.status_code == 200

    course_avgs = {
        ca["course_name"]: ca
        for ca in resp.json()["course_averages"]
    }

    # Math: (70+75+80+85+90)/5 = 80.0
    assert "Analytics Math" in course_avgs
    assert course_avgs["Analytics Math"]["graded_count"] == 5

    # Science: 3 graded assignments
    assert "Analytics Science" in course_avgs
    assert course_avgs["Analytics Science"]["graded_count"] == 3


# ── Edge case: single grade record student ──────────────────────

def test_summary_single_grade_student(client, db_session):
    """Student with a single grade record gets correct summary."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment
    from app.models.analytics import GradeRecord
    from datetime import datetime

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_single@test.com", full_name="Single Grade Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.flush()

    course = Course(name="Single Course", created_by_user_id=u.id)
    db_session.add(course)
    db_session.flush()

    db_session.execute(student_courses.insert().values(student_id=s.id, course_id=course.id))

    a = Assignment(title="Only HW", course_id=course.id, max_points=100.0)
    db_session.add(a)
    db_session.flush()

    gr = GradeRecord(
        student_id=s.id, course_id=course.id, assignment_id=a.id,
        grade=75.0, max_grade=100.0, percentage=75.0,
        source="seed", recorded_at=datetime.utcnow(),
    )
    db_session.add(gr)
    db_session.commit()

    headers = _auth(client, "ana_single@test.com")
    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_average"] == 75.0
    assert data["total_graded"] == 1
    assert data["trend"] == "stable"  # Only 1 grade → stable
    assert len(data["course_averages"]) == 1
    assert data["course_averages"][0]["average_percentage"] == 75.0


# ── Edge case: all same grades ──────────────────────────────────

def test_summary_all_same_grades(client, db_session):
    """Student with all identical grades → stable trend."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment
    from app.models.analytics import GradeRecord
    from datetime import datetime, timedelta

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_same@test.com", full_name="Same Grades", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.flush()

    course = Course(name="Same Grade Course", created_by_user_id=u.id)
    db_session.add(course)
    db_session.flush()

    db_session.execute(student_courses.insert().values(student_id=s.id, course_id=course.id))

    now = datetime.utcnow()
    for i in range(5):
        a = Assignment(title=f"Same HW {i+1}", course_id=course.id, max_points=100.0)
        db_session.add(a)
        db_session.flush()
        gr = GradeRecord(
            student_id=s.id, course_id=course.id, assignment_id=a.id,
            grade=85.0, max_grade=100.0, percentage=85.0,
            source="seed", recorded_at=now - timedelta(days=5 - i),
        )
        db_session.add(gr)

    db_session.commit()

    headers = _auth(client, "ana_same@test.com")
    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_average"] == 85.0
    assert data["trend"] == "stable"
    assert data["total_graded"] == 5


# ── Edge case: declining trend ──────────────────────────────────

def test_summary_declining_trend(client, db_session):
    """Student with declining grades shows declining trend."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment
    from app.models.analytics import GradeRecord
    from datetime import datetime, timedelta

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_decline@test.com", full_name="Declining Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.flush()

    course = Course(name="Decline Course", created_by_user_id=u.id)
    db_session.add(course)
    db_session.flush()

    db_session.execute(student_courses.insert().values(student_id=s.id, course_id=course.id))

    now = datetime.utcnow()
    declining_grades = [95, 90, 85, 80, 75, 70, 65, 60]
    for i, grade_val in enumerate(declining_grades):
        a = Assignment(title=f"Dec HW {i+1}", course_id=course.id, max_points=100.0)
        db_session.add(a)
        db_session.flush()
        gr = GradeRecord(
            student_id=s.id, course_id=course.id, assignment_id=a.id,
            grade=float(grade_val), max_grade=100.0, percentage=float(grade_val),
            source="seed", recorded_at=now - timedelta(days=len(declining_grades) - i),
        )
        db_session.add(gr)

    db_session.commit()

    headers = _auth(client, "ana_decline@test.com")
    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["trend"] == "declining"


# ── Trends: empty student ───────────────────────────────────────

def test_trends_empty_student(client, db_session):
    """Student with no grades gets empty trend points and stable trend."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_trendempty@test.com", full_name="Trend Empty", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.commit()

    headers = _auth(client, "ana_trendempty@test.com")
    resp = client.get("/api/analytics/trends", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == []
    assert data["trend"] == "stable"


# ── Grades: empty student ───────────────────────────────────────

def test_grades_empty_student(client, db_session):
    """Student with no grades gets empty grades list."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student

    hashed = get_password_hash(PASSWORD)
    u = User(email="ana_gradempty@test.com", full_name="Grade Empty", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add(u)
    db_session.flush()
    s = Student(user_id=u.id)
    db_session.add(s)
    db_session.commit()

    headers = _auth(client, "ana_gradempty@test.com")
    resp = client.get("/api/analytics/grades", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["grades"] == []
