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

from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, RequestLogger, generate_trace_id, trace_id_var, user_id_var, endpoint_var
from app.core.middleware import DomainRedirectMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.db.database import Base, engine, SessionLocal
from app.api.routes import auth, users, students, courses, assignments, google_classroom, study, logs, messages, notifications, teacher_communications, parent, parent_ai, parent_kids, admin, admin_waitlist, invites, tasks, course_contents, search, inspiration, faq, analytics, link_requests, quiz_results, onboarding, grades, waitlist, notes, ai_usage, account_deletion, data_export, activity, resource_links, help as help_routes, briefing, weekly_digest, study_sharing, calendar_import, tutorials, readiness, conversation_starters, daily_digest, survey, admin_survey, xp, events, study_requests, timeline, study_sessions, report_card, bug_reports, daily_quiz
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
from app.api.routes import asgf
from app.api.routes import demo_verify  # CB-DEMO-001 B2 (#3604)
from app.api.routes import public as public_routes  # CB-DEMO-001 B2 (#3604)
from app.api.routes import demo  # CB-DEMO-001 B1 (#3603)
from app.api.routes import class_import  # CB-ONBOARD-001 (#3985)
from app.api.routes import tutor  # CB-TUTOR-002 Phase 1 (#4063)
from app.api.routes import dci_streak  # CB-DCI-001 M0-8 (#4145)
from app.api.routes import dci_consent  # CB-DCI-001 M0-11 (#4148)
from app.api.routes import dci  # CB-DCI-001 M0-4 (#4139)
from app.api.routes import curriculum  # CB-CMCP-001 M0-B 0B-1 (#4415)
from app.api.routes import ceg_admin_review  # CB-CMCP-001 M0-B 0B-3a (#4428)
from app.api.routes import cmcp_generate  # CB-CMCP-001 M1-A 1A-2 (#4471)
from app.api.routes import cmcp_generate_stream  # CB-CMCP-001 M1-E 1E-1 (#4481)
from app.api.routes import cmcp_review  # CB-CMCP-001 M3-A 3A-1 (#4576)
from app.api.routes import cmcp_surface_click  # CB-CMCP-001 M3-C 3C-5 (#4581)
from app.mcp.routes import router as mcp_router  # CB-CMCP-001 M2-A 2A-2 (#4550)

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
from app.models import User, Student, Teacher, Course, Assignment, StudyGuide, Conversation, Message, Notification, TeacherCommunication, Invite, Task, CourseContent, AuditLog, InspirationMessage, FAQQuestion, FAQAnswer, GradeRecord, LinkRequest, NotificationSuppression, QuizResult, Waitlist, AILimitRequest, Note, NoteVersion, NoteImage, DataExportRequest, SourceFile, HelpArticle, EnrollmentRequest, ContentImage, SurveyResponse, SurveyAnswer, HolidayDate, StudyRequest
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
from app.models.learning_history import LearningHistory  # noqa: F401 — ASGF learning history (#3391)
from app.models.demo_session import DemoSession  # noqa: F401 — CB-DEMO-001 demo sessions (#3600)
from app.models.learning_cycle import (  # noqa: F401 — CB-TUTOR-002 Phase 2 (#4067)
    LearningCycleSession,
    LearningCycleChunk,
    LearningCycleQuestion,
    LearningCycleAnswer,
)
from app.models.tutor import TutorConversation, TutorMessage  # noqa: F401 — CB-TUTOR-002 Phase 1 (#4063)
from app.models.dci import (  # noqa: F401 — CB-DCI-001 M0 (#4140)
    DailyCheckin,
    ClassificationEvent,
    AISummary,
    ConversationStarter,
    CheckinStreakSummary,
    CheckinConsent,
)
from app.models.checkin_settings import CheckinSettings  # noqa: F401 — CB-DCI-001 M0-11 (#4148)
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")

# ============================================================================
# MIGRATION PATTERN REFERENCE  (CB-CMCP-001 0A-4 / #4427)
# ============================================================================
# Every synchronous startup migration block below MUST follow this pattern.
# The contract is enforced by ``tests/test_main_migrations.py``.
#
# Why this pattern exists
# -----------------------
# Cloud Run can leave a previous revision's instance alive long enough to
# hold an exclusive advisory lock past the new revision's cold-start
# window. A bare ``pg_advisory_lock(...)`` call in startup deadlocks the
# new instance forever; Cloud Run never gets a healthy ``/health`` response
# and traffic never shifts (#3425). The pattern below is the recovery:
# probe with ``pg_try_advisory_lock`` (non-blocking), retry 3× with 5s
# sleeps, and run the migration anyway on the third failure with a
# warning log (the migrations themselves are written to be idempotent
# via ``IF NOT EXISTS`` / ``ADD VALUE IF NOT EXISTS`` / PRAGMA probes).
#
# Canonical block shape
# ---------------------
#     _<tag>_lock_conn = None
#     _<tag>_lock_acquired = False
#     try:
#         if _is_pg:                                  # SQLite gating
#             _<tag>_lock_conn = engine.connect()
#             for _<tag>_attempt in range(1, 4):      # 3 attempts
#                 _r = _<tag>_lock_conn.execute(
#                     text("SELECT pg_try_advisory_lock(<id>)")
#                 )
#                 _<tag>_lock_acquired = _r.scalar()
#                 if _<tag>_lock_acquired:
#                     logger.info("Acquired advisory lock <id> ...")
#                     break
#                 logger.warning("Advisory lock <id> held ... retrying in 5s")
#                 time.sleep(5)                       # 5s between attempts
#             if not _<tag>_lock_acquired:
#                 logger.warning(
#                     "Could not acquire advisory lock <id> after 3 "
#                     "attempts — running ... without lock"
#                 )
#
#         with engine.connect() as _conn:             # Per-block conn
#             try:
#                 if _is_pg:
#                     _conn.execute(text("ALTER TABLE ... IF NOT EXISTS ..."))
#                 else:
#                     # SQLite: probe via PRAGMA (no IF NOT EXISTS)
#                     ...
#                 _conn.commit()
#                 logger.info("<table> migration completed (#<issue>)")
#             except Exception as _col_err:
#                 _conn.rollback()                    # Don't poison conn
#                 logger.warning("<table> migration note: %s", _col_err)
#     except Exception as _err:
#         logger.warning("<table> migration outer note: %s", _err)
#     finally:
#         if _<tag>_lock_conn is not None:
#             if _<tag>_lock_acquired:
#                 try:
#                     _<tag>_lock_conn.execute(
#                         text("SELECT pg_advisory_unlock(<id>)")
#                     )
#                     _<tag>_lock_conn.commit()
#                 except Exception:
#                     pass
#             _<tag>_lock_conn.close()
#
# Hard rules (non-negotiable — see CLAUDE.md "Migration locking")
# ---------------------------------------------------------------
# 1. Use ``pg_try_advisory_lock`` (non-blocking) — NEVER ``pg_advisory_lock``.
# 2. Exactly 3 attempts with 5s sleep between each — no longer total wait,
#    no extra retries beyond the third.
# 3. PG-only paths (``ALTER TYPE``, ``JSONB``, ``IF NOT EXISTS`` on ALTER)
#    must be gated on ``_is_pg`` (SQLite re-creates schema via
#    ``Base.metadata.create_all``).
# 4. Outer try/except MUST swallow exceptions — startup must never crash.
# 5. Failed inner ALTER MUST ``rollback()`` so the next block isn't poisoned.
# 6. Reserve a unique advisory-lock ID (we use the GitHub issue number).
# 7. Idempotency: every statement must be safe to re-run on cold start.
#
# Reserved lock IDs (extend as new stripes ship)
# ----------------------------------------------
# 3391 learning_history table (#3391)
# 3600 demo_sessions table (#3600)
# 3913 tasks source-attribution columns (#3913)
# 4063 tutor_conversations / tutor_messages (#4063)
# 4067 learning_cycle_* (#4067)
# 4140 dci.* tables (#4140)
# 4301 students.profile_photo_url (#4301)
# 4413 study_guides CMCP extension columns (#4413)
# 4414 userrole enum extension (#4414)
# 4428 ceg_expectations curriculum-admin review columns (#4428)
# 4448 users.roles widen String(50) -> String(120) (#4452)
# ============================================================================

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
        # CB-DEMO-001 F2 (#3601, #3711) — variant column must exist before
        # the FeatureFlag model can SELECT. The background-thread migration
        # in _run_migrations_inner ran too late / silently failed, leaving
        # /api/features and /admin/features returning 500 after the
        # CB-DEMO-001 deploy.
        ("feature_flags", "variant", "VARCHAR(20) NOT NULL DEFAULT 'off'"),
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

