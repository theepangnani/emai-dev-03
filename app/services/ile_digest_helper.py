"""Helper functions for ILE data in parent email digests (#3214)."""

from datetime import datetime

from sqlalchemy import and_, func as sa_func
from sqlalchemy.orm import Session

from app.models.ile_session import ILESession
from app.models.ile_topic_mastery import ILETopicMastery


def get_daily_ile_summary(db: Session, student_id: int, date: datetime) -> dict:
    """Get ILE activity for a student on a specific date.

    Args:
        db: Database session.
        student_id: The student's user ID (users.id, not students.id).
        date: The start-of-day datetime (UTC, timezone-aware).

    Returns:
        Dict with keys: session_count, topics, total_correct, total_questions,
        score_pct, weak_areas.
    """
    from datetime import timedelta

    day_end = date + timedelta(days=1)

    # Completed, non-private sessions on this date
    sessions = (
        db.query(ILESession)
        .filter(
            ILESession.student_id == student_id,
            ILESession.status == "completed",
            ILESession.is_private_practice.is_(False),
            ILESession.completed_at >= date,
            ILESession.completed_at < day_end,
        )
        .all()
    )

    if not sessions:
        return {
            "session_count": 0,
            "topics": [],
            "total_correct": 0,
            "total_questions": 0,
            "score_pct": None,
            "weak_areas": [],
        }

    topics = sorted({s.topic for s in sessions})
    total_correct = sum(s.total_correct or 0 for s in sessions)
    total_questions = sum(s.question_count or 0 for s in sessions)
    score_pct = round(total_correct / total_questions * 100, 1) if total_questions > 0 else None

    # Current weak areas for this student
    weak_rows = (
        db.query(ILETopicMastery.topic)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.is_weak_area.is_(True),
        )
        .all()
    )
    weak_areas = [r[0] for r in weak_rows]

    return {
        "session_count": len(sessions),
        "topics": topics,
        "total_correct": total_correct,
        "total_questions": total_questions,
        "score_pct": score_pct,
        "weak_areas": weak_areas,
    }


def get_weekly_ile_summary(
    db: Session, student_id: int, start_date: datetime, end_date: datetime
) -> dict:
    """Get ILE activity for a student over a week.

    Args:
        db: Database session.
        student_id: The student's user ID (users.id, not students.id).
        start_date: Week start datetime (UTC, timezone-aware).
        end_date: Week end datetime (UTC, timezone-aware).

    Returns:
        Dict with keys: session_count, topics, total_correct, total_questions,
        avg_score_pct, mastery_improved, new_topics, aha_moments, weak_areas.
    """
    # Completed, non-private sessions this week
    sessions = (
        db.query(ILESession)
        .filter(
            ILESession.student_id == student_id,
            ILESession.status == "completed",
            ILESession.is_private_practice.is_(False),
            ILESession.completed_at >= start_date,
            ILESession.completed_at < end_date,
        )
        .all()
    )

    if not sessions:
        return {
            "session_count": 0,
            "topics": [],
            "total_correct": 0,
            "total_questions": 0,
            "avg_score_pct": None,
            "mastery_improved": [],
            "new_topics": [],
            "aha_moments": [],
            "weak_areas": [],
        }

    topics = sorted({s.topic for s in sessions})
    total_correct = sum(s.total_correct or 0 for s in sessions)
    total_questions = sum(s.question_count or 0 for s in sessions)
    avg_score_pct = round(total_correct / total_questions * 100, 1) if total_questions > 0 else None

    # Topic mastery data for topics practiced this week
    mastery_rows = (
        db.query(ILETopicMastery)
        .filter(
            ILETopicMastery.student_id == student_id,
            ILETopicMastery.topic.in_(topics),
        )
        .all()
    )

    mastery_improved = []
    new_topics = []
    aha_moments = []
    weak_areas = []

    for m in mastery_rows:
        # New topics: first session was this week (total_sessions == count this week)
        week_sessions_for_topic = sum(
            1 for s in sessions if s.topic == m.topic
        )
        if m.total_sessions == week_sessions_for_topic:
            new_topics.append(m.topic)

        # Mastery improved: difficulty went up (medium->hard or easy->medium)
        if m.current_difficulty in ("hard",) and m.total_sessions > 1:
            mastery_improved.append(m.topic)

        # Aha moments: avg_attempts_per_question dropped below 1.3
        # (meaning student is getting answers right on first try)
        if (
            m.avg_attempts_per_question > 0
            and m.avg_attempts_per_question < 1.3
            and m.total_sessions > 1
        ):
            aha_moments.append(m.topic)

        if m.is_weak_area:
            weak_areas.append(m.topic)

    return {
        "session_count": len(sessions),
        "topics": topics,
        "total_correct": total_correct,
        "total_questions": total_questions,
        "avg_score_pct": avg_score_pct,
        "mastery_improved": mastery_improved,
        "new_topics": new_topics,
        "aha_moments": aha_moments,
        "weak_areas": weak_areas,
    }
