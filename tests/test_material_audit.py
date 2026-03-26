"""Tests for material access audit logging (#2272)."""
import json

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course

    parent = db_session.query(User).filter(User.email == "ma_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "ma_teacher@test.com").first()
        other = db_session.query(User).filter(User.email == "ma_other@test.com").first()
        course = db_session.query(Course).filter(Course.name == "MA Test Course").first()
        private_course = db_session.query(Course).filter(Course.name == "MA Private Course").first()
        return {"parent": parent, "teacher": teacher, "other": other, "course": course, "private_course": private_course}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="ma_parent@test.com", full_name="MA Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="ma_teacher@test.com", full_name="MA Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    other = User(email="ma_other@test.com", full_name="MA Other", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, teacher, other])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(name="MA Test Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id)
    private_course = Course(name="MA Private Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id, is_private=True)
    db_session.add_all([course, private_course])
    db_session.commit()

    for u in [parent, teacher, other]:
        db_session.refresh(u)
    db_session.refresh(course)
    db_session.refresh(private_course)
    return {"parent": parent, "teacher": teacher, "other": other, "course": course, "private_course": private_course}


def _create_content_on_private_course(db_session, users):
    """Helper to create content on the private course directly in DB."""
    from app.models.course_content import CourseContent
    content = CourseContent(
        course_id=users["private_course"].id,
        title="Private Audit Material",
        content_type="other",
        created_by_user_id=users["teacher"].id,
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def _create_content(client, users, title="Audit Test Material"):
    """Helper to create a course content item."""
    headers = _auth(client, users["teacher"].email)
    resp = client.post("/api/course-contents/", json={
        "course_id": users["course"].id, "title": title,
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestMaterialViewAudit:
    def test_view_creates_audit_entry(self, client, db_session, users):
        content = _create_content(client, users)
        headers = _auth(client, users["teacher"].email)

        # Clear existing audit entries for clean check
        from app.models.audit_log import AuditLog
        initial_count = db_session.query(AuditLog).filter(
            AuditLog.action == "material_view",
        ).count()

        resp = client.get(f"/api/course-contents/{content['id']}", headers=headers)
        assert resp.status_code == 200

        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_view",
            AuditLog.resource_type == "course_content",
            AuditLog.resource_id == content["id"],
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        assert entry.user_id == users["teacher"].id
        details = json.loads(entry.details)
        assert details["course_id"] == users["course"].id

    def test_denied_view_creates_audit_entry(self, client, db_session, users):
        content = _create_content_on_private_course(db_session, users)
        headers = _auth(client, users["other"].email)

        resp = client.get(f"/api/course-contents/{content.id}", headers=headers)
        assert resp.status_code == 403

        from app.models.audit_log import AuditLog
        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_view",
            AuditLog.resource_id == content.id,
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        assert entry.user_id == users["other"].id
        details = json.loads(entry.details)
        assert details["denied"] is True


class TestMaterialDownloadAudit:
    def test_download_creates_audit_entry(self, client, db_session, users):
        content = _create_content(client, users)
        headers = _auth(client, users["teacher"].email)

        # Download will 404 since there's no file, but audit should still be logged
        resp = client.get(f"/api/course-contents/{content['id']}/download", headers=headers)
        # 404 is expected — no file was uploaded, but audit log should exist
        assert resp.status_code in (200, 404)

        from app.models.audit_log import AuditLog
        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_download",
            AuditLog.resource_type == "course_content",
            AuditLog.resource_id == content["id"],
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        assert entry.user_id == users["teacher"].id

    def test_denied_download_creates_audit_entry(self, client, db_session, users):
        content = _create_content_on_private_course(db_session, users)
        headers = _auth(client, users["other"].email)

        resp = client.get(f"/api/course-contents/{content.id}/download", headers=headers)
        assert resp.status_code == 403

        from app.models.audit_log import AuditLog
        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_download",
            AuditLog.resource_id == content.id,
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        details = json.loads(entry.details)
        assert details["denied"] is True


class TestMaterialUploadAudit:
    def test_upload_creates_audit_entry(self, client, db_session, users):
        headers = _auth(client, users["teacher"].email)

        resp = client.post(
            "/api/course-contents/upload",
            headers=headers,
            data={"course_id": str(users["course"].id), "title": "Upload Audit Test"},
            files={"file": ("test.txt", b"Hello audit world", "text/plain")},
        )
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        from app.models.audit_log import AuditLog
        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_upload",
            AuditLog.resource_type == "course_content",
            AuditLog.resource_id == content_id,
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        assert entry.user_id == users["teacher"].id
        details = json.loads(entry.details)
        assert details["course_id"] == users["course"].id
        assert details["filename"] == "test.txt"
        assert details["file_size"] == 17

    def test_upload_multi_creates_audit_entry(self, client, db_session, users):
        headers = _auth(client, users["teacher"].email)

        resp = client.post(
            "/api/course-contents/upload-multi",
            headers=headers,
            data={"course_id": str(users["course"].id), "title": "Multi Audit Test"},
            files=[
                ("files", ("a.txt", b"file one", "text/plain")),
                ("files", ("b.txt", b"file two", "text/plain")),
            ],
        )
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        from app.models.audit_log import AuditLog
        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_upload",
            AuditLog.resource_type == "course_content",
            AuditLog.resource_id == content_id,
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        assert entry.user_id == users["teacher"].id
        details = json.loads(entry.details)
        assert details["file_count"] == 2


class TestAuditEntryDetails:
    def test_audit_entry_has_ip_and_user_agent(self, client, db_session, users):
        content = _create_content(client, users)
        headers = _auth(client, users["teacher"].email)
        headers["User-Agent"] = "TestAgent/1.0"

        resp = client.get(f"/api/course-contents/{content['id']}", headers=headers)
        assert resp.status_code == 200

        from app.models.audit_log import AuditLog
        db_session.expire_all()
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "material_view",
            AuditLog.resource_id == content["id"],
        ).order_by(AuditLog.id.desc()).first()

        assert entry is not None
        assert entry.ip_address is not None
        assert entry.user_agent is not None
