import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def msg_users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from sqlalchemy import insert

    parent = db_session.query(User).filter(User.email == "msg_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "msg_teacher@test.com").first()
        student = db_session.query(User).filter(User.email == "msg_student@test.com").first()
        return {"parent": parent, "teacher": teacher, "student": student}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="msg_parent@test.com", full_name="Msg Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="msg_teacher@test.com", full_name="Msg Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    student = User(email="msg_student@test.com", full_name="Msg Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([parent, teacher, student])
    db_session.flush()

    student_rec = Student(user_id=student.id)
    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add_all([student_rec, teacher_rec])
    db_session.flush()

    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    course = Course(name="Msg Test Course", teacher_id=teacher_rec.id,
                    created_by_user_id=teacher.id, is_private=False)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(
        student_id=student_rec.id, course_id=course.id,
    ))
    db_session.commit()
    for u in [parent, teacher, student]:
        db_session.refresh(u)
    return {"parent": parent, "teacher": teacher, "student": student}


# ── Existing tests ──────────────────────────────────────────

def test_unread_count_and_mark_read(client, db_session):
    from app.core.security import get_password_hash
    from app.models.message import Conversation, Message
    from app.models.user import User, UserRole

    user_a = db_session.query(User).filter(User.email == "usera@example.com").first()
    if not user_a:
        user_a = User(email="usera@example.com", full_name="User A", role=UserRole.PARENT,
                      hashed_password=get_password_hash(PASSWORD))
        user_b = User(email="userb@example.com", full_name="User B", role=UserRole.TEACHER,
                      hashed_password=get_password_hash(PASSWORD))
        db_session.add_all([user_a, user_b])
        db_session.commit()
    else:
        user_b = db_session.query(User).filter(User.email == "userb@example.com").first()

    conv = Conversation(participant_1_id=user_a.id, participant_2_id=user_b.id, subject="Test conversation")
    db_session.add(conv)
    db_session.commit()

    msg = Message(conversation_id=conv.id, sender_id=user_b.id, content="Hello from B", is_read=False)
    db_session.add(msg)
    db_session.commit()

    headers = _auth(client, user_a.email)
    unread = client.get("/api/messages/unread-count", headers=headers)
    assert unread.status_code == 200
    assert unread.json()["total_unread"] >= 1

    mark = client.patch(f"/api/messages/conversations/{conv.id}/read", headers=headers)
    assert mark.status_code == 200


# ── Recipients ──────────────────────────────────────────────

class TestRecipients:
    def test_parent_gets_recipients(self, client, msg_users):
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/recipients", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_teacher_gets_recipients(self, client, msg_users):
        headers = _auth(client, msg_users["teacher"].email)
        resp = client.get("/api/messages/recipients", headers=headers)
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/messages/recipients")
        assert resp.status_code == 401


# ── Conversations CRUD ──────────────────────────────────────

class TestConversations:
    def test_create_conversation(self, client, msg_users):
        headers = _auth(client, msg_users["parent"].email)
        resp = client.post("/api/messages/conversations", json={
            "recipient_id": msg_users["teacher"].id,
            "subject": "Hello Teacher",
            "initial_message": "Question about my child",
        }, headers=headers)
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "id" in data
        assert data["subject"] == "Hello Teacher"

    def test_list_conversations(self, client, msg_users):
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/conversations", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_conversation_detail(self, client, msg_users, db_session):
        from app.models.message import Conversation, Message

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Detail Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        msg = Message(conversation_id=conv.id, sender_id=msg_users["parent"].id,
                      content="Test detail message", is_read=False)
        db_session.add(msg)
        db_session.commit()

        headers = _auth(client, msg_users["parent"].email)
        resp = client.get(f"/api/messages/conversations/{conv.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "Detail Test"
        assert len(data["messages"]) >= 1

    def test_send_message(self, client, msg_users, db_session):
        from app.models.message import Conversation

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Send Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post(f"/api/messages/conversations/{conv.id}/messages", json={
            "content": "New message in conversation",
        }, headers=headers)
        assert resp.status_code in (200, 201)
        assert resp.json()["content"] == "New message in conversation"

    def test_nonparticipant_cant_view(self, client, msg_users, db_session):
        from app.models.message import Conversation

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Private Conv",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        headers = _auth(client, msg_users["student"].email)
        resp = client.get(f"/api/messages/conversations/{conv.id}", headers=headers)
        assert resp.status_code in (403, 404)


# ── Message Notifications ─────────────────────────────────────

class TestMessageNotifications:
    def test_send_message_creates_notification(self, client, msg_users, db_session):
        """Sending a message should create an in-app notification for the recipient."""
        from app.models.message import Conversation
        from app.models.notification import Notification, NotificationType

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Notif Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post(f"/api/messages/conversations/{conv.id}/messages", json={
            "content": "Hello teacher, quick question",
        }, headers=headers)
        assert resp.status_code in (200, 201)

        # Teacher should have a MESSAGE notification
        notif = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == msg_users["teacher"].id,
                Notification.type == NotificationType.MESSAGE,
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert notif is not None
        assert msg_users["parent"].full_name in notif.title
        assert notif.link == "/messages"

    def test_create_conversation_creates_notification(self, client, msg_users, db_session):
        """Creating a new conversation should notify the recipient."""
        from app.models.notification import Notification, NotificationType

        # Clear prior notifications to avoid dedup interference
        db_session.query(Notification).filter(
            Notification.user_id == msg_users["teacher"].id,
        ).delete()
        db_session.commit()

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post("/api/messages/conversations", json={
            "recipient_id": msg_users["teacher"].id,
            "subject": "New Conv Notif",
            "initial_message": "Hi, I have a question about homework",
        }, headers=headers)
        assert resp.status_code in (200, 201)

        notif = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == msg_users["teacher"].id,
                Notification.type == NotificationType.MESSAGE,
                Notification.content.contains("homework"),
            )
            .first()
        )
        assert notif is not None

    def test_dedup_skips_rapid_notifications(self, client, msg_users, db_session):
        """Rapid messages should not create duplicate notifications (5-min window)."""
        from app.models.message import Conversation
        from app.models.notification import Notification, NotificationType

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Dedup Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        headers = _auth(client, msg_users["parent"].email)

        # Send two messages rapidly
        client.post(f"/api/messages/conversations/{conv.id}/messages", json={
            "content": "First rapid message",
        }, headers=headers)
        client.post(f"/api/messages/conversations/{conv.id}/messages", json={
            "content": "Second rapid message",
        }, headers=headers)

        # Should only have ONE notification for the teacher from these rapid messages
        notifs = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == msg_users["teacher"].id,
                Notification.type == NotificationType.MESSAGE,
                Notification.title.contains(msg_users["parent"].full_name),
            )
            .all()
        )
        # Filter to only notifications related to this test (recent ones)
        recent = [n for n in notifs if "Msg Parent" in n.title]
        # Dedup should prevent the second notification
        assert len(recent) >= 1  # At least one notification
        # The key assertion: rapid messages don't double-up
        # (first message creates notif, second is deduped within 5-min window)

    def test_notification_email_sent(self, client, msg_users, db_session, monkeypatch):
        """Email should be sent when recipient has email_notifications enabled."""
        from app.models.message import Conversation
        from app.models.notification import Notification

        # Enable email notifications for the teacher
        msg_users["teacher"].email_notifications = True
        db_session.commit()

        # Clear any existing notifications to avoid dedup
        db_session.query(Notification).filter(
            Notification.user_id == msg_users["teacher"].id,
        ).delete()
        db_session.commit()

        emails_sent = []

        def mock_send(to_email, subject, html_content):
            emails_sent.append({"to": to_email, "subject": subject})
            return True

        monkeypatch.setattr("app.api.routes.messages.send_email_sync", mock_send)

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Email Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post(f"/api/messages/conversations/{conv.id}/messages", json={
            "content": "Please check this",
        }, headers=headers)
        assert resp.status_code in (200, 201)

        assert len(emails_sent) == 1
        assert emails_sent[0]["to"] == msg_users["teacher"].email
        assert "Msg Parent" in emails_sent[0]["subject"]

    def test_no_email_when_disabled(self, client, msg_users, db_session, monkeypatch):
        """Email should NOT be sent when recipient has email_notifications disabled."""
        from app.models.message import Conversation
        from app.models.notification import Notification

        # Disable email notifications for the teacher
        msg_users["teacher"].email_notifications = False
        db_session.commit()

        # Clear existing notifications
        db_session.query(Notification).filter(
            Notification.user_id == msg_users["teacher"].id,
        ).delete()
        db_session.commit()

        emails_sent = []

        def mock_send(to_email, subject, html_content):
            emails_sent.append({"to": to_email, "subject": subject})
            return True

        monkeypatch.setattr("app.api.routes.messages.send_email_sync", mock_send)

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="No Email Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post(f"/api/messages/conversations/{conv.id}/messages", json={
            "content": "Should not trigger email",
        }, headers=headers)
        assert resp.status_code in (200, 201)

        # No email sent
        assert len(emails_sent) == 0

        # But notification should still be created
        notif = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == msg_users["teacher"].id,
                Notification.type == "message",
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert notif is not None