# CB-DCI-001 M0-8 (#4145, #4183): widen ``streak_log`` unique constraint to
# include ``qualifying_action`` so the study stream and the DCI
# ``daily_checkin`` stream can coexist on the same kid + same day. The
# original constraint ``uq_student_log_date`` (student_id, log_date) blocks
# the second stream's INSERT with IntegrityError. Idempotent — wrapped in
# try/except per existing migration pattern. PG only; SQLite test runs use
# ``Base.metadata.create_all`` which already picks up the widened constraint.
if _is_pg:
    try:
        with engine.connect() as _sl_conn:
            try:
                _sl_conn.execute(text(
                    "ALTER TABLE streak_log DROP CONSTRAINT IF EXISTS uq_student_log_date"
                ))
                _sl_conn.commit()
            except Exception as _sl_drop_err:
                _sl_conn.rollback()
                logger.warning("streak_log uq_student_log_date drop note: %s", _sl_drop_err)
            try:
                _sl_conn.execute(text(
                    "ALTER TABLE streak_log ADD CONSTRAINT uq_student_log_date_action "
                    "UNIQUE (student_id, log_date, qualifying_action)"
                ))
                _sl_conn.commit()
                logger.info("streak_log uq_student_log_date_action constraint added (#4183)")
            except Exception as _sl_add_err:
                _sl_conn.rollback()
                logger.warning("streak_log uq_student_log_date_action add note: %s", _sl_add_err)
    except Exception as _sl_conn_err:
        logger.error("streak_log constraint migration FAILED: %s", _sl_conn_err)

# Safety CREATE TABLE for learning_history (#3391) — create_all should handle it,
# but explicit migration ensures it exists even if import order changes.
# Wrapped with pg_try_advisory_lock for Cloud Run safety (#3425).
_lh_lock_conn = None
_lh_lock_acquired = False
try:
    if _is_pg:
        import time as _lh_time
        _lh_lock_conn = engine.connect()
        for _lh_attempt in range(1, 4):
            _lh_result = _lh_lock_conn.execute(text("SELECT pg_try_advisory_lock(3391)"))
            _lh_lock_acquired = _lh_result.scalar()
            if _lh_lock_acquired:
                logger.info("Acquired advisory lock 3391 for learning_history migration (attempt %d)", _lh_attempt)
                break
            logger.warning("Advisory lock 3391 held by another instance (attempt %d/3), retrying in 5s...", _lh_attempt)
            _lh_time.sleep(5)
        if not _lh_lock_acquired:
            logger.warning("Could not acquire advisory lock 3391 after 3 attempts — running learning_history migration without lock")

    with engine.connect() as _conn:
        if _is_pg:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_history (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    session_id VARCHAR(36) NOT NULL UNIQUE,
                    session_type VARCHAR(20) NOT NULL,
                    question_asked TEXT,
                    subject VARCHAR(100),
                    topic_tags JSON,
                    grade_level VARCHAR(20),
                    school_board VARCHAR(100),
                    documents_uploaded JSON,
                    quiz_results JSON,
                    overall_score_pct INTEGER,
                    avg_attempts_per_q DOUBLE PRECISION,
                    weak_concepts JSON,
                    slides_generated JSON,
                    material_id INTEGER REFERENCES study_guides(id) ON DELETE SET NULL,
                    assigned_to_course VARCHAR(255),
                    session_duration_sec INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    teacher_visible BOOLEAN NOT NULL DEFAULT FALSE
                )
            """))
            _conn.execute(text("CREATE INDEX IF NOT EXISTS ix_learning_history_student_id ON learning_history(student_id)"))
            _conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_learning_history_session_id ON learning_history(session_id)"))
        else:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    session_id VARCHAR(36) NOT NULL UNIQUE,
                    session_type VARCHAR(20) NOT NULL,
                    question_asked TEXT,
                    subject VARCHAR(100),
                    topic_tags JSON,
                    grade_level VARCHAR(20),
                    school_board VARCHAR(100),
                    documents_uploaded JSON,
                    quiz_results JSON,
                    overall_score_pct INTEGER,
                    avg_attempts_per_q REAL,
                    weak_concepts JSON,
                    slides_generated JSON,
                    material_id INTEGER REFERENCES study_guides(id) ON DELETE SET NULL,
                    assigned_to_course VARCHAR(255),
                    session_duration_sec INTEGER,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    teacher_visible BOOLEAN NOT NULL DEFAULT FALSE
                )
            """))
        _conn.commit()
        logger.info("learning_history table migration completed (#3391)")
except Exception as _lh_err:
    logger.warning("learning_history table migration note: %s", _lh_err)
finally:
    if _lh_lock_conn is not None:
        if _lh_lock_acquired:
            try:
                _lh_lock_conn.execute(text("SELECT pg_advisory_unlock(3391)"))
                _lh_lock_conn.commit()
            except Exception:
                pass
        _lh_lock_conn.close()

# demo_sessions table (#3600 — CB-DEMO-001 Instant Trial & Demo Experience).
# Wrapped with pg_try_advisory_lock for Cloud Run safety.
_ds_lock_conn = None
_ds_lock_acquired = False
try:
    if _is_pg:
        import time as _ds_time
        _ds_lock_conn = engine.connect()
        for _ds_attempt in range(1, 4):
            _ds_result = _ds_lock_conn.execute(text("SELECT pg_try_advisory_lock(3600)"))
            _ds_lock_acquired = _ds_result.scalar()
            if _ds_lock_acquired:
                logger.info("Acquired advisory lock 3600 for demo_sessions migration (attempt %d)", _ds_attempt)
                break
            logger.warning("Advisory lock 3600 held by another instance (attempt %d/3), retrying in 5s...", _ds_attempt)
            _ds_time.sleep(5)
        if not _ds_lock_acquired:
            logger.warning("Could not acquire advisory lock 3600 after 3 attempts — running demo_sessions migration without lock")

    with engine.connect() as _conn:
        if _is_pg:
            # Ensure pgcrypto is available for gen_random_uuid(); ignore if already present.
            try:
                _conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            except Exception as _ext_err:
                logger.warning("pgcrypto extension note: %s", _ext_err)
            try:
                # Required for CITEXT column below; citext is not installed
                # by default on all PG distributions.
                _conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
            except Exception as _ext_err:
                logger.warning("citext extension note: %s", _ext_err)
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS demo_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    email_hash CHAR(64) NOT NULL,
                    email CITEXT NOT NULL,
                    full_name TEXT,
                    role TEXT NOT NULL CHECK (role IN ('parent','student','teacher','other')),
                    consent_ts TIMESTAMPTZ,
                    verified BOOLEAN NOT NULL DEFAULT FALSE,
                    verified_ts TIMESTAMPTZ,
                    verification_token_hash CHAR(64),
                    verification_expires_at TIMESTAMPTZ,
                    fallback_code_hash CHAR(64),
                    fallback_code_expires_at TIMESTAMPTZ,
                    generations_count INTEGER NOT NULL DEFAULT 0,
                    generations_json JSONB,
                    moat_engagement_json JSONB,
                    source_ip_hash CHAR(64),
                    user_agent TEXT,
                    admin_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (admin_status IN ('pending','approved','rejected','blocklisted')),
                    archived_at TIMESTAMPTZ
                )
            """))
            _conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_demo_sessions_email_hash "
                "ON demo_sessions(email_hash)"
            ))
        else:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS demo_sessions (
                    id VARCHAR(36) PRIMARY KEY,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    email_hash CHAR(64) NOT NULL,
                    email TEXT COLLATE NOCASE NOT NULL,
                    full_name TEXT,
                    role VARCHAR(10) NOT NULL CHECK (role IN ('parent','student','teacher','other')),
                    consent_ts DATETIME,
                    verified BOOLEAN NOT NULL DEFAULT FALSE,
                    verified_ts DATETIME,
                    verification_token_hash CHAR(64),
                    verification_expires_at DATETIME,
                    fallback_code_hash CHAR(64),
                    fallback_code_expires_at DATETIME,
                    generations_count INTEGER NOT NULL DEFAULT 0,
                    generations_json JSON,
                    moat_engagement_json JSON,
                    source_ip_hash CHAR(64),
                    user_agent TEXT,
                    admin_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (admin_status IN ('pending','approved','rejected','blocklisted')),
                    archived_at DATETIME
                )
            """))
            _conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_demo_sessions_email_hash "
                "ON demo_sessions(email_hash)"
            ))
        _conn.commit()
        logger.info("demo_sessions table migration completed (#3600)")
