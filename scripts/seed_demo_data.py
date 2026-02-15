"""Seed the database with realistic demo data for pilot testing.

Creates 9 users (1 admin, 2 teachers, 3 parents, 3 students),
4 courses, 13 assignments with grades, conversations, messages,
notifications, and tasks.

Usage:
  python -m scripts.seed_demo_data                  # local SQLite
  python -m scripts.seed_demo_data --force           # wipe & reseed local
  python -m scripts.seed_demo_data --database-url "postgresql+psycopg2://..."  # target production
"""
import argparse
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.db.database import SessionLocal, engine as default_engine, Base
from app.models import (
    User, Teacher, Student, Course, Assignment, Conversation, Message,
    Notification, Task, StudyGuide, TeacherCommunication, Invite, Broadcast,
    CourseContent, AuditLog, InspirationMessage,
)
from app.models.user import UserRole
from app.models.teacher import TeacherType
from app.models.student import parent_students, student_teachers, RelationshipType
from app.models.notification import NotificationType
from app.models.assignment import StudentAssignment
from app.models.course import student_courses
from app.models.token_blacklist import TokenBlacklist
from app.models.teacher_google_account import TeacherGoogleAccount

DEMO_PASSWORD = "Pilot2026!"


def _now():
    return datetime.now(timezone.utc)