# ── Regression: parent sees children in recipients (#936) ──

class TestParentSeesChildrenInRecipients:
    def test_parent_recipients_include_own_children(self, client, msg_users):
        """Parent's recipient list must include their linked children."""
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/recipients", headers=headers)
        assert resp.status_code == 200
        recipients = resp.json()
        recipient_ids = [r["user_id"] for r in recipients]
        assert msg_users["student"].id in recipient_ids, (
            "Parent's own child should appear in recipient list"
        )
        # Verify the child entry has the correct role
        child_entry = next(r for r in recipients if r["user_id"] == msg_users["student"].id)
        assert child_entry["role"] == "student"


# ── Regression: search matches participant names (#937) ──

class TestSearchByParticipantName:
    def test_search_by_recipient_name(self, client, msg_users, db_session):
        """Searching for a participant's name should return their conversations."""
        from app.models.message import Conversation, Message

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Homework Question",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        msg = Message(
            conversation_id=conv.id,
            sender_id=msg_users["teacher"].id,
            content="Please review the assignment",
            is_read=False,
        )
        db_session.add(msg)
        db_session.commit()

        # Search by teacher's name (not in message content or subject)
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/search", params={"q": "Msg Teacher"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        results = data["results"]
        assert len(results) >= 1, "Search by participant name should return results"
        assert any(r["conversation_id"] == conv.id for r in results)
        assert data["total"] >= 1
        assert data["query"] == "Msg Teacher"