except Exception as _ds_err:
    logger.warning("demo_sessions table migration note: %s", _ds_err)
finally:
    if _ds_lock_conn is not None:
        if _ds_lock_acquired:
            try:
                _ds_lock_conn.execute(text("SELECT pg_advisory_unlock(3600)"))
                _ds_lock_conn.commit()
            except Exception:
                pass
        _ds_lock_conn.close()

# CB-DEMO-001 fast-follow: demo_sessions indexes (#3641, #3658, #3659).
# Idempotent CREATE INDEX IF NOT EXISTS — runs on both PG and SQLite.
# Partial index on verified_ts uses WHERE verified = TRUE (PG partial indexes;
# SQLite has partial index support since 3.8.0). Runs after the demo_sessions
# CREATE TABLE block above so the table is guaranteed to exist.
_utdf_indexes = [
    ("idx_demo_sessions_verification_token_hash",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_verification_token_hash "
     "ON demo_sessions(verification_token_hash)"),
    ("idx_demo_sessions_source_ip_hash",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_source_ip_hash "
     "ON demo_sessions(source_ip_hash)"),
    ("idx_demo_sessions_verified_ts",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_verified_ts "
     "ON demo_sessions(verified_ts) WHERE verified = TRUE"),
]
try:
    with engine.connect() as _conn:
        for _ix_name, _ix_sql in _utdf_indexes:
            try:
                _conn.execute(text(_ix_sql))
            except Exception as _ix_err:
                logger.warning("Index %s migration note: %s", _ix_name, _ix_err)
        _conn.commit()
        logger.info("demo_sessions index migration completed")
except Exception as _ix_conn_err:
    logger.error("demo_sessions index migration FAILED (connection level): %s", _ix_conn_err)

# CB-TASKSYNC-001 (#3912, #3913) — Task source attribution columns + indexes.
# Synchronous startup migration (mirrors UTDF pattern above) so the Task model
# can SELECT/INSERT these columns on the very first request after a deploy.
# All columns nullable, no ORM defaults. Wrapped in pg_try_advisory_lock for
# Cloud Run safety (3 retries × 5s — see CLAUDE.md migration-locking section).
_tasksync_lock_conn = None
_tasksync_lock_acquired = False
try:
    if _is_pg:
        import time as _ts_time
        _tasksync_lock_conn = engine.connect()
        for _ts_attempt in range(1, 4):
            _ts_result = _tasksync_lock_conn.execute(text("SELECT pg_try_advisory_lock(3913)"))
            _tasksync_lock_acquired = _ts_result.scalar()
            if _tasksync_lock_acquired:
                logger.info("Acquired advisory lock 3913 for tasks source-col migration (attempt %d)", _ts_attempt)
                break
            logger.warning("Advisory lock 3913 held by another instance (attempt %d/3), retrying in 5s...", _ts_attempt)
            _ts_time.sleep(5)
        if not _tasksync_lock_acquired:
            logger.warning("Could not acquire advisory lock 3913 after 3 attempts — running tasks source-col migration without lock")

    _tasksync_cols_pg = [
        ("tasks", "source", "VARCHAR(20)"),
        ("tasks", "source_ref", "VARCHAR(128)"),
        ("tasks", "source_confidence", "DOUBLE PRECISION"),
        ("tasks", "source_status", "VARCHAR(20)"),
        ("tasks", "source_message_id", "VARCHAR(255)"),
        ("tasks", "source_created_at", "TIMESTAMPTZ"),
    ]
    _tasksync_cols_sqlite = [
        ("tasks", "source", "VARCHAR(20)"),
        ("tasks", "source_ref", "VARCHAR(128)"),
        ("tasks", "source_confidence", "REAL"),
        ("tasks", "source_status", "VARCHAR(20)"),
        ("tasks", "source_message_id", "VARCHAR(255)"),
        ("tasks", "source_created_at", "DATETIME"),
    ]
    _tasksync_cols = _tasksync_cols_pg if _is_pg else _tasksync_cols_sqlite

    with engine.connect() as _conn:
        if _is_pg:
            for _tbl, _col, _typ in _tasksync_cols:
                try:
                    _conn.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN IF NOT EXISTS {_col} {_typ}"))
                except Exception as _col_err:
                    logger.warning("Column %s.%s migration note: %s", _tbl, _col, _col_err)
        else:
            # SQLite has no ADD COLUMN IF NOT EXISTS — probe via PRAGMA.
            _existing = {
                row[1]
                for row in _conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
            }
            for _tbl, _col, _typ in _tasksync_cols:
                if _col in _existing:
                    continue
                try:
                    _conn.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                except Exception as _col_err:
                    logger.warning("Column %s.%s migration note: %s", _tbl, _col, _col_err)

        # Indexes (PG partial WHERE + SQLite partial WHERE both supported).
        _tasksync_indexes = [
            "CREATE INDEX IF NOT EXISTS ix_tasks_source_ref "
            "ON tasks(source, source_ref)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_source_upsert "
            "ON tasks(source, source_ref, assigned_to_user_id) "
            "WHERE source IS NOT NULL",
        ]
        for _ix_sql in _tasksync_indexes:
            try:
                _conn.execute(text(_ix_sql))
            except Exception as _ix_err:
                logger.warning("Task source-attribution index migration note: %s", _ix_err)
        _conn.commit()
        logger.info("tasks source-attribution migration completed (#3913)")
except Exception as _ts_err:
    logger.warning("tasks source-attribution migration note: %s", _ts_err)
finally:
    if _tasksync_lock_conn is not None:
        if _tasksync_lock_acquired:
            try:
                _tasksync_lock_conn.execute(text("SELECT pg_advisory_unlock(3913)"))
                _tasksync_lock_conn.commit()
            except Exception:
                pass
        _tasksync_lock_conn.close()

# CB-TUTOR-002 Phase 1 (#4063) — tutor_conversations & tutor_messages tables.
# `create_all` already handles these, but an explicit CREATE TABLE keeps the
# migration self-describing for Cloud Run cold starts and gives us a single
# pg_try_advisory_lock boundary. Wrapped in try/except so startup never blocks.
_tutor_lock_conn = None
_tutor_lock_acquired = False
try:
    if _is_pg:
        import time as _tutor_time
        _tutor_lock_conn = engine.connect()
        for _tutor_attempt in range(1, 4):
            _tutor_result = _tutor_lock_conn.execute(text("SELECT pg_try_advisory_lock(4063)"))
            _tutor_lock_acquired = _tutor_result.scalar()
            if _tutor_lock_acquired:
                logger.info("Acquired advisory lock 4063 for tutor tables migration (attempt %d)", _tutor_attempt)
                break
            logger.warning("Advisory lock 4063 held by another instance (attempt %d/3), retrying in 5s...", _tutor_attempt)
            _tutor_time.sleep(5)
        if not _tutor_lock_acquired:
            logger.warning("Could not acquire advisory lock 4063 after 3 attempts — running tutor tables migration without lock")

    with engine.connect() as _conn:
        if _is_pg:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tutor_conversations (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tutor_messages (
                    id VARCHAR(36) PRIMARY KEY,
                    conversation_id VARCHAR(36) NOT NULL REFERENCES tutor_conversations(id) ON DELETE CASCADE,
                    role VARCHAR(10) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
        else:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tutor_conversations (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tutor_messages (
                    id VARCHAR(36) PRIMARY KEY,
                    conversation_id VARCHAR(36) NOT NULL REFERENCES tutor_conversations(id) ON DELETE CASCADE,
                    role VARCHAR(10) NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
        _conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_tutor_conversations_user_created "
            "ON tutor_conversations(user_id, created_at)"
        ))
        _conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_tutor_messages_conv_created "
            "ON tutor_messages(conversation_id, created_at)"
        ))
        _conn.commit()
        logger.info("tutor_conversations/tutor_messages migration completed (#4063)")
