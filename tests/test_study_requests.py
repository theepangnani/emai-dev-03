import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from sqlalchemy import insert

    parent = db_session.query(User).filter(User.email == "sr_parent@test.com").first()
    if parent:
        student = db_session.query(User).filter(User.email == "sr_student@test.com").first()
        outsider = db_session.query(User).filter(User.email == "sr_outsider@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student.id).first()
        return {
            "parent": parent, "student": student, "outsider": outsider,
            "student_rec": student_rec,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="sr_parent@test.com", full_name="SR Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email="sr_student@test.com", full_name="SR Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="sr_outsider@test.com", full_name="SR Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, student, outsider])
    db_session.flush()

    student_rec = Student(user_id=student.id)
    db_session.add(student_rec)
    db_session.flush()

    # Link parent -> student
    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))
    db_session.commit()

    for u in [parent, student, outsider]:
        db_session.refresh(u)
    db_session.refresh(student_rec)

    return {
        "parent": parent, "student": student, "outsider": outsider,
        "student_rec": student_rec,
    }


class TestCreateStudyRequest:
    def test_parent_creates_request(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "Math",
            "topic": "Fractions",
            "urgency": "normal",
            "message": "Please review before Friday",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "Math"
        assert data["topic"] == "Fractions"
        assert data["urgency"] == "normal"
        assert data["status"] == "pending"
        assert data["parent_id"] == users["parent"].id
        assert data["student_id"] == users["student"].id

    def test_outsider_cannot_create(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "Science",
        }, headers=headers)
        assert resp.status_code == 403

    def test_student_cannot_create(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "English",
        }, headers=headers)
        assert resp.status_code == 403

    def test_notification_created_for_student(self, client, users, db_session):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "History",
        }, headers=headers)
        assert resp.status_code == 200

        from app.models.notification import Notification
        notif = db_session.query(Notification).filter(
            Notification.user_id == users["student"].id,
            Notification.source_type == "study_request",
            Notification.source_id == resp.json()["id"],
        ).first()
        assert notif is not None
        assert "History" in notif.title


class TestListStudyRequests:
    def test_parent_sees_sent(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Create one first
        client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "ListTest",
        }, headers=headers)

        resp = client.get("/api/study-requests", headers=headers)
        assert resp.status_code == 200
        subjects = [r["subject"] for r in resp.json()]
        assert "ListTest" in subjects

    def test_student_sees_received(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "StudentView",
        }, headers=parent_headers)

        student_headers = _auth(client, users["student"].email)
        resp = client.get("/api/study-requests", headers=student_headers)
        assert resp.status_code == 200
        subjects = [r["subject"] for r in resp.json()]
        assert "StudentView" in subjects


class TestRespondStudyRequest:
    def test_student_accepts(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "AcceptTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        student_headers = _auth(client, users["student"].email)
        resp = client.patch(f"/api/study-requests/{sr_id}/respond", json={
            "status": "accepted",
            "response": "On it!",
        }, headers=student_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"
        assert resp.json()["student_response"] == "On it!"

    def test_student_defers(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "DeferTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        student_headers = _auth(client, users["student"].email)
        resp = client.patch(f"/api/study-requests/{sr_id}/respond", json={
            "status": "deferred",
        }, headers=student_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deferred"

    def test_parent_cannot_respond(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "ParentRespondTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        resp = client.patch(f"/api/study-requests/{sr_id}/respond", json={
            "status": "accepted",
        }, headers=parent_headers)
        assert resp.status_code == 403

    def test_outsider_cannot_respond(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "OutsiderRespondTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        outsider_headers = _auth(client, users["outsider"].email)
        resp = client.patch(f"/api/study-requests/{sr_id}/respond", json={
            "status": "accepted",
        }, headers=outsider_headers)
        assert resp.status_code == 403

    def test_notification_created_for_parent_on_response(self, client, users, db_session):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "NotifResponseTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        student_headers = _auth(client, users["student"].email)
        client.patch(f"/api/study-requests/{sr_id}/respond", json={
            "status": "completed",
        }, headers=student_headers)

        from app.models.notification import Notification
        notif = db_session.query(Notification).filter(
            Notification.user_id == users["parent"].id,
            Notification.source_type == "study_request",
            Notification.source_id == sr_id,
        ).first()
        assert notif is not None
        assert "marked as done" in notif.title


class TestPendingCount:
    def test_student_pending_count(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "PendingCount1",
        }, headers=parent_headers)

        student_headers = _auth(client, users["student"].email)
        resp = client.get("/api/study-requests/pending", headers=student_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1


class TestGetStudyRequest:
    def test_parent_can_view(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "ViewTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        resp = client.get(f"/api/study-requests/{sr_id}", headers=parent_headers)
        assert resp.status_code == 200
        assert resp.json()["subject"] == "ViewTest"

    def test_student_can_view(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "StudentViewTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        student_headers = _auth(client, users["student"].email)
        resp = client.get(f"/api/study-requests/{sr_id}", headers=student_headers)
        assert resp.status_code == 200

    def test_outsider_cannot_view(self, client, users):
        parent_headers = _auth(client, users["parent"].email)
        create_resp = client.post("/api/study-requests", json={
            "student_id": users["student"].id,
            "subject": "OutsiderViewTest",
        }, headers=parent_headers)
        sr_id = create_resp.json()["id"]

        outsider_headers = _auth(client, users["outsider"].email)
        resp = client.get(f"/api/study-requests/{sr_id}", headers=outsider_headers)
        assert resp.status_code == 403