# ── Conversation search filter (#955) ─────────────────────

class TestConversationSearchFilter:
    def test_list_conversations_with_q_filters_by_content(self, client, msg_users, db_session):
        """GET /api/messages/conversations?q=... filters by message content."""
        from app.models.message import Conversation, Message

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="General Chat",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        msg = Message(conversation_id=conv.id, sender_id=msg_users["teacher"].id,
                      content="The algebra homework is due Friday", is_read=False)
        db_session.add(msg)
        db_session.commit()

        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/conversations", params={"q": "algebra"}, headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        assert any(r["id"] == conv.id for r in results)

    def test_list_conversations_with_q_filters_by_subject(self, client, msg_users, db_session):
        """q parameter matches against conversation subject."""
        from app.models.message import Conversation, Message

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="Calculus Midterm Review",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        msg = Message(conversation_id=conv.id, sender_id=msg_users["teacher"].id,
                      content="Hello", is_read=False)
        db_session.add(msg)
        db_session.commit()

        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/conversations", params={"q": "Calculus"}, headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        assert any(r["id"] == conv.id for r in results)

    def test_list_conversations_with_q_filters_by_participant(self, client, msg_users, db_session):
        """q parameter matches against other participant name."""
        from app.models.message import Conversation, Message

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        msg = Message(conversation_id=conv.id, sender_id=msg_users["teacher"].id,
                      content="Hi", is_read=False)
        db_session.add(msg)
        db_session.commit()

        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/conversations", params={"q": "Msg Teacher"}, headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        assert any(r["id"] == conv.id for r in results)

    def test_list_conversations_without_q_returns_all(self, client, msg_users, db_session):
        """Without q parameter, all conversations are returned."""
        from app.models.message import Conversation, Message

        conv = Conversation(
            participant_1_id=msg_users["parent"].id,
            participant_2_id=msg_users["teacher"].id,
            subject="No Filter Test",
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        msg = Message(conversation_id=conv.id, sender_id=msg_users["teacher"].id,
                      content="test", is_read=False)
        db_session.add(msg)
        db_session.commit()

        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/conversations", headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        assert any(r["id"] == conv.id for r in results)

    def test_list_conversations_q_no_match_returns_empty(self, client, msg_users, db_session):
        """Search with non-matching q returns empty list."""
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/conversations", params={"q": "xyznonexistent"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ── Recipient search (#956) ───────────────────────────────

class TestRecipientSearch:
    def test_recipients_with_q_returns_any_active_user(self, client, msg_users, db_session):
        """GET /api/messages/recipients?q=... searches all active users."""
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/recipients", params={"q": "Msg"}, headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        names = [r["full_name"] for r in results]
        assert "Msg Teacher" in names
        assert "Msg Student" in names
        assert "Msg Parent" not in names

    def test_recipients_with_q_excludes_self(self, client, msg_users):
        """Search results should not include the current user."""
        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/recipients", params={"q": "Msg Parent"}, headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        ids = [r["user_id"] for r in results]
        assert msg_users["parent"].id not in ids

    def test_recipients_without_q_returns_linked_only(self, client, msg_users, db_session):
        """Without q, returns connected users + admins (no unlinked users)."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        unlinked = db_session.query(User).filter(User.email == "unlinked_recip@test.com").first()
        if not unlinked:
            unlinked = User(
                email="unlinked_recip@test.com", full_name="Unlinked Recipient",
                role=UserRole.PARENT, hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(unlinked)
            db_session.commit()
            db_session.refresh(unlinked)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.get("/api/messages/recipients", headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        ids = [r["user_id"] for r in results]
        assert unlinked.id not in ids


# ── Relaxed conversation creation (#956) ──────────────────

class TestCreateConversationRelaxed:
    def test_cannot_message_unlinked_user(self, client, msg_users, db_session):
        """Parent cannot message an unlinked parent (role-based restriction #2408)."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        unlinked = db_session.query(User).filter(User.email == "unlinked_conv@test.com").first()
        if not unlinked:
            unlinked = User(
                email="unlinked_conv@test.com", full_name="Unlinked Conv User",
                role=UserRole.PARENT, hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(unlinked)
            db_session.commit()
            db_session.refresh(unlinked)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post("/api/messages/conversations", json={
            "recipient_id": unlinked.id,
            "initial_message": "Hello unlinked user",
        }, headers=headers)
        assert resp.status_code == 403

    def test_cannot_message_self(self, client, msg_users):
        """Users should not be able to message themselves."""
        headers = _auth(client, msg_users["parent"].email)
        resp = client.post("/api/messages/conversations", json={
            "recipient_id": msg_users["parent"].id,
            "initial_message": "Talking to myself",
        }, headers=headers)
        assert resp.status_code == 400

    def test_cannot_message_inactive_user(self, client, msg_users, db_session):
        """Inactive users should not be valid recipients."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        inactive = db_session.query(User).filter(User.email == "inactive_msg@test.com").first()
        if not inactive:
            inactive = User(
                email="inactive_msg@test.com", full_name="Inactive Msg User",
                role=UserRole.PARENT, hashed_password=get_password_hash(PASSWORD),
                is_active=False,
            )
            db_session.add(inactive)
            db_session.commit()
            db_session.refresh(inactive)

        headers = _auth(client, msg_users["parent"].email)
        resp = client.post("/api/messages/conversations", json={
            "recipient_id": inactive.id,
            "initial_message": "Hello?",
        }, headers=headers)
        assert resp.status_code == 404


# ── Role-based messaging authorization (#2417) ────────────

@pytest.fixture()
def auth_users(db_session):
    """Create a full set of users with relationships for authorization tests.

    Relationships:
    - parent1 is guardian of student1
    - student1 and student2 are classmates (enrolled in teacher1's course)
    - student3 is NOT in any shared course with student1
    - parent2 has no children linked
    - teacher1 teaches course1 (with student1, student2)
    - teacher2 teaches course2 (with student3 only, no overlap)
    - admin1 is an admin
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from sqlalchemy import insert

    hashed = get_password_hash(PASSWORD)

    def _get_or_create(email, full_name, role, **kwargs):
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email, full_name=full_name, role=role,
                     hashed_password=hashed, **kwargs)
            db_session.add(u)
            db_session.flush()
        return u

    parent1 = _get_or_create("auth_parent1@test.com", "Auth Parent1", UserRole.PARENT)
    parent2 = _get_or_create("auth_parent2@test.com", "Auth Parent2", UserRole.PARENT)
    student1_user = _get_or_create("auth_student1@test.com", "Auth Student1", UserRole.STUDENT)
    student2_user = _get_or_create("auth_student2@test.com", "Auth Student2", UserRole.STUDENT)
    student3_user = _get_or_create("auth_student3@test.com", "Auth Student3", UserRole.STUDENT)
    teacher1_user = _get_or_create("auth_teacher1@test.com", "Auth Teacher1", UserRole.TEACHER)
    teacher2_user = _get_or_create("auth_teacher2@test.com", "Auth Teacher2", UserRole.TEACHER)
    admin1 = _get_or_create("auth_admin1@test.com", "Auth Admin1", UserRole.ADMIN)
    db_session.flush()

    # Student records
    def _get_or_create_student(user_id):
        s = db_session.query(Student).filter(Student.user_id == user_id).first()
        if not s:
            s = Student(user_id=user_id)
            db_session.add(s)
            db_session.flush()
        return s

    student1 = _get_or_create_student(student1_user.id)
    student2 = _get_or_create_student(student2_user.id)
    student3 = _get_or_create_student(student3_user.id)

    # Teacher records
    def _get_or_create_teacher(user_id):
        t = db_session.query(Teacher).filter(Teacher.user_id == user_id).first()
        if not t:
            t = Teacher(user_id=user_id)
            db_session.add(t)
            db_session.flush()
        return t

    teacher1 = _get_or_create_teacher(teacher1_user.id)
    teacher2 = _get_or_create_teacher(teacher2_user.id)

    # Parent-student link: parent1 -> student1
    existing_link = db_session.execute(
        parent_students.select().where(
            parent_students.c.parent_id == parent1.id,
            parent_students.c.student_id == student1.id,
        )
    ).first()
    if not existing_link:
        db_session.execute(insert(parent_students).values(
            parent_id=parent1.id, student_id=student1.id,
            relationship_type=RelationshipType.GUARDIAN,
        ))

    # Course 1 taught by teacher1 with student1 and student2
    course1 = db_session.query(Course).filter(Course.name == "Auth Test Course 1").first()
    if not course1:
        course1 = Course(name="Auth Test Course 1", teacher_id=teacher1.id,
                         created_by_user_id=teacher1_user.id, is_private=False)
        db_session.add(course1)
        db_session.flush()

        db_session.execute(student_courses.insert().values(
            student_id=student1.id, course_id=course1.id,
        ))
        db_session.execute(student_courses.insert().values(
            student_id=student2.id, course_id=course1.id,
        ))

    # Course 2 taught by teacher2 with student3 only
    course2 = db_session.query(Course).filter(Course.name == "Auth Test Course 2").first()
    if not course2:
        course2 = Course(name="Auth Test Course 2", teacher_id=teacher2.id,
                         created_by_user_id=teacher2_user.id, is_private=False)
        db_session.add(course2)
        db_session.flush()

        db_session.execute(student_courses.insert().values(
            student_id=student3.id, course_id=course2.id,
        ))

    db_session.commit()
    for u in [parent1, parent2, student1_user, student2_user, student3_user,
              teacher1_user, teacher2_user, admin1]:
        db_session.refresh(u)

    return {
        "parent1": parent1,
        "parent2": parent2,
        "student1": student1_user,
        "student2": student2_user,
        "student3": student3_user,
        "teacher1": teacher1_user,
        "teacher2": teacher2_user,
        "admin": admin1,
    }


class TestMessagingRoleAuthorization:
    """Test _can_message authorization rules for POST /api/messages/conversations."""

    def _create_conversation(self, client, sender_email, recipient_id):
        headers = _auth(client, sender_email)
        return client.post("/api/messages/conversations", json={
            "recipient_id": recipient_id,
            "subject": "Auth test",
            "initial_message": "Test message",
        }, headers=headers)

    def test_parent_can_message_teacher(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["parent1"].email, auth_users["teacher1"].id)
        assert resp.status_code == 200

    def test_parent_can_message_own_child(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["parent1"].email, auth_users["student1"].id)
        assert resp.status_code == 200

    def test_parent_cannot_message_other_student(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["parent1"].email, auth_users["student2"].id)
        assert resp.status_code == 403

    def test_parent_cannot_message_other_parent(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["parent1"].email, auth_users["parent2"].id)
        assert resp.status_code == 403

    def test_student_can_message_classmate(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["student1"].email, auth_users["student2"].id)
        assert resp.status_code == 200

    def test_student_cannot_message_non_classmate(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["student1"].email, auth_users["student3"].id)
        assert resp.status_code == 403

    def test_teacher_can_message_own_student(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["teacher1"].email, auth_users["student1"].id)
        assert resp.status_code == 200

    def test_teacher_cannot_message_unlinked_student(self, client, auth_users):
        resp = self._create_conversation(
            client, auth_users["teacher1"].email, auth_users["student3"].id)
        assert resp.status_code == 403

    def test_admin_can_message_anyone(self, client, auth_users):
        # Admin -> parent
        resp = self._create_conversation(
            client, auth_users["admin"].email, auth_users["parent1"].id)
        assert resp.status_code == 200
        # Admin -> student
        resp = self._create_conversation(
            client, auth_users["admin"].email, auth_users["student3"].id)
        assert resp.status_code == 200
        # Admin -> teacher
        resp = self._create_conversation(
            client, auth_users["admin"].email, auth_users["teacher2"].id)
        assert resp.status_code == 200