except Exception as _tutor_err:
    logger.warning("tutor tables migration note: %s", _tutor_err)
finally:
    if _tutor_lock_conn is not None:
        if _tutor_lock_acquired:
            try:
                _tutor_lock_conn.execute(text("SELECT pg_advisory_unlock(4063)"))
                _tutor_lock_conn.commit()
            except Exception:
                pass
        _tutor_lock_conn.close()

# CB-TUTOR-002 Phase 2 (#4067) — learning_cycle_* tables (sessions/chunks/questions/answers).
# `create_all` already handles these, but an explicit CREATE TABLE with CHECK
# constraints (mirroring the ORM) keeps the migration self-describing for
# Cloud Run cold starts and gives us a single pg_try_advisory_lock boundary.
# Wrapped in try/except so startup never blocks (#4085).
_lc_lock_conn = None
_lc_lock_acquired = False
try:
    if _is_pg:
        _lc_lock_conn = engine.connect()
        for _lc_attempt in range(1, 4):
            _lc_result = _lc_lock_conn.execute(text("SELECT pg_try_advisory_lock(4067)"))
            _lc_lock_acquired = _lc_result.scalar()
            if _lc_lock_acquired:
                logger.info("Acquired advisory lock 4067 for learning_cycle tables migration (attempt %d)", _lc_attempt)
                break
            logger.warning("Advisory lock 4067 held by another instance (attempt %d/3), retrying in 5s...", _lc_attempt)
            time.sleep(5)
        if not _lc_lock_acquired:
            logger.warning("Could not acquire advisory lock 4067 after 3 attempts — running learning_cycle migration without lock")

    with engine.connect() as _conn:
        if _is_pg:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_sessions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    topic VARCHAR(200) NOT NULL,
                    subject VARCHAR(100) NOT NULL,
                    grade_level INTEGER,
                    status VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'abandoned')),
                    current_chunk_idx INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_chunks (
                    id VARCHAR(36) PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL REFERENCES learning_cycle_sessions(id) ON DELETE CASCADE,
                    order_index INTEGER NOT NULL,
                    teach_content_md TEXT NOT NULL,
                    mastery_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (mastery_status IN ('pending', 'passed', 'moved_on'))
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_questions (
                    id VARCHAR(36) PRIMARY KEY,
                    chunk_id VARCHAR(36) NOT NULL REFERENCES learning_cycle_chunks(id) ON DELETE CASCADE,
                    order_index INTEGER NOT NULL,
                    format VARCHAR(20) NOT NULL
                        CHECK (format IN ('mcq', 'true_false', 'fill_blank')),
                    prompt TEXT NOT NULL,
                    options JSONB,
                    correct_answer TEXT NOT NULL,
                    explanation TEXT NOT NULL
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_answers (
                    id VARCHAR(36) PRIMARY KEY,
                    question_id VARCHAR(36) NOT NULL REFERENCES learning_cycle_questions(id) ON DELETE CASCADE,
                    attempt_number INTEGER NOT NULL DEFAULT 1,
                    answer_given TEXT NOT NULL,
                    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
                    xp_awarded INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
        else:
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_sessions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    topic VARCHAR(200) NOT NULL,
                    subject VARCHAR(100) NOT NULL,
                    grade_level INTEGER,
                    status VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'abandoned')),
                    current_chunk_idx INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_chunks (
                    id VARCHAR(36) PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL REFERENCES learning_cycle_sessions(id) ON DELETE CASCADE,
                    order_index INTEGER NOT NULL,
                    teach_content_md TEXT NOT NULL,
                    mastery_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (mastery_status IN ('pending', 'passed', 'moved_on'))
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_questions (
                    id VARCHAR(36) PRIMARY KEY,
                    chunk_id VARCHAR(36) NOT NULL REFERENCES learning_cycle_chunks(id) ON DELETE CASCADE,
                    order_index INTEGER NOT NULL,
                    format VARCHAR(20) NOT NULL
                        CHECK (format IN ('mcq', 'true_false', 'fill_blank')),
                    prompt TEXT NOT NULL,
                    options JSON,
                    correct_answer TEXT NOT NULL,
                    explanation TEXT NOT NULL
                )
            """))
            _conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_cycle_answers (
                    id VARCHAR(36) PRIMARY KEY,
                    question_id VARCHAR(36) NOT NULL REFERENCES learning_cycle_questions(id) ON DELETE CASCADE,
                    attempt_number INTEGER NOT NULL DEFAULT 1,
                    answer_given TEXT NOT NULL,
                    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
                    xp_awarded INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
        _conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_learning_cycle_sessions_user_status "
            "ON learning_cycle_sessions(user_id, status)"
        ))
        _conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_learning_cycle_chunks_session_order "
            "ON learning_cycle_chunks(session_id, order_index)"
        ))
        _conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_learning_cycle_questions_chunk_order "
            "ON learning_cycle_questions(chunk_id, order_index)"
        ))
        _conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_learning_cycle_answers_question_attempt "
            "ON learning_cycle_answers(question_id, attempt_number)"
        ))
        _conn.commit()
        logger.info("learning_cycle_* tables migration completed (#4067)")
except Exception as _lc_err:
    logger.warning("learning_cycle migration note: %s", _lc_err)
finally:
    if _lc_lock_conn is not None:
        if _lc_lock_acquired:
            try:
                _lc_lock_conn.execute(text("SELECT pg_advisory_unlock(4067)"))
                _lc_lock_conn.commit()
            except Exception:
                pass
        _lc_lock_conn.close()

# CB-DCI-001 M0 (#4140) — Daily Check-In Ritual: 6 new tables.
# `create_all` already handles these, but explicit CREATE TABLE keeps the
# migration self-describing for Cloud Run cold starts and gives us a single
# pg_try_advisory_lock boundary. Wrapped in try/except so startup never blocks.
def _migrate_dci_tables() -> None:
    """Create the 6 DCI tables (daily_checkins, classification_events,
    ai_summaries, conversation_starters, checkin_streak_summary, checkin_consent)
    plus required indexes and unique constraints. Idempotent — safe to call
    on every cold start.

    Each statement runs inside a single ``with engine.connect()`` block with
    its own ``conn.commit()`` and a top-level try/except so a partial failure
    cannot block startup.
    """
    _dci_lock_conn = None
    _dci_lock_acquired = False
    try:
        if _is_pg:
            _dci_lock_conn = engine.connect()
            for _dci_attempt in range(1, 4):
                _dci_result = _dci_lock_conn.execute(
                    text("SELECT pg_try_advisory_lock(4140)")
                )
                _dci_lock_acquired = _dci_result.scalar()
                if _dci_lock_acquired:
                    logger.info(
                        "Acquired advisory lock 4140 for DCI tables migration "
                        "(attempt %d)",
                        _dci_attempt,
                    )
                    break
                logger.warning(
                    "Advisory lock 4140 held by another instance "
                    "(attempt %d/3), retrying in 5s...",
                    _dci_attempt,
                )
                time.sleep(5)
            if not _dci_lock_acquired:
                logger.warning(
                    "Could not acquire advisory lock 4140 after 3 attempts — "
                    "running DCI tables migration without lock"
                )

        # 1) daily_checkins
        try:
            with engine.connect() as _conn:
                if _is_pg:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS daily_checkins (
                            id SERIAL PRIMARY KEY,
                            kid_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            photo_uris JSON NOT NULL DEFAULT '[]',
                            voice_uri VARCHAR(500),
                            text_content VARCHAR(280),
                            source VARCHAR(20) NOT NULL DEFAULT 'kid_web',
                            CONSTRAINT ck_daily_checkins_source
                                CHECK (source IN ('kid_web', 'kid_mobile'))
                        )
                    """))
                    # Idempotent add for tables created before the CHECK was inlined
                    _conn.execute(text("""
                        DO $$
                        BEGIN
                            ALTER TABLE daily_checkins
                                ADD CONSTRAINT ck_daily_checkins_source
                                CHECK (source IN ('kid_web', 'kid_mobile'));
                        EXCEPTION WHEN duplicate_object THEN NULL;
                        END$$;
                    """))
                else:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS daily_checkins (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            kid_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            photo_uris JSON NOT NULL DEFAULT '[]',
                            voice_uri VARCHAR(500),
                            text_content VARCHAR(280),
                            source VARCHAR(20) NOT NULL DEFAULT 'kid_web',
                            CONSTRAINT ck_daily_checkins_source
                                CHECK (source IN ('kid_web', 'kid_mobile'))
                        )
                    """))
                _conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_daily_checkins_kid_date "
                    "ON daily_checkins(kid_id, submitted_at)"
                ))
                _conn.commit()
                logger.info("dci.daily_checkins migration completed (#4140)")
        except Exception as _err:
            logger.warning("dci.daily_checkins migration note: %s", _err)

        # 2) classification_events
        try:
            with engine.connect() as _conn:
                if _is_pg:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS classification_events (
                            id SERIAL PRIMARY KEY,
                            checkin_id INTEGER NOT NULL REFERENCES daily_checkins(id) ON DELETE CASCADE,
                            artifact_type VARCHAR(20) NOT NULL,
                            subject VARCHAR(50),
                            topic VARCHAR(200),
                            strand_code VARCHAR(20),
                            deadline_iso DATE,
                            confidence DOUBLE PRECISION,
                            corrected_by_kid BOOLEAN NOT NULL DEFAULT FALSE,
                            model_version VARCHAR(50),
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CONSTRAINT ck_classification_events_artifact_type
                                CHECK (artifact_type IN ('photo', 'voice', 'text'))
                        )
                    """))
                    # Idempotent add for tables created before the CHECK was inlined
                    _conn.execute(text("""
                        DO $$
                        BEGIN
                            ALTER TABLE classification_events
                                ADD CONSTRAINT ck_classification_events_artifact_type
                                CHECK (artifact_type IN ('photo', 'voice', 'text'));
                        EXCEPTION WHEN duplicate_object THEN NULL;
                        END$$;
                    """))
                else:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS classification_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            checkin_id INTEGER NOT NULL REFERENCES daily_checkins(id) ON DELETE CASCADE,
                            artifact_type VARCHAR(20) NOT NULL,
                            subject VARCHAR(50),
                            topic VARCHAR(200),
                            strand_code VARCHAR(20),
                            deadline_iso DATE,
                            confidence REAL,
                            corrected_by_kid BOOLEAN NOT NULL DEFAULT FALSE,
                            model_version VARCHAR(50),
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT ck_classification_events_artifact_type
                                CHECK (artifact_type IN ('photo', 'voice', 'text'))
                        )
                    """))
                _conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_classification_events_checkin_id "
                    "ON classification_events(checkin_id)"
                ))
                _conn.commit()
                logger.info("dci.classification_events migration completed (#4140)")
        except Exception as _err:
            logger.warning("dci.classification_events migration note: %s", _err)

        # 3) ai_summaries
        try:
            with engine.connect() as _conn:
                if _is_pg:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS ai_summaries (
                            id SERIAL PRIMARY KEY,
                            kid_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            summary_date DATE NOT NULL,
                            summary_json JSON NOT NULL,
                            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            model_version VARCHAR(50) NOT NULL,
                            prompt_hash VARCHAR(64) NOT NULL,
                            policy_blocked BOOLEAN NOT NULL DEFAULT FALSE,
                            parent_edited BOOLEAN NOT NULL DEFAULT FALSE,
                            CONSTRAINT uq_ai_summaries_kid_date UNIQUE (kid_id, summary_date)
                        )
                    """))
                else:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS ai_summaries (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            kid_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            summary_date DATE NOT NULL,
                            summary_json JSON NOT NULL,
                            generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            model_version VARCHAR(50) NOT NULL,
                            prompt_hash VARCHAR(64) NOT NULL,
                            policy_blocked BOOLEAN NOT NULL DEFAULT FALSE,
                            parent_edited BOOLEAN NOT NULL DEFAULT FALSE,
                            CONSTRAINT uq_ai_summaries_kid_date UNIQUE (kid_id, summary_date)
                        )
                    """))
                _conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_ai_summaries_kid_id "
                    "ON ai_summaries(kid_id)"
                ))
                _conn.commit()
                logger.info("dci.ai_summaries migration completed (#4140)")
        except Exception as _err:
            logger.warning("dci.ai_summaries migration note: %s", _err)

        # 4) conversation_starters
        try:
            with engine.connect() as _conn:
                if _is_pg:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS conversation_starters (
                            id SERIAL PRIMARY KEY,
                            summary_id INTEGER NOT NULL REFERENCES ai_summaries(id) ON DELETE CASCADE,
                            text TEXT NOT NULL,
                            was_used BOOLEAN,
                            parent_feedback VARCHAR(20),
                            regenerated_from INTEGER REFERENCES conversation_starters(id) ON DELETE SET NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CONSTRAINT ck_conversation_starters_parent_feedback
                                CHECK (parent_feedback IS NULL OR parent_feedback IN ('thumbs_up', 'regenerate'))
                        )
                    """))
                    # Idempotent add for tables created before the CHECK was inlined
                    _conn.execute(text("""
                        DO $$
                        BEGIN
                            ALTER TABLE conversation_starters
                                ADD CONSTRAINT ck_conversation_starters_parent_feedback
                                CHECK (parent_feedback IS NULL OR parent_feedback IN ('thumbs_up', 'regenerate'));
                        EXCEPTION WHEN duplicate_object THEN NULL;
                        END$$;
                    """))
                else:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS conversation_starters (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            summary_id INTEGER NOT NULL REFERENCES ai_summaries(id) ON DELETE CASCADE,
                            text TEXT NOT NULL,
                            was_used BOOLEAN,
                            parent_feedback VARCHAR(20),
                            regenerated_from INTEGER REFERENCES conversation_starters(id) ON DELETE SET NULL,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT ck_conversation_starters_parent_feedback
                                CHECK (parent_feedback IS NULL OR parent_feedback IN ('thumbs_up', 'regenerate'))
                        )
                    """))
                _conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_conversation_starters_summary_id "
                    "ON conversation_starters(summary_id)"
                ))
                _conn.commit()
                logger.info("dci.conversation_starters migration completed (#4140)")
        except Exception as _err:
            logger.warning("dci.conversation_starters migration note: %s", _err)

        # 5) checkin_streak_summary
        try:
            with engine.connect() as _conn:
                if _is_pg:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS checkin_streak_summary (
                            kid_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
                            current_streak INTEGER NOT NULL DEFAULT 0,
                            longest_streak INTEGER NOT NULL DEFAULT 0,
                            last_checkin_date DATE,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """))
                else:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS checkin_streak_summary (
                            kid_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
                            current_streak INTEGER NOT NULL DEFAULT 0,
                            longest_streak INTEGER NOT NULL DEFAULT 0,
                            last_checkin_date DATE,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                _conn.commit()
                logger.info("dci.checkin_streak_summary migration completed (#4140)")
        except Exception as _err:
            logger.warning("dci.checkin_streak_summary migration note: %s", _err)

        # 6) checkin_consent (composite PK)
        try:
            with engine.connect() as _conn:
                if _is_pg:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS checkin_consent (
                            parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            kid_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            photo_ok BOOLEAN NOT NULL DEFAULT FALSE,
                            voice_ok BOOLEAN NOT NULL DEFAULT FALSE,
                            ai_ok BOOLEAN NOT NULL DEFAULT FALSE,
                            retention_days INTEGER NOT NULL DEFAULT 90,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CONSTRAINT pk_checkin_consent PRIMARY KEY (parent_id, kid_id)
                        )
                    """))
                else:
                    _conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS checkin_consent (
                            parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            kid_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            photo_ok BOOLEAN NOT NULL DEFAULT FALSE,
                            voice_ok BOOLEAN NOT NULL DEFAULT FALSE,
                            ai_ok BOOLEAN NOT NULL DEFAULT FALSE,
                            retention_days INTEGER NOT NULL DEFAULT 90,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT pk_checkin_consent PRIMARY KEY (parent_id, kid_id)
                        )
                    """))
                _conn.commit()
                logger.info("dci.checkin_consent migration completed (#4140)")
        except Exception as _err:
            logger.warning("dci.checkin_consent migration note: %s", _err)

    finally:
        if _dci_lock_conn is not None:
            if _dci_lock_acquired:
                try:
                    _dci_lock_conn.execute(text("SELECT pg_advisory_unlock(4140)"))
                    _dci_lock_conn.commit()
                except Exception:
                    pass
            _dci_lock_conn.close()


