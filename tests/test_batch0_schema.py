"""Tests for Batch 0 schema migrations — retention bundle foundation.

Tests cover:
- is_master Boolean column (#2025)
- source_type column on course_contents and source_files (#2010)
- User preferred_language and timezone columns (#2024)
- holiday_dates table and admin CRUD endpoints (#2024)
"""
import pytest
from datetime import date

from conftest import PASSWORD, _auth


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture()
def admin_user(db_session):
    """Create an admin user for testing (idempotent)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == "b0_admin@test.com").first()
    if user:
        return user

    user = User(
        email="b0_admin@test.com",
        full_name="Batch0 Admin",
        role=UserRole.ADMIN,
        roles="admin",
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher_user(db_session):
    """Create a teacher user for testing (idempotent)."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course

    user = db_session.query(User).filter(User.email == "b0_teacher@test.com").first()
    if user:
        course = db_session.query(Course).filter(Course.name == "B0 Test Course").first()
        return {"user": user, "course": course}

    user = User(
        email="b0_teacher@test.com",
        full_name="Batch0 Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.flush()

    teacher = Teacher(user_id=user.id)
    db_session.add(teacher)
    db_session.flush()

    course = Course(
        name="B0 Test Course",
        teacher_id=teacher.id,
        created_by_user_id=user.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(course)
    return {"user": user, "course": course}


# ── is_master Boolean (#2025) ───────────────────────────────


class TestIsMasterBoolean:
    def test_column_exists_as_boolean(self, db_session):
        """is_master column should exist on course_contents table."""
        from sqlalchemy import inspect as sa_inspect
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"]: c for c in inspector.get_columns("course_contents")}
        assert "is_master" in cols

    def test_default_is_false(self, db_session, teacher_user):
        """New CourseContent should have is_master=False by default."""
        from app.models.course_content import CourseContent

        cc = CourseContent(
            course_id=teacher_user["course"].id,
            title="Default Test",
            content_type="notes",
            created_by_user_id=teacher_user["user"].id,
        )
        db_session.add(cc)
        db_session.commit()
        db_session.refresh(cc)
        assert cc.is_master is False

    def test_set_to_true(self, db_session, teacher_user):
        """is_master can be set to True (boolean)."""
        from app.models.course_content import CourseContent

        cc = CourseContent(
            course_id=teacher_user["course"].id,
            title="Master Test",
            content_type="notes",
            created_by_user_id=teacher_user["user"].id,
            is_master=True,
        )
        db_session.add(cc)
        db_session.commit()
        db_session.refresh(cc)
        assert cc.is_master is True

    def test_hierarchy_uses_boolean(self, db_session, teacher_user):
        """create_material_hierarchy sets is_master=True/False (boolean)."""
        from app.models.course_content import CourseContent
        from app.services.material_hierarchy import create_material_hierarchy

        master = CourseContent(
            course_id=teacher_user["course"].id,
            title="Bool Master",
            content_type="notes",
            created_by_user_id=teacher_user["user"].id,
        )
        db_session.add(master)
        db_session.flush()

        sub = CourseContent(
            course_id=teacher_user["course"].id,
            title="Bool Sub",
            content_type="notes",
            created_by_user_id=teacher_user["user"].id,
        )
        db_session.add(sub)
        db_session.flush()

        create_material_hierarchy(db_session, master, [sub])
        db_session.commit()
        db_session.refresh(master)
        db_session.refresh(sub)

        assert master.is_master is True
        assert sub.is_master is False

    def test_api_returns_boolean(self, client, teacher_user):
        """API response should return is_master as boolean."""
        headers = _auth(client, teacher_user["user"].email)
        resp = client.post(
            "/api/course-contents/",
            json={
                "course_id": teacher_user["course"].id,
                "title": "API Bool Test",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_master"] is False
        assert isinstance(data["is_master"], bool)


# ── source_type column (#2010) ───────────────────────────────


class TestSourceTypeColumn:
    def test_column_exists_on_course_contents(self, db_session):
        """source_type column should exist on course_contents table."""
        from sqlalchemy import inspect as sa_inspect
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("course_contents")}
        assert "source_type" in cols

    def test_column_exists_on_source_files(self, db_session):
        """source_type column should exist on source_files table."""
        from sqlalchemy import inspect as sa_inspect
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("source_files")}
        assert "source_type" in cols

    def test_default_value(self, db_session, teacher_user):
        """source_type should default to 'local_upload'."""
        from app.models.course_content import CourseContent

        cc = CourseContent(
            course_id=teacher_user["course"].id,
            title="Source Type Test",
            content_type="notes",
            created_by_user_id=teacher_user["user"].id,
        )
        db_session.add(cc)
        db_session.commit()
        db_session.refresh(cc)
        assert cc.source_type == "local_upload"


# ── User preferred_language & timezone (#2024) ───────────────


class TestUserLanguageTimezone:
    def test_columns_exist(self, db_session):
        """preferred_language and timezone columns should exist on users table."""
        from sqlalchemy import inspect as sa_inspect
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("users")}
        assert "preferred_language" in cols
        assert "timezone" in cols

    def test_default_values(self, db_session):
        """New user should have default language='en' and timezone='America/Toronto'."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        user = User(
            email="b0_langtest@test.com",
            full_name="Lang Test",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        assert user.preferred_language == "en"
        assert user.timezone == "America/Toronto"


# ── holiday_dates table (#2024) ──────────────────────────────


class TestHolidayDatesTable:
    def test_table_exists(self, db_session):
        """holiday_dates table should exist."""
        from sqlalchemy import inspect as sa_inspect
        from app.db.database import engine

        inspector = sa_inspect(engine)
        assert "holiday_dates" in inspector.get_table_names()

    def test_create_holiday(self, db_session):
        """Can create a HolidayDate record."""
        from app.models.holiday import HolidayDate

        holiday = HolidayDate(
            date=date(2026, 12, 25),
            board_name="YRDSB",
            description="Christmas Day",
        )
        db_session.add(holiday)
        db_session.commit()
        db_session.refresh(holiday)
        assert holiday.id is not None
        assert holiday.date == date(2026, 12, 25)
        assert holiday.board_name == "YRDSB"


class TestHolidayCRUDEndpoints:
    def test_list_holidays_empty(self, client, admin_user):
        """GET /api/admin/holidays returns empty list initially."""
        headers = _auth(client, admin_user.email)
        resp = client.get("/api/admin/holidays", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_holiday_endpoint(self, client, admin_user):
        """POST /api/admin/holidays creates a holiday."""
        headers = _auth(client, admin_user.email)
        resp = client.post(
            "/api/admin/holidays",
            json={
                "date": "2026-09-07",
                "board_name": "YRDSB",
                "description": "Labour Day",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2026-09-07"
        assert data["board_name"] == "YRDSB"
        assert data["description"] == "Labour Day"
        assert data["id"] is not None

    def test_delete_holiday_endpoint(self, client, admin_user):
        """DELETE /api/admin/holidays/{id} removes a holiday."""
        headers = _auth(client, admin_user.email)
        # Create first
        create_resp = client.post(
            "/api/admin/holidays",
            json={"date": "2026-10-12", "description": "Thanksgiving"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        holiday_id = create_resp.json()["id"]

        # Delete
        del_resp = client.delete(f"/api/admin/holidays/{holiday_id}", headers=headers)
        assert del_resp.status_code == 204

    def test_delete_nonexistent_holiday(self, client, admin_user):
        """DELETE /api/admin/holidays/99999 returns 404."""
        headers = _auth(client, admin_user.email)
        resp = client.delete("/api/admin/holidays/99999", headers=headers)
        assert resp.status_code == 404

    def test_non_admin_cannot_access(self, client, teacher_user):
        """Non-admin users cannot access holiday endpoints."""
        headers = _auth(client, teacher_user["user"].email)
        resp = client.get("/api/admin/holidays", headers=headers)
        assert resp.status_code == 403
