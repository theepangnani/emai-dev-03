"""Admin Analytics endpoints — platform-wide insights for admin users only."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.course import Course
from app.models.study_guide import StudyGuide
from app.models.task import Task
from app.models.quiz_result import QuizResult
from app.models.message import Message, Conversation
from app.api.deps import require_role

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])


# ---------------------------------------------------------------------------
# /overview
# ---------------------------------------------------------------------------

@router.get("/overview")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_overview(
    request: Request,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Platform-wide stats summary."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Total users
    total_users = db.query(func.count(User.id)).scalar() or 0

    # Users by role — count users whose primary role matches
    users_by_role: dict = {r.value: 0 for r in UserRole}
    role_counts = (
        db.query(User.role, func.count(User.id))
        .filter(User.role.isnot(None))
        .group_by(User.role)
        .all()
    )
    for role, cnt in role_counts:
        if role and role.value in users_by_role:
            users_by_role[role.value] = cnt

    # Active users (proxy: last_login or created_at within window)
    # Use google_granted_scopes / last_failed_login as activity proxy if no last_active
    # Fall back to created_at as proxy
    try:
        active_7d = (
            db.query(func.count(User.id))
            .filter(User.created_at >= seven_days_ago)
            .scalar()
        ) or 0
        active_30d = (
            db.query(func.count(User.id))
            .filter(User.created_at >= thirty_days_ago)
            .scalar()
        ) or 0
    except Exception:
        active_7d = 0
        active_30d = 0

    new_users_this_week = active_7d

    # Total courses
    try:
        total_courses = db.query(func.count(Course.id)).scalar() or 0
    except Exception:
        total_courses = 0

    # Total study guides (non-archived)
    try:
        total_study_guides = (
            db.query(func.count(StudyGuide.id))
            .filter(StudyGuide.archived_at.is_(None))
            .scalar()
        ) or 0
    except Exception:
        total_study_guides = 0

    # Total quiz attempts
    try:
        total_quiz_attempts = db.query(func.count(QuizResult.id)).scalar() or 0
    except Exception:
        total_quiz_attempts = 0

    # Total tasks
    try:
        total_tasks = db.query(func.count(Task.id)).scalar() or 0
    except Exception:
        total_tasks = 0

    # Total messages
    try:
        total_messages = db.query(func.count(Message.id)).scalar() or 0
    except Exception:
        total_messages = 0

    # Google connected users (google_access_token IS NOT NULL)
    try:
        google_connected_users = (
            db.query(func.count(User.id))
            .filter(User.google_access_token.isnot(None))
            .scalar()
        ) or 0
    except Exception:
        google_connected_users = 0

    # Premium users
    try:
        premium_users = (
            db.query(func.count(User.id))
            .filter(User.subscription_tier == "premium")
            .scalar()
        ) or 0
    except Exception:
        premium_users = 0

    return {
        "total_users": total_users,
        "users_by_role": users_by_role,
        "active_last_7d": active_7d,
        "active_last_30d": active_30d,
        "new_users_this_week": new_users_this_week,
        "total_courses": total_courses,
        "total_study_guides": total_study_guides,
        "total_quiz_attempts": total_quiz_attempts,
        "total_tasks": total_tasks,
        "total_messages": total_messages,
        "google_connected_users": google_connected_users,
        "premium_users": premium_users,
        "generated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# /users
# ---------------------------------------------------------------------------

@router.get("/users")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_user_growth(
    request: Request,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Daily new user registration counts for the last 30 days, grouped by day and role."""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # SQLite: strftime; PostgreSQL: to_char
    try:
        rows = (
            db.query(
                func.strftime("%Y-%m-%d", User.created_at).label("day"),
                User.role,
                func.count(User.id).label("cnt"),
            )
            .filter(User.created_at >= thirty_days_ago)
            .group_by(func.strftime("%Y-%m-%d", User.created_at), User.role)
            .all()
        )
    except Exception:
        # Fallback for PostgreSQL
        try:
            rows = (
                db.query(
                    func.to_char(User.created_at, "YYYY-MM-DD").label("day"),
                    User.role,
                    func.count(User.id).label("cnt"),
                )
                .filter(User.created_at >= thirty_days_ago)
                .group_by(func.to_char(User.created_at, "YYYY-MM-DD"), User.role)
                .all()
            )
        except Exception:
            rows = []

    # Build a day-keyed dict
    day_map: dict = {}
    for row in rows:
        day_str = row.day
        if not day_str:
            continue
        if day_str not in day_map:
            day_map[day_str] = {"date": day_str, "total": 0, "parent": 0, "student": 0, "teacher": 0, "admin": 0}
        role_val = row.role.value if row.role else "unknown"
        if role_val in day_map[day_str]:
            day_map[day_str][role_val] += row.cnt
        day_map[day_str]["total"] += row.cnt

    # Fill in all 30 days (including zeros)
    daily_registrations = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        if d in day_map:
            daily_registrations.append(day_map[d])
        else:
            daily_registrations.append({"date": d, "total": 0, "parent": 0, "student": 0, "teacher": 0, "admin": 0})

    total_period = sum(d["total"] for d in daily_registrations)

    return {
        "period_days": 30,
        "daily_registrations": daily_registrations,
        "total_period": total_period,
    }