_migrate_dci_tables()


# CB-KIDPHOTO-001 (#4301) — students.profile_photo_url column for parent-uploaded
# kid profile photos. Wrapped in pg_try_advisory_lock for Cloud Run safety
# (3 retries × 5s — see CLAUDE.md migration-locking section). Idempotent.
_kp_lock_conn = None
_kp_lock_acquired = False
try:
    if _is_pg:
        _kp_lock_conn = engine.connect()
        for _kp_attempt in range(1, 4):
            _kp_result = _kp_lock_conn.execute(text("SELECT pg_try_advisory_lock(4301)"))
            _kp_lock_acquired = _kp_result.scalar()
            if _kp_lock_acquired:
                logger.info("Acquired advisory lock 4301 for students.profile_photo_url migration (attempt %d)", _kp_attempt)
                break
            logger.warning("Advisory lock 4301 held by another instance (attempt %d/3), retrying in 5s...", _kp_attempt)
            time.sleep(5)
        if not _kp_lock_acquired:
            logger.warning("Could not acquire advisory lock 4301 after 3 attempts — running students.profile_photo_url migration without lock")

    with engine.connect() as _conn:
        try:
            if _is_pg:
                _conn.execute(text(
                    "ALTER TABLE students ADD COLUMN IF NOT EXISTS profile_photo_url VARCHAR(512)"
                ))
            else:
                _existing = {
                    row[1]
                    for row in _conn.execute(text("PRAGMA table_info(students)")).fetchall()
                }
                if "profile_photo_url" not in _existing:
                    _conn.execute(text(
                        "ALTER TABLE students ADD COLUMN profile_photo_url VARCHAR(512)"
                    ))
            _conn.commit()
            logger.info("students.profile_photo_url migration completed (#4301)")
        except Exception as _kp_col_err:
            _conn.rollback()
            logger.warning("students.profile_photo_url migration note: %s", _kp_col_err)