def seed(force: bool = False, database_url: str | None = None):
    if database_url:
        eng = create_engine(database_url)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    else:
        eng = default_engine
        Session = SessionLocal
    Base.metadata.create_all(bind=eng)
    db = Session()
    try:
        if not force and db.query(User).count() > 0:
            print("Database already has users. Use --force to seed anyway.")
            return

        if force:
            # Delete all tables in dependency order
            db.query(Message).delete()
            db.query(Conversation).delete()
            db.query(StudentAssignment).delete()
            db.query(StudyGuide).delete()
            db.query(Assignment).delete()
            db.query(Notification).delete()
            db.query(Task).delete()
            db.query(CourseContent).delete()
            db.execute(student_courses.delete())
            db.execute(student_teachers.delete())
            db.execute(parent_students.delete())
            db.query(Course).delete()
            db.query(TeacherGoogleAccount).delete()
            db.query(TeacherCommunication).delete()
            db.query(TokenBlacklist).delete()
            db.query(AuditLog).delete()
            db.query(Invite).delete()
            db.query(Broadcast).delete()
            db.query(Student).delete()
            db.query(Teacher).delete()
            db.query(User).delete()
            db.commit()

        pw = get_password_hash(DEMO_PASSWORD)

        # ── Users ─────────────────────────────────────────────
        admin = User(
            email="admin@classbridge.local", full_name="Alex Rivera",
            role=UserRole.ADMIN, hashed_password=pw,
        )
        t1_user = User(
            email="sarah.chen@classbridge.local", full_name="Sarah Chen",
            role=UserRole.TEACHER, hashed_password=pw,
        )
        t2_user = User(
            email="james.wilson@classbridge.local", full_name="James Wilson",
            role=UserRole.TEACHER, hashed_password=pw,
        )
        p1_user = User(
            email="priya.sharma@classbridge.local", full_name="Priya Sharma",
            role=UserRole.PARENT, hashed_password=pw,
        )
        p2_user = User(
            email="michael.torres@classbridge.local", full_name="Michael Torres",
            role=UserRole.PARENT, hashed_password=pw,
        )
        p3_user = User(
            email="jennifer.kim@classbridge.local", full_name="Jennifer Kim",
            role=UserRole.PARENT, hashed_password=pw,
        )
        s1_user = User(
            email="aiden.sharma@classbridge.local", full_name="Aiden Sharma",
            role=UserRole.STUDENT, hashed_password=pw,
        )
        s2_user = User(
            email="sofia.torres@classbridge.local", full_name="Sofia Torres",
            role=UserRole.STUDENT, hashed_password=pw,
        )
        s3_user = User(
            email="ethan.kim@classbridge.local", full_name="Ethan Kim",
            role=UserRole.STUDENT, hashed_password=pw,
        )
        db.add_all([admin, t1_user, t2_user, p1_user, p2_user, p3_user,
                     s1_user, s2_user, s3_user])
        db.flush()

        # ── Teacher profiles ──────────────────────────────────
        t1 = Teacher(
            user_id=t1_user.id, school_name="Maple Ridge Academy",
            department="Science & Math", teacher_type=TeacherType.SCHOOL_TEACHER,
        )
        t2 = Teacher(
            user_id=t2_user.id, school_name="Maple Ridge Academy",
            department="Humanities", teacher_type=TeacherType.SCHOOL_TEACHER,
        )
        db.add_all([t1, t2])
        db.flush()

        # ── Student profiles ─────────────────────────────────
        s1 = Student(user_id=s1_user.id, grade_level=8, school_name="Maple Ridge Academy")
        s2 = Student(user_id=s2_user.id, grade_level=8, school_name="Maple Ridge Academy")
        s3 = Student(user_id=s3_user.id, grade_level=7, school_name="Maple Ridge Academy")
        db.add_all([s1, s2, s3])
        db.flush()

        # ── Parent-Student links ──────────────────────────────
        for parent_id, student_id, rel in [
            (p1_user.id, s1.id, RelationshipType.MOTHER),
            (p2_user.id, s2.id, RelationshipType.FATHER),
            (p3_user.id, s3.id, RelationshipType.MOTHER),
        ]:
            db.execute(parent_students.insert().values(
                parent_id=parent_id, student_id=student_id,
                relationship_type=rel,
            ))

        # ── Student-Teacher links ─────────────────────────────
        for sid, tuser, tname, temail, added_by in [
            (s1.id, t1_user.id, "Sarah Chen", "sarah.chen@classbridge.local", p1_user.id),
            (s1.id, t2_user.id, "James Wilson", "james.wilson@classbridge.local", p1_user.id),
            (s2.id, t1_user.id, "Sarah Chen", "sarah.chen@classbridge.local", p2_user.id),
            (s2.id, t2_user.id, "James Wilson", "james.wilson@classbridge.local", p2_user.id),
            (s3.id, t1_user.id, "Sarah Chen", "sarah.chen@classbridge.local", p3_user.id),
        ]:
            db.execute(student_teachers.insert().values(
                student_id=sid, teacher_user_id=tuser,
                teacher_name=tname, teacher_email=temail,
                added_by_user_id=added_by,
            ))

        # ── Courses ───────────────────────────────────────────
        c_sci = Course(
            name="Science 8", subject="Science", teacher_id=t1.id,
            description="Grade 8 Science: cells, ecosystems, and energy.",
        )
        c_math = Course(
            name="Mathematics 8", subject="Mathematics", teacher_id=t1.id,
            description="Grade 8 Math: linear equations, geometry, and data analysis.",
        )
        c_eng = Course(
            name="English Language Arts 8", subject="English", teacher_id=t2.id,
            description="Grade 8 ELA: literature analysis, persuasive writing, and grammar.",
        )
        c_ss = Course(
            name="Social Studies 8", subject="Social Studies", teacher_id=t2.id,
            description="Grade 8 Social Studies: world history and geography.",
        )
        db.add_all([c_sci, c_math, c_eng, c_ss])
        db.flush()

        # ── Enroll students in courses ────────────────────────
        for course in [c_sci, c_math, c_eng, c_ss]:
            for student in [s1, s2]:
                db.execute(student_courses.insert().values(
                    student_id=student.id, course_id=course.id,
                ))
        for course in [c_sci, c_math, c_eng]:
            db.execute(student_courses.insert().values(
                student_id=s3.id, course_id=course.id,
            ))

        # ── Assignments ───────────────────────────────────────
        t = _now()
        sci_assignments = [
            Assignment(
                title="Cell Structure Lab Report",
                description="Draw and label plant and animal cells. Include at least 8 organelles.",
                course_id=c_sci.id, due_date=t - timedelta(days=3), max_points=100,
            ),
            Assignment(
                title="Photosynthesis Quiz",
                description="Short quiz on the light and dark reactions of photosynthesis.",
                course_id=c_sci.id, due_date=t + timedelta(days=2), max_points=50,
            ),
            Assignment(
                title="Ecosystem Diorama Project",
                description="Build a diorama of a biome and present to the class.",
                course_id=c_sci.id, due_date=t + timedelta(days=10), max_points=150,
            ),
        ]
        math_assignments = [
            Assignment(
                title="Linear Equations Worksheet",
                description="Solve 20 linear equations. Show all work.",
                course_id=c_math.id, due_date=t - timedelta(days=5), max_points=40,
            ),
            Assignment(
                title="Slope and Intercept Test",
                description="Unit test covering slope, y-intercept, and graphing lines.",
                course_id=c_math.id, due_date=t + timedelta(days=3), max_points=100,
            ),
            Assignment(
                title="Data Analysis Project",
                description="Collect survey data, create graphs, and interpret trends.",
                course_id=c_math.id, due_date=t + timedelta(days=14), max_points=60,
            ),
        ]
        eng_assignments = [
            Assignment(
                title="Book Report: The Giver",
                description="Write a 3-page report on themes and character development.",
                course_id=c_eng.id, due_date=t - timedelta(days=1), max_points=100,
            ),
            Assignment(
                title="Persuasive Essay Draft",
                description="First draft of a persuasive essay on a topic of your choice.",
                course_id=c_eng.id, due_date=t + timedelta(days=5), max_points=75,
            ),
            Assignment(
                title="Grammar Review Exercises",
                description="Complete exercises on subject-verb agreement and punctuation.",
                course_id=c_eng.id, due_date=t + timedelta(days=7), max_points=30,
            ),
            Assignment(
                title="Poetry Analysis",
                description="Analyze two poems and compare the literary devices used.",
                course_id=c_eng.id, due_date=t + timedelta(days=18), max_points=80,
            ),
        ]
        ss_assignments = [
            Assignment(
                title="Ancient Civilizations Timeline",
                description="Create an illustrated timeline of Mesopotamia, Egypt, and Greece.",
                course_id=c_ss.id, due_date=t - timedelta(days=7), max_points=50,
            ),
            Assignment(
                title="Geography Map Quiz",
                description="Label countries, capitals, and major rivers on a blank map.",
                course_id=c_ss.id, due_date=t + timedelta(days=1), max_points=40,
            ),
            Assignment(
                title="Research Paper Outline",
                description="Submit a detailed outline for the historical research paper.",
                course_id=c_ss.id, due_date=t + timedelta(days=12), max_points=60,
            ),
        ]
        all_assignments = sci_assignments + math_assignments + eng_assignments + ss_assignments
        db.add_all(all_assignments)
        db.flush()

        # ── Grades for past-due assignments ───────────────────
        grades = [
            StudentAssignment(
                student_id=s1.id, assignment_id=sci_assignments[0].id,
                grade=92, status="graded", submitted_at=t - timedelta(days=4),
            ),
            StudentAssignment(
                student_id=s1.id, assignment_id=math_assignments[0].id,
                grade=36, status="graded", submitted_at=t - timedelta(days=6),
            ),
            StudentAssignment(
                student_id=s1.id, assignment_id=eng_assignments[0].id,
                grade=88, status="graded", submitted_at=t - timedelta(days=2),
            ),
            StudentAssignment(
                student_id=s1.id, assignment_id=ss_assignments[0].id,
                grade=45, status="graded", submitted_at=t - timedelta(days=8),
            ),
            StudentAssignment(
                student_id=s2.id, assignment_id=sci_assignments[0].id,
                grade=85, status="graded", submitted_at=t - timedelta(days=4),
            ),
            StudentAssignment(
                student_id=s2.id, assignment_id=math_assignments[0].id,
                grade=38, status="graded", submitted_at=t - timedelta(days=6),
            ),
            StudentAssignment(
                student_id=s2.id, assignment_id=eng_assignments[0].id,
                status="submitted", submitted_at=t - timedelta(days=1),
            ),
            StudentAssignment(
                student_id=s2.id, assignment_id=ss_assignments[0].id,
                grade=48, status="graded", submitted_at=t - timedelta(days=8),
            ),
            StudentAssignment(
                student_id=s3.id, assignment_id=sci_assignments[0].id,
                grade=78, status="graded", submitted_at=t - timedelta(days=3),
            ),
            StudentAssignment(
                student_id=s3.id, assignment_id=math_assignments[0].id,
                grade=32, status="graded", submitted_at=t - timedelta(days=5),
            ),
            StudentAssignment(
                student_id=s3.id, assignment_id=eng_assignments[0].id,
                status="pending",
            ),
        ]
        db.add_all(grades)

        # ── Conversations & Messages ──────────────────────────
        conv1 = Conversation(
            participant_1_id=t1_user.id, participant_2_id=p1_user.id,
            student_id=s1.id, subject="Aiden's progress in Science",
        )
        conv2 = Conversation(
            participant_1_id=t2_user.id, participant_2_id=p2_user.id,
            student_id=s2.id, subject="Sofia's English paper",
        )
        conv3 = Conversation(
            participant_1_id=t1_user.id, participant_2_id=p3_user.id,
            student_id=s3.id, subject="Upcoming Math test preparation",
        )
        db.add_all([conv1, conv2, conv3])
        db.flush()

        msgs = [
            Message(
                conversation_id=conv1.id, sender_id=t1_user.id,
                content="Hi Priya, just wanted to let you know Aiden did great on his cell lab report -- 92/100! He clearly put a lot of effort into the diagrams.",
                is_read=True, created_at=t - timedelta(days=2, hours=3),
            ),
            Message(
                conversation_id=conv1.id, sender_id=p1_user.id,
                content="That's wonderful to hear, Mrs. Chen! He was really excited about using the microscope. Any areas he should focus on for the upcoming quiz?",
                is_read=True, created_at=t - timedelta(days=2, hours=1),
            ),
            Message(
                conversation_id=conv1.id, sender_id=t1_user.id,
                content="He should review the light reactions section -- that's where most students struggle. Chapter 4 in the textbook has a good summary.",
                is_read=True, created_at=t - timedelta(days=1, hours=22),
            ),
            Message(
                conversation_id=conv1.id, sender_id=p1_user.id,
                content="Thanks for the tip! We'll go over that this weekend.",
                is_read=False, created_at=t - timedelta(hours=5),
            ),
            Message(
                conversation_id=conv2.id, sender_id=t2_user.id,
                content="Hi Mr. Torres, Sofia submitted her book report on time but I noticed she could strengthen her thesis statement. I'd like to give her a chance to revise.",
                is_read=True, created_at=t - timedelta(days=1, hours=8),
            ),
            Message(
                conversation_id=conv2.id, sender_id=p2_user.id,
                content="Thank you for letting me know. She mentioned she rushed the conclusion. When is the revision due?",
                is_read=True, created_at=t - timedelta(days=1, hours=4),
            ),
            Message(
                conversation_id=conv2.id, sender_id=t2_user.id,
                content="She has until Friday to resubmit. I'd suggest she outline her main argument first, then build the thesis around it.",
                is_read=False, created_at=t - timedelta(hours=12),
            ),
            Message(
                conversation_id=conv3.id, sender_id=p3_user.id,
                content="Hi Mrs. Chen, Ethan is worried about the slope and intercept test next week. Is there any extra practice material available?",
                is_read=True, created_at=t - timedelta(days=1, hours=6),
            ),
            Message(
                conversation_id=conv3.id, sender_id=t1_user.id,
                content="Hi Jennifer, I've posted some practice problems on the course page. Ethan can also come to tutoring on Wednesday after school.",
                is_read=True, created_at=t - timedelta(days=1, hours=2),
            ),
            Message(
                conversation_id=conv3.id, sender_id=p3_user.id,
                content="That's great -- I'll make sure he attends. He scored 32/40 on the worksheet, so he has a solid foundation to build on.",
                is_read=False, created_at=t - timedelta(hours=8),
            ),
        ]
        db.add_all(msgs)

        # ── Notifications ─────────────────────────────────────
        notifications = [
            Notification(
                user_id=p1_user.id, type=NotificationType.ASSIGNMENT_DUE,
                title="Photosynthesis Quiz due soon",
                content="Aiden's Photosynthesis Quiz in Science 8 is due in 2 days.",
                link="/dashboard", read=False,
            ),
            Notification(
                user_id=p1_user.id, type=NotificationType.GRADE_POSTED,
                title="Grade posted: Cell Structure Lab Report",
                content="Aiden received 92/100 on Cell Structure Lab Report.",
                link="/dashboard", read=True,
            ),
            Notification(
                user_id=p2_user.id, type=NotificationType.ASSIGNMENT_DUE,
                title="Persuasive Essay Draft due in 5 days",
                content="Sofia's Persuasive Essay Draft in English Language Arts 8 is due soon.",
                link="/dashboard", read=False,
            ),
            Notification(
                user_id=p2_user.id, type=NotificationType.MESSAGE,
                title="New message from James Wilson",
                content="Regarding: Sofia's English paper",
                link="/messages", read=False,
            ),
            Notification(
                user_id=p3_user.id, type=NotificationType.ASSIGNMENT_DUE,
                title="Slope and Intercept Test in 3 days",
                content="Ethan's Slope and Intercept Test in Mathematics 8 is coming up.",
                link="/dashboard", read=False,
            ),
            Notification(
                user_id=p3_user.id, type=NotificationType.GRADE_POSTED,
                title="Grade posted: Linear Equations Worksheet",
                content="Ethan received 32/40 on Linear Equations Worksheet.",
                link="/dashboard", read=True,
            ),
            Notification(
                user_id=p1_user.id, type=NotificationType.SYSTEM,
                title="Welcome to ClassBridge!",
                content="Your account is set up. Explore the dashboard to see your child's courses and assignments.",
                link="/dashboard", read=True,
            ),
            Notification(
                user_id=p2_user.id, type=NotificationType.SYSTEM,
                title="Welcome to ClassBridge!",
                content="Your account is set up. Explore the dashboard to see your child's courses and assignments.",
                link="/dashboard", read=True,
            ),
            Notification(
                user_id=p3_user.id, type=NotificationType.SYSTEM,
                title="Welcome to ClassBridge!",
                content="Your account is set up. Explore the dashboard to see your child's courses and assignments.",
                link="/dashboard", read=True,
            ),
        ]
        db.add_all(notifications)

        # ── Tasks ─────────────────────────────────────────────
        tasks = [
            Task(
                created_by_user_id=p1_user.id, assigned_to_user_id=p1_user.id,
                title="Review Aiden's science project outline",
                description="Help Aiden choose a biome for his ecosystem diorama and gather materials.",
                due_date=t + timedelta(days=5), priority="medium", category="Schoolwork",
            ),
            Task(
                created_by_user_id=p1_user.id, assigned_to_user_id=p1_user.id,
                title="Buy poster board for diorama",
                description="Pick up supplies from the craft store for the ecosystem project.",
                due_date=t + timedelta(days=7), priority="low", category="Shopping",
            ),
            Task(
                created_by_user_id=p2_user.id, assigned_to_user_id=p2_user.id,
                title="Help Sofia practice essay structure",
                description="Go over thesis statements and supporting arguments for her persuasive essay revision.",
                due_date=t + timedelta(days=3), priority="high", category="Schoolwork",
            ),
            Task(
                created_by_user_id=p3_user.id, assigned_to_user_id=p3_user.id,
                title="Schedule parent-teacher conference",
                description="Reach out to Mrs. Chen about Ethan's math progress and test preparation.",
                due_date=t + timedelta(days=10), priority="medium", category="Communication",
            ),
            Task(
                created_by_user_id=p3_user.id, assigned_to_user_id=p3_user.id,
                title="Print math practice problems",
                description="Download and print the extra practice problems Mrs. Chen posted.",
                due_date=t + timedelta(days=1), priority="high", category="Schoolwork",
            ),
        ]
        db.add_all(tasks)

        db.commit()

        print("=" * 60)
        print("  ClassBridge Demo Data Seeded Successfully!")
        print("=" * 60)
        print()
        print(f"  Password for all accounts: {DEMO_PASSWORD}")
        print()
        print("  ADMIN:")
        print("    admin@classbridge.local")
        print()
        print("  TEACHERS:")
        print("    sarah.chen@classbridge.local   (Science & Math)")
        print("    james.wilson@classbridge.local  (English & Social Studies)")
        print()
        print("  PARENTS:")
        print("    priya.sharma@classbridge.local    (mother of Aiden)")
        print("    michael.torres@classbridge.local  (father of Sofia)")
        print("    jennifer.kim@classbridge.local    (mother of Ethan)")
        print()
        print("  STUDENTS:")
        print("    aiden.sharma@classbridge.local  (Grade 8, 4 courses)")
        print("    sofia.torres@classbridge.local  (Grade 8, 4 courses)")
        print("    ethan.kim@classbridge.local     (Grade 7, 3 courses)")
        print()
        print("  DATA:")
        print("    4 courses, 13 assignments, 11 grades")
        print("    3 conversations, 10 messages")
        print("    9 notifications, 5 tasks")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed ClassBridge with realistic demo data.")
    parser.add_argument("--force", action="store_true", help="Wipe existing data before seeding.")
    parser.add_argument("--database-url", help="Database URL (defaults to local DB from .env)")
    args = parser.parse_args()

    if args.database_url:
        print(f"Targeting: {args.database_url.split('@')[-1] if '@' in args.database_url else args.database_url}")
        confirm = input("This will write to an external database. Continue? [y/N] ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    seed(force=args.force, database_url=args.database_url)
