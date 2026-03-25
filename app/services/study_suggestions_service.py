"""Smart Study Time Suggestions service (#2227).

Analyzes study session and AI usage timestamps to find peak activity windows.
Simple statistical approach — no ML required.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ai_usage_history import AIUsageHistory
from app.models.audit_log import AuditLog
from app.models.study_session import StudySession
from app.schemas.study_suggestions import (
    DailyStudyMinutes,
    StudySuggestionsResponse,
    StudyTimeSlot,
)

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Time-of-day buckets
PERIODS = {
    "morning": (6, 12, "Morning (6 AM - 12 PM)"),
    "afternoon": (12, 17, "Afternoon (12 - 5 PM)"),
    "evening": (17, 22, "Evening (5 - 10 PM)"),
}


def _get_period(hour: int) -> tuple[str, str]:
    """Return (period_key, period_label) for a given hour."""
    for key, (start, end, label) in PERIODS.items():
        if start <= hour < end:
            return key, label
    return "evening", "Evening (5 - 10 PM)"


def _collect_activity_timestamps(
    db: Session, user_id: int, since: datetime,
) -> list[datetime]:
    """Gather activity timestamps from study sessions, AI usage, and audit logs."""
    timestamps: list[datetime] = []

    # Study sessions (strongest signal — actual study time)
    sessions = (
        db.query(StudySession.created_at, StudySession.duration_seconds)
        .filter(
            StudySession.student_id == user_id,
            StudySession.created_at >= since,
        )
        .all()
    )
    for created_at, duration in sessions:
        if created_at:
            # Weight longer sessions by adding multiple timestamps
            weight = max(1, (duration or 0) // 600)  # 1 per 10 min
            timestamps.extend([created_at] * weight)

    # AI usage (study guide generation, quizzes, etc.)
    ai_rows = (
        db.query(AIUsageHistory.created_at)
        .filter(
            AIUsageHistory.user_id == user_id,
            AIUsageHistory.created_at >= since,
        )
        .all()
    )
    for (created_at,) in ai_rows:
        if created_at:
            timestamps.append(created_at)

    # Audit log activity (material views, reads, etc.)
    audit_rows = (
        db.query(AuditLog.created_at)
        .filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= since,
            AuditLog.action.in_(["read", "material_view", "material_download"]),
        )
        .all()
    )
    for (created_at,) in audit_rows:
        if created_at:
            timestamps.append(created_at)

    return timestamps


def _build_time_slots(timestamps: list[datetime]) -> list[StudyTimeSlot]:
    """Analyze timestamps to find top 3 study time slots."""
    if not timestamps:
        return []

    # Build a grid: (is_weekday, period) -> count
    slot_counts: dict[tuple[bool, str], int] = defaultdict(int)
    for ts in timestamps:
        is_weekday = ts.weekday() < 5
        period_key, _ = _get_period(ts.hour)
        slot_counts[(is_weekday, period_key)] += 1

    if not slot_counts:
        return []

    max_count = max(slot_counts.values())
    if max_count == 0:
        return []

    # Convert to scored slots
    scored: list[tuple[float, bool, str]] = []
    for (is_weekday, period_key), count in slot_counts.items():
        score = round((count / max_count) * 100, 1)
        scored.append((score, is_weekday, period_key))

    scored.sort(key=lambda x: x[0], reverse=True)

    slots: list[StudyTimeSlot] = []
    for score, is_weekday, period_key in scored[:3]:
        _, _, period_label = PERIODS[period_key]
        day_label = "Weekdays" if is_weekday else "Weekends"
        label = f"You study best on {day_label.lower()} — {period_label.lower()}"
        slots.append(StudyTimeSlot(
            day_of_week=day_label,
            time_of_day=period_label,
            period=period_key,
            score=score,
            label=label,
        ))

    return slots


def _build_weekly_chart(
    db: Session, user_id: int, now: datetime,
) -> list[DailyStudyMinutes]:
    """Build last-7-days bar chart data from study sessions."""
    chart: list[DailyStudyMinutes] = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        rows = (
            db.query(StudySession.duration_seconds)
            .filter(
                StudySession.student_id == user_id,
                StudySession.created_at >= day_start,
                StudySession.created_at < day_end,
            )
            .all()
        )
        minutes = sum((row[0] or 0) for row in rows) // 60

        chart.append(DailyStudyMinutes(
            day=DAY_ABBREVS[day.weekday()],
            date=day.strftime("%Y-%m-%d"),
            minutes=minutes,
        ))

    return chart


def _compute_weekly_totals(
    db: Session, user_id: int, now: datetime,
) -> tuple[int, int]:
    """Return (current_week_minutes, previous_week_minutes)."""
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    prev_week_start = week_start - timedelta(days=7)

    def _sum_minutes(start: datetime, end: datetime) -> int:
        rows = (
            db.query(StudySession.duration_seconds)
            .filter(
                StudySession.student_id == user_id,
                StudySession.created_at >= start,
                StudySession.created_at < end,
            )
            .all()
        )
        return sum((r[0] or 0) for r in rows) // 60

    current = _sum_minutes(week_start, now)
    previous = _sum_minutes(prev_week_start, week_start)
    return current, previous


def _suggest_next_session(slots: list[StudyTimeSlot], now: datetime) -> str | None:
    """Suggest when the next study session should be based on top slot."""
    if not slots:
        return None

    top = slots[0]
    is_weekday_now = now.weekday() < 5
    top_is_weekday = top.day_of_week == "Weekdays"

    # Determine the target hour range
    period_start = PERIODS.get(top.period, (17, 22, ""))[0]

    if top_is_weekday == is_weekday_now:
        # Same day type
        if now.hour < period_start:
            return f"Today at {period_start % 12 or 12} {'AM' if period_start < 12 else 'PM'}"
        else:
            # Suggest tomorrow (or next weekday/weekend)
            if top_is_weekday and now.weekday() == 4:
                return f"Monday at {period_start % 12 or 12} {'AM' if period_start < 12 else 'PM'}"
            return f"Tomorrow at {period_start % 12 or 12} {'AM' if period_start < 12 else 'PM'}"
    else:
        if top_is_weekday:
            # Current is weekend, suggest Monday
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 1
            target = now + timedelta(days=days_until_monday)
            return f"{DAY_NAMES[target.weekday()]} at {period_start % 12 or 12} {'AM' if period_start < 12 else 'PM'}"
        else:
            # Current is weekday, suggest Saturday
            days_until_sat = (5 - now.weekday()) % 7
            if days_until_sat == 0:
                days_until_sat = 7
            target = now + timedelta(days=days_until_sat)
            return f"{DAY_NAMES[target.weekday()]} at {period_start % 12 or 12} {'AM' if period_start < 12 else 'PM'}"


def get_study_suggestions(
    db: Session, user_id: int,
) -> StudySuggestionsResponse:
    """Compute study time suggestions for a student."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=28)  # Analyze last 4 weeks

    timestamps = _collect_activity_timestamps(db, user_id, since)
    top_slots = _build_time_slots(timestamps)
    weekly_chart = _build_weekly_chart(db, user_id, now)
    current_week, previous_week = _compute_weekly_totals(db, user_id, now)

    if previous_week == 0 and current_week == 0:
        trend = "steady"
    elif current_week > previous_week:
        trend = "up"
    elif current_week < previous_week:
        trend = "down"
    else:
        trend = "steady"

    next_session = _suggest_next_session(top_slots, now)

    return StudySuggestionsResponse(
        top_slots=top_slots,
        weekly_chart=weekly_chart,
        current_week_minutes=current_week,
        previous_week_minutes=previous_week,
        weekly_trend=trend,
        next_suggested_session=next_session,
    )
