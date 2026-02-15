import os
import time
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, RequestLogger
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.db.database import Base, engine, SessionLocal
from app.api.routes import auth, users, students, courses, assignments, google_classroom, study, logs, messages, notifications, teacher_communications, parent, admin, invites, tasks, course_contents, search, inspiration

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
from app.models import User, Student, Teacher, Course, Assignment, StudyGuide, Conversation, Message, Notification, TeacherCommunication, Invite, Task, CourseContent, AuditLog, InspirationMessage
from app.models.student import parent_students, student_teachers  # noqa: F401 — ensure join tables are created
from app.models.token_blacklist import TokenBlacklist  # noqa: F401 — ensure table is created
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
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE study_guides ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to study_guides")
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


app = FastAPI(
    title=settings.app_name,
    description="AI-powered education management platform",
    version="0.1.0",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Include all API routers at /api prefix
# NOTE: Mobile apps will use these same endpoints initially.
# Dedicated /api/v1 endpoints will be created as mobile-specific features are needed.
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(google_classroom.router, prefix="/api")
app.include_router(study.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(teacher_communications.router, prefix="/api")
app.include_router(parent.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(course_contents.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(inspiration.router, prefix="/api")

logger.info("API routes registered at /api")

logger.info("All routers registered")


@app.get("/health")
def health_check():
    logger.debug("Health check requested")
    return {"status": "healthy"}


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

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve frontend SPA — returns index.html for all non-API routes."""
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
    from app.services.inspiration_service import seed_messages

    # Seed inspiration messages if table is empty
    db = SessionLocal()
    try:
        seed_messages(db)
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

    # Teacher comm sync disabled — all syncs are manual/on-demand per parent-first platform design
    # from apscheduler.triggers.interval import IntervalTrigger
    # from app.jobs.teacher_comm_sync import check_teacher_communications
    # scheduler.add_job(check_teacher_communications, IntervalTrigger(minutes=15), id="teacher_comm_sync", replace_existing=True)
    start_scheduler()
    logger.info("EMAI application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("EMAI application shutting down")
