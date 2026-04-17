# ClassBridge v1.0 - Phase 1 Launch
# Deploy test - 2026-03-21
import os
import time
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from jose import jwt as jose_jwt

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, RequestLogger, generate_trace_id, trace_id_var, user_id_var, endpoint_var
from app.core.middleware import DomainRedirectMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.db.database import Base, engine, SessionLocal
from app.api.routes import auth, users, students, courses, assignments, google_classroom, study, logs, messages, notifications, teacher_communications, parent, parent_ai, admin, admin_waitlist, invites, tasks, course_contents, search, inspiration, faq, analytics, link_requests, quiz_results, onboarding, grades, waitlist, notes, ai_usage, account_deletion, data_export, activity, resource_links, help as help_routes, briefing, weekly_digest, study_sharing, calendar_import, tutorials, readiness, conversation_starters, daily_digest, survey, admin_survey, xp, events, study_requests, timeline, study_sessions, report_card, bug_reports, daily_quiz
from app.api.routes import school_report_cards  # §6.121 Report Card Upload & AI Analysis
from app.api.routes import study_suggestions
from app.api.routes import holiday_dates
from app.api.routes import family_report
from app.api.routes import teacher_thanks
from app.api.routes import csv_import
from app.api.routes import weekly_report
from app.api.routes import journey
from app.api.routes import parent_email_digest
from app.api.routes import admin_contacts
from app.api.routes import features as features_route
from app.api.routes import ile

# Initialize logging first (auto-determines level based on environment)
setup_logging(
    app_name="emai",
    log_level=settings.log_level,  # Empty = auto (DEBUG in dev, WARNING in prod)
    environment=settings.environment,
    enable_console=True,
    enable_file=settings.log_to_file,
    log_format=getattr(settings, "log_format", ""),  # Empty = auto (json in prod, text in dev)
)

logger = get_logger(__name__)
request_logger = RequestLogger(get_logger("emai.requests"))

logger.info("Starting EMAI application...")

# Create database tables
from app.models import User, Student, Teacher, Course, Assignment, StudyGuide, Conversation, Message, Notification, TeacherCommunication, Invite, Task, CourseContent, AuditLog, InspirationMessage, FAQQuestion, FAQAnswer, GradeRecord, LinkRequest, NotificationSuppression, QuizResult, Waitlist, AILimitRequest, Note, NoteVersion, DataExportRequest, SourceFile, HelpArticle, EnrollmentRequest, ContentImage, SurveyResponse, SurveyAnswer, HolidayDate, StudyRequest
from app.models.student import parent_students, student_teachers  # noqa: F401 — ensure join tables are created
from app.models.token_blacklist import TokenBlacklist  # noqa: F401 — ensure table is created
from app.models.ai_usage_history import AIUsageHistory, AIAdminActionLog  # noqa: F401 — ensure tables are created
from app.models.wallet import Wallet, PackageTier, WalletTransaction, CreditPackage  # noqa: F401
from app.models.xp import XpLedger, XpSummary, Badge, StreakLog  # noqa: F401
from app.models.detected_event import DetectedEvent  # noqa: F401
from app.models.translated_summary import TranslatedSummary  # noqa: F401
from app.models.study_session import StudySession  # noqa: F401
from app.models.bug_report import BugReport  # noqa: F401
from app.models.daily_quiz import DailyQuiz  # noqa: F401
from app.models.course_announcement import CourseAnnouncement  # noqa: F401
from app.models.teacher_thanks import TeacherThanks  # noqa: F401
from app.models.parent_contact import ParentContact, ParentContactNote, OutreachTemplate, OutreachLog  # noqa: F401 — ensure CRM tables are created
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")

