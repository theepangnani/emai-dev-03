"""Tests for CASCADE delete rules and unique constraints (#145, #146, #187)."""
import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError


def _make_user(db, email, role_name, full_name=None):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    role = UserRole(role_name)
    user = User(
        email=email,
        full_name=full_name or email.split("@")[0],
        role=role,
        hashed_password=get_password_hash("Password123!"),
    )
    db.add(user)
    db.flush()
    return user


# ── CASCADE DELETE tests ─────────────────────────────────────


class TestCascadeDeleteUser:
    def test_deleting_user_cascades_student(self, db_session):
        """Deleting a user should cascade-delete their Student record."""
        from app.models.user import User
        from app.models.student import Student

        user = _make_user(db_session, "cas_stu@test.com", "student")
        student = Student(user_id=user.id)
        db_session.add(student)
        db_session.flush()
        student_id = student.id

        db_session.delete(user)
        db_session.commit()

        assert db_session.query(Student).filter(Student.id == student_id).first() is None

    def test_deleting_user_cascades_notifications(self, db_session):
        """Deleting a user should cascade-delete their notifications."""
        from app.models.user import User
        from app.models.notification import Notification, NotificationType

        user = _make_user(db_session, "cas_notif@test.com", "parent")
        notif = Notification(
            user_id=user.id, type=NotificationType.SYSTEM,
            title="Test", content="test",
        )
        db_session.add(notif)
        db_session.flush()
        notif_id = notif.id

        db_session.delete(user)
        db_session.commit()

        assert db_session.query(Notification).filter(Notification.id == notif_id).first() is None

    def test_deleting_user_cascades_created_tasks(self, db_session):
        """Deleting a user should cascade-delete tasks they created."""
        from app.models.user import User
        from app.models.task import Task

        user = _make_user(db_session, "cas_task@test.com", "parent")
        task = Task(
            title="Test Task", created_by_user_id=user.id,
        )
        db_session.add(task)
        db_session.flush()
        task_id = task.id

        db_session.delete(user)
        db_session.commit()

        assert db_session.query(Task).filter(Task.id == task_id).first() is None


class TestCascadeDeleteCourse:
    def test_deleting_course_cascades_assignments(self, db_session):
        """Deleting a course should cascade-delete its assignments."""
        from app.models.course import Course
        from app.models.assignment import Assignment

        creator = _make_user(db_session, "cas_course_creator@test.com", "teacher")
        course = Course(name="Cascade Test Course", created_by_user_id=creator.id)
        db_session.add(course)
        db_session.flush()

        assignment = Assignment(title="Test Assignment", course_id=course.id)
        db_session.add(assignment)
        db_session.flush()
        assignment_id = assignment.id

        db_session.delete(course)
        db_session.commit()

        assert db_session.query(Assignment).filter(Assignment.id == assignment_id).first() is None

    def test_deleting_course_cascades_course_contents(self, db_session):
        """Deleting a course should cascade-delete its contents."""
        from app.models.course import Course
        from app.models.course_content import CourseContent

        creator = _make_user(db_session, "cas_cc_creator@test.com", "teacher")
        course = Course(name="CC Cascade Course", created_by_user_id=creator.id)
        db_session.add(course)
        db_session.flush()

        content = CourseContent(
            title="Test Content", course_id=course.id,
            content_type="notes", created_by_user_id=creator.id,
        )
        db_session.add(content)
        db_session.flush()
        content_id = content.id

        db_session.delete(course)
        db_session.commit()

        assert db_session.query(CourseContent).filter(CourseContent.id == content_id).first() is None


class TestCascadeDeleteConversation:
    def test_deleting_conversation_cascades_messages(self, db_session):
        """Deleting a conversation should cascade-delete its messages."""
        from app.models.message import Conversation, Message

        user1 = _make_user(db_session, "cas_conv1@test.com", "parent")
        user2 = _make_user(db_session, "cas_conv2@test.com", "teacher")
        conv = Conversation(
            participant_1_id=user1.id, participant_2_id=user2.id,
        )
        db_session.add(conv)
        db_session.flush()

        msg = Message(
            conversation_id=conv.id, sender_id=user1.id, content="Hello",
        )
        db_session.add(msg)
        db_session.flush()
        msg_id = msg.id

        db_session.delete(conv)
        db_session.commit()

        assert db_session.query(Message).filter(Message.id == msg_id).first() is None


# ── SET NULL tests ───────────────────────────────────────────


class TestSetNull:
    def test_deleting_user_sets_null_on_course_creator(self, db_session):
        """Deleting a user should SET NULL on courses.created_by_user_id."""
        from app.models.user import User
        from app.models.course import Course

        creator = _make_user(db_session, "cas_setnull_creator@test.com", "parent")
        course = Course(name="SetNull Test Course", created_by_user_id=creator.id)
        db_session.add(course)
        db_session.commit()
        course_id = course.id

        db_session.delete(creator)
        db_session.commit()

        db_session.expire_all()
        course = db_session.query(Course).filter(Course.id == course_id).first()
        assert course is not None
        assert course.created_by_user_id is None

    def test_deleting_course_sets_null_on_task(self, db_session):
        """Deleting a course should SET NULL on tasks.course_id."""
        from app.models.course import Course
        from app.models.task import Task

        creator = _make_user(db_session, "cas_task_setnull@test.com", "parent")
        course = Course(name="Task SetNull Course", created_by_user_id=creator.id)
        db_session.add(course)
        db_session.flush()

        task = Task(
            title="Linked Task", created_by_user_id=creator.id, course_id=course.id,
        )
        db_session.add(task)
        db_session.commit()
        task_id = task.id

        db_session.delete(course)
        db_session.commit()

        db_session.expire_all()
        task = db_session.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        assert task.course_id is None


# ── UNIQUE CONSTRAINT tests ──────────────────────────────────


class TestUniqueConstraints:
    def test_duplicate_parent_student_rejected(self, db_session):
        """Inserting duplicate parent_students pair should raise IntegrityError."""
        from app.models.student import Student, parent_students, RelationshipType

        parent = _make_user(db_session, "cas_uq_parent@test.com", "parent")
        student_user = _make_user(db_session, "cas_uq_student@test.com", "student")
        student = Student(user_id=student_user.id)
        db_session.add(student)
        db_session.flush()

        db_session.execute(insert(parent_students).values(
            parent_id=parent.id, student_id=student.id,
            relationship_type=RelationshipType.GUARDIAN,
        ))
        db_session.flush()

        with pytest.raises(IntegrityError):
            db_session.execute(insert(parent_students).values(
                parent_id=parent.id, student_id=student.id,
                relationship_type=RelationshipType.MOTHER,
            ))
            db_session.flush()
        db_session.rollback()

    def test_duplicate_student_teacher_rejected(self, db_session):
        """Inserting duplicate student_teachers pair should raise IntegrityError."""
        from app.models.student import Student, student_teachers

        parent = _make_user(db_session, "cas_uq_parent2@test.com", "parent")
        student_user = _make_user(db_session, "cas_uq_student2@test.com", "student")
        student = Student(user_id=student_user.id)
        db_session.add(student)
        db_session.flush()

        db_session.execute(insert(student_teachers).values(
            student_id=student.id, teacher_email="cas_teacher@test.com",
            teacher_name="Test", added_by_user_id=parent.id,
        ))
        db_session.flush()

        with pytest.raises(IntegrityError):
            db_session.execute(insert(student_teachers).values(
                student_id=student.id, teacher_email="cas_teacher@test.com",
                teacher_name="Duplicate", added_by_user_id=parent.id,
            ))
            db_session.flush()
        db_session.rollback()
