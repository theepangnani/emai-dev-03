"""
Badge trigger service — checks and awards achievement badges (#2004).

Called after XP is awarded. Each badge has a condition that is checked
against the student's activity data.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Badge definitions: badge_id -> {name, description, checker function name}
BADGE_DEFINITIONS: list[dict] = [
    {
        "badge_id": "first_upload",
        "badge_name": "First Upload",
        "badge_description": "Upload first document",
        "icon": "\U0001f4e4",
    },
    {
        "badge_id": "first_guide",
        "badge_name": "First Study Guide",
        "badge_description": "Generate first study guide",
        "icon": "\U0001f4d6",
    },
    {
        "badge_id": "streak_7",
        "badge_name": "7-Day Streak",
        "badge_description": "Achieve a 7-day streak",
        "icon": "\U0001f525",
    },
    {
        "badge_id": "streak_30",
        "badge_name": "30-Day Streak",
        "badge_description": "Achieve a 30-day streak",
        "icon": "\U0001f31f",
    },
    {
        "badge_id": "flashcard_fanatic",
        "badge_name": "Flashcard Fanatic",
        "badge_description": "Review 100 flashcards",
        "icon": "\U0001f0cf",
    },
    {
        "badge_id": "lms_linker",
        "badge_name": "LMS Linker",
        "badge_description": "Upload 5 docs from LMS",
        "icon": "\U0001f517",
    },
    {
        "badge_id": "exam_ready",
        "badge_name": "Exam Ready",
        "badge_description": "Generate guide from past exam",
        "icon": "\U0001f393",
    },
    {
        "badge_id": "quiz_improver",
        "badge_name": "Quiz Improver",
        "badge_description": "Score higher 3 times",
        "icon": "\U0001f4c8",
    },
    # Interactive Learning Engine (CB-ILE-001)
    {
        "badge_id": "ile_first_session",
        "badge_name": "Flash Learner",
        "badge_description": "Complete first Flash Tutor session",
        "icon": "\u26a1",
    },
    {
        "badge_id": "ile_streak_5",
        "badge_name": "On Fire",
        "badge_description": "5+ consecutive first-attempt correct in one session",
        "icon": "\U0001f525",
    },
    {
        "badge_id": "ile_mastery_topic",
        "badge_name": "Topic Master",
        "badge_description": "Achieve mastery on any topic",
        "icon": "\U0001f3af",
    },
    {
        "badge_id": "ile_parent_teaching",
        "badge_name": "Team Player",
        "badge_description": "Complete 3+ parent teaching sessions",
        "icon": "\U0001f91d",
    },
]


def _count_actions(db: Session, student_id: int, action_types: list[str]) -> int:
    """Count total xp_ledger entries for given action types."""
    from app.models.xp import XpLedger

    result = (
        db.query(func.count(XpLedger.id))
        .filter(
            XpLedger.student_id == student_id,
            XpLedger.action_type.in_(action_types),
        )
        .scalar()
    )
    return int(result or 0)


def _get_current_streak(db: Session, student_id: int) -> int:
    """Get current streak from xp_summary."""
    from app.models.xp import XpSummary

    summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
    if not summary:
        return 0
    return summary.current_streak or 0


def _has_ile_streak_5(db: Session, student_id: int) -> bool:
    """Check if student has a streak of 5+ first-attempt correct in any ILE session.

    Uses a single joined query to avoid N+1 (#3252).
    """
    from app.models.ile_session import ILESession
    from app.models.ile_question_attempt import ILEQuestionAttempt

    # Single query: load all attempts for all completed sessions
    rows = (
        db.query(ILEQuestionAttempt.session_id, ILEQuestionAttempt.question_index,
                 ILEQuestionAttempt.attempt_number, ILEQuestionAttempt.is_correct,
                 ILESession.question_count)
        .join(ILESession, ILEQuestionAttempt.session_id == ILESession.id)
        .filter(
            ILESession.student_id == student_id,
            ILESession.status == "completed",
        )
        .order_by(ILEQuestionAttempt.session_id, ILEQuestionAttempt.question_index,
                  ILEQuestionAttempt.attempt_number)
        .all()
    )
    if not rows:
        return False

    # Group by session, then by question_index
    sessions: dict[int, dict] = {}
    session_qcount: dict[int, int] = {}
    for sid, qidx, anum, is_correct, qcount in rows:
        sessions.setdefault(sid, {}).setdefault(qidx, []).append((anum, is_correct))
        session_qcount[sid] = qcount

    for sid, by_q in sessions.items():
        streak = 0
        max_streak = 0
        for idx in range(session_qcount.get(sid, 0)):
            q_attempts = by_q.get(idx, [])
            if len(q_attempts) == 1 and q_attempts[0][1]:  # (attempt_number, is_correct)
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        if max_streak >= 5:
            return True
    return False


def _has_ile_mastery_topic(db: Session, student_id: int) -> bool:
    """Check if student has mastered any topic (avg_attempts < 1.3 with 3+ sessions)."""
    from app.models.ile_topic_mastery import ILETopicMastery

    result = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.avg_attempts_per_question < 1.3,
            ILETopicMastery.total_sessions >= 3,
        )
        .first()
    )
    return result is not None


def _has_ile_parent_teaching(db: Session, student_id: int) -> bool:
    """Check if student has completed 3+ parent teaching sessions."""
    from app.models.ile_session import ILESession

    count = (
        db.query(func.count(ILESession.id))
        .filter(
            ILESession.student_id == student_id,
            ILESession.mode == "parent_teaching",
            ILESession.status == "completed",
        )
        .scalar()
    )
    return (count or 0) >= 3


def _has_past_exam_guide(db: Session, student_id: int) -> bool:
    """Check if student has generated a study guide from a past_exam document."""
    from app.models.study_guide import StudyGuide
    from app.models.course_content import CourseContent

    result = (
        db.query(StudyGuide.id)
        .join(CourseContent, StudyGuide.course_content_id == CourseContent.id)
        .filter(
            StudyGuide.user_id == student_id,
            CourseContent.document_type == "past_exam",
        )
        .first()
    )
    return result is not None


# Badge checker functions: badge_id -> (checker, relevant_action_types)
# checker returns True if the badge condition is met
_BADGE_CHECKERS: dict[str, dict] = {
    "first_upload": {
        "check": lambda db, sid: _count_actions(db, sid, ["upload"]) >= 1,
        "actions": {"upload"},
    },
    "first_guide": {
        "check": lambda db, sid: _count_actions(db, sid, ["study_guide"]) >= 1,
        "actions": {"study_guide"},
    },
    "streak_7": {
        "check": lambda db, sid: _get_current_streak(db, sid) >= 7,
        "actions": None,  # Check on any action (streak can change anytime)
    },
    "streak_30": {
        "check": lambda db, sid: _get_current_streak(db, sid) >= 30,
        "actions": None,
    },
    "flashcard_fanatic": {
        "check": lambda db, sid: _count_actions(db, sid, ["flashcard_review", "flashcard_got_it"]) >= 100,
        "actions": {"flashcard_review", "flashcard_got_it"},
    },
    "lms_linker": {
        "check": lambda db, sid: _count_actions(db, sid, ["upload_lms"]) >= 5,
        "actions": {"upload_lms"},
    },
    "exam_ready": {
        "check": lambda db, sid: _has_past_exam_guide(db, sid),
        "actions": {"study_guide"},
    },
    "quiz_improver": {
        "check": lambda db, sid: _count_actions(db, sid, ["quiz_improvement"]) >= 3,
        "actions": {"quiz_improvement"},
    },
    # Interactive Learning Engine (CB-ILE-001)
    "ile_first_session": {
        "check": lambda db, sid: _count_actions(db, sid, ["ile_session_complete"]) >= 1,
        "actions": {"ile_session_complete"},
    },
    "ile_streak_5": {
        "check": lambda db, sid: _has_ile_streak_5(db, sid),
        "actions": {"ile_session_complete"},
    },
    "ile_mastery_topic": {
        "check": lambda db, sid: _has_ile_mastery_topic(db, sid),
        "actions": {"ile_session_complete"},
    },
    "ile_parent_teaching": {
        "check": lambda db, sid: _has_ile_parent_teaching(db, sid),
        "actions": {"ile_session_complete"},
    },
}


def _award_badge(db: Session, student_id: int, badge_id: str) -> bool:
    """Award a badge. Returns True if newly awarded, False if already had it."""
    from app.models.xp import Badge

    existing = (
        db.query(Badge)
        .filter(Badge.student_id == student_id, Badge.badge_id == badge_id)
        .first()
    )
    if existing:
        return False

    badge = Badge(student_id=student_id, badge_id=badge_id)
    db.add(badge)
    db.flush()
    return True


def _create_badge_notification(db: Session, student_id: int, badge_name: str) -> None:
    """Create an in-app notification for a newly earned badge."""
    from app.models.notification import Notification, NotificationType

    notification = Notification(
        user_id=student_id,
        type=NotificationType.SYSTEM,
        title=f"You earned the {badge_name} badge!",
        content=f"Congratulations! You've earned the \"{badge_name}\" achievement badge.",
        link="/xp/badges",
    )
    db.add(notification)
    db.flush()


class BadgeService:
    @staticmethod
    def check_and_award(db: Session, student_id: int, action_type: str) -> list[str]:
        """Called after XP award. Checks if any new badges should be awarded.

        Returns list of newly awarded badge_ids.
        """
        newly_awarded: list[str] = []

        for badge_id, checker_info in _BADGE_CHECKERS.items():
            # Only check badges relevant to this action type (or all if actions is None)
            relevant_actions = checker_info["actions"]
            if relevant_actions is not None and action_type not in relevant_actions:
                continue

            try:
                if checker_info["check"](db, student_id):
                    if _award_badge(db, student_id, badge_id):
                        # Find badge name for notification
                        badge_def = next(
                            (b for b in BADGE_DEFINITIONS if b["badge_id"] == badge_id),
                            None,
                        )
                        badge_name = badge_def["badge_name"] if badge_def else badge_id
                        _create_badge_notification(db, student_id, badge_name)
                        newly_awarded.append(badge_id)
                        logger.info(
                            "Badge awarded | student_id=%s | badge=%s",
                            student_id, badge_id,
                        )
            except Exception:
                logger.exception(
                    "Badge check failed | student_id=%s | badge=%s",
                    student_id, badge_id,
                )

        return newly_awarded
