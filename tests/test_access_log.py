"""Tests for GET /api/course-contents/{id}/access-log endpoint (#2273)."""
import pytest
from conftest import PASSWORD, _auth


def _register(client, email, role="teacher", full_name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


def _create_course_and_content(client, db_session, teacher_headers, teacher_email):
    """Helper: create a course and content item owned by the teacher."""
    from app.models.user import User
    teacher = db_session.query(User).filter(User.email == teacher_email).first()

    resp = client.post("/api/courses", json={"name": "Access Log Test Course"}, headers=teacher_headers)
    assert resp.status_code == 200, resp.text
    course_id = resp.json()["id"]

    resp = client.post("/api/course-contents", json={
        "course_id": course_id,
        "title": "Test Material",
        "content_type": "notes",
    }, headers=teacher_headers)
    assert resp.status_code in (200, 201), resp.text
    content_id = resp.json()["id"]
    return course_id, content_id, teacher


def _insert_audit_log(db_session, user_id, content_id, action="read"):
    """Insert audit log entries for testing."""
    from app.models.audit_log import AuditLog
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type="course_content",
        resource_id=content_id,
        ip_address="127.0.0.1",
    )
    db_session.add(entry)
    db_session.commit()
    return entry


class TestAccessLogOwnerAccess:
    def test_owner_can_view_access_log(self, client, db_session):
        email = "accesslog-owner@test.com"
        _register(client, email, role="teacher", full_name="Owner Teacher")
        headers = _auth(client, email)
        course_id, content_id, teacher = _create_course_and_content(
            client, db_session, headers, email
        )

        # Insert some audit log entries
        from app.models.user import User
        viewer = db_session.query(User).filter(User.email == email).first()
        _insert_audit_log(db_session, viewer.id, content_id, action="read")
        _insert_audit_log(db_session, viewer.id, content_id, action="material_download")

        resp = client.get(f"/api/course-contents/{content_id}/access-log", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_id"] == content_id
        assert data["content_title"] == "Test Material"
        assert len(data["access_log"]) == 2
        assert data["total_views"] == 1
        assert data["total_downloads"] == 1
        assert data["unique_viewers"] == 1

    def test_non_owner_gets_403(self, client, db_session):
        owner_email = "accesslog-owner2@test.com"
        other_email = "accesslog-other@test.com"
        _register(client, owner_email, role="teacher", full_name="Owner")
        _register(client, other_email, role="teacher", full_name="Other")

        owner_headers = _auth(client, owner_email)
        other_headers = _auth(client, other_email)

        _, content_id, _ = _create_course_and_content(
            client, db_session, owner_headers, owner_email
        )

        resp = client.get(f"/api/course-contents/{content_id}/access-log", headers=other_headers)
        assert resp.status_code == 403

    def test_access_log_not_found(self, client, db_session):
        email = "accesslog-notfound@test.com"
        _register(client, email, role="teacher")
        headers = _auth(client, email)
        resp = client.get("/api/course-contents/99999/access-log", headers=headers)
        assert resp.status_code == 404


class TestAccessLogFiltering:
    def test_filter_by_action(self, client, db_session):
        email = "accesslog-filter@test.com"
        _register(client, email, role="teacher", full_name="Filter Teacher")
        headers = _auth(client, email)
        _, content_id, teacher = _create_course_and_content(
            client, db_session, headers, email
        )

        from app.models.user import User
        user = db_session.query(User).filter(User.email == email).first()
        _insert_audit_log(db_session, user.id, content_id, action="read")
        _insert_audit_log(db_session, user.id, content_id, action="material_download")

        resp = client.get(
            f"/api/course-contents/{content_id}/access-log?action=material_download",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["access_log"]) == 1
        assert data["access_log"][0]["action"] == "material_download"

    def test_days_param_validation(self, client, db_session):
        email = "accesslog-days@test.com"
        _register(client, email, role="teacher")
        headers = _auth(client, email)
        _, content_id, _ = _create_course_and_content(
            client, db_session, headers, email
        )

        # days=0 should fail validation (ge=1)
        resp = client.get(
            f"/api/course-contents/{content_id}/access-log?days=0",
            headers=headers,
        )
        assert resp.status_code == 422

        # days=366 should fail validation (le=365)
        resp = client.get(
            f"/api/course-contents/{content_id}/access-log?days=366",
            headers=headers,
        )
        assert resp.status_code == 422


class TestAccessLogParentAccess:
    def test_parent_of_student_creator_can_view(self, client, db_session):
        """Parent of a student content creator should be able to view access logs."""
        from app.models.user import User, UserRole
        from app.models.student import Student
        from app.core.security import get_password_hash

        # Create student user
        student_email = "accesslog-student-creator@test.com"
        _register(client, student_email, role="student", full_name="Student Creator")
        student_user = db_session.query(User).filter(User.email == student_email).first()

        # Create parent user
        parent_email = "accesslog-parent@test.com"
        _register(client, parent_email, role="parent", full_name="Parent User")
        parent_user = db_session.query(User).filter(User.email == parent_email).first()

        # Create student record and link parent
        student_record = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        if not student_record:
            student_record = Student(user_id=student_user.id)
            db_session.add(student_record)
            db_session.commit()
            db_session.refresh(student_record)

        student_record.parents.append(parent_user)
        db_session.commit()

        # Create content as student
        student_headers = _auth(client, student_email)
        resp = client.post("/api/courses", json={"name": "Student Course"}, headers=student_headers)
        assert resp.status_code in (200, 201)
        course_id = resp.json()["id"]

        resp = client.post("/api/course-contents", json={
            "course_id": course_id,
            "title": "Student Notes",
            "content_type": "notes",
        }, headers=student_headers)
        assert resp.status_code in (200, 201)
        content_id = resp.json()["id"]

        _insert_audit_log(db_session, parent_user.id, content_id, action="read")

        # Parent should be able to view access log
        parent_headers = _auth(client, parent_email)
        resp = client.get(f"/api/course-contents/{content_id}/access-log", headers=parent_headers)
        assert resp.status_code == 200
        assert resp.json()["content_id"] == content_id
