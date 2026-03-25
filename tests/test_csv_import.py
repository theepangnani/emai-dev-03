"""Tests for CSV template import (#2167)."""

import io

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.course import Course

    parent = db_session.query(User).filter(User.email == "csv_parent@test.com").first()
    if parent:
        student_user = db_session.query(User).filter(User.email == "csv_student@test.com").first()
        course = db_session.query(Course).filter(Course.name == "CSV Test Course").first()
        return {"parent": parent, "student": student_user, "course": course}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="csv_parent@test.com", full_name="CSV Parent", role=UserRole.PARENT, hashed_password=hashed)
    student_user = User(email="csv_student@test.com", full_name="CSV Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([parent, student_user])
    db_session.flush()

    course = Course(name="CSV Test Course", description="For assignment import", created_by_user_id=parent.id, is_private=True)
    db_session.add(course)
    db_session.commit()

    for u in [parent, student_user]:
        db_session.refresh(u)
    db_session.refresh(course)

    return {"parent": parent, "student": student_user, "course": course}


class TestTemplateDownload:
    def test_download_students_template(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/import/templates/students", headers=headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "name,email,grade" in resp.text

    def test_download_courses_template(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/import/templates/courses", headers=headers)
        assert resp.status_code == 200
        assert "name,description,subject" in resp.text

    def test_download_assignments_template(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/import/templates/assignments", headers=headers)
        assert resp.status_code == 200
        assert "title,course_name,due_date,description" in resp.text

    def test_download_invalid_type(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/import/templates/invalid", headers=headers)
        assert resp.status_code == 400

    def test_student_role_forbidden(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/import/templates/students", headers=headers)
        assert resp.status_code == 403


class TestCSVImport:
    def _upload(self, client, headers, template_type, csv_content, filename="test.csv"):
        return client.post(
            "/api/import/csv",
            data={"template_type": template_type},
            files={"file": (filename, io.BytesIO(csv_content.encode()), "text/csv")},
            headers=headers,
        )

    def test_import_courses(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = "name,description,subject\nMath 101,Intro to Math,Mathematics\nScience 201,Intro to Science,Science\n"
        resp = self._upload(client, headers, "courses", csv_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["errors"] == []

    def test_import_courses_missing_name(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = "name,description,subject\n,Missing name,Math\nValid Course,,\n"
        resp = self._upload(client, headers, "courses", csv_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1
        assert len(data["errors"]) == 1
        assert "name is required" in data["errors"][0]

    def test_import_assignments(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = f"title,course_name,due_date,description\nHomework 1,CSV Test Course,2026-04-01,First assignment\n"
        resp = self._upload(client, headers, "assignments", csv_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1

    def test_import_assignments_bad_course(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = "title,course_name,due_date,description\nHW,Nonexistent Course,,\n"
        resp = self._upload(client, headers, "assignments", csv_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert len(data["errors"]) == 1
        assert "not found" in data["errors"][0]

    def test_import_invalid_type(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = "col1\nval1\n"
        resp = self._upload(client, headers, "badtype", csv_data)
        assert resp.status_code == 400

    def test_import_non_csv_file(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            "/api/import/csv",
            data={"template_type": "courses"},
            files={"file": ("test.txt", io.BytesIO(b"not csv"), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_import_empty_csv(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = "name,description,subject\n"
        resp = self._upload(client, headers, "courses", csv_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert len(data["errors"]) > 0

    def test_student_role_forbidden(self, client, users):
        headers = _auth(client, users["student"].email)
        csv_data = "name,description,subject\nTest,,\n"
        resp = self._upload(client, headers, "courses", csv_data)
        assert resp.status_code == 403

    def test_import_missing_columns(self, client, users):
        headers = _auth(client, users["parent"].email)
        csv_data = "name\nTest\n"
        resp = self._upload(client, headers, "courses", csv_data)
        assert resp.status_code == 200
        data = resp.json()
        # Should report missing columns but not crash
        # description and subject are optional in the template but present as headers
        # Actually the CSV has all headers but only name is required for validation
        # The import_csv function checks for missing required columns from TEMPLATES
        assert data["imported"] == 0
        assert any("Missing required columns" in e for e in data["errors"])
