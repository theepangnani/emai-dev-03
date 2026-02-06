"""Seed the local database with demo data for UI and API testing.

Usage:
  python -m scripts.seed_demo_data
  python -m scripts.seed_demo_data --force
"""
import argparse
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.database import SessionLocal, engine, Base
from app.models import User, Teacher, Student, Course, Assignment, Conversation, Message, Notification
from app.models.user import UserRole
from app.models.teacher import TeacherType
from app.models.student import parent_students, RelationshipType
from app.models.notification import NotificationType


def seed(force: bool = False):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not force and db.query(User).count() > 0:
            print("Database already has users. Use --force to seed anyway.")
            return

        if force:
            db.query(Message).delete()
            db.query(Conversation).delete()
            db.query(Assignment).delete()
            db.query(Course).delete()
            db.query(Notification).delete()
            db.query(Student).delete()
            db.query(Teacher).delete()
            db.query(User).delete()
            db.commit()

        admin = User(
            email="admin@classbridge.local",
            full_name="Avery Admin",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash("password123!"),
        )
        teacher_user = User(
            email="teacher@classbridge.local",
            full_name="Tara Teacher",
            role=UserRole.TEACHER,
            hashed_password=get_password_hash("password123!"),
        )
        parent_user = User(
            email="parent@classbridge.local",
            full_name="Pat Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash("password123!"),
        )
        student_user = User(
            email="student@classbridge.local",
            full_name="Sam Student",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash("password123!"),
        )

        db.add_all([admin, teacher_user, parent_user, student_user])
        db.flush()

        teacher = Teacher(user_id=teacher_user.id, teacher_type=TeacherType.SCHOOL_TEACHER)
        student = Student(
            user_id=student_user.id, grade_level=8, school_name="North Ridge MS"
        )
        db.add_all([teacher, student])
        db.flush()

        db.execute(
            parent_students.insert().values(
                parent_id=parent_user.id,
                student_id=student.id,
                relationship_type=RelationshipType.GUARDIAN,
            )
        )

        course = Course(
            name="Foundations of Science",
            description="Exploring ecosystems, energy, and change.",
            subject="Science",
            teacher_id=teacher.id,
        )
        db.add(course)
        db.flush()

        assignments = [
            Assignment(
                title="Energy Flow Lab",
                description="Analyze energy transfer in a terrarium.",
                course_id=course.id,
                due_date=datetime.utcnow() + timedelta(days=5),
                max_points=100,
            ),
            Assignment(
                title="Ecosystem Reflection",
                description="Write a short reflection on food webs.",
                course_id=course.id,
                due_date=datetime.utcnow() + timedelta(days=12),
                max_points=50,
            ),
        ]
        db.add_all(assignments)

        conversation = Conversation(
            participant_1_id=teacher_user.id,
            participant_2_id=parent_user.id,
            student_id=student.id,
            subject="Weekly progress update",
        )
        db.add(conversation)
        db.flush()

        messages = [
            Message(
                conversation_id=conversation.id,
                sender_id=teacher_user.id,
                content="Sam is doing well in lab activities. Encourage a little extra reading this week.",
            ),
            Message(
                conversation_id=conversation.id,
                sender_id=parent_user.id,
                content="Thanks! We'll review the notes and focus on vocabulary.",
            ),
        ]
        db.add_all(messages)

        notification = Notification(
            user_id=parent_user.id,
            type=NotificationType.ASSIGNMENT_DUE,
            title="Energy Flow Lab due soon",
            content="Due in 5 days. Check the instructions and rubric.",
            link="/dashboard",
            read=False,
        )
        db.add(notification)

        db.commit()
        print("Seeded demo data. Logins: admin/teacher/parent/student with password password123!")
    finally:
        db.close()


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--force", action="store_true", help="Wipe existing data before seeding.")
  args = parser.parse_args()
  seed(force=args.force)
