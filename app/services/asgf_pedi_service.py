"""ASGF digest enrichment — provide session summaries for the Parent Email Digest (#3404)."""

from datetime import datetime, timedelta

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.learning_history import LearningHistory

logger = get_logger(__name__)


def _compute_xp_trend(
    db: Session,
    student_id: int,
    since: datetime,
) -> str:
    """Compare total scores in the recent window vs the prior window of equal length.

    Returns 'up', 'down', or 'stable'.
    """
    # Use the same window length for the prior period
    window_days = (datetime.now(since.tzinfo) - since).days or 7
    prior_start = since - timedelta(days=window_days)

    def _avg_score(start: datetime, end: datetime) -> float | None:
        result = (
            db.query(sa_func.avg(LearningHistory.overall_score_pct))
            .filter(
                LearningHistory.student_id == student_id,
                LearningHistory.session_type == "asgf",
                LearningHistory.overall_score_pct.isnot(None),
                LearningHistory.created_at >= start,
                LearningHistory.created_at < end,
            )
            .scalar()
        )
        return float(result) if result is not None else None

    current_avg = _avg_score(since, datetime.now(since.tzinfo))
    prior_avg = _avg_score(prior_start, since)

    if current_avg is None or prior_avg is None:
        return "stable"
    if current_avg > prior_avg + 5:
        return "up"
    if current_avg < prior_avg - 5:
        return "down"
    return "stable"


async def get_asgf_digest_data(
    student_id: int,
    since: datetime,
    db: Session,
) -> dict:
    """Query learning_history for ASGF sessions in the given window.

    Args:
        student_id: The student's ID (students.id, matching learning_history.student_id).
        since: Start of the reporting window (typically 7 days ago, UTC-aware).
        db: Database session.

    Returns:
        Dict with keys:
            session_count (int): Number of ASGF sessions.
            top_subjects (list[str]): Subjects ordered by frequency.
            xp_trend (str): 'up', 'down', or 'stable'.
            weak_topics (list[str]): Topics flagged as weak.
            session_summaries (list[dict]): Per-session summaries with
                date, subject, score, summary.
    """
    sessions = (
        db.query(LearningHistory)
        .filter(
            LearningHistory.student_id == student_id,
            LearningHistory.session_type == "asgf",
            LearningHistory.created_at >= since,
        )
        .order_by(LearningHistory.created_at.desc())
        .all()
    )

    if not sessions:
        return {
            "session_count": 0,
            "top_subjects": [],
            "xp_trend": "stable",
            "weak_topics": [],
            "session_summaries": [],
        }

    # Top subjects by frequency
    subject_counts: dict[str, int] = {}
    for s in sessions:
        subj = s.subject or "Unknown"
        subject_counts[subj] = subject_counts.get(subj, 0) + 1
    top_subjects = sorted(subject_counts, key=subject_counts.get, reverse=True)

    # Weak topics — collect from weak_concepts JSON across sessions
    weak_set: set[str] = set()
    for s in sessions:
        if s.weak_concepts:
            concepts = s.weak_concepts if isinstance(s.weak_concepts, list) else []
            for concept in concepts:
                if isinstance(concept, str):
                    weak_set.add(concept)
                elif isinstance(concept, dict):
                    weak_set.add(concept.get("name", concept.get("topic", str(concept))))
    weak_topics = sorted(weak_set)

    # XP trend
    xp_trend = _compute_xp_trend(db, student_id, since)

    # Session summaries
    session_summaries = []
    for s in sessions:
        summary_text = s.question_asked or ""
        if len(summary_text) > 120:
            summary_text = summary_text[:117] + "..."

        session_summaries.append({
            "date": s.created_at.isoformat() if s.created_at else None,
            "subject": s.subject or "Unknown",
            "score": s.overall_score_pct,
            "summary": summary_text,
        })

    return {
        "session_count": len(sessions),
        "top_subjects": top_subjects,
        "xp_trend": xp_trend,
        "weak_topics": weak_topics,
        "session_summaries": session_summaries,
    }
