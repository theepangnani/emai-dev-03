"""CB-KIDPHOTO-001 (#4301) — kid profile photo upload + delete route tests."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy import insert

from conftest import PASSWORD, _auth


def _png_bytes(size: tuple[int, int] = (64, 64), color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(size: tuple[int, int] = (64, 64), color: str = "blue") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


@pytest.fixture()
def kp_users(client, db_session):
    """parent + outsider parent + linked student."""
    from app.models.student import Student, parent_students
    from app.models.user import User

    def _ensure(email: str, name: str, role: str) -> User:
        existing = db_session.query(User).filter(User.email == email).first()
        if existing:
            return existing
        resp = client.post(
            "/api/auth/register",
            json={"email": email, "password": PASSWORD, "full_name": name, "role": role},
        )
        assert resp.status_code in (200, 201, 409), resp.text
        return db_session.query(User).filter(User.email == email).first()

    parent = _ensure("kp_parent@test.com", "KP Parent", "parent")
    outsider = _ensure("kp_outsider@test.com", "KP Outsider", "parent")
    stu_user = _ensure("kp_student@test.com", "KP Student", "student")

    student = db_session.query(Student).filter(Student.user_id == stu_user.id).first()
    if not student:
        student = Student(user_id=stu_user.id, grade_level=8, school_name="KP School")
        db_session.add(student)
        db_session.commit()

    link = db_session.execute(
        parent_students.select().where(
            parent_students.c.parent_id == parent.id,
            parent_students.c.student_id == student.id,
        )
    ).first()
    if not link:
        db_session.execute(
            insert(parent_students).values(
                parent_id=parent.id,
                student_id=student.id,
                relationship_type="GUARDIAN",
            )
        )
        db_session.commit()

    return {"parent": parent, "outsider": outsider, "student": student}


def test_upload_succeeds_with_valid_jpg(client, db_session, kp_users):
    headers = _auth(client, "kp_parent@test.com")
    student = kp_users["student"]

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("avatar.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"))],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "profile_photo_url" in body
    assert body["profile_photo_url"]

    db_session.expire_all()
    from app.models.student import Student
    refreshed = db_session.query(Student).filter(Student.id == student.id).first()
    assert refreshed.profile_photo_url == body["profile_photo_url"]


def test_upload_succeeds_with_valid_png(client, kp_users):
    headers = _auth(client, "kp_parent@test.com")
    student = kp_users["student"]

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("avatar.png", io.BytesIO(_png_bytes()), "image/png"))],
    )
    assert resp.status_code == 200, resp.text


def test_upload_rejects_oversized_image(client, kp_users):
    headers = _auth(client, "kp_parent@test.com")
    student = kp_users["student"]

    # Build a payload > 5 MB. Magic bytes valid (JPEG) so the size check is what fires.
    blob = b"\xff\xd8\xff" + (b"\x00" * (5 * 1024 * 1024 + 16))

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("big.jpg", io.BytesIO(blob), "image/jpeg"))],
    )
    assert resp.status_code == 422, resp.text
    assert "limit" in resp.json()["detail"].lower()


def test_upload_rejects_invalid_extension(client, kp_users):
    headers = _auth(client, "kp_parent@test.com")
    student = kp_users["student"]

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("doc.pdf", io.BytesIO(b"%PDF-1.4 not an image"), "application/pdf"))],
    )
    assert resp.status_code == 422, resp.text


def test_upload_rejects_bad_magic_bytes(client, kp_users):
    headers = _auth(client, "kp_parent@test.com")
    student = kp_users["student"]

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("fake.jpg", io.BytesIO(b"this is plainly not an image"), "image/jpeg"))],
    )
    assert resp.status_code == 422, resp.text


def test_upload_rejects_other_parents_kid(client, kp_users):
    headers = _auth(client, "kp_outsider@test.com")
    student = kp_users["student"]

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("avatar.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"))],
    )
    assert resp.status_code == 403, resp.text


def test_upload_requires_parent_role(client, kp_users):
    headers = _auth(client, "kp_student@test.com")
    student = kp_users["student"]

    resp = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("avatar.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"))],
    )
    assert resp.status_code == 403, resp.text


def test_delete_succeeds(client, db_session, kp_users):
    headers = _auth(client, "kp_parent@test.com")
    student = kp_users["student"]

    # First, upload a photo
    up = client.post(
        f"/api/parent/children/{student.id}/photo",
        headers=headers,
        files=[("file", ("avatar.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"))],
    )
    assert up.status_code == 200

    # Then delete it
    resp = client.delete(f"/api/parent/children/{student.id}/photo", headers=headers)
    assert resp.status_code == 204, resp.text

    db_session.expire_all()
    from app.models.student import Student
    refreshed = db_session.query(Student).filter(Student.id == student.id).first()
    assert refreshed.profile_photo_url is None


def test_delete_other_parents_kid_fails(client, kp_users):
    headers = _auth(client, "kp_outsider@test.com")
    student = kp_users["student"]

    resp = client.delete(f"/api/parent/children/{student.id}/photo", headers=headers)
    assert resp.status_code == 403, resp.text