except Exception as _kp_err:
    logger.warning("students.profile_photo_url migration outer note: %s", _kp_err)
finally:
    if _kp_lock_conn is not None:
        if _kp_lock_acquired:
            try:
                _kp_lock_conn.execute(text("SELECT pg_advisory_unlock(4301)"))
                _kp_lock_conn.commit()
            except Exception:
                pass
        _kp_lock_conn.close()


# CB-CMCP-001 M0-A 0A-3 (#4414) — extend the ``userrole`` PG enum type with two
# new values for the Curriculum + Master Content Plan: BOARD_ADMIN and
# CURRICULUM_ADMIN. SQLAlchemy ``Enum(UserRole)`` creates a native PG enum and
# ``create_all`` does NOT add new values to an existing enum type — that
# requires ``ALTER TYPE``. SQLite uses VARCHAR + CHECK constraint refreshed by
# ``create_all`` so no migration is needed there. ``IF NOT EXISTS`` on
# ``ADD VALUE`` requires PG 9.6+ and makes this idempotent. Wrapped in
# pg_try_advisory_lock for Cloud Run safety (3 retries × 5s — see CLAUDE.md
# migration-locking section).
_ur_lock_conn = None
_ur_lock_acquired = False
try:
    if _is_pg:
        _ur_lock_conn = engine.connect()
        for _ur_attempt in range(1, 4):
            _ur_result = _ur_lock_conn.execute(text("SELECT pg_try_advisory_lock(4414)"))
            _ur_lock_acquired = _ur_result.scalar()
            if _ur_lock_acquired:
                logger.info("Acquired advisory lock 4414 for userrole enum migration (attempt %d)", _ur_attempt)
                break
            logger.warning("Advisory lock 4414 held by another instance (attempt %d/3), retrying in 5s...", _ur_attempt)
            time.sleep(5)
        if not _ur_lock_acquired:
            logger.warning("Could not acquire advisory lock 4414 after 3 attempts — running userrole enum migration without lock")

        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in
        # older PG, so use AUTOCOMMIT isolation. Each value gets its own
        # statement; ``IF NOT EXISTS`` makes both idempotent.
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as _ur_conn:
                for _ur_value in ("BOARD_ADMIN", "CURRICULUM_ADMIN"):
                    try:
                        _ur_conn.execute(text(
                            f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{_ur_value}'"
                        ))
                    except Exception as _ur_value_err:
                        logger.warning("userrole enum ADD VALUE %s note: %s", _ur_value, _ur_value_err)
                logger.info("userrole enum migration completed (#4414)")
        except Exception as _ur_inner_err:
            logger.warning("userrole enum migration note: %s", _ur_inner_err)
except Exception as _ur_err:
    logger.warning("userrole enum migration outer note: %s", _ur_err)
finally:
    if _ur_lock_conn is not None:
        if _ur_lock_acquired:
            try:
                _ur_lock_conn.execute(text("SELECT pg_advisory_unlock(4414)"))
                _ur_lock_conn.commit()
            except Exception:
                pass
        _ur_lock_conn.close()


# CB-CMCP-001 0A-2 (#4413) — extend study_guides per locked decision D2=B with
# 8 curriculum-aware columns (se_codes, alignment_score, ceg_version, state,
# board_id, voice_module_hash, class_context_envelope_summary, requested_persona).
# All nullable / defaulted so existing rows + non-CMCP code paths continue to
# work unchanged. Wrapped in pg_try_advisory_lock for Cloud Run safety
# (3 retries x 5s — see CLAUDE.md migration-locking section). Idempotent.
_cmcp_sg_lock_conn = None
_cmcp_sg_lock_acquired = False
try:
    if _is_pg:
        import time as _cmcp_sg_time
        _cmcp_sg_lock_conn = engine.connect()
        for _cmcp_sg_attempt in range(1, 4):
            _cmcp_sg_result = _cmcp_sg_lock_conn.execute(text("SELECT pg_try_advisory_lock(4413)"))
            _cmcp_sg_lock_acquired = _cmcp_sg_result.scalar()
            if _cmcp_sg_lock_acquired:
                logger.info("Acquired advisory lock 4413 for study_guides CMCP-extension migration (attempt %d)", _cmcp_sg_attempt)
                break
            logger.warning("Advisory lock 4413 held by another instance (attempt %d/3), retrying in 5s...", _cmcp_sg_attempt)
            _cmcp_sg_time.sleep(5)
        if not _cmcp_sg_lock_acquired:
            logger.warning("Could not acquire advisory lock 4413 after 3 attempts — running study_guides CMCP-extension migration without lock")

    # Per-dialect column type list. JSON columns map to JSONB on PG, JSON on
    # SQLite (memory rule: gate per-DB-dialect via settings.database_url).
    _cmcp_sg_cols_pg = [
        ("se_codes", "JSONB"),
        ("alignment_score", "NUMERIC(4,3)"),
        ("ceg_version", "INTEGER"),
        ("state", "VARCHAR(30) DEFAULT 'DRAFT'"),
        ("board_id", "VARCHAR(50)"),
        ("voice_module_hash", "VARCHAR(64)"),
        ("class_context_envelope_summary", "JSONB"),
        ("requested_persona", "VARCHAR(20)"),
    ]
    _cmcp_sg_cols_sqlite = [
        ("se_codes", "JSON"),
        ("alignment_score", "NUMERIC(4,3)"),
        ("ceg_version", "INTEGER"),
        ("state", "VARCHAR(30) DEFAULT 'DRAFT'"),
        ("board_id", "VARCHAR(50)"),
        ("voice_module_hash", "VARCHAR(64)"),
        ("class_context_envelope_summary", "JSON"),
        ("requested_persona", "VARCHAR(20)"),
    ]
    _cmcp_sg_cols = _cmcp_sg_cols_pg if _is_pg else _cmcp_sg_cols_sqlite

    with engine.connect() as _conn:
        try:
            if _is_pg:
                for _col, _typ in _cmcp_sg_cols:
                    _conn.execute(text(
                        f"ALTER TABLE study_guides ADD COLUMN IF NOT EXISTS {_col} {_typ}"
                    ))
            else:
                # SQLite has no ADD COLUMN IF NOT EXISTS — probe via PRAGMA.
                _existing = {
                    row[1]
                    for row in _conn.execute(text("PRAGMA table_info(study_guides)")).fetchall()
                }
                for _col, _typ in _cmcp_sg_cols:
                    if _col in _existing:
                        continue
                    _conn.execute(text(
                        f"ALTER TABLE study_guides ADD COLUMN {_col} {_typ}"
                    ))
            _conn.commit()
            logger.info("study_guides CMCP-extension migration completed (#4413)")
        except Exception as _cmcp_sg_col_err:
            _conn.rollback()
            logger.warning("study_guides CMCP-extension migration note: %s", _cmcp_sg_col_err)
