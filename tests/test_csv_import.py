"""Tests for CSV import endpoints (#2167)."""

import io

import pytest

from tests.conftest import PASSWORD, _auth


@pytest.fixture()
def parent_user(client, db_session):
    """Create a parent user for testing."""
    from app.models.user import User, UserRole

    email = "csv_parent@test.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        return existing

    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": PASSWORD,
        "full_name": "CSV Test Parent",
        "role": "parent",
    })
    assert resp.status_code in (200, 201), resp.text
    user = db_session.query(User).filter(User.email == email).first()
    return user


def test_list_templates(client, parent_user):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/import/templates", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    types = {t["type"] for t in data}
    assert types == {"students", "courses", "assignments"}


def test_download_template(client, parent_user):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/import/templates/students", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    content = resp.text
    assert "name" in content
    assert "email" in content
    assert "grade" in content


def test_download_template_invalid_type(client, parent_user):
    headers = _auth(client, parent_user.email)
    resp = client.get("/api/import/templates/invalid", headers=headers)
    assert resp.status_code == 400


def test_upload_preview_students(client, parent_user):
    headers = _auth(client, parent_user.email)
    csv_content = "name,email,grade\nAlice Smith,alice@test.com,5\nBob Jones,bob@test.com,8\n"
    files = {"file": ("students.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=students&confirm=false",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preview"] is True
    assert data["valid"] == 2
    assert len(data["rows"]) == 2
    assert data["errors"] == []


def test_upload_preview_validation_errors(client, parent_user):
    headers = _auth(client, parent_user.email)
    csv_content = "name,email,grade\n,bad-email,99\nAlice,alice@test.com,5\n"
    files = {"file": ("students.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=students&confirm=false",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["errors"]) > 0
    assert data["valid"] == 1


def test_upload_missing_columns(client, parent_user):
    headers = _auth(client, parent_user.email)
    csv_content = "name,grade\nAlice,5\n"
    files = {"file": ("students.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=students&confirm=false",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["errors"]) > 0
    assert "Missing required columns" in data["errors"][0]


def test_upload_non_csv_file(client, parent_user):
    headers = _auth(client, parent_user.email)
    files = {"file": ("data.txt", io.BytesIO(b"not csv"), "text/plain")}
    resp = client.post(
        "/api/import/csv?template_type=students&confirm=false",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 400


def test_import_courses_confirm(client, parent_user):
    headers = _auth(client, parent_user.email)
    csv_content = "name,description,subject\nMath 101,Intro to math,Math\nScience 201,Intro to science,Science\n"
    files = {"file": ("courses.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=courses&confirm=true",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preview"] is False
    assert data["created"] == 2
    assert data["errors"] == []


def test_import_courses_duplicate_skipped(client, parent_user):
    """Second import of same courses should skip duplicates."""
    headers = _auth(client, parent_user.email)
    csv_content = "name,description,subject\nMath 101,Intro to math,Math\n"
    files = {"file": ("courses.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=courses&confirm=true",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skipped"] >= 1


def test_import_assignments_course_not_found(client, parent_user):
    headers = _auth(client, parent_user.email)
    csv_content = "title,course,due_date,description\nHW1,Nonexistent Course,2026-04-01,Do stuff\n"
    files = {"file": ("assignments.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=assignments&confirm=true",
        headers=headers,
        files=files,
    )
    # Should fail with validation errors (course not found)
    assert resp.status_code == 422


def test_import_assignments_success(client, parent_user):
    """Import assignments after courses exist."""
    headers = _auth(client, parent_user.email)

    # First ensure course exists
    csv_content = "name,description,subject\nCSV Test Course,,\n"
    files = {"file": ("courses.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    client.post(
        "/api/import/csv?template_type=courses&confirm=true",
        headers=headers,
        files=files,
    )

    # Now import assignments
    csv_content = "title,course,due_date,description\nHomework 1,CSV Test Course,2026-05-01,First assignment\n"
    files = {"file": ("assignments.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(
        "/api/import/csv?template_type=assignments&confirm=true",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1


def test_unauthenticated_access(client):
    resp = client.get("/api/import/templates")
    assert resp.status_code == 401
