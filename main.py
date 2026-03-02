import os
import time
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.gzip import GZipMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, RequestLogger
from app.core.middleware import DomainRedirectMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.db.database import Base, engine, SessionLocal
from app.api.routes import auth, users, students, courses, assignments, google_classroom, google_calendar, study, logs, messages, notifications, notification_preferences, teacher_communications, parent, admin, invites, tasks, course_contents, search, inspiration, faq, analytics, link_requests, quiz_results, onboarding, grades, consent, mcp_config, documents, profile, quiz_assignments, grade_entries, report_cards, mock_exams, academic_plans, course_recommendations, ontario, curriculum, exam_prep, notes, projects, admin_analytics, sample_exams, lms_connections

# Initialize logging first (auto-determines level based on environment)
setup_logging(
    app_name="emai",
    log_level=settings.log_level,  # Empty = auto (DEBUG in dev, WARNING in prod)
    environment=settings.environment,
    enable_console=True,
    enable_file=settings.log_to_file,
)

logger = get_logger(__name__)
request_logger = RequestLogger(get_logger("emai.requests"))

logger.info("Starting EMAI application...")

# Create database tables
from app.models import User, Student, Teacher, Course, Assignment, StudyGuide, Conversation, Message, Notification, TeacherCommunication, Invite, Task, TaskTemplate, TaskComment, CourseContent, AuditLog, InspirationMessage, FAQQuestion, FAQAnswer, GradeRecord, LinkRequest, NotificationSuppression, NotificationPreference, QuizResult
from app.models.quiz_assignment import QuizAssignment  # noqa: F401 — ensure table is created
from app.models.grade_entry import GradeEntry  # noqa: F401 — ensure table is created
from app.models.student import parent_students, student_teachers  # noqa: F401 — ensure join tables are created
from app.models.token_blacklist import TokenBlacklist  # noqa: F401 — ensure table is created
from app.models.teacher_google_account import TeacherGoogleAccount  # noqa: F401 — ensure table is created
from app.models.email_template import EmailTemplate  # noqa: F401 — ensure table is created
from app.models.report_card import ReportCard  # noqa: F401 — ensure table is created
from app.models.mock_exam import MockExam, MockExamAssignment  # noqa: F401 — ensure tables are created (#667)
from app.models.academic_plan import AcademicPlan, PlanCourse  # noqa: F401 — ensure tables are created (#501)
from app.models.course_recommendation import CourseRecommendation  # noqa: F401 — ensure table is created (#503)
from app.models.ontario_board import OntarioBoard  # noqa: F401 — ensure table is created (#500)
from app.models.course_catalog import CourseCatalogItem  # noqa: F401 — ensure table is created (#500)
from app.models.student_board import StudentBoard  # noqa: F401 — ensure table is created (#511)
from app.models.curriculum import CurriculumExpectation  # noqa: F401 — ensure table is created (#571)
from app.models.exam_prep_plan import ExamPrepPlan  # noqa: F401 — ensure table is created (#576)
from app.models.note import Note  # noqa: F401 — ensure table is created
from app.models.project import Project, ProjectMilestone  # noqa: F401 — ensure tables are created
from app.models.sample_exam import SampleExam  # noqa: F401 — ensure table is created (#577)
from app.models.lms_institution import LMSInstitution  # noqa: F401 — ensure table is created (#22)
from app.models.lms_connection import LMSConnection  # noqa: F401 — ensure table is created (#22)
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")

# Lightweight schema migration: add columns missing from pre-existing tables
from sqlalchemy import inspect as sa_inspect, text


