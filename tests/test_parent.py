import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from sqlalchemy import insert

    parent = db_session.query(User).filter(User.email == "par_parent@test.com").first()
    if parent:
        student = db_session.query(User).filter(User.email == "par_student@test.com").first()
        teacher = db_session.query(User).filter(User.email == "par_teacher@test.com").first()
        outsider = db_session.query(User).filter(User.email == "par_outsider@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student.id).first()
        teacher_rec = db_session.query(Teacher).filter(Teacher.user_id == teacher.id).first()
        course = db_session.query(Course).filter(Course.name == "Par Test Course").first()
        return {
            "parent": parent, "student": student, "teacher": teacher, "outsider": outsider,
            "student_rec": student_rec, "teacher_rec": teacher_rec, "course": course,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="par_parent@test.com", full_name="Par Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email="par_student@test.com", full_name="Par Student", role=UserRole.STUDENT, hashed_password=hashed)
    teacher = User(email="par_teacher@test.com", full_name="Par Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    outsider = User(email="par_outsider@test.com", full_name="Par Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, student, teacher, outsider])
    db_session.flush()

    student_rec = Student(user_id=student.id)
    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add_all([student_rec, teacher_rec])
    db_session.flush()

    # Link parent → student
    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    # Create a public course owned by teacher, enroll student
    course = Course(name="Par Test Course", teacher_id=teacher_rec.id,
                    created_by_user_id=teacher.id, is_private=False)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(
        student_id=student_rec.id, course_id=course.id,
    ))
    db_session.commit()

    for u in [parent, student, teacher, outsider]:
        db_session.refresh(u)
    db_session.refresh(student_rec)
    db_session.refresh(teacher_rec)
    db_session.refresh(course)

    return {
        "parent": parent, "student": student, "teacher": teacher, "outsider": outsider,
        "student_rec": student_rec, "teacher_rec": teacher_rec, "course": course,
    }


# ── List children ─────────────────────────────────────────────

