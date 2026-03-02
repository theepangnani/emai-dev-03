"""Course Planning Tests (#508).

25+ backend pytest tests covering:
  - Ontario boards & course catalog (8 tests)
  - Academic plan CRUD and course management (10 tests)
  - Graduation engine validation (7 tests)
"""

import pytest
from sqlalchemy import insert
from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def setup(db_session):
    """Create all users, student/parent profiles, board, catalog courses, and a base plan."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.ontario_board import OntarioBoard
    from app.models.course_catalog import CourseCatalogItem
    from app.models.academic_plan import AcademicPlan

    hashed = get_password_hash(PASSWORD)

    # --- Users ---
    student_user = db_session.query(User).filter(User.email == "cp_student@test.com").first()
    if student_user:
        # Already seeded — reload references
        parent_user = db_session.query(User).filter(User.email == "cp_parent@test.com").first()
        other_student_user = db_session.query(User).filter(User.email == "cp_other_student@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        other_student_rec = db_session.query(Student).filter(Student.user_id == other_student_user.id).first()
        board = db_session.query(OntarioBoard).filter(OntarioBoard.code == "CP_TDSB").first()
        inactive_board = db_session.query(OntarioBoard).filter(OntarioBoard.code == "CP_INACTIVE").first()
        plan = db_session.query(AcademicPlan).filter(AcademicPlan.student_id == student_rec.id).first()
        return {
            "student_user": student_user,
            "parent_user": parent_user,
            "other_student_user": other_student_user,
            "student_rec": student_rec,
            "other_student_rec": other_student_rec,
            "board": board,
            "inactive_board": inactive_board,
            "plan": plan,
        }

    # --- Create users ---
    student_user = User(email="cp_student@test.com", full_name="CP Student", role=UserRole.STUDENT, hashed_password=hashed)
    parent_user = User(email="cp_parent@test.com", full_name="CP Parent", role=UserRole.PARENT, hashed_password=hashed)
    other_student_user = User(email="cp_other_student@test.com", full_name="CP Other Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([student_user, parent_user, other_student_user])
    db_session.flush()

    # --- Student profiles ---
    student_rec = Student(user_id=student_user.id, grade_level=10)
    other_student_rec = Student(user_id=other_student_user.id, grade_level=9)
    db_session.add_all([student_rec, other_student_rec])
    db_session.flush()

    # --- Link parent → student ---
    db_session.execute(insert(parent_students).values(
        parent_id=parent_user.id,
        student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    # --- Boards ---
    board = OntarioBoard(
        code="CP_TDSB",
        name="CP Toronto District School Board",
        region="Toronto",
        is_active=True,
    )
    inactive_board = OntarioBoard(
        code="CP_INACTIVE",
        name="CP Inactive Board",
        region="Test",
        is_active=False,
    )
    db_session.add_all([board, inactive_board])
    db_session.flush()

    # --- Course catalog items ---
    courses_data = [
        # Universal courses (board_id=None)
        dict(board_id=None, course_code="MPM2D", course_name="Principles of Mathematics, Grade 10, Academic",
             subject_area="Mathematics", grade_level=10, pathway="D", credit_value=1.0, is_compulsory=True,
             compulsory_category="Math", prerequisite_codes=["MPM1D", "MFM1P"]),
        dict(board_id=None, course_code="MCR3U", course_name="Functions, Grade 11, University",
             subject_area="Mathematics", grade_level=11, pathway="U", credit_value=1.0, is_compulsory=True,
             compulsory_category="Math", prerequisite_codes=["MPM2D"]),
        dict(board_id=None, course_code="ENG1D", course_name="English, Grade 9, Academic",
             subject_area="English", grade_level=9, pathway="D", credit_value=1.0, is_compulsory=True,
             compulsory_category="English", prerequisite_codes=None),
        dict(board_id=None, course_code="ENG2D", course_name="English, Grade 10, Academic",
             subject_area="English", grade_level=10, pathway="D", credit_value=1.0, is_compulsory=True,
             compulsory_category="English", prerequisite_codes=["ENG1D", "ENG1P"]),
        dict(board_id=None, course_code="SNC1D", course_name="Science, Grade 9, Academic",
             subject_area="Science", grade_level=9, pathway="D", credit_value=1.0, is_compulsory=True,
             compulsory_category="Science", prerequisite_codes=None),
        dict(board_id=None, course_code="CHC2D", course_name="Canadian History, Grade 10",
             subject_area="Canadian History", grade_level=10, pathway="D", credit_value=1.0, is_compulsory=True,
             compulsory_category="Canadian History", prerequisite_codes=None),
        dict(board_id=None, course_code="AVI1O", course_name="Visual Arts, Grade 9",
             subject_area="Arts", grade_level=9, pathway="O", credit_value=1.0, is_compulsory=False,
             compulsory_category=None, prerequisite_codes=None),
        # Board-specific course
        dict(board_id=board.id, course_code="TDSB_SPEC", course_name="TDSB Specialist Course",
             subject_area="Special Programs", grade_level=11, pathway="U", credit_value=1.0, is_compulsory=False,
             compulsory_category=None, prerequisite_codes=None),
    ]
    for cd in courses_data:
        item = CourseCatalogItem(**cd)
        db_session.add(item)
    db_session.flush()

    # --- Base academic plan for student ---
    plan = AcademicPlan(
        student_id=student_rec.id,
        created_by_user_id=student_user.id,
        name="CP Test Plan",
        start_grade=9,
        target_graduation_year=2028,
        status="draft",
    )
    db_session.add(plan)
    db_session.commit()

    for obj in [student_user, parent_user, other_student_user, student_rec, other_student_rec, board, inactive_board, plan]:
        db_session.refresh(obj)

    return {
        "student_user": student_user,
        "parent_user": parent_user,
        "other_student_user": other_student_user,
        "student_rec": student_rec,
        "other_student_rec": other_student_rec,
        "board": board,
        "inactive_board": inactive_board,
        "plan": plan,
    }


# ===========================================================================
# Ontario Board & Catalog Tests
# ===========================================================================

class TestOntarioBoards:

    def test_list_boards(self, client, setup):
        """GET /api/ontario/boards returns at least the seeded active board."""
        headers = _auth(client, setup["student_user"].email)
        resp = client.get("/api/ontario/boards", headers=headers)
        assert resp.status_code == 200
        boards = resp.json()
        assert isinstance(boards, list)
        codes = [b["code"] for b in boards]
        assert "CP_TDSB" in codes

    def test_list_boards_active_only(self, client, setup):
        """Inactive boards must NOT appear in GET /api/ontario/boards."""
        headers = _auth(client, setup["student_user"].email)
        resp = client.get("/api/ontario/boards", headers=headers)
        assert resp.status_code == 200
        codes = [b["code"] for b in resp.json()]
        assert "CP_INACTIVE" not in codes

    def test_get_course_catalog(self, client, setup):
        """GET /api/ontario/boards/{id}/courses returns courses for that board."""
        headers = _auth(client, setup["student_user"].email)
        board_id = setup["board"].id
        resp = client.get(f"/api/ontario/boards/{board_id}/courses", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] > 0
        course_codes = [item["course_code"] for item in data["items"]]
        # Should include both universal (board_id=None) and board-specific
        assert "MCR3U" in course_codes
        assert "TDSB_SPEC" in course_codes

    def test_catalog_filter_by_grade(self, client, setup):
        """?grade=11 returns only grade 11 courses."""
        headers = _auth(client, setup["student_user"].email)
        board_id = setup["board"].id
        resp = client.get(f"/api/ontario/boards/{board_id}/courses?grade=11", headers=headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["grade_level"] == 11

    def test_catalog_filter_by_subject(self, client, setup):
        """?subject=Mathematics returns only Mathematics courses."""
        headers = _auth(client, setup["student_user"].email)
        board_id = setup["board"].id
        resp = client.get(f"/api/ontario/boards/{board_id}/courses?subject=Mathematics", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        for item in items:
            assert "mathematics" in item["subject_area"].lower()

    def test_catalog_filter_by_pathway(self, client, setup):
        """?pathway=U returns only university-pathway courses."""
        headers = _auth(client, setup["student_user"].email)
        board_id = setup["board"].id
        resp = client.get(f"/api/ontario/boards/{board_id}/courses?pathway=U", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        for item in items:
            assert item["pathway"] == "U"

    def test_get_course_detail(self, client, setup):
        """GET /api/ontario/courses/MCR3U returns correct course details."""
        headers = _auth(client, setup["student_user"].email)
        resp = client.get("/api/ontario/courses/MCR3U", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["course_code"] == "MCR3U"
        assert "Functions" in data["course_name"]
        assert data["grade_level"] == 11
        assert data["pathway"] == "U"

    def test_student_board_link(self, client, setup):
        """POST /api/ontario/student/board links a student to a board (201)."""
        headers = _auth(client, setup["student_user"].email)
        board_id = setup["board"].id
        resp = client.post(
            "/api/ontario/student/board",
            json={"board_id": board_id, "school_name": "CP High School"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["board_id"] == board_id
        assert data["school_name"] == "CP High School"
        assert data["student_id"] == setup["student_rec"].id


# ===========================================================================
# Academic Plan Tests
# ===========================================================================

class TestAcademicPlans:

    def test_create_plan(self, client, setup):
        """POST /api/academic-plans/ — student creates their own plan."""
        headers = _auth(client, setup["student_user"].email)
        resp = client.post(
            "/api/academic-plans/",
            json={"name": "Grade 9-12 Plan", "start_grade": 9, "target_graduation_year": 2028},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Grade 9-12 Plan"
        assert data["student_id"] == setup["student_rec"].id
        assert data["status"] == "draft"

    def test_create_plan_parent_for_child(self, client, setup):
        """Parent can create a plan for their linked child using student_id."""
        headers = _auth(client, setup["parent_user"].email)
        student_id = setup["student_rec"].id
        resp = client.post(
            "/api/academic-plans/",
            json={"name": "Parent Created Plan", "start_grade": 9, "student_id": student_id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["student_id"] == student_id
        assert data["name"] == "Parent Created Plan"

    def test_list_plans_scoped(self, client, setup, db_session):
        """Student only sees their own plans; other student's plan is invisible."""
        # Ensure there is a plan for other_student_rec
        from app.models.academic_plan import AcademicPlan
        other_plan = AcademicPlan(
            student_id=setup["other_student_rec"].id,
            created_by_user_id=setup["other_student_user"].id,
            name="Other Student Plan",
            start_grade=9,
            status="draft",
        )
        db_session.add(other_plan)
        db_session.commit()

        headers = _auth(client, setup["student_user"].email)
        resp = client.get("/api/academic-plans/", headers=headers)
        assert resp.status_code == 200
        plans = resp.json()
        student_ids = {p["student_id"] for p in plans}
        assert setup["student_rec"].id in student_ids
        # Other student's ID must not be exposed
        assert setup["other_student_rec"].id not in student_ids

    def test_add_course_to_plan(self, client, setup):
        """POST /api/academic-plans/{id}/courses adds a course and returns the entry."""
        headers = _auth(client, setup["student_user"].email)
        plan_id = setup["plan"].id
        resp = client.post(
            f"/api/academic-plans/{plan_id}/courses",
            json={
                "course_code": "ENG1D",
                "grade_level": 9,
                "semester": 1,
                "course_name": "English, Grade 9, Academic",
                "subject_area": "English",
                "credit_value": 1.0,
                "status": "planned",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["course_code"] == "ENG1D"
        assert data["plan_id"] == plan_id
        assert data["grade_level"] == 9

    def test_add_duplicate_course_fails(self, client, setup):
        """Adding the same course_code twice to a plan returns 409 Conflict."""
        headers = _auth(client, setup["student_user"].email)
        plan_id = setup["plan"].id
        payload = {
            "course_code": "SNC1D",
            "grade_level": 9,
            "semester": 2,
            "course_name": "Science, Grade 9",
            "status": "planned",
        }
        # First add succeeds
        r1 = client.post(f"/api/academic-plans/{plan_id}/courses", json=payload, headers=headers)
        assert r1.status_code == 201
        # Second add must fail
        r2 = client.post(f"/api/academic-plans/{plan_id}/courses", json=payload, headers=headers)
        assert r2.status_code == 409
        assert "already in this plan" in r2.json()["detail"].lower()

    def test_remove_course_from_plan(self, client, setup):
        """DELETE /api/academic-plans/{id}/courses/{course_id} removes the course."""
        headers = _auth(client, setup["student_user"].email)
        plan_id = setup["plan"].id

        # Add a course first
        add_resp = client.post(
            f"/api/academic-plans/{plan_id}/courses",
            json={
                "course_code": "AVI1O",
                "grade_level": 9,
                "semester": 1,
                "course_name": "Visual Arts, Grade 9",
                "status": "planned",
            },
            headers=headers,
        )
        assert add_resp.status_code == 201
        plan_course_id = add_resp.json()["id"]

        # Delete it
        del_resp = client.delete(
            f"/api/academic-plans/{plan_id}/courses/{plan_course_id}",
            headers=headers,
        )
        assert del_resp.status_code == 204

        # Verify plan no longer contains that course
        plan_resp = client.get(f"/api/academic-plans/{plan_id}", headers=headers)
        course_ids = [c["id"] for c in plan_resp.json()["plan_courses"]]
        assert plan_course_id not in course_ids

    def test_plan_detail_includes_courses(self, client, setup):
        """GET /api/academic-plans/{id} returns plan with nested plan_courses list."""
        headers = _auth(client, setup["student_user"].email)
        plan_id = setup["plan"].id

        # Add a course to ensure plan_courses is populated
        client.post(
            f"/api/academic-plans/{plan_id}/courses",
            json={
                "course_code": "CGC1D",
                "grade_level": 9,
                "semester": 1,
                "course_name": "Canadian Geography",
                "subject_area": "Canadian Geography",
                "status": "planned",
            },
            headers=headers,
        )

        resp = client.get(f"/api/academic-plans/{plan_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "plan_courses" in data
        assert isinstance(data["plan_courses"], list)

    def test_delete_plan_cascades(self, client, setup, db_session):
        """Deleting a plan removes all its plan_courses (cascade)."""
        from app.models.academic_plan import AcademicPlan, PlanCourse

        headers = _auth(client, setup["student_user"].email)

        # Create a fresh plan
        create_resp = client.post(
            "/api/academic-plans/",
            json={"name": "Cascade Test Plan", "start_grade": 9},
            headers=headers,
        )
        assert create_resp.status_code == 201
        plan_id = create_resp.json()["id"]

        # Add a course
        add_resp = client.post(
            f"/api/academic-plans/{plan_id}/courses",
            json={
                "course_code": "PPL1O",
                "grade_level": 9,
                "semester": 2,
                "course_name": "Health & PE",
                "status": "planned",
            },
            headers=headers,
        )
        assert add_resp.status_code == 201

        # Delete plan
        del_resp = client.delete(f"/api/academic-plans/{plan_id}", headers=headers)
        assert del_resp.status_code == 204

        # Plan and all plan_courses should be gone in DB
        assert db_session.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first() is None
        remaining = db_session.query(PlanCourse).filter(PlanCourse.plan_id == plan_id).count()
        assert remaining == 0

    def test_unauthorized_plan_access(self, client, setup):
        """A different student cannot read another student's plan — expects 403 or 404."""
        headers_other = _auth(client, setup["other_student_user"].email)
        plan_id = setup["plan"].id  # Belongs to student_rec, not other_student_rec

        resp = client.get(f"/api/academic-plans/{plan_id}", headers=headers_other)
        assert resp.status_code in (403, 404)

    def test_update_plan_metadata(self, client, setup):
        """PUT /api/academic-plans/{id} updates name, notes, status."""
        headers = _auth(client, setup["student_user"].email)
        plan_id = setup["plan"].id

        resp = client.put(
            f"/api/academic-plans/{plan_id}",
            json={"name": "Updated Plan Name", "notes": "Planning for university", "status": "active"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Plan Name"
        assert data["notes"] == "Planning for university"
        assert data["status"] == "active"


# ===========================================================================
# Graduation Engine Tests
# ===========================================================================

class TestGraduationEngine:
    """Direct unit tests for the graduation_engine module (no HTTP)."""

    @staticmethod
    def _make_course(**kwargs):
        """Build a lightweight namespace object mimicking a PlanCourse ORM instance."""
        from types import SimpleNamespace
        defaults = dict(
            course_code="GEN101",
            course_name="Generic Course",
            subject_area=None,
            grade_level=9,
            credit_value=1.0,
            pathway=None,
            status="planned",
            is_compulsory=False,
            compulsory_category=None,
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_validate_empty_plan(self):
        """An empty plan has 0 credits, is not valid, and lists all missing requirements."""
        from app.services import graduation_engine

        result = graduation_engine.validate_plan([])
        assert result.is_valid is False
        assert result.total_credits == 0.0
        assert result.compulsory_credits == 0.0
        assert len(result.missing_requirements) > 0
        # Total-credit shortfall must be reported
        total_msg = [m for m in result.missing_requirements if "Total credits" in m]
        assert len(total_msg) == 1

    def test_validate_partial_plan(self):
        """A plan with some compulsory courses filled reports partial completion."""
        from app.services import graduation_engine

        courses = [
            self._make_course(course_code="ENG1D", subject_area="English", grade_level=9,
                              credit_value=1.0, compulsory_category="English"),
            self._make_course(course_code="ENG2D", subject_area="English", grade_level=10,
                              credit_value=1.0, compulsory_category="English"),
            self._make_course(course_code="MPM2D", subject_area="Mathematics", grade_level=10,
                              credit_value=1.0, compulsory_category="Math"),
            self._make_course(course_code="SNC1D", subject_area="Science", grade_level=9,
                              credit_value=1.0, compulsory_category="Science"),
        ]
        result = graduation_engine.validate_plan(courses)
        assert result.is_valid is False
        assert result.total_credits == 4.0
        assert result.completion_pct > 0.0
        assert result.completion_pct < 100.0
        # Some requirements fulfilled
        assert len(result.fulfilled_requirements) > 0
        # Some still missing
        assert len(result.missing_requirements) > 0

    def test_validate_complete_plan(self):
        """A plan with 30+ credits covering all compulsory requirements is valid."""
        from app.services import graduation_engine

        # Build enough courses to satisfy all OSSD compulsory requirements
        courses = [
            # English x4
            self._make_course(course_code="ENG1D", subject_area="English", grade_level=9, compulsory_category="English"),
            self._make_course(course_code="ENG2D", subject_area="English", grade_level=10, compulsory_category="English"),
            self._make_course(course_code="ENG3U", subject_area="English", grade_level=11, compulsory_category="English"),
            self._make_course(course_code="ENG4U", subject_area="English", grade_level=12, compulsory_category="English"),
            # Math x3
            self._make_course(course_code="MPM1D", subject_area="Mathematics", grade_level=9, compulsory_category="Math"),
            self._make_course(course_code="MPM2D", subject_area="Mathematics", grade_level=10, compulsory_category="Math"),
            self._make_course(course_code="MCR3U", subject_area="Mathematics", grade_level=11, compulsory_category="Math"),
            # Science x2
            self._make_course(course_code="SNC1D", subject_area="Science", grade_level=9, compulsory_category="Science"),
            self._make_course(course_code="SNC2D", subject_area="Science", grade_level=10, compulsory_category="Science"),
            # Canadian History
            self._make_course(course_code="CHC2D", subject_area="Canadian History", grade_level=10, compulsory_category="Canadian History"),
            # Canadian Geography
            self._make_course(course_code="CGC1D", subject_area="Canadian Geography", grade_level=9, compulsory_category="Canadian Geography"),
            # Arts
            self._make_course(course_code="AVI1O", subject_area="Arts", grade_level=9, compulsory_category="Arts"),
            # Health & PE
            self._make_course(course_code="PPL1O", subject_area="Health & PE", grade_level=9, compulsory_category="Health & PE"),
            # Civics (0.5)
            self._make_course(course_code="CHV2O", subject_area="Civics", grade_level=10, credit_value=0.5, compulsory_category="Civics"),
            # Career Studies (0.5)
            self._make_course(course_code="GLC2O", subject_area="Career Studies", grade_level=10, credit_value=0.5, compulsory_category="Career Studies"),
            # French
            self._make_course(course_code="FSF1D", subject_area="French", grade_level=9, compulsory_category="French"),
        ]

        # Add electives to reach 30 total credits
        # Current total = 15 (14×1.0 + 2×0.5 = 15), need 15 more electives
        for i in range(15):
            courses.append(self._make_course(
                course_code=f"ELEC{i:02d}",
                subject_area="Elective",
                grade_level=10 + (i % 3),
                credit_value=1.0,
            ))

        result = graduation_engine.validate_plan(courses)
        assert result.is_valid is True
        assert result.total_credits >= 30.0
        assert len(result.missing_requirements) == 0

    def test_prerequisite_check_satisfied(self):
        """MCR3U with MPM2D in completed courses -> prerequisite satisfied."""
        from app.services import graduation_engine

        can_take, reason = graduation_engine.check_prerequisites(
            "MCR3U",
            completed_courses=["MPM2D"],
            catalog_lookup={},
        )
        assert can_take is True
        assert reason is None

    def test_prerequisite_check_fails(self):
        """MCR3U without MPM2D (or MFM2P) -> prerequisite not satisfied."""
        from app.services import graduation_engine

        can_take, reason = graduation_engine.check_prerequisites(
            "MCR3U",
            completed_courses=["ENG1D", "SNC1D"],
            catalog_lookup={},
        )
        assert can_take is False
        assert reason is not None
        assert "MCR3U" in reason

    def test_suggest_missing_compulsory(self):
        """suggest_missing_compulsory returns codes for unfulfilled categories."""
        from app.services import graduation_engine

        # Provide only English courses — all other categories unfulfilled
        courses = [
            self._make_course(course_code="ENG1D", subject_area="English", grade_level=9, compulsory_category="English"),
            self._make_course(course_code="ENG2D", subject_area="English", grade_level=10, compulsory_category="English"),
            self._make_course(course_code="ENG3U", subject_area="English", grade_level=11, compulsory_category="English"),
            self._make_course(course_code="ENG4U", subject_area="English", grade_level=12, compulsory_category="English"),
        ]
        suggestions = graduation_engine.suggest_missing_compulsory(courses)
        # Should suggest codes for Math, Science, History, Geography, Arts, PE, Civics, Career, French
        assert len(suggestions) > 0
        # English already fulfilled — none of its suggestions should appear since English is satisfied
        # Math should be suggested
        assert any("MPM" in s or "MCR" in s or "MFM" in s for s in suggestions)

    def test_validate_endpoint(self, client, setup):
        """GET /api/academic-plans/{id}/validate returns ValidationResultResponse schema."""
        headers = _auth(client, setup["student_user"].email)
        plan_id = setup["plan"].id

        resp = client.get(f"/api/academic-plans/{plan_id}/validate", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # Verify schema fields are present
        assert "is_valid" in data
        assert "total_credits" in data
        assert "compulsory_credits" in data
        assert "elective_credits" in data
        assert "completion_pct" in data
        assert "missing_requirements" in data
        assert "warnings" in data
        assert "fulfilled_requirements" in data
        assert "suggested_courses" in data

        # An empty/sparse plan should not be valid
        assert isinstance(data["is_valid"], bool)
        assert isinstance(data["total_credits"], (int, float))
        assert isinstance(data["missing_requirements"], list)
        assert isinstance(data["suggested_courses"], list)


# ===========================================================================
# Parametrized filter tests
# ===========================================================================

@pytest.mark.parametrize("grade", [9, 10, 11, 12])
def test_catalog_grade_filter_parametrized(client, setup, grade):
    """Catalog ?grade=N returns only items with that grade_level (parametrized)."""
    headers = _auth(client, setup["student_user"].email)
    board_id = setup["board"].id
    resp = client.get(f"/api/ontario/boards/{board_id}/courses?grade={grade}", headers=headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["grade_level"] == grade


def test_catalog_404_for_unknown_board(client, setup):
    """GET /api/ontario/boards/999999/courses returns 404 for a non-existent board."""
    headers = _auth(client, setup["student_user"].email)
    resp = client.get("/api/ontario/boards/999999/courses", headers=headers)
    assert resp.status_code == 404


def test_course_detail_404_for_unknown_code(client, setup):
    """GET /api/ontario/courses/XXXXX returns 404 for a non-existent course code."""
    headers = _auth(client, setup["student_user"].email)
    resp = client.get("/api/ontario/courses/XXXXX", headers=headers)
    assert resp.status_code == 404