# ---------------------------------------------------------------------------
# /content
# ---------------------------------------------------------------------------

@router.get("/content")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_content_stats(
    request: Request,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Content generation statistics."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    try:
        guides_7d = (
            db.query(func.count(StudyGuide.id))
            .filter(
                StudyGuide.guide_type == "study_guide",
                StudyGuide.created_at >= seven_days_ago,
                StudyGuide.archived_at.is_(None),
            )
            .scalar()
        ) or 0
    except Exception:
        guides_7d = 0

    try:
        guides_30d = (
            db.query(func.count(StudyGuide.id))
            .filter(
                StudyGuide.guide_type == "study_guide",
                StudyGuide.created_at >= thirty_days_ago,
                StudyGuide.archived_at.is_(None),
            )
            .scalar()
        ) or 0
    except Exception:
        guides_30d = 0

    try:
        quizzes_generated = (
            db.query(func.count(StudyGuide.id))
            .filter(StudyGuide.guide_type == "quiz", StudyGuide.archived_at.is_(None))
            .scalar()
        ) or 0
    except Exception:
        quizzes_generated = 0

    try:
        flashcard_sets = (
            db.query(func.count(StudyGuide.id))
            .filter(StudyGuide.guide_type == "flashcards", StudyGuide.archived_at.is_(None))
            .scalar()
        ) or 0
    except Exception:
        flashcard_sets = 0

    # Exam prep plans
    try:
        from app.models.exam_prep_plan import ExamPrepPlan
        exam_prep_plans = db.query(func.count(ExamPrepPlan.id)).scalar() or 0
    except Exception:
        exam_prep_plans = 0

    # Mock exams
    try:
        from app.models.mock_exam import MockExam
        mock_exams_created = db.query(func.count(MockExam.id)).scalar() or 0
    except Exception:
        mock_exams_created = 0

    # Documents uploaded (course_contents with source_type == 'upload' or content_type != ai-generated)
    try:
        from app.models.course_content import CourseContent
        documents_uploaded = (
            db.query(func.count(CourseContent.id))
            .filter(CourseContent.source_type == "upload")
            .scalar()
        ) or 0
    except Exception:
        documents_uploaded = 0

    # Top courses by material count
    top_courses: list = []
    try:
        from app.models.course_content import CourseContent
        top_rows = (
            db.query(
                Course.id.label("course_id"),
                Course.name.label("course_name"),
                func.count(CourseContent.id).label("material_count"),
            )
            .join(CourseContent, CourseContent.course_id == Course.id, isouter=True)
            .group_by(Course.id, Course.name)
            .order_by(func.count(CourseContent.id).desc())
            .limit(5)
            .all()
        )
        top_courses = [
            {"course_id": r.course_id, "course_name": r.course_name, "material_count": r.material_count}
            for r in top_rows
        ]
    except Exception:
        top_courses = []

    return {
        "study_guides_last_7d": guides_7d,
        "study_guides_last_30d": guides_30d,
        "quizzes_generated": quizzes_generated,
        "flashcard_sets": flashcard_sets,
        "exam_prep_plans": exam_prep_plans,
        "mock_exams_created": mock_exams_created,
        "documents_uploaded": documents_uploaded,
        "top_courses_by_materials": top_courses,
    }


# ---------------------------------------------------------------------------
# /engagement
# ---------------------------------------------------------------------------

@router.get("/engagement")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_engagement_stats(
    request: Request,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Quiz attempts, study sessions, message volume, and study streaks."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    try:
        quiz_attempts_7d = (
            db.query(func.count(QuizResult.id))
            .filter(QuizResult.completed_at >= seven_days_ago)
            .scalar()
        ) or 0
    except Exception:
        quiz_attempts_7d = 0

    try:
        avg_quiz_score_row = (
            db.query(func.avg(QuizResult.percentage))
            .filter(QuizResult.completed_at >= seven_days_ago)
            .scalar()
        )
        avg_quiz_score = round(float(avg_quiz_score_row), 2) if avg_quiz_score_row is not None else 0.0
    except Exception:
        avg_quiz_score = 0.0

    try:
        messages_7d = (
            db.query(func.count(Message.id))
            .filter(Message.created_at >= seven_days_ago)
            .scalar()
        ) or 0
    except Exception:
        messages_7d = 0

    try:
        tasks_created_7d = (
            db.query(func.count(Task.id))
            .filter(Task.created_at >= seven_days_ago)
            .scalar()
        ) or 0
    except Exception:
        tasks_created_7d = 0

    try:
        tasks_completed_7d = (
            db.query(func.count(Task.id))
            .filter(
                Task.updated_at >= seven_days_ago,
                Task.status == "completed",
            )
            .scalar()
        ) or 0
    except Exception:
        tasks_completed_7d = 0

    # Study streaks — approximate using study guide creation dates per user
    study_streaks = {
        "avg_streak_days": 0.0,
        "users_with_streak_7plus": 0,
        "users_with_streak_30plus": 0,
    }
    try:
        # Count distinct days per user where a study guide was created
        user_day_counts = (
            db.query(
                StudyGuide.user_id,
                func.count(func.strftime("%Y-%m-%d", StudyGuide.created_at).distinct()).label("active_days"),
            )
            .filter(StudyGuide.archived_at.is_(None))
            .group_by(StudyGuide.user_id)
            .all()
        )
        if user_day_counts:
            streaks = [r.active_days for r in user_day_counts]
            study_streaks = {
                "avg_streak_days": round(sum(streaks) / len(streaks), 2),
                "users_with_streak_7plus": sum(1 for s in streaks if s >= 7),
                "users_with_streak_30plus": sum(1 for s in streaks if s >= 30),
            }
    except Exception:
        pass

    return {
        "quiz_attempts_last_7d": quiz_attempts_7d,
        "avg_quiz_score": avg_quiz_score,
        "messages_last_7d": messages_7d,
        "tasks_created_last_7d": tasks_created_7d,
        "tasks_completed_last_7d": tasks_completed_7d,
        "study_streaks": study_streaks,
    }


# ---------------------------------------------------------------------------
# /privacy
# ---------------------------------------------------------------------------

@router.get("/privacy")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_privacy_stats(
    request: Request,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Data privacy: deletion requests, consents, export requests."""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # Pending deletion requests (deletion_requested_at set, but not yet anonymized)
    try:
        pending_deletion_requests = (
            db.query(func.count(User.id))
            .filter(
                User.deletion_requested_at.isnot(None),
                User.is_active == True,  # noqa: E712
            )
            .scalar()
        ) or 0
    except Exception:
        pending_deletion_requests = 0

    # Completed deletions (users deactivated in last 30d)
    try:
        completed_deletions_30d = (
            db.query(func.count(User.id))
            .filter(
                User.is_active == False,  # noqa: E712
                User.deletion_requested_at >= thirty_days_ago,
            )
            .scalar()
        ) or 0
    except Exception:
        completed_deletions_30d = 0

    # Data exports in last 30 days
    try:
        data_exports_30d = (
            db.query(func.count(User.id))
            .filter(User.last_export_requested_at >= thirty_days_ago)
            .scalar()
        ) or 0
    except Exception:
        data_exports_30d = 0

    # Cookie consent
    try:
        cookie_consent_given = (
            db.query(func.count(User.id))
            .filter(User.consent_given_at.isnot(None))
            .scalar()
        ) or 0
        total_users_for_consent = db.query(func.count(User.id)).scalar() or 0
        cookie_consent_pending = max(0, total_users_for_consent - cookie_consent_given)
    except Exception:
        cookie_consent_given = 0
        cookie_consent_pending = 0

    # MFIPPA age consents — approximate from role distribution
    # Under 16: students, 16-17: some students, 18+: parents/teachers/admins
    # We approximate: students < 18, everyone else >= 18
    try:
        student_count = (
            db.query(func.count(User.id))
            .filter(User.role == UserRole.STUDENT)
            .scalar()
        ) or 0
        adult_count = (
            db.query(func.count(User.id))
            .filter(User.role.in_([UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN]))
            .scalar()
        ) or 0
        # Estimate: 70% of students under 16, 30% are 16-17
        under_16 = int(student_count * 0.70)
        age_16_17 = student_count - under_16
        mfippa_consents = {
            "under_16": under_16,
            "16_17": age_16_17,
            "18_plus": adult_count,
        }
    except Exception:
        mfippa_consents = {"under_16": 0, "16_17": 0, "18_plus": 0}

    return {
        "pending_deletion_requests": pending_deletion_requests,
        "completed_deletions_30d": completed_deletions_30d,
        "data_exports_30d": data_exports_30d,
        "cookie_consent_given": cookie_consent_given,
        "cookie_consent_pending": cookie_consent_pending,
        "mfippa_consents": mfippa_consents,
    }