def _apply_cascade_and_unique_migration(conn, inspector):
    """Add CASCADE/SET NULL FK rules and unique constraints (idempotent)."""
    is_sqlite = "sqlite" in settings.database_url
    table_names = inspector.get_table_names()

    # Check if migration already applied by looking for our unique index
    if "parent_students" in table_names:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("parent_students") if idx.get("name")}
        if "uq_parent_students_pair" in existing_indexes:
            return  # Already migrated

    logger.info("Applying CASCADE/UNIQUE migration (#145, #146, #187)...")

    # --- Deduplicate + add UNIQUE CONSTRAINTS ---
    _dedup_and_add_unique = [
        ("parent_students", ["parent_id", "student_id"], "uq_parent_students_pair"),
        ("student_teachers", ["student_id", "teacher_email"], "uq_student_teachers_pair"),
        ("student_assignments", ["student_id", "assignment_id"], "uq_student_assignment_pair"),
    ]

    for table, cols, constraint_name in _dedup_and_add_unique:
        if table not in table_names:
            continue
        col_list = ", ".join(cols)
        # Remove duplicates, keeping the earliest row
        conn.execute(text(
            f"DELETE FROM {table} WHERE id NOT IN ("
            f"SELECT MIN(id) FROM {table} GROUP BY {col_list})"
        ))
        if is_sqlite:
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name} ON {table}({col_list})"
            ))
        else:
            try:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} UNIQUE ({col_list})"
                ))
            except Exception:
                pass  # Already exists
        logger.info(f"Added unique constraint {constraint_name} on {table}")

    # --- CASCADE FK rules (PostgreSQL only) ---
    if not is_sqlite:
        fk_changes = [
            # (table, column, references, ondelete)
            ("assignments", "course_id", "courses(id)", "CASCADE"),
            ("course_contents", "course_id", "courses(id)", "CASCADE"),
            ("messages", "conversation_id", "conversations(id)", "CASCADE"),
            ("messages", "sender_id", "users(id)", "CASCADE"),
            ("notifications", "user_id", "users(id)", "CASCADE"),
            ("students", "user_id", "users(id)", "CASCADE"),
            ("teachers", "user_id", "users(id)", "CASCADE"),
            ("study_guides", "user_id", "users(id)", "CASCADE"),
            ("teacher_communications", "user_id", "users(id)", "CASCADE"),
            ("tasks", "created_by_user_id", "users(id)", "CASCADE"),
            ("parent_students", "parent_id", "users(id)", "CASCADE"),
            ("parent_students", "student_id", "students(id)", "CASCADE"),
            ("student_courses", "student_id", "students(id)", "CASCADE"),
            ("student_courses", "course_id", "courses(id)", "CASCADE"),
            ("student_assignments", "student_id", "students(id)", "CASCADE"),
            ("student_assignments", "assignment_id", "assignments(id)", "CASCADE"),
            ("student_teachers", "student_id", "students(id)", "CASCADE"),
            ("conversations", "participant_1_id", "users(id)", "CASCADE"),
            ("conversations", "participant_2_id", "users(id)", "CASCADE"),
            ("courses", "teacher_id", "teachers(id)", "SET NULL"),
            ("courses", "created_by_user_id", "users(id)", "SET NULL"),
            ("tasks", "assigned_to_user_id", "users(id)", "SET NULL"),
            ("tasks", "course_id", "courses(id)", "SET NULL"),
            ("tasks", "course_content_id", "course_contents(id)", "SET NULL"),
            ("tasks", "study_guide_id", "study_guides(id)", "SET NULL"),
            ("tasks", "parent_id", "users(id)", "SET NULL"),
            ("tasks", "student_id", "students(id)", "SET NULL"),
            ("study_guides", "assignment_id", "assignments(id)", "SET NULL"),
            ("study_guides", "course_id", "courses(id)", "SET NULL"),
            ("study_guides", "course_content_id", "course_contents(id)", "SET NULL"),
            ("study_guides", "parent_guide_id", "study_guides(id)", "SET NULL"),
            ("invites", "invited_by_user_id", "users(id)", "SET NULL"),
            ("audit_logs", "user_id", "users(id)", "SET NULL"),
            ("student_teachers", "teacher_user_id", "users(id)", "SET NULL"),
            ("student_teachers", "added_by_user_id", "users(id)", "SET NULL"),
            ("conversations", "student_id", "students(id)", "SET NULL"),
            ("course_contents", "created_by_user_id", "users(id)", "SET NULL"),
        ]

        for table, column, references, ondelete in fk_changes:
            if table not in table_names:
                continue
            try:
                fks = inspector.get_foreign_keys(table)
                for fk in fks:
                    if column in fk.get("constrained_columns", []):
                        fk_name = fk.get("name")
                        if fk_name:
                            conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {fk_name}"))
                        break
                constraint_name = f"fk_{table}_{column}"
                conn.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
                    f"FOREIGN KEY ({column}) REFERENCES {references} ON DELETE {ondelete}"
                ))
            except Exception as e:
                logger.warning(f"Failed to update FK {table}.{column}: {e}")

        # Nullability changes for SET NULL columns
        for table, column in [
            ("invites", "invited_by_user_id"),
            ("course_contents", "created_by_user_id"),
            ("student_teachers", "added_by_user_id"),
        ]:
            if table in table_names:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL"))
                except Exception:
                    pass  # Already nullable

    logger.info("CASCADE/UNIQUE migration complete")


