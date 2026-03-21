"""Service layer for the End-of-Term Report Card feature (#2018)."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.course_content import CourseContent
from app.models.quiz_result import QuizResult
from app.models.study_guide import StudyGuide
from app.models.study_session import StudySession
from app.models.user import User
from app.models.xp import Badge, XpLedger, XpSummary
from app.services.xp_service import LEVELS


# Badge ID -> human-readable name
_BADGE_NAMES: dict[str, str] = {
    "first_upload": "First Upload",
    "first_guide": "First Study Guide",
    "streak_7": "7-Day Streak",
    "streak_30": "30-Day Streak",
    "flashcard_fanatic": "Flashcard Fanatic",
    "lms_linker": "LMS Linker",
    "exam_ready": "Exam Ready",
    "quiz_improver": "Quiz Improver",
}


def _determine_term_label(term_start: date, term_end: date) -> str:
    """Determine a human-readable term label from date range."""
    mid = term_start + (term_end - term_start) / 2
    month = mid.month
    year = mid.year
    if month >= 9:
        return f"Fall {year}"
    elif month >= 5:
        return f"Summer {year}"
    elif month >= 1:
        return f"Winter {year}"
    return f"Term {year}"


def _get_level_for_xp(total_xp: int) -> dict:
    """Return the level info for a given total XP."""
    current = LEVELS[0]
    for lvl in LEVELS:
        if total_xp >= lvl["xp_required"]:
            current = lvl
        else:
            break
    return current


class ReportCardService:
    @staticmethod
    def generate(
        db: Session,
        student_id: int,
        term_start: Optional[date] = None,
        term_end: Optional[date] = None,
    ) -> dict:
        """Generate semester report card data for a student."""
        # Default: last 4 months if no dates provided
        if term_end is None:
            term_end = date.today()
        if term_start is None:
            term_start = term_end - timedelta(days=120)

        # Convert to datetime for query filters
        start_dt = datetime(term_start.year, term_start.month, term_start.day, tzinfo=timezone.utc)
        end_dt = datetime(term_end.year, term_end.month, term_end.day, 23, 59, 59, tzinfo=timezone.utc)

        # Student name
        user = db.query(User).filter(User.id == student_id).first()
        student_name = user.full_name if user else "Unknown Student"

        # Term label
        term_label = _determine_term_label(term_start, term_end)

        # --- Uploads ---
        uploads = (
            db.query(CourseContent)
            .filter(
                CourseContent.created_by_user_id == student_id,
                CourseContent.created_at >= start_dt,
                CourseContent.created_at <= end_dt,
                CourseContent.archived_at.is_(None),
            )
            .all()
        )
        total_uploads = len(uploads)

        # --- Study Guides ---
        guides = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.user_id == student_id,
                StudyGuide.created_at >= start_dt,
                StudyGuide.created_at <= end_dt,
                StudyGuide.archived_at.is_(None),
            )
            .all()
        )
        total_guides = len(guides)

        # --- Quizzes ---
        quizzes = (
            db.query(QuizResult)
            .filter(
                QuizResult.user_id == student_id,
                QuizResult.completed_at >= start_dt,
                QuizResult.completed_at <= end_dt,
            )
            .all()
        )
        total_quizzes = len(quizzes)

        # --- Subjects studied (from study guides with course info) ---
        subject_rows = (
            db.query(
                Course.name,
                func.count(StudyGuide.id).label("guide_count"),
            )
            .join(StudyGuide, StudyGuide.course_id == Course.id)
            .filter(
                StudyGuide.user_id == student_id,
                StudyGuide.created_at >= start_dt,
                StudyGuide.created_at <= end_dt,
                StudyGuide.archived_at.is_(None),
            )
            .group_by(Course.name)
            .all()
        )

        # Count quizzes per course via study guide
        quiz_by_course: dict[str, int] = {}
        quiz_course_rows = (
            db.query(Course.name, func.count(QuizResult.id))
            .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
            .join(Course, StudyGuide.course_id == Course.id)
            .filter(
                QuizResult.user_id == student_id,
                QuizResult.completed_at >= start_dt,
                QuizResult.completed_at <= end_dt,
            )
            .group_by(Course.name)
            .all()
        )
        for course_name, count in quiz_course_rows:
            quiz_by_course[course_name] = count

        subjects_studied = [
            {
                "name": name,
                "guides": guide_count,
                "quizzes": quiz_by_course.get(name, 0),
            }
            for name, guide_count in subject_rows
        ]

        # --- XP ---
        xp_in_term = (
            db.query(func.coalesce(func.sum(XpLedger.xp_awarded), 0))
            .filter(
                XpLedger.student_id == student_id,
                XpLedger.created_at >= start_dt,
                XpLedger.created_at <= end_dt,
            )
            .scalar()
        )
        total_xp = int(xp_in_term) if xp_in_term else 0

        # Level reached
        summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
        if summary:
            level_info = _get_level_for_xp(summary.total_xp)
        else:
            level_info = LEVELS[0]
        level_reached = {"level": level_info["level"], "title": level_info["title"]}

        # --- Badges earned in term ---
        badges = (
            db.query(Badge)
            .filter(
                Badge.student_id == student_id,
                Badge.awarded_at >= start_dt,
                Badge.awarded_at <= end_dt,
            )
            .all()
        )
        badges_earned = [
            {
                "name": _BADGE_NAMES.get(b.badge_id, b.badge_id),
                "date": b.awarded_at.isoformat() if b.awarded_at else "",
            }
            for b in badges
        ]

        # --- Longest streak ---
        longest_streak = summary.longest_streak if summary else 0

        # --- Most reviewed topics (top 5 study guide titles by quiz attempts) ---
        most_reviewed_rows = (
            db.query(StudyGuide.title, func.count(QuizResult.id).label("attempts"))
            .join(QuizResult, QuizResult.study_guide_id == StudyGuide.id)
            .filter(
                QuizResult.user_id == student_id,
                QuizResult.completed_at >= start_dt,
                QuizResult.completed_at <= end_dt,
            )
            .group_by(StudyGuide.title)
            .order_by(func.count(QuizResult.id).desc())
            .limit(5)
            .all()
        )
        most_reviewed_topics = [row[0] for row in most_reviewed_rows]

        # --- Study sessions ---
        sessions = (
            db.query(StudySession)
            .filter(
                StudySession.student_id == student_id,
                StudySession.created_at >= start_dt,
                StudySession.created_at <= end_dt,
            )
            .all()
        )
        study_sessions = len(sessions)
        total_study_minutes = sum(s.duration_seconds for s in sessions) // 60

        return {
            "student_name": student_name,
            "term": term_label,
            "subjects_studied": subjects_studied,
            "total_uploads": total_uploads,
            "total_guides": total_guides,
            "total_quizzes": total_quizzes,
            "total_xp": total_xp,
            "level_reached": level_reached,
            "badges_earned": badges_earned,
            "longest_streak": longest_streak,
            "most_reviewed_topics": most_reviewed_topics,
            "study_sessions": study_sessions,
            "total_study_minutes": total_study_minutes,
        }
