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
from app.db.database import Base, engine
from app.api.routes import auth, users, students, courses, assignments, google_classroom, study, logs, messages, notifications, teacher_communications, parent, admin, invites, tasks, course_contents, search

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
from app.models import User, Student, Teacher, Course, Assignment, StudyGuide, Conversation, Message, Notification, TeacherCommunication, Invite, Task, CourseContent, AuditLog
from app.models.student import parent_students, student_teachers  # noqa: F401 — ensure join tables are created
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")

# Lightweight schema migration: add columns missing from pre-existing tables
from sqlalchemy import inspect as sa_inspect, text
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

        # ── audit_logs migrations ────────────────────────────────────
        existing_cols = {c["name"] for c in inspector.get_columns("audit_logs")}
        if "action" in existing_cols:
            # Widen action column from VARCHAR(20) to VARCHAR(50)
            if "sqlite" not in settings.database_url:
                conn.execute(text("ALTER TABLE audit_logs ALTER COLUMN action TYPE VARCHAR(50)"))
                logger.info("Widened audit_logs.action to VARCHAR(50)")

        # ── users migrations (task_reminder_days) ─────────────────────
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "task_reminder_days" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN task_reminder_days VARCHAR(50) DEFAULT '1,3'"))
            logger.info("Added 'task_reminder_days' column to users")

        # ── notifications enum migration (TASK_DUE) ──────────────────
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'TASK_DUE'"))
                logger.info("Added TASK_DUE to notificationtype enum")
            except Exception:
                pass  # Value may already exist

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

# Include routers
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

logger.info("All routers registered")


@app.get("/health")
def health_check():
    logger.debug("Health check requested")
    return {"status": "healthy"}


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
            headers={"Cache-Control": "no-cache"},
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