except Exception as _cmcp_sg_err:
    logger.warning("study_guides CMCP-extension migration outer note: %s", _cmcp_sg_err)
finally:
    if _cmcp_sg_lock_conn is not None:
        if _cmcp_sg_lock_acquired:
            try:
                _cmcp_sg_lock_conn.execute(text("SELECT pg_advisory_unlock(4413)"))
                _cmcp_sg_lock_conn.commit()
            except Exception:
                pass
        _cmcp_sg_lock_conn.close()


# CB-CMCP-001 M3-A 3A-1 (#4576) — Teacher Review Queue review-state columns.
# Adds ``edit_history`` (JSONB on PG / JSON on SQLite — append-only edit log),
# ``reviewed_by_user_id``, ``reviewed_at``, and ``rejection_reason``. All four
# columns are nullable so legacy ``study_guides`` rows continue to work.
#
# Idempotent. Wrapped in pg_try_advisory_lock for Cloud Run safety
# (3 retries x 5s — see CLAUDE.md migration-locking section).
_cmcp_review_q_lock_conn = None
_cmcp_review_q_lock_acquired = False
try:
    if _is_pg:
        import time as _cmcp_review_q_time
        _cmcp_review_q_lock_conn = engine.connect()
        for _cmcp_review_q_attempt in range(1, 4):
            _cmcp_review_q_result = _cmcp_review_q_lock_conn.execute(text("SELECT pg_try_advisory_lock(4576)"))
            _cmcp_review_q_lock_acquired = _cmcp_review_q_result.scalar()
            if _cmcp_review_q_lock_acquired:
                logger.info("Acquired advisory lock 4576 for study_guides review-queue migration (attempt %d)", _cmcp_review_q_attempt)
                break
            logger.warning("Advisory lock 4576 held by another instance (attempt %d/3), retrying in 5s...", _cmcp_review_q_attempt)
            _cmcp_review_q_time.sleep(5)
        if not _cmcp_review_q_lock_acquired:
            logger.warning("Could not acquire advisory lock 4576 after 3 attempts — running study_guides review-queue migration without lock")

    _cmcp_review_q_cols_pg = [
        ("edit_history", "JSONB"),
        ("reviewed_by_user_id", "INTEGER"),
        ("reviewed_at", "TIMESTAMPTZ"),
        ("rejection_reason", "TEXT"),
    ]
    _cmcp_review_q_cols_sqlite = [
        ("edit_history", "JSON"),
        ("reviewed_by_user_id", "INTEGER"),
        ("reviewed_at", "DATETIME"),
        ("rejection_reason", "TEXT"),
    ]
    _cmcp_review_q_cols = _cmcp_review_q_cols_pg if _is_pg else _cmcp_review_q_cols_sqlite

    with engine.connect() as _conn:
        try:
            if _is_pg:
                for _col, _typ in _cmcp_review_q_cols:
                    _conn.execute(text(
                        f"ALTER TABLE study_guides ADD COLUMN IF NOT EXISTS {_col} {_typ}"
                    ))
            else:
                _existing = {
                    row[1]
                    for row in _conn.execute(text("PRAGMA table_info(study_guides)")).fetchall()
                }
                for _col, _typ in _cmcp_review_q_cols:
                    if _col in _existing:
                        continue
                    _conn.execute(text(
                        f"ALTER TABLE study_guides ADD COLUMN {_col} {_typ}"
                    ))
            _conn.commit()
            logger.info("study_guides review-queue migration completed (#4576)")
        except Exception as _cmcp_review_q_col_err:
            _conn.rollback()
            logger.warning("study_guides review-queue migration note: %s", _cmcp_review_q_col_err)
except Exception as _cmcp_review_q_err:
    logger.warning("study_guides review-queue migration outer note: %s", _cmcp_review_q_err)
finally:
    if _cmcp_review_q_lock_conn is not None:
        if _cmcp_review_q_lock_acquired:
            try:
                _cmcp_review_q_lock_conn.execute(text("SELECT pg_advisory_unlock(4576)"))
                _cmcp_review_q_lock_conn.commit()
            except Exception:
                pass
        _cmcp_review_q_lock_conn.close()