# CRITICAL: Add UTDF columns synchronously before any request can hit the model.
# Background migrations may be blocked by advisory lock from previous instance.
# These are idempotent (try/except on "column already exists").
_is_pg = "sqlite" not in settings.database_url
print(f"[UTDF-MIGRATION] _is_pg={_is_pg} database_url_prefix={settings.database_url[:20]}", flush=True)
if _is_pg:
    _utdf_cols = [
        ("course_contents", "detected_subject", "VARCHAR(50)"),
        ("course_contents", "detection_confidence", "DOUBLE PRECISION"),
        ("course_contents", "subject_confidence", "DOUBLE PRECISION"),
        ("course_contents", "template_key", "VARCHAR(50)"),
        ("course_contents", "classification_override", "BOOLEAN DEFAULT FALSE"),
        ("study_guides", "template_key", "VARCHAR(50)"),
        ("study_guides", "num_questions", "INTEGER"),
        ("study_guides", "difficulty", "VARCHAR(20)"),
        ("study_guides", "answer_key_markdown", "TEXT"),
        ("study_guides", "weak_topics", "TEXT"),
        ("study_guides", "ai_engine", "VARCHAR(20)"),
    ]
    try:
        with engine.connect() as _conn:
            for _tbl, _col, _typ in _utdf_cols:
                try:
                    _conn.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN IF NOT EXISTS {_col} {_typ}"))
                except Exception as _col_err:
                    logger.warning("Column %s.%s migration note: %s", _tbl, _col, _col_err)
            _conn.commit()
            print("[UTDF-MIGRATION] All columns committed successfully", flush=True)
            logger.info("UTDF synchronous column migration completed")
    except Exception as _conn_err:
        print(f"[UTDF-MIGRATION] FAILED: {_conn_err}", flush=True)
        logger.error("UTDF synchronous migration FAILED (connection level): %s", _conn_err)

# Lightweight schema migration: extracted to app/db/migrations.py (#2824)
from app.db.migrations import run_startup_migrations


_is_prod = "sqlite" not in settings.database_url

# Readiness flag — set to True after startup_event() completes.
# Prevents Cloud Run from routing traffic before migrations/seeding finish (#2034).
_app_ready = os.environ.get("TESTING") == "1"  # Skip readiness gate in tests

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

# Google credential refresh failures → 401 with reauth hint
from google.auth.exceptions import RefreshError as _GoogleRefreshError  # noqa: E402
from app.core.faq_errors import GOOGLE_REAUTH_REQUIRED  # noqa: E402


@app.exception_handler(_GoogleRefreshError)
async def google_refresh_error_handler(request: Request, exc: _GoogleRefreshError):
    """Convert permanent Google token refresh failures to 401 with FAQ hint."""
    return JSONResponse(
        status_code=401,
        content={
            "detail": "Your Google connection has expired. Please reconnect your Google account.",
            "faq_code": GOOGLE_REAUTH_REQUIRED,
        },
    )


