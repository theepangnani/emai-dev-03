"""Service layer for the Study Timeline feature (#2017)."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.course_content import CourseContent
from app.models.course import Course
from app.models.study_guide import StudyGuide
from app.models.quiz_result import QuizResult
from app.models.xp import Badge, XpLedger
from app.schemas.timeline import TimelineEntry, TimelineResponse
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

# Level thresholds for detecting level-up events
_LEVEL_THRESHOLDS: dict[int, int] = {lvl["level"]: lvl["xp_required"] for lvl in LEVELS}
_LEVEL_TITLES: dict[int, str] = {lvl["level"]: lvl["title"] for lvl in LEVELS}


def get_timeline(
    db: Session,
    user_id: int,
    *,
    days: int = 30,
    activity_type: Optional[str] = None,
    course_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> TimelineResponse:
    """Build a unified study timeline for a student."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    all_items: list[TimelineEntry] = []

    # Only gather types the user wants (or all if no filter)
    types_wanted = {activity_type} if activity_type else {"upload", "study_guide", "quiz", "badge", "level_up"}

    # 1. Uploads
    if "upload" in types_wanted:
        q = (
            db.query(CourseContent, Course.name)
            .outerjoin(Course, CourseContent.course_id == Course.id)
            .filter(
                CourseContent.created_by_user_id == user_id,
                CourseContent.created_at >= cutoff,
                CourseContent.archived_at.is_(None),
            )
        )
        if course_id:
            q = q.filter(CourseContent.course_id == course_id)
        for cc, course_name in q.all():
            # Look up XP for this upload
            xp_row = (
                db.query(func.sum(XpLedger.xp_awarded))
                .filter(
                    XpLedger.student_id == user_id,
                    XpLedger.action_type.in_(["upload", "upload_lms"]),
                    func.date(XpLedger.created_at) == func.date(cc.created_at),
                )
                .scalar()
            )
            all_items.append(TimelineEntry(
                type="upload",
                title=cc.title,
                course=course_name,
                date=cc.created_at.isoformat() if cc.created_at else "",
                xp=int(xp_row) if xp_row else None,
            ))

    # 2. Study guides
    if "study_guide" in types_wanted:
        q = (
            db.query(StudyGuide, Course.name)
            .outerjoin(Course, StudyGuide.course_id == Course.id)
            .filter(
                StudyGuide.user_id == user_id,
                StudyGuide.created_at >= cutoff,
                StudyGuide.archived_at.is_(None),
            )
        )
        if course_id:
            q = q.filter(StudyGuide.course_id == course_id)
        for sg, course_name in q.all():
            all_items.append(TimelineEntry(
                type="study_guide",
                title=sg.title,
                course=course_name,
                date=sg.created_at.isoformat() if sg.created_at else "",
                xp=20,  # standard XP for study guide generation
            ))

    # 3. Quizzes
    if "quiz" in types_wanted:
        q = (
            db.query(QuizResult, StudyGuide.title, Course.name)
            .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
            .outerjoin(Course, StudyGuide.course_id == Course.id)
            .filter(
                QuizResult.user_id == user_id,
                QuizResult.completed_at >= cutoff,
            )
        )
        if course_id:
            q = q.filter(StudyGuide.course_id == course_id)
        for qr, guide_title, course_name in q.all():
            all_items.append(TimelineEntry(
                type="quiz",
                title=f"Quiz: {guide_title}",
                course=course_name,
                date=qr.completed_at.isoformat() if qr.completed_at else "",
                xp=15,
                score=int(qr.percentage),
            ))

    # 4. Badges
    if "badge" in types_wanted:
        badges = (
            db.query(Badge)
            .filter(
                Badge.student_id == user_id,
                Badge.awarded_at >= cutoff,
            )
            .all()
        )
        for badge in badges:
            badge_name = _BADGE_NAMES.get(badge.badge_id, badge.badge_id)
            all_items.append(TimelineEntry(
                type="badge",
                title=badge_name,
                date=badge.awarded_at.isoformat() if badge.awarded_at else "",
                badge_id=badge.badge_id,
            ))

    # 5. Level-ups (detect from XP ledger running total)
    if "level_up" in types_wanted:
        ledger_rows = (
            db.query(XpLedger)
            .filter(
                XpLedger.student_id == user_id,
                XpLedger.created_at >= cutoff,
            )
            .order_by(XpLedger.created_at.asc())
            .all()
        )
        if ledger_rows:
            # Get total XP at cutoff by subtracting all XP since cutoff from current total
            total_since = sum(r.xp_awarded for r in ledger_rows)
            # Get current total
            from app.models.xp import XpSummary
            summary = db.query(XpSummary).filter(XpSummary.student_id == user_id).first()
            current_total = summary.total_xp if summary else 0
            running = current_total - total_since

            for row in ledger_rows:
                prev_running = running
                running += row.xp_awarded
                # Check if any level threshold was crossed
                for level_num in sorted(_LEVEL_THRESHOLDS.keys()):
                    threshold = _LEVEL_THRESHOLDS[level_num]
                    if threshold > 0 and prev_running < threshold <= running:
                        title_str = _LEVEL_TITLES.get(level_num, "")
                        all_items.append(TimelineEntry(
                            type="level_up",
                            title=f"Reached Level {level_num}: {title_str}",
                            date=row.created_at.isoformat() if row.created_at else "",
                        ))

    # Sort all items by date descending
    all_items.sort(key=lambda x: x.date, reverse=True)

    total = len(all_items)
    paginated = all_items[offset: offset + limit]

    return TimelineResponse(items=paginated, total=total)