with engine.connect() as conn:
    inspector = sa_inspect(engine)
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "version" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
            logger.info("Added 'version' column to study_guides")
        if "parent_guide_id" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN parent_guide_id INTEGER REFERENCES study_guides(id)"))
            logger.info("Added 'parent_guide_id' column to study_guides")
        if "content_hash" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN content_hash VARCHAR(64)"))
            logger.info("Added 'content_hash' column to study_guides")
        conn.commit()
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "created_by_user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN created_by_user_id INTEGER REFERENCES users(id)"))
            logger.info("Added 'created_by_user_id' column to courses")
        if "is_private" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info("Added 'is_private' column to courses")
        conn.commit()
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "created_by_user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN created_by_user_id INTEGER REFERENCES users(id)"))
            # Migrate existing parent_id data
            conn.execute(text("UPDATE tasks SET created_by_user_id = parent_id WHERE created_by_user_id IS NULL AND parent_id IS NOT NULL"))
            logger.info("Added 'created_by_user_id' column to tasks (migrated from parent_id)")
        if "assigned_to_user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN assigned_to_user_id INTEGER REFERENCES users(id)"))
            # Migrate existing student_id data: resolve student.user_id
            conn.execute(text("UPDATE tasks SET assigned_to_user_id = (SELECT s.user_id FROM students s WHERE s.id = tasks.student_id) WHERE assigned_to_user_id IS NULL AND student_id IS NOT NULL"))
            logger.info("Added 'assigned_to_user_id' column to tasks (migrated from student_id)")
        if "priority" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN priority VARCHAR(10) DEFAULT 'medium'"))
            logger.info("Added 'priority' column to tasks")
        if "category" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN category VARCHAR(50)"))
            logger.info("Added 'category' column to tasks")
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE tasks ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to tasks")
        # Linked entity FK columns
        if "course_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN course_id INTEGER REFERENCES courses(id)"))
            logger.info("Added 'course_id' column to tasks")
        if "course_content_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN course_content_id INTEGER REFERENCES course_contents(id)"))
            logger.info("Added 'course_content_id' column to tasks")
        if "study_guide_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN study_guide_id INTEGER REFERENCES study_guides(id)"))
            logger.info("Added 'study_guide_id' column to tasks")
        # Make parent_id nullable (was NOT NULL in original schema) — PostgreSQL only
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TABLE tasks ALTER COLUMN parent_id DROP NOT NULL"))
                logger.info("Made 'parent_id' nullable on tasks table")
            except Exception:
                pass  # Already nullable or not applicable
        conn.commit()
    # ── tasks: last_reminder_sent_at column (#876) ──────────
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "last_reminder_sent_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN last_reminder_sent_at {col_type}"))
                logger.info("Added 'last_reminder_sent_at' column to tasks")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── tasks: recurring task fields (#880) ──────────────────
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "recurrence_rule" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN recurrence_rule VARCHAR(50)"))
                logger.info("Added 'recurrence_rule' column to tasks")
            except Exception:
                conn.rollback()
        conn.commit()
        if "recurrence_end_date" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN recurrence_end_date {col_type}"))
                logger.info("Added 'recurrence_end_date' column to tasks")
            except Exception:
                conn.rollback()
        conn.commit()
        if "template_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN template_id INTEGER REFERENCES task_templates(id)"))
                logger.info("Added 'template_id' column to tasks")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── tasks: google_calendar_event_id column (Google Calendar sync) ──
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "google_calendar_event_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN google_calendar_event_id VARCHAR(255)"))
                logger.info("Added 'google_calendar_event_id' column to tasks")
            except Exception:
                conn.rollback()
        conn.commit()

    # Make users.email nullable for students created without email (by parent)
    if "users" in inspector.get_table_names():
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
                logger.info("Made 'email' nullable on users table")
            except Exception:
                pass  # Already nullable
            # Drop the unique constraint issue for NULL emails — PostgreSQL unique allows multiple NULLs by default
            conn.commit()
    # Multi-role support: add roles column and backfill from existing role
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "roles" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN roles VARCHAR(50)"))
            if "sqlite" in settings.database_url:
                conn.execute(text("UPDATE users SET roles = role WHERE roles IS NULL"))
            else:
                conn.execute(text("UPDATE users SET roles = LOWER(role::text) WHERE roles IS NULL"))
            logger.info("Added 'roles' column to users and backfilled from role")
            conn.commit()
    # onboarding_completed column (#413/#414)
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "onboarding_completed" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE"))
                # Backfill: users who already completed onboarding (needs_onboarding=0 AND have a role)
                conn.execute(text(
                    "UPDATE users SET onboarding_completed = TRUE "
                    "WHERE needs_onboarding = FALSE AND role IS NOT NULL"
                ))
                logger.info("Added 'onboarding_completed' column to users and backfilled")
            except Exception:
                conn.rollback()
            conn.commit()
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "course_content_id" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN course_content_id INTEGER REFERENCES course_contents(id)"))
            logger.info("Added 'course_content_id' column to study_guides")
        conn.commit()
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "is_default" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info("Added 'is_default' column to courses")
        conn.commit()
    if "course_contents" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "text_content" not in existing_cols:
            conn.execute(text("ALTER TABLE course_contents ADD COLUMN text_content TEXT"))
            logger.info("Added 'text_content' column to course_contents")
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE course_contents ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to course_contents")
        if "last_viewed_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE course_contents ADD COLUMN last_viewed_at {col_type}"))
            logger.info("Added 'last_viewed_at' column to course_contents")
        conn.commit()
        if "google_classroom_material_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN google_classroom_material_id VARCHAR(255)"))
                logger.info("Added 'google_classroom_material_id' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()
        # File storage columns (#572)
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        for col_name, col_type in [
            ("file_path", "VARCHAR(500)"),
            ("original_filename", "VARCHAR(500)"),
            ("file_size", "INTEGER"),
            ("mime_type", "VARCHAR(100)"),
        ]:
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE course_contents ADD COLUMN {col_name} {col_type}"))
                    logger.info("Added '%s' column to course_contents", col_name)
                except Exception:
                    conn.rollback()
        conn.commit()
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE study_guides ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to study_guides")
        conn.commit()

    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "focus_prompt" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN focus_prompt VARCHAR(2000)"))
                logger.info("Added 'focus_prompt' column to study_guides")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: needs_onboarding column (#412) ───────────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "needs_onboarding" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN needs_onboarding BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'needs_onboarding' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: make role column nullable (#412) ───────────────
    if "sqlite" not in settings.database_url:
        if "users" in inspector.get_table_names():
            try:
                conn.execute(text("ALTER TABLE users ALTER COLUMN role DROP NOT NULL"))
                logger.info("Made 'role' nullable on users table")
            except Exception:
                conn.rollback()
            conn.commit()

    # ── audit_logs migrations ────────────────────────────────────
    if "audit_logs" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("audit_logs")}
        if "action" in existing_cols:
            # Widen action column from VARCHAR(20) to VARCHAR(50)
            if "sqlite" not in settings.database_url:
                try:
                    conn.execute(text("ALTER TABLE audit_logs ALTER COLUMN action TYPE VARCHAR(50)"))
                    logger.info("Widened audit_logs.action to VARCHAR(50)")
                except Exception:
                    conn.rollback()
        conn.commit()

    # ── users migrations (task_reminder_days) ─────────────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "task_reminder_days" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN task_reminder_days VARCHAR(50) DEFAULT '1,3'"))
            logger.info("Added 'task_reminder_days' column to users")
        conn.commit()

    # ── notifications enum migration (TASK_DUE) ──────────────────
    # NOTE: ALTER TYPE ADD VALUE in PostgreSQL can leave connection in
    # aborted state on failure; commit before and after to isolate.
    if "sqlite" not in settings.database_url:
        try:
            conn.execute(text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'TASK_DUE'"))
            conn.commit()
            logger.info("Added TASK_DUE to notificationtype enum")
        except Exception:
            conn.rollback()  # Required: clear aborted transaction state
        try:
            conn.execute(text("ALTER TYPE invitetype ADD VALUE IF NOT EXISTS 'PARENT'"))
            conn.commit()
            logger.info("Added PARENT to invitetype enum")
        except Exception:
            conn.rollback()  # Required: clear aborted transaction state

    # ── student_teachers: make teacher_user_id nullable ──────────
    if "student_teachers" in inspector.get_table_names():
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TABLE student_teachers ALTER COLUMN teacher_user_id DROP NOT NULL"))
                logger.info("Made 'teacher_user_id' nullable on student_teachers table")
            except Exception:
                conn.rollback()  # Required: clear aborted transaction state
        conn.commit()

    # ── students: add profile detail columns (#267, #303) ────────
    is_pg = "sqlite" not in settings.database_url
    if "students" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        col_type_date = "DATE"
        col_type_ts = "TIMESTAMPTZ" if is_pg else "DATETIME"
        new_student_cols = [
            ("date_of_birth", col_type_date),
            ("phone", "VARCHAR(30)"),
            ("address", "VARCHAR(255)"),
            ("city", "VARCHAR(100)"),
            ("province", "VARCHAR(100)"),
            ("postal_code", "VARCHAR(20)"),
            ("notes", "TEXT"),
            ("updated_at", col_type_ts),
        ]
        for col_name, col_type in new_student_cols:
            if col_name not in existing_cols:
                try:
                    if is_pg:
                        conn.execute(text(f"ALTER TABLE students ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    else:
                        conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Added '{col_name}' column to students")
                except Exception:
                    conn.rollback()  # Column may already exist from concurrent instance
        conn.commit()

    # ── CASCADE + UNIQUE constraint migration (#145, #146, #187) ──
    _apply_cascade_and_unique_migration(conn, inspector)

    # ── One-time: promote users to admin ──
    for admin_email in ["theepang@gmail.com", "clazzbridge@gmail.com"]:
        try:
            row = conn.execute(text(
                "SELECT id, roles FROM users WHERE email = :email "
                "AND (roles IS NULL OR roles NOT LIKE '%admin%')"
            ), {"email": admin_email}).first()
            if row:
                existing = row[1] or ""
                new_roles = "admin," + existing if existing else "admin"
                conn.execute(text(
                    "UPDATE users SET role = 'ADMIN', roles = :roles WHERE id = :id"
                ), {"roles": new_roles, "id": row[0]})
                logger.info("Promoted %s to admin", admin_email)
        except Exception:
            pass  # User may not exist yet in this environment

    conn.commit()

    # ── users: email_verified columns (#417) ───────────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "email_verified" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'email_verified' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        if "email_verified_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN email_verified_at {col_type}"))
                logger.info("Added 'email_verified_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        # Grandfather existing users as verified
        try:
            conn.execute(text("UPDATE users SET email_verified = TRUE WHERE email_verified = FALSE OR email_verified IS NULL"))
            logger.info("Grandfathered existing users as email_verified=TRUE")
        except Exception:
            conn.rollback()
        conn.commit()

    # --- teachers table: add is_platform_user (#58) ---
    if "teachers" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("teachers")}
        if "is_platform_user" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE teachers ADD COLUMN is_platform_user BOOLEAN DEFAULT TRUE"))
                logger.info("Added 'is_platform_user' column to teachers")
            except Exception:
                conn.rollback()
        conn.commit()

    # --- invites table: add last_resent_at (#253) ---
    if "invites" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("invites")}
        if "last_resent_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE invites ADD COLUMN last_resent_at {col_type}"))
                logger.info("Added 'last_resent_at' column to invites")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── Phase 1 New Workflow: users.username column ─────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "username" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
                logger.info("Added 'username' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── Phase 1 New Workflow: students.parent_email column ────
    if "students" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        if "parent_email" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE students ADD COLUMN parent_email VARCHAR(255)"))
                logger.info("Added 'parent_email' column to students")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── Phase 1 New Workflow: courses.classroom_type column ───
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "classroom_type" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE courses ADD COLUMN classroom_type VARCHAR(20)"))
                logger.info("Added 'classroom_type' column to courses")
            except Exception:
                conn.rollback()
        conn.commit()
        # Backfill NULL classroom_type rows (fix for courses added before column had a default)
        try:
            conn.execute(text("UPDATE courses SET classroom_type = 'manual' WHERE classroom_type IS NULL"))
            logger.info("Backfilled NULL classroom_type values to 'manual'")
        except Exception:
            conn.rollback()
        conn.commit()

    # ── Phase 1 New Workflow: notifications ACK columns ───────
    if "notifications" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("notifications")}

        if "requires_ack" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN requires_ack BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'requires_ack' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "acked_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE notifications ADD COLUMN acked_at {col_type}"))
                logger.info("Added 'acked_at' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "source_type" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN source_type VARCHAR(50)"))
                logger.info("Added 'source_type' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "source_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN source_id INTEGER"))
                logger.info("Added 'source_id' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "next_reminder_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE notifications ADD COLUMN next_reminder_at {col_type}"))
                logger.info("Added 'next_reminder_at' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "reminder_count" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN reminder_count INTEGER DEFAULT 0"))
                logger.info("Added 'reminder_count' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── Phase 1 New Workflow: notification enum types (PostgreSQL) ──
    if is_pg:
        new_notif_types = [
            "LINK_REQUEST", "MATERIAL_UPLOADED", "STUDY_GUIDE_CREATED",
            "PARENT_REQUEST", "ASSESSMENT_UPCOMING", "PROJECT_DUE",
        ]
        for ntype in new_notif_types:
            try:
                conn.execute(text(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{ntype}'"))
                conn.commit()
            except Exception:
                conn.rollback()

    # ── users.google_granted_scopes column (#727) ────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "google_granted_scopes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_granted_scopes VARCHAR(1024)"))
                logger.info("Added 'google_granted_scopes' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users.onboarding_dismissed_at column (#869) ─────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "onboarding_dismissed_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN onboarding_dismissed_at {col_type}"))
                logger.info("Added 'onboarding_dismissed_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── student_assignments: submission fields (#839) ──────────
    if "student_assignments" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("student_assignments")}
        if "submission_file_path" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN submission_file_path VARCHAR(500)"))
                logger.info("Added 'submission_file_path' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

        if "submission_file_name" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN submission_file_name VARCHAR(255)"))
                logger.info("Added 'submission_file_name' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

        if "submission_notes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN submission_notes TEXT"))
                logger.info("Added 'submission_notes' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

        if "is_late" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN is_late BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'is_late' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── teachers: auto_invited_at column (#946) ──────────────
    if "teachers" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("teachers")}
        if "auto_invited_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE teachers ADD COLUMN auto_invited_at {col_type}"))
                logger.info("Added 'auto_invited_at' column to teachers")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: account lockout columns (#796) ──────────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "failed_login_attempts" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"))
                logger.info("Added 'failed_login_attempts' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "locked_until" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN locked_until {col_type}"))
                logger.info("Added 'locked_until' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "last_failed_login" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN last_failed_login {col_type}"))
                logger.info("Added 'last_failed_login' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: unique index on username (#546) ──────────────────
    try:
        if "sqlite" in settings.database_url:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_unique ON users(username)"))
        else:
            conn.execute(text("CREATE UNIQUE INDEX ix_users_username_unique ON users(username) WHERE username IS NOT NULL"))
        logger.info("Added unique index ix_users_username_unique on users.username")
    except Exception:
        conn.rollback()
    conn.commit()

    # One-time data fix: correct known invalid email (#408)
    try:
        conn.execute(text(
            "UPDATE users SET email = 'haashinik30@gmail.com' WHERE email = 'haashinik30@gmailcom'"
        ))
        conn.execute(text(
            "UPDATE invites SET email = 'haashinik30@gmail.com' WHERE email = 'haashinik30@gmailcom'"
        ))
        conn.commit()
    except Exception:
        conn.rollback()

    # ── users: consent_preferences + consent_given_at columns (#797) ──
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "consent_preferences" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN consent_preferences TEXT"))
                logger.info("Added 'consent_preferences' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        if "consent_given_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN consent_given_at {col_type}"))
                logger.info("Added 'consent_given_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── students: MFIPPA consent columns (#783) ──────────────────────
    if "students" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        if "consent_status" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE students ADD COLUMN consent_status VARCHAR(20) DEFAULT 'pending'"))
                logger.info("Added 'consent_status' column to students")
            except Exception:
                conn.rollback()
        conn.commit()
        if "parent_consent_given_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE students ADD COLUMN parent_consent_given_at {col_type}"))
                logger.info("Added 'parent_consent_given_at' column to students")
            except Exception:
                conn.rollback()
        conn.commit()
        if "student_consent_given_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE students ADD COLUMN student_consent_given_at {col_type}"))
                logger.info("Added 'student_consent_given_at' column to students")
            except Exception:
                conn.rollback()
        conn.commit()
        # Study streak columns (#834)
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        if "study_streak_days" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE students ADD COLUMN study_streak_days INTEGER NOT NULL DEFAULT 0"))
                logger.info("Added 'study_streak_days' column to students")
            except Exception:
                conn.rollback()
        conn.commit()
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        if "last_study_date" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE students ADD COLUMN last_study_date DATE"))
                logger.info("Added 'last_study_date' column to students")
            except Exception:
                conn.rollback()
        conn.commit()
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        if "longest_streak" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE students ADD COLUMN longest_streak INTEGER NOT NULL DEFAULT 0"))
                logger.info("Added 'longest_streak' column to students")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: account deletion columns (#964) ────────────────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "deletion_requested_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN deletion_requested_at {col_type}"))
                logger.info("Added 'deletion_requested_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        if "deletion_scheduled_for" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN deletion_scheduled_for {col_type}"))
                logger.info("Added 'deletion_scheduled_for' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        if "last_export_requested_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN last_export_requested_at {col_type}"))
                logger.info("Added 'last_export_requested_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: BYOK encrypted AI key column (#578) ───────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "ai_api_key_encrypted" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN ai_api_key_encrypted VARCHAR(512)"))
                logger.info("Added 'ai_api_key_encrypted' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── study_guides: source_guide_id column (#573) — content reuse pool ──
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "source_guide_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN source_guide_id INTEGER REFERENCES study_guides(id)"))
                logger.info("Added 'source_guide_id' column to study_guides")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── users: subscription_tier column (#1007) ──────────────────
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "subscription_tier" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) NOT NULL DEFAULT 'free'"))
                logger.info("Added 'subscription_tier' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── course_contents: material_type + is_assessment columns (#666) ──
    if "course_contents" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "material_type" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN material_type VARCHAR(50)"))
                logger.info("Added 'material_type' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "is_assessment" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN is_assessment INTEGER DEFAULT 0"))
                logger.info("Added 'is_assessment' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── sample_exams: ensure table has all expected columns (#577) ────────────
    if "sample_exams" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("sample_exams")}
        for col_name, col_def in [
            ("description", "TEXT"),
            ("original_content", "TEXT"),
            ("file_name", "VARCHAR(500)"),
            ("assessment_json", "TEXT"),
            ("assessment_generated_at", "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"),
            ("exam_type", "VARCHAR(50) DEFAULT 'sample'"),
            ("difficulty_level", "VARCHAR(20)"),
            ("is_public", "BOOLEAN DEFAULT FALSE" if "sqlite" not in settings.database_url else "INTEGER DEFAULT 0"),
        ]:
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE sample_exams ADD COLUMN {col_name} {col_def}"))
                    logger.info("Added '%s' column to sample_exams", col_name)
                except Exception:
                    conn.rollback()
        conn.commit()

    # ── Multi-LMS: lms_provider + lms_external_id on courses (#22) ───────────
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "lms_provider" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE courses ADD COLUMN lms_provider VARCHAR(50)"))
                logger.info("Added 'lms_provider' column to courses")
            except Exception:
                conn.rollback()
        conn.commit()
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "lms_external_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE courses ADD COLUMN lms_external_id VARCHAR(255)"))
                logger.info("Added 'lms_external_id' column to courses")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── Multi-LMS: lms_provider + lms_external_id on assignments (#22) ───────
    if "assignments" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("assignments")}
        if "lms_provider" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN lms_provider VARCHAR(50)"))
                logger.info("Added 'lms_provider' column to assignments")
            except Exception:
                conn.rollback()
        conn.commit()
        existing_cols = {c["name"] for c in inspector.get_columns("assignments")}
        if "lms_external_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN lms_external_id VARCHAR(255)"))
                logger.info("Added 'lms_external_id' column to assignments")
            except Exception:
                conn.rollback()
        conn.commit()

    # ── Multi-LMS: lms_provider + lms_external_id on course_contents (#22) ──
    if "course_contents" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "lms_provider" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN lms_provider VARCHAR(50)"))
                logger.info("Added 'lms_provider' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "lms_external_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN lms_external_id VARCHAR(255)"))
                logger.info("Added 'lms_external_id' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()

# ── Seed email templates (#513) ──────────────────────────────────────────────
with SessionLocal() as _seed_db:
    try:
        from app.api.routes.admin import seed_email_templates
        seed_email_templates(_seed_db)
    except Exception as _e:
        logger.warning("Failed to seed email templates at startup: %s", _e)

# ── Seed Ontario boards + OSSD course catalog (#500, #511) ───────────────────
with SessionLocal() as _seed_db:
    try:
        from app.data.ontario_seed import seed_ontario_data
        seed_ontario_data(_seed_db)
    except Exception as _e:
        logger.warning("Failed to seed Ontario course catalog at startup: %s", _e)

# ── Seed Ontario curriculum expectations (#571) ───────────────────────────────
with SessionLocal() as _seed_db:
    try:
        from app.data.curriculum_seed import seed_curriculum_data
        seed_curriculum_data(_seed_db)
    except Exception as _e:
        logger.warning("Failed to seed Ontario curriculum expectations at startup: %s", _e)


_is_prod = "sqlite" not in settings.database_url

app = FastAPI(
    title=settings.app_name,
    description="AI-powered education management platform",
    version="0.1.0",
    docs_url=None if _is_prod else "/api/docs",
    redoc_url=None if _is_prod else "/api/redoc",
    openapi_url=None if _is_prod else "/api/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# FAQ hint exceptions (errors with faq_code for frontend hint links)
from app.core.faq_errors import FAQHintException, faq_hint_exception_handler  # noqa: E402
app.add_exception_handler(FAQHintException, faq_hint_exception_handler)


# Global exception handler — logs full tracebacks for 500 errors
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions, log full traceback, return 500."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}\n"
        f"{traceback.format_exc()}"
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing."""
    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Get user ID from request state if available
    user_id = getattr(request.state, "user_id", None)

    # Log the request
    request_logger.log_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_ip=client_ip,
        user_id=user_id,
    )

    return response


# CORS middleware — restrict origins (never use wildcard with credentials)
if settings.allowed_origins:
    cors_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
else:
    # Safe defaults: local dev + deployed frontend
    cors_origins = [
        "http://localhost:5173",
        "http://localhost:8000",
        settings.frontend_url,
    ]
    if settings.environment == "production":
        # In production, only allow the configured frontend URL
        cors_origins = [settings.frontend_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Domain redirect middleware (301 non-canonical → canonical)
# No-ops when canonical_domain is empty; always registered, checks at runtime
app.add_middleware(DomainRedirectMiddleware)

# GZip compression — compress responses > 500 bytes (#516)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Include all API routers at /api prefix
# NOTE: Mobile apps will use these same endpoints initially.
# Dedicated /api/v1 endpoints will be created as mobile-specific features are needed.
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(google_classroom.router, prefix="/api")
app.include_router(google_calendar.router, prefix="/api")
app.include_router(study.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(notification_preferences.router, prefix="/api")
app.include_router(teacher_communications.router, prefix="/api")
app.include_router(parent.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(course_contents.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(inspiration.router, prefix="/api")
app.include_router(faq.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(link_requests.router, prefix="/api")
app.include_router(quiz_results.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(grades.router, prefix="/api")
app.include_router(consent.router, prefix="/api")
app.include_router(mcp_config.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(quiz_assignments.router, prefix="/api")
app.include_router(grade_entries.router, prefix="/api")
app.include_router(report_cards.router, prefix="/api")
app.include_router(mock_exams.router, prefix="/api")
app.include_router(academic_plans.router, prefix="/api")
app.include_router(course_recommendations.router, prefix="/api")
app.include_router(ontario.router, prefix="/api")
app.include_router(curriculum.router, prefix="/api")
app.include_router(exam_prep.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(admin_analytics.router, prefix="/api")
app.include_router(sample_exams.router, prefix="/api")
app.include_router(lms_connections.router, prefix="/api")

logger.info("API routes registered at /api")

# MCP server — mount after all routers so it can discover endpoints
from app.mcp import setup_mcp  # noqa: E402
setup_mcp(app)
logger.info("MCP server mounted at /mcp")

logger.info("All routers registered")


@app.get("/health")
def health_check():
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "version": os.environ.get("APP_VERSION", "dev"),
        "environment": settings.environment,
    }


@app.post("/api/errors/log")
async def log_frontend_error(request: Request):
    """Receive frontend error reports so they appear in Cloud Run logs."""
    try:
        body = await request.json()
        logger.error("FRONTEND ERROR at %s: %s\nStack: %s\nComponent: %s",
                     body.get("url", "?"),
                     body.get("message", "?"),
                     body.get("stack", ""),
                     body.get("componentStack", ""))
    except Exception:
        pass
    return {"ok": True}


# Serve frontend static files in production
FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static-assets")

    # Long-lived cache for hashed static assets (#516)
    @app.middleware("http")
    async def cache_hashed_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve frontend SPA — returns index.html for all non-API routes."""
        # Return JSON 404 for unmatched /api/* paths (#517)
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            FRONTEND_DIR / "index.html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
else:
    @app.get("/")
    def root():
        return {"message": "ClassBridge API", "app": settings.app_name, "docs": "/docs"}


@app.on_event("startup")
async def startup_event():
    from apscheduler.triggers.cron import CronTrigger
    from app.services.scheduler import scheduler, start_scheduler
    from app.jobs.assignment_reminders import check_assignment_reminders
    from app.jobs.task_reminders import check_task_reminders
    from app.jobs.notification_reminders import check_notification_reminders
    from app.services.inspiration_service import seed_messages
    from app.services.faq_seed_service import seed_faq
    from app.services.grade_seed_service import seed_grades

    # Seed inspiration messages, FAQ entries, and grade records if tables are empty
    db = SessionLocal()
    try:
        seed_messages(db)
        seed_faq(db)
        seed_grades(db)
    finally:
        db.close()

    scheduler.add_job(
        check_assignment_reminders,
        CronTrigger(hour=8, minute=0),
        id="assignment_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_task_reminders,
        CronTrigger(hour=8, minute=15),
        id="task_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_notification_reminders,
        CronTrigger(hour="*/6"),
        id="notification_reminders",
        replace_existing=True,
    )

    # Cleanup expired token blacklist entries daily at 3 AM
    def cleanup_token_blacklist():
        from datetime import datetime
        _db = SessionLocal()
        try:
            deleted = _db.query(TokenBlacklist).filter(TokenBlacklist.expires_at < datetime.utcnow()).delete()
            _db.commit()
            if deleted:
                logger.info(f"Cleaned up {deleted} expired token blacklist entries")
        except Exception as e:
            _db.rollback()
            logger.warning(f"Token blacklist cleanup failed: {e}")
        finally:
            _db.close()

    scheduler.add_job(
        cleanup_token_blacklist,
        CronTrigger(hour=3, minute=0),
        id="token_blacklist_cleanup",
        replace_existing=True,
    )

    # Background Google Classroom sync once daily at 6 AM
    from app.jobs.google_sync import sync_google_classrooms
    scheduler.add_job(
        sync_google_classrooms,
        CronTrigger(hour=6, minute=0),
        id="google_classroom_sync",
        replace_existing=True,
    )

    # Account deletion cleanup — runs daily at 2 AM (#964)
    from app.jobs.account_deletion import process_scheduled_deletions
    scheduler.add_job(
        process_scheduled_deletions,
        CronTrigger(hour=2, minute=0),
        id="account_deletion_cleanup",
        replace_existing=True,
    )

    # Daily notification digest — runs every hour, sends to users whose digest_hour matches (#966)
    from app.jobs.notification_digest import send_daily_digests
    scheduler.add_job(
        send_daily_digests,
        CronTrigger(minute=0),  # top of every hour
        id="notification_digest",
        replace_existing=True,
    )

    # Teacher comm sync disabled — all syncs are manual/on-demand per parent-first platform design
    # from app.jobs.teacher_comm_sync import check_teacher_communications
    # scheduler.add_job(check_teacher_communications, IntervalTrigger(minutes=15), id="teacher_comm_sync", replace_existing=True)
    start_scheduler()
    logger.info("EMAI application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("EMAI application shutting down")