# Global exception handler — logs full tracebacks for 500 errors
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions, log full traceback, return 500."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}\n"
        f"{traceback.format_exc()}"
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Readiness gate — return 503 while app is still initializing (#2034).
# Allows /health so Cloud Run startup probes can check readiness.
@app.middleware("http")
async def check_ready(request: Request, call_next):
    if not _app_ready and request.url.path != "/health":
        return JSONResponse(
            status_code=503,
            content={"detail": "Service starting"},
        )
    return await call_next(request)


# Request logging middleware with correlation IDs
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing and correlation IDs."""
    # Generate or reuse trace ID from incoming header
    tid = request.headers.get("X-Request-ID") or generate_trace_id()
    trace_id_var.set(tid)
    endpoint_var.set(request.url.path)

    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Best-effort user identification for logging — NOT an auth check
    uid = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = jose_jwt.decode(
                auth_header[7:],
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
            uid = payload.get("sub") or payload.get("user_id")
            if uid is not None:
                uid = int(uid)
        except Exception:
            pass
    if uid is not None:
        user_id_var.set(uid)

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Prefer user_id from request.state (set by deps) over JWT parse
    user_id = getattr(request.state, "user_id", None) or uid

    # Add trace ID to response headers
    response.headers["X-Request-ID"] = tid

    # Log the request
    request_logger.log_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_ip=client_ip,
        user_id=user_id,
        trace_id=tid,
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
    expose_headers=["Content-Disposition", "X-Request-ID"],
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
app.include_router(study.router, prefix="/api")
app.include_router(study_sharing.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(teacher_communications.router, prefix="/api")
app.include_router(parent.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(admin_waitlist.router, prefix="/api")
app.include_router(admin_contacts.router, prefix="/api")
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
app.include_router(waitlist.router, prefix="/api")
app.include_router(ai_usage.router, prefix="/api")
app.include_router(ai_usage.admin_router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(account_deletion.router, prefix="/api")
app.include_router(account_deletion.admin_router, prefix="/api")
app.include_router(data_export.router, prefix="/api")
app.include_router(activity.router, prefix="/api")
app.include_router(resource_links.router, prefix="/api")
app.include_router(help_routes.router, prefix="/api")
app.include_router(briefing.router, prefix="/api")
app.include_router(parent_ai.router, prefix="/api")
app.include_router(weekly_digest.router, prefix="/api")
app.include_router(calendar_import.router, prefix="/api")
app.include_router(tutorials.router, prefix="/api")
app.include_router(readiness.router, prefix="/api")
app.include_router(conversation_starters.router, prefix="/api")
app.include_router(daily_digest.router, prefix="/api")
app.include_router(survey.router, prefix="/api")
app.include_router(admin_survey.router, prefix="/api")
app.include_router(xp.router, prefix="/api")
app.include_router(study_requests.router, prefix="/api")
app.include_router(study_sessions.router, prefix="/api")
from app.api.routes import wallet as wallet_routes
app.include_router(wallet_routes.router, prefix="/api")
app.include_router(wallet_routes.payments_router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(report_card.router, prefix="/api")
app.include_router(bug_reports.router, prefix="/api")
app.include_router(school_report_cards.router, prefix="/api")
app.include_router(study_suggestions.router, prefix="/api")
app.include_router(daily_quiz.router, prefix="/api")
app.include_router(holiday_dates.router, prefix="/api")
app.include_router(family_report.router, prefix="/api")
app.include_router(teacher_thanks.router, prefix="/api")
app.include_router(csv_import.router, prefix="/api")
app.include_router(weekly_report.router, prefix="/api")
app.include_router(journey.router, prefix="/api")
app.include_router(parent_email_digest.router, prefix="/api")
from app.api.routes import admin_outreach_templates
app.include_router(admin_outreach_templates.router, prefix="/api")
from app.api.routes import admin_outreach
app.include_router(admin_outreach.router, prefix="/api")
app.include_router(features_route.router, prefix="/api")
app.include_router(ile.router, prefix="/api")

logger.info("API routes registered at /api")

logger.info("All routers registered")


@app.get("/health")
def health_check():
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "version": os.environ.get("APP_VERSION", "dev"),
        "environment": settings.environment,
        "migrations_complete": _app_ready,
    }


@app.get("/api/features")
def get_feature_toggles():
    """Public endpoint returning feature availability for the frontend."""
    return {
        "google_classroom": settings.google_classroom_enabled,
        "waitlist_enabled": settings.waitlist_enabled,
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


def seed_wallet_data(db):
    """Seed package_tiers and credit_packages if tables are empty."""
    from app.models.wallet import PackageTier, CreditPackage
    if db.query(PackageTier).count() == 0:
        db.add_all([
            PackageTier(name="free", monthly_credits=0, price_cents=0),
            PackageTier(name="standard", monthly_credits=0, price_cents=0),
            PackageTier(name="premium", monthly_credits=0, price_cents=0),
        ])
        db.commit()
        logger.info("Seeded package_tiers with default tiers")
    if db.query(CreditPackage).count() == 0:
        db.add_all([
            CreditPackage(name="Starter", credits=50, price_cents=200),
            CreditPackage(name="Standard", credits=200, price_cents=500),
            CreditPackage(name="Bulk", credits=500, price_cents=1000),
        ])
        db.commit()
        logger.info("Seeded credit_packages with default bundles")


@app.on_event("startup")
async def startup_event():
    # Run DB schema migrations in a background thread so the /health endpoint
    # responds immediately for Cloud Run startup probes (#2282).
    # The readiness middleware still blocks normal traffic until _app_ready is set.
    import threading

    def _run_migrations_background():
        global _app_ready
        try:
            run_startup_migrations(engine, settings, logger)
            logger.info("Background migrations completed successfully")
        except Exception as e:
            logger.error("Background migrations failed: %s", e)
        finally:
            _app_ready = True

    migration_thread = threading.Thread(target=_run_migrations_background, daemon=True)
    migration_thread.start()

    from apscheduler.triggers.cron import CronTrigger
    from app.services.scheduler import scheduler, start_scheduler
    from app.jobs.assignment_reminders import check_assignment_reminders
    from app.jobs.task_reminders import check_task_reminders
    from app.jobs.notification_reminders import check_notification_reminders
    from app.services.inspiration_service import seed_messages, sync_new_messages
    from app.services.faq_seed_service import seed_faq
    from app.services.grade_seed_service import seed_grades
    from app.services.feature_seed_service import seed_features

    # Seed inspiration messages, FAQ entries, and grade records if tables are empty
    db = SessionLocal()
    try:
        seed_messages(db)
        sync_new_messages(db)
        seed_faq(db)
        seed_grades(db)
        seed_wallet_data(db)
        from app.services.outreach_template_seed import seed_outreach_templates
        seed_outreach_templates(db)
        seed_features(db)
    finally:
        db.close()

    # APScheduler: 1-hour grace window for Cloud Run cold-start delays
    SCHEDULER_MISFIRE_GRACE = 3600

    scheduler.add_job(
        check_assignment_reminders,
        CronTrigger(hour=8, minute=0),
        id="assignment_reminders",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )
    scheduler.add_job(
        check_task_reminders,
        CronTrigger(hour=8, minute=15),
        id="task_reminders",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )
    scheduler.add_job(
        check_notification_reminders,
        CronTrigger(hour="*/6"),
        id="notification_reminders",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
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
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Background Google Classroom sync once daily at 6 AM
    from app.jobs.google_sync import sync_google_classrooms
    scheduler.add_job(
        sync_google_classrooms,
        CronTrigger(hour=6, minute=0),
        id="google_classroom_sync",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Process expired account deletions daily at 4 AM (#964)
    from app.jobs.account_deletion import process_expired_account_deletions
    scheduler.add_job(
        process_expired_account_deletions,
        CronTrigger(hour=4, minute=0),
        id="account_deletion_cleanup",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Cleanup note versions older than 365 days, daily at 3:30 AM (#1139)
    def cleanup_note_versions():
        _db = SessionLocal()
        try:
            from app.api.routes.notes import cleanup_old_versions
            deleted = cleanup_old_versions(_db)
            if deleted:
                logger.info(f"Cleaned up {deleted} note versions older than 365 days")
        except Exception as e:
            logger.warning(f"Note version cleanup failed: {e}")
        finally:
            _db.close()

    scheduler.add_job(
        cleanup_note_versions,
        CronTrigger(hour=3, minute=30),
        id="note_version_cleanup",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    from app.jobs.wallet_refresh import refresh_monthly_credits
    scheduler.add_job(
        refresh_monthly_credits,
        CronTrigger(day=1, hour=0, minute=0),
        id="wallet_monthly_refresh",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Nightly streak evaluation at 12:30 AM (#2002)
    from app.jobs.streak_check import check_all_streaks, refresh_freeze_tokens
    scheduler.add_job(
        check_all_streaks,
        CronTrigger(hour=0, minute=30),
        id="streak_check",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Monthly freeze token refresh on 1st of month (#2003)
    scheduler.add_job(
        refresh_freeze_tokens,
        CronTrigger(day=1, hour=0, minute=0),
        id="freeze_token_refresh",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Weekly digest email — every Sunday at 7 PM UTC (#2022)
    from app.jobs.weekly_digest import send_weekly_digests
    scheduler.add_job(
        send_weekly_digests,
        CronTrigger(day_of_week="sun", hour=19, minute=0),
        id="weekly_digest",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Weekly family report card — every Sunday at 8 PM UTC (#2228)
    from app.jobs.weekly_report import send_weekly_reports
    scheduler.add_job(
        send_weekly_reports,
        CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="weekly_report",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Daily digest email — every day at 7 AM UTC (#2023)
    from app.jobs.daily_digest_job import send_daily_digests
    scheduler.add_job(
        send_daily_digests,
        CronTrigger(hour=7, minute=0),
        id="daily_digest",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Parent email digest — every 4 hours (#2651)
    from app.jobs.parent_email_digest_job import process_parent_email_digests
    scheduler.add_job(
        process_parent_email_digests,
        CronTrigger(hour="*/4"),
        id="parent_email_digest",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
        coalesce=True,
    )

    # Teacher comm sync disabled — all syncs are manual/on-demand per parent-first platform design
    # from app.jobs.teacher_comm_sync import check_teacher_communications
    # scheduler.add_job(check_teacher_communications, IntervalTrigger(minutes=15), id="teacher_comm_sync", replace_existing=True)
    start_scheduler()

    # Initialize help chatbot embedding service (non-blocking)
    import asyncio
    from app.services.help_embedding_service import help_embedding_service
    asyncio.create_task(help_embedding_service.initialize())

    # Initialize intent embedding service (anchor phrase embeddings)
    try:
        from app.services.intent_embedding_service import intent_embedding_service
        from app.core.config import settings
        if settings.openai_api_key:
            intent_embedding_service.initialize(settings.openai_api_key)
    except Exception as e:
        logger.warning("Could not initialize intent embedding service: %s", e)

    logger.info("EMAI application started — migrations running in background")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("EMAI application shutting down")