# CB-CMCP-001 0B-3a (#4428) — extend ceg_expectations with curriculum-admin
# review workflow columns: review_state, reviewed_by_user_id, reviewed_at,
# review_notes, updated_at. Default ``review_state='accepted'`` so any
# already-active legacy rows do NOT show up in the pending-review queue.
# Rows that were inserted with ``active=False`` BEFORE this column landed
# are extractor-pending (0B-2's contract is "extracted but not yet
# reviewed"), so the migration also runs a one-shot UPDATE to set them
# to ``review_state='pending'``. The extractor (stripe 0B-2) inserts
# future rows with ``review_state='pending'`` directly.
#
# Note: PG 11+ optimizes ``ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT
# <constant>`` to a metadata-only operation (no full table rewrite under
# ACCESS EXCLUSIVE lock). NOW() qualifies because it's evaluated once
# per ALTER. ClassBridge runs on Cloud SQL PG 14+, so this is safe;
# verify before back-porting to clusters older than PG 11.
#
# Idempotent. Wrapped in pg_try_advisory_lock for Cloud Run safety
# (3 retries x 5s — see CLAUDE.md migration-locking section).
_cmcp_review_lock_conn = None
_cmcp_review_lock_acquired = False
try:
    if _is_pg:
        import time as _cmcp_review_time
        _cmcp_review_lock_conn = engine.connect()
        for _cmcp_review_attempt in range(1, 4):
            _cmcp_review_result = _cmcp_review_lock_conn.execute(text("SELECT pg_try_advisory_lock(4428)"))
            _cmcp_review_lock_acquired = _cmcp_review_result.scalar()
            if _cmcp_review_lock_acquired:
                logger.info("Acquired advisory lock 4428 for ceg_expectations review-columns migration (attempt %d)", _cmcp_review_attempt)
                break
            logger.warning("Advisory lock 4428 held by another instance (attempt %d/3), retrying in 5s...", _cmcp_review_attempt)
            _cmcp_review_time.sleep(5)
        if not _cmcp_review_lock_acquired:
            logger.warning("Could not acquire advisory lock 4428 after 3 attempts — running ceg_expectations review-columns migration without lock")

    # Per-dialect column type list. ``TIMESTAMPTZ`` on PG / ``DATETIME``
    # on SQLite (memory rule). ``review_state`` defaults to ``accepted``
    # so legacy rows are not surfaced as pending.
    _cmcp_review_cols_pg = [
        ("review_state", "VARCHAR(20) NOT NULL DEFAULT 'accepted'"),
        ("reviewed_by_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ("reviewed_at", "TIMESTAMPTZ"),
        ("review_notes", "TEXT"),
        ("updated_at", "TIMESTAMPTZ NOT NULL DEFAULT NOW()"),
    ]
    _cmcp_review_cols_sqlite = [
        ("review_state", "VARCHAR(20) NOT NULL DEFAULT 'accepted'"),
        # SQLite cannot add a column with a non-constant default like
        # CURRENT_TIMESTAMP after-the-fact in some configurations; use
        # NULL-safe ADD then leave server_default to the model. For
        # ``updated_at`` we accept a NULL-able fallback in dev/test.
        ("reviewed_by_user_id", "INTEGER REFERENCES users(id)"),
        ("reviewed_at", "DATETIME"),
        ("review_notes", "TEXT"),
        ("updated_at", "DATETIME"),
    ]
    _cmcp_review_cols = _cmcp_review_cols_pg if _is_pg else _cmcp_review_cols_sqlite

    with engine.connect() as _conn:
        try:
            if _is_pg:
                for _col, _typ in _cmcp_review_cols:
                    _conn.execute(text(
                        f"ALTER TABLE ceg_expectations ADD COLUMN IF NOT EXISTS {_col} {_typ}"
                    ))
            else:
                _existing = {
                    row[1]
                    for row in _conn.execute(text("PRAGMA table_info(ceg_expectations)")).fetchall()
                }
                for _col, _typ in _cmcp_review_cols:
                    if _col in _existing:
                        continue
                    _conn.execute(text(
                        f"ALTER TABLE ceg_expectations ADD COLUMN {_col} {_typ}"
                    ))
            # Backfill: rows already in ``active=False`` predate this
            # column and are extractor-pending — promote them to
            # ``review_state='pending'`` so they surface in the queue.
            # Idempotent on second run (already-pending rows are a
            # no-op). Cross-dialect: PG uses ``FALSE`` literal, SQLite
            # uses ``0`` (Boolean is stored as integer).
            if _is_pg:
                _conn.execute(text(
                    "UPDATE ceg_expectations SET review_state='pending' "
                    "WHERE active = FALSE AND review_state = 'accepted'"
                ))
            else:
                _conn.execute(text(
                    "UPDATE ceg_expectations SET review_state='pending' "
                    "WHERE active = 0 AND review_state = 'accepted'"
                ))
            _conn.commit()
            logger.info("ceg_expectations review-columns migration completed (#4428)")
        except Exception as _cmcp_review_col_err:
            _conn.rollback()
            logger.warning("ceg_expectations review-columns migration note: %s", _cmcp_review_col_err)
except Exception as _cmcp_review_err:
    logger.warning("ceg_expectations review-columns migration outer note: %s", _cmcp_review_err)
finally:
    if _cmcp_review_lock_conn is not None:
        if _cmcp_review_lock_acquired:
            try:
                _cmcp_review_lock_conn.execute(text("SELECT pg_advisory_unlock(4428)"))
                _cmcp_review_lock_conn.commit()
            except Exception:
                pass
        _cmcp_review_lock_conn.close()


# CB-CMCP-001 S1 (#4452) — widen ``users.roles`` from VARCHAR(50) to VARCHAR(120)
# so multi-role users with the new BOARD_ADMIN (11) + CURRICULUM_ADMIN (16)
# values fit without silent truncation. The full 6-role string
# "parent,student,teacher,admin,BOARD_ADMIN,CURRICULUM_ADMIN" is 57 chars,
# already over the old 50-char ceiling. Idempotent — PG ALTER TABLE ... ALTER
# COLUMN ... TYPE VARCHAR(120) is metadata-only when widening (no row rewrite,
# no data loss). SQLite stores VARCHAR as TEXT internally and ignores length,
# so the widening is a no-op there but the schema rebuilt by ``create_all``
# already reflects ``String(120)``. Wrapped in pg_try_advisory_lock for
# Cloud Run safety (3 retries x 5s — see CLAUDE.md migration-locking section).
_ur_widen_lock_conn = None
_ur_widen_lock_acquired = False
try:
    if _is_pg:
        import time as _ur_widen_time
        _ur_widen_lock_conn = engine.connect()
        for _ur_widen_attempt in range(1, 4):
            _ur_widen_result = _ur_widen_lock_conn.execute(text("SELECT pg_try_advisory_lock(4448)"))
            _ur_widen_lock_acquired = _ur_widen_result.scalar()
            if _ur_widen_lock_acquired:
                logger.info("Acquired advisory lock 4448 for users.roles widen migration (attempt %d)", _ur_widen_attempt)
                break
            logger.warning("Advisory lock 4448 held by another instance (attempt %d/3), retrying in 5s...", _ur_widen_attempt)
            _ur_widen_time.sleep(5)
        if not _ur_widen_lock_acquired:
            logger.warning("Could not acquire advisory lock 4448 after 3 attempts — running users.roles widen migration without lock")

        with engine.connect() as _conn:
            try:
                _conn.execute(text(
                    "ALTER TABLE users ALTER COLUMN roles TYPE VARCHAR(120)"
                ))
                _conn.commit()
                logger.info("users.roles widen migration completed (#4452)")
            except Exception as _ur_widen_col_err:
                _conn.rollback()
                logger.warning("users.roles widen migration note: %s", _ur_widen_col_err)
    # SQLite: no-op. ``Base.metadata.create_all`` rebuilds the schema with the
    # new String(120) length on test/dev startup; SQLite ignores VARCHAR length.
except Exception as _ur_widen_err:
    logger.warning("users.roles widen migration outer note: %s", _ur_widen_err)
finally:
    if _ur_widen_lock_conn is not None:
        if _ur_widen_lock_acquired:
            try:
                _ur_widen_lock_conn.execute(text("SELECT pg_advisory_unlock(4448)"))
                _ur_widen_lock_conn.commit()
            except Exception:
                pass
        _ur_widen_lock_conn.close()


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
app.include_router(class_import.router, prefix="/api")  # CB-ONBOARD-001 (#3985) — must come before courses to win over /{course_id}
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
app.include_router(parent_kids.router, prefix="/api")
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
app.include_router(parent_email_digest.profiles_router, prefix="/api")
from app.api.routes import admin_outreach_templates
app.include_router(admin_outreach_templates.router, prefix="/api")
from app.api.routes import admin_outreach
app.include_router(admin_outreach.router, prefix="/api")
app.include_router(features_route.router, prefix="/api")
app.include_router(ile.router, prefix="/api")
app.include_router(asgf.router, prefix="/api")
app.include_router(demo_verify.router, prefix="/api/v1")  # CB-DEMO-001 B2 (#3604)
app.include_router(public_routes.router, prefix="/api/v1")  # CB-DEMO-001 B2 (#3604)
app.include_router(demo.router, prefix="/api/v1")  # CB-DEMO-001 B1 (#3603)
app.include_router(tutor.router, prefix="/api")  # CB-TUTOR-002 Phase 1 (#4063)
app.include_router(dci_streak.router, prefix="/api")  # CB-DCI-001 M0-8 (#4145)
app.include_router(dci_consent.router, prefix="/api")  # CB-DCI-001 M0-11 (#4148)
app.include_router(dci.router, prefix="/api")  # CB-DCI-001 M0-4 (#4139)
app.include_router(curriculum.router, prefix="/api")  # CB-CMCP-001 M0-B 0B-1 (#4415)
app.include_router(ceg_admin_review.router, prefix="/api")  # CB-CMCP-001 M0-B 0B-3a (#4428)
app.include_router(cmcp_generate.router, prefix="/api")  # CB-CMCP-001 M1-A 1A-2 (#4471)
app.include_router(cmcp_generate_stream.router, prefix="/api")  # CB-CMCP-001 M1-E 1E-1 (#4481)
app.include_router(cmcp_review.router, prefix="/api")  # CB-CMCP-001 M3-A 3A-1 (#4576)
app.include_router(cmcp_surface_click.router, prefix="/api")  # CB-CMCP-001 M3-C 3C-5 (#4581)
# CB-CMCP-001 M2-A 2A-2 (#4550): MCP transport router. Mounted at the
# top-level /mcp prefix (not /api/mcp) so MCP clients can target the
# canonical MCP path. Per-route guard ``require_mcp_enabled`` returns
# 401 unauth / 403 when ``mcp.enabled`` flag is OFF (default).
app.include_router(mcp_router)  # CB-CMCP-001 M2-A 2A-2 (#4550)

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

    # Task sync from assignments — daily at 6:45 AM UTC, 15 min before the
    # daily digest at 7:00 AM, so the digest reflects the freshly-synced tasks
    # (CB-TASKSYNC-001 I4, #3916).
    from app.jobs.task_sync_job import sync_assignments_to_tasks
    scheduler.add_job(
        sync_assignments_to_tasks,
        CronTrigger(hour=6, minute=45),
        id="task_sync_assignments",
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