class TestListChildren:
    def test_parent_sees_linked_children(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/parent/children", headers=headers)
        assert resp.status_code == 200
        children = resp.json()
        assert len(children) >= 1
        assert any(c["full_name"] == "Par Student" for c in children)

    def test_no_children_returns_empty(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.get("/api/parent/children", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_non_parent_rejected(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/parent/children", headers=headers)
        assert resp.status_code == 403

    def test_pending_child_has_invite_link_with_token(self, client, users):
        """Regression: invite_link must include the token so the copied URL works."""
        headers = _auth(client, users["parent"].email)
        # Create a child with email (generates a pending invite)
        create_resp = client.post("/api/parent/children/create", json={
            "full_name": "Invite Link Kid", "email": "invite_link_regression@test.com",
        }, headers=headers)
        assert create_resp.status_code == 200

        # Fetch children list — the pending child must have invite_link with token
        list_resp = client.get("/api/parent/children", headers=headers)
        assert list_resp.status_code == 200
        children = list_resp.json()
        pending = next((c for c in children if c["email"] == "invite_link_regression@test.com"), None)
        assert pending is not None, "Invited child not found in children list"
        assert pending["invite_status"] == "pending"
        invite_link = pending.get("invite_link")
        assert invite_link is not None, "invite_link must be populated for pending children"
        assert "token=" in invite_link, f"invite_link missing token param: {invite_link}"
        assert "/accept-invite" in invite_link, f"invite_link missing /accept-invite path: {invite_link}"


# ── Create child ──────────────────────────────────────────────

class TestCreateChild:
    def test_create_with_name_only(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/create", json={
            "full_name": "New Kid",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "New Kid"
        assert data["relationship_type"] == "guardian"

    def test_create_with_email(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/create", json={
            "full_name": "Email Kid", "email": "par_email_kid@test.com",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Email Kid"
        assert data.get("invite_link") is not None

    def test_duplicate_email_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/create", json={
            "full_name": "Dup Kid", "email": users["student"].email,
        }, headers=headers)
        assert resp.status_code == 400

    def test_non_parent_rejected(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/parent/children/create", json={
            "full_name": "Bad Create",
        }, headers=headers)
        assert resp.status_code == 403


# ── Link child ────────────────────────────────────────────────

class TestLinkChild:
    def test_link_existing_student(self, client, users, db_session):
        """Create a fresh unlinked student, then link them."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.student import Student

        email = "par_linkable@test.com"
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email, full_name="Linkable", role=UserRole.STUDENT,
                     hashed_password=get_password_hash(PASSWORD))
            db_session.add(u)
            db_session.flush()
            db_session.add(Student(user_id=u.id))
            db_session.commit()

        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/link", json={
            "student_email": email,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Linkable"

    def test_auto_create_if_not_found(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/link", json={
            "student_email": "par_autocreate@test.com",
        }, headers=headers)
        assert resp.status_code == 200

    def test_non_student_email_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/link", json={
            "student_email": users["teacher"].email,
        }, headers=headers)
        assert resp.status_code == 400
        assert "non-student" in resp.json()["detail"].lower()

    def test_already_linked_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/parent/children/link", json={
            "student_email": users["student"].email,
        }, headers=headers)
        assert resp.status_code == 400
        assert "already linked" in resp.json()["detail"].lower()


# ── Child overview ────────────────────────────────────────────

class TestChildOverview:
    def test_get_overview(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(
            f"/api/parent/children/{users['student_rec'].id}/overview",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Par Student"
        assert "courses" in data
        assert "assignments" in data
        assert "study_guides_count" in data

    def test_unlinked_child_returns_404(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.get(
            f"/api/parent/children/{users['student_rec'].id}/overview",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_nonexistent_student_returns_404(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/parent/children/999999/overview", headers=headers)
        assert resp.status_code == 404


# ── Update child ──────────────────────────────────────────────

class TestUpdateChild:
    def test_update_name(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.patch(
            f"/api/parent/children/{users['student_rec'].id}",
            json={"full_name": "Updated Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

        # Restore original name
        client.patch(
            f"/api/parent/children/{users['student_rec'].id}",
            json={"full_name": "Par Student"},
            headers=headers,
        )

    def test_update_grade_and_school(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.patch(
            f"/api/parent/children/{users['student_rec'].id}",
            json={"grade_level": 10, "school_name": "Test High"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["grade_level"] == 10
        assert resp.json()["school_name"] == "Test High"

    def test_unlinked_child_returns_404(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.patch(
            f"/api/parent/children/{users['student_rec'].id}",
            json={"full_name": "Hijacked"},
            headers=headers,
        )
        assert resp.status_code == 404


# ── Assign / unassign courses ────────────────────────────────

class TestAssignCourses:
    def test_assign_public_course(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/courses",
            json={"course_ids": [users["course"].id]},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_assign_own_private_course(self, client, users, db_session):
        from app.models.course import Course

        # Create private course owned by parent
        course = Course(name="Par Private", created_by_user_id=users["parent"].id, is_private=True)
        db_session.add(course)
        db_session.commit()
        db_session.refresh(course)

        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/courses",
            json={"course_ids": [course.id]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(a["course_id"] == course.id for a in data.get("assigned", []))

    def test_assign_coparent_private_course(self, client, users, db_session):
        """Regression: co-parent's private course should be assignable (#1101)."""
        from sqlalchemy import insert
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.course import Course
        from app.models.student import parent_students, RelationshipType

        hashed = get_password_hash("Test1234!")
        co_parent = User(email="par_coparent@test.com", full_name="Co Parent", role=UserRole.PARENT, hashed_password=hashed)
        db_session.add(co_parent)
        db_session.flush()

        # Link co-parent to the same student
        db_session.execute(insert(parent_students).values(
            parent_id=co_parent.id, student_id=users["student_rec"].id,
            relationship_type=RelationshipType.GUARDIAN,
        ))

        # Co-parent's private course (like their "Main Class")
        co_course = Course(name="Co-Parent Main Class", created_by_user_id=co_parent.id, is_private=True)
        db_session.add(co_course)
        db_session.commit()
        db_session.refresh(co_course)

        # Original parent should be able to assign co-parent's private course
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/courses",
            json={"course_ids": [co_course.id]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(a["course_id"] == co_course.id for a in data.get("assigned", []))

    def test_assign_child_private_course(self, client, users, db_session):
        """Regression: child's private course should be assignable (#1101)."""
        from app.models.course import Course

        # Child-created private course
        child_course = Course(name="Child Main Class", created_by_user_id=users["student"].id, is_private=True)
        db_session.add(child_course)
        db_session.commit()
        db_session.refresh(child_course)

        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/courses",
            json={"course_ids": [child_course.id]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(a["course_id"] == child_course.id for a in data.get("assigned", []))

    def test_unassign_course(self, client, users, db_session):
        from app.models.course import Course, student_courses
        from sqlalchemy import insert

        # Create a course and enroll student
        course = Course(name="Par Unassign Target", created_by_user_id=users["parent"].id, is_private=True)
        db_session.add(course)
        db_session.flush()
        db_session.execute(insert(student_courses).values(
            student_id=users["student_rec"].id, course_id=course.id,
        ))
        db_session.commit()
        db_session.refresh(course)

        headers = _auth(client, users["parent"].email)
        resp = client.delete(
            f"/api/parent/children/{users['student_rec'].id}/courses/{course.id}",
            headers=headers,
        )
        assert resp.status_code == 200

    def test_unassign_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.delete(
            f"/api/parent/children/{users['student_rec'].id}/courses/999999",
            headers=headers,
        )
        assert resp.status_code == 404


# ── Link / unlink teachers ───────────────────────────────────

class TestLinkTeacher:
    def test_link_teacher_by_email(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": users["teacher"].email},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["teacher_email"] == users["teacher"].email
        assert data["teacher_user_id"] == users["teacher"].id
        assert data["teacher_name"] == "Par Teacher"

    def test_link_teacher_with_custom_name(self, client, users, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.teacher import Teacher

        email = "par_custom_teacher@test.com"
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email, full_name="Custom Teacher", role=UserRole.TEACHER,
                     hashed_password=get_password_hash(PASSWORD))
            db_session.add(u)
            db_session.flush()
            db_session.add(Teacher(user_id=u.id))
            db_session.commit()

        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": email, "teacher_name": "My Custom Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["teacher_name"] == "My Custom Name"

    def test_duplicate_link_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Ensure teacher is already linked (from test_link_teacher_by_email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": users["teacher"].email},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "already linked" in resp.json()["detail"].lower()

    def test_non_teacher_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": users["outsider"].email},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not a teacher" in resp.json()["detail"].lower()

    def test_list_linked_teachers(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            headers=headers,
        )
        assert resp.status_code == 200
        teachers = resp.json()
        assert isinstance(teachers, list)
        assert any(t["teacher_email"] == users["teacher"].email for t in teachers)

    def test_unlink_teacher(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Get the link ID
        resp = client.get(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            headers=headers,
        )
        teachers = resp.json()
        link = next(t for t in teachers if t["teacher_email"] == users["teacher"].email)

        resp = client.delete(
            f"/api/parent/children/{users['student_rec'].id}/teachers/{link['id']}",
            headers=headers,
        )
        assert resp.status_code == 200

    def test_unlink_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.delete(
            f"/api/parent/children/{users['student_rec'].id}/teachers/999999",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_outsider_cannot_link(self, client, users):
        headers = _auth(client, users["outsider"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": users["teacher"].email},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_link_sends_notification_to_existing_teacher(self, client, users, db_session, monkeypatch):
        """When a registered teacher is linked, a notification email is sent."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.teacher import Teacher

        # Create a fresh teacher to avoid conflicts with other tests
        email = "par_notif_teacher@test.com"
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email, full_name="Notif Teacher", role=UserRole.TEACHER,
                     hashed_password=get_password_hash(PASSWORD))
            db_session.add(u)
            db_session.flush()
            db_session.add(Teacher(user_id=u.id))
            db_session.commit()

        emails_sent = []

        def mock_send(**kwargs):
            emails_sent.append(kwargs)
            return True

        monkeypatch.setattr("app.api.routes.parent.send_email_sync", mock_send)

        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": email},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["teacher_user_id"] == u.id

        # Notification email should have been sent to the teacher
        assert len(emails_sent) == 1
        assert emails_sent[0]["to_email"] == email
        assert "connected" in emails_sent[0]["subject"].lower() or "classbridge" in emails_sent[0]["subject"].lower()

        # In-app notification should exist
        from app.models.notification import Notification
        notif = db_session.query(Notification).filter(
            Notification.user_id == u.id,
            Notification.title == "New Parent Connection",
        ).first()
        assert notif is not None

    def test_link_sends_invite_to_unknown_teacher(self, client, users, db_session, monkeypatch):
        """When a teacher email is not in the system, an invite is created and email sent."""
        emails_sent = []

        def mock_send(**kwargs):
            emails_sent.append(kwargs)
            return True

        monkeypatch.setattr("app.api.routes.parent.send_email_sync", mock_send)

        unknown_email = "par_unknown_teacher@test.com"
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": unknown_email, "teacher_name": "Unknown Teacher"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["teacher_user_id"] is None
        assert data["teacher_name"] == "Unknown Teacher"

        # Invite email should have been sent
        assert len(emails_sent) == 1
        assert emails_sent[0]["to_email"] == unknown_email
        assert "invited" in emails_sent[0]["subject"].lower()

        # Invite record should exist in the database
        from app.models.invite import Invite, InviteType
        invite = db_session.query(Invite).filter(
            Invite.email == unknown_email,
            Invite.invite_type == InviteType.TEACHER,
        ).first()
        assert invite is not None
        assert invite.accepted_at is None

    def test_accept_invite_backfills_teacher_user_id(self, client, users, db_session, monkeypatch):
        """When an invited teacher accepts, student_teachers.teacher_user_id is backfilled."""
        emails_sent = []

        def mock_send(**kwargs):
            emails_sent.append(kwargs)
            return True

        monkeypatch.setattr("app.api.routes.parent.send_email_sync", mock_send)

        invite_email = "par_backfill_teacher@test.com"
        headers = _auth(client, users["parent"].email)

        # Link teacher who doesn't exist
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/teachers",
            json={"teacher_email": invite_email, "teacher_name": "Backfill Teacher"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["teacher_user_id"] is None

        # Find the invite token
        from app.models.invite import Invite, InviteType
        invite = db_session.query(Invite).filter(
            Invite.email == invite_email,
            Invite.invite_type == InviteType.TEACHER,
        ).first()
        assert invite is not None

        # Accept the invite — this creates the teacher user
        resp = client.post("/api/auth/accept-invite", json={
            "token": invite.token,
            "full_name": "Backfill Teacher",
            "password": PASSWORD,
        })
        assert resp.status_code == 200

        # Verify token returned (teacher is logged in)
        assert "access_token" in resp.json()

        # Check that student_teachers.teacher_user_id was backfilled
        from app.models.student import student_teachers
        from app.models.user import User
        new_user = db_session.query(User).filter(User.email == invite_email).first()
        assert new_user is not None

        db_session.expire_all()
        row = db_session.query(student_teachers).filter(
            student_teachers.c.teacher_email == invite_email,
        ).first()
        assert row is not None
        assert row.teacher_user_id == new_user.id


# ── Request completion (#549) ────────────────────────────────

class TestRequestCompletion:
    """Tests for POST /api/parent/children/{student_id}/request-completion."""

    @pytest.fixture()
    def task_for_student(self, users, db_session):
        """Create a pending task assigned to the linked student."""
        from app.models.task import Task
        task = Task(
            title="Test Homework",
            description="Complete the math worksheet",
            created_by_user_id=users["parent"].id,
            assigned_to_user_id=users["student"].id,
            priority="medium",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    @pytest.fixture()
    def completed_task(self, users, db_session):
        """Create an already-completed task."""
        from app.models.task import Task
        from datetime import datetime, timezone
        task = Task(
            title="Already Done",
            created_by_user_id=users["parent"].id,
            assigned_to_user_id=users["student"].id,
            is_completed=True,
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    def test_request_completion_success(self, client, users, task_for_student):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": task_for_student.id},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert task_for_student.title in data["message"]

    def test_request_completion_with_message(self, client, users, task_for_student):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": task_for_student.id, "message": "Please finish before dinner!"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_request_completion_creates_notification(self, client, users, task_for_student, db_session):
        from app.models.notification import Notification

        # Count existing notifications before request
        before_count = db_session.query(Notification).filter(
            Notification.user_id == users["student"].id,
            Notification.title == "Parent Completion Request",
        ).count()

        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": task_for_student.id, "message": "Please do this now"},
            headers=headers,
        )
        assert resp.status_code == 200

        db_session.expire_all()
        notif = db_session.query(Notification).filter(
            Notification.user_id == users["student"].id,
            Notification.title == "Parent Completion Request",
            Notification.content.contains("Please do this now"),
        ).first()
        assert notif is not None
        assert task_for_student.title in notif.content

        # Verify a new notification was actually created
        after_count = db_session.query(Notification).filter(
            Notification.user_id == users["student"].id,
            Notification.title == "Parent Completion Request",
        ).count()
        assert after_count > before_count

    def test_non_parent_rejected(self, client, users, task_for_student):
        headers = _auth(client, users["student"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": task_for_student.id},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_unlinked_child_rejected(self, client, users, task_for_student):
        headers = _auth(client, users["outsider"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": task_for_student.id},
            headers=headers,
        )
        assert resp.status_code == 404
        assert "not linked" in resp.json()["detail"].lower()

    def test_task_not_found(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": 999999},
            headers=headers,
        )
        assert resp.status_code == 404
        assert "task" in resp.json()["detail"].lower()

    def test_task_not_assigned_to_student(self, client, users, db_session):
        """Task assigned to someone else should be rejected."""
        from app.models.task import Task
        task = Task(
            title="Someone Else Task",
            created_by_user_id=users["parent"].id,
            assigned_to_user_id=users["parent"].id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": task.id},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not assigned" in resp.json()["detail"].lower()

    def test_already_completed_task_rejected(self, client, users, completed_task):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            f"/api/parent/children/{users['student_rec'].id}/request-completion",
            json={"task_id": completed_task.id},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "already completed" in resp.json()["detail"].lower()

    def test_nonexistent_student_rejected(self, client, users, task_for_student):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            "/api/parent/children/999999/request-completion",
            json={"task_id": task_for_student.id},
            headers=headers,
        )
        assert resp.status_code == 404
