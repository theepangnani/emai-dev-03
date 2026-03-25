"""Service that builds and sends the Weekly Family Report Card email (#2228).

Generates a per-family weekly summary with per-child breakdowns including
assignments, tasks, study guides, quizzes, streaks, upcoming deadlines,
and an engagement score.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.quiz_result import QuizResult
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.task import Task
from app.models.user import User
from app.services.email_service import send_email, wrap_branded_email
from app.services.streak_service import StreakService
from app.schemas.weekly_report import (
    ChildReport,
    ReportChildAssignment,
    ReportChildQuiz,
    ReportChildStreak,
    ReportChildTask,
    ReportUpcomingDeadline,
    WeeklyFamilyReportResponse,
)

logger = logging.getLogger(__name__)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _compute_engagement_score(
    tasks_completed: int,
    tasks_total: int,
    assignments_submitted: int,
    assignments_due: int,
    study_guides: int,
    quiz_count: int,
    streak_days: int,
) -> int:
    """Compute a simple engagement score (0-100).

    Weights:
    - Task completion: 25%
    - Assignment submission: 25%
    - Study guide creation: 20% (capped at 5 guides = full marks)
    - Quiz participation: 15% (capped at 3 quizzes = full marks)
    - Streak: 15% (capped at 7 days = full marks)
    """
    task_pct = (tasks_completed / tasks_total * 100) if tasks_total > 0 else 100
    assign_pct = (assignments_submitted / assignments_due * 100) if assignments_due > 0 else 100
    guide_pct = min(study_guides / 5, 1.0) * 100
    quiz_pct = min(quiz_count / 3, 1.0) * 100
    streak_pct = min(streak_days / 7, 1.0) * 100

    score = (
        task_pct * 0.25
        + assign_pct * 0.25
        + guide_pct * 0.20
        + quiz_pct * 0.15
        + streak_pct * 0.15
    )
    return max(0, min(100, round(score)))


def generate_share_token(parent_user_id: int, week_start: str) -> str:
    """Generate a deterministic share token for a report.

    Uses HMAC so that the same parent + week always produces the same token.
    The token is not secret — it's a short identifier for the shareable URL.
    """
    from app.core.config import settings

    key = (settings.secret_key or "classbridge").encode()
    msg = f"weekly-report:{parent_user_id}:{week_start}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:32]


def generate_weekly_report(db: Session, parent_user_id: int) -> WeeklyFamilyReportResponse:
    """Build the weekly family report card data for a parent."""

    parent = db.query(User).filter(User.id == parent_user_id).first()
    first_name = (parent.full_name or "").split()[0] if parent else "there"

    now = datetime.now(timezone.utc)
    week_end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_start = week_end - timedelta(days=7)
    upcoming_end = week_end + timedelta(days=7)

    # Load children
    child_rows = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(parent_students.c.parent_id == parent_user_id)
        .all()
    )

    if not child_rows:
        return WeeklyFamilyReportResponse(
            week_start=week_start.date().isoformat(),
            week_end=week_end.date().isoformat(),
            greeting=f"Hi {first_name}",
            overall_summary="No children linked to your account yet.",
        )

    student_ids = [s.id for s, _ in child_rows]
    child_user_ids = [u.id for _, u in child_rows]

    # ── Batch queries ──

    # 1. Tasks for children
    tasks = (
        db.query(Task)
        .filter(
            Task.assigned_to_user_id.in_(child_user_ids),
            Task.archived_at.is_(None),
        )
        .all()
    )
    tasks_by_user: dict[int, list[Task]] = {}
    for t in tasks:
        tasks_by_user.setdefault(t.assigned_to_user_id, []).append(t)

    # 2. Courses per student
    course_rows = (
        db.query(student_courses.c.student_id, Course)
        .join(Course, Course.id == student_courses.c.course_id)
        .filter(student_courses.c.student_id.in_(student_ids))
        .all()
    )
    courses_by_student: dict[int, list[Course]] = {}
    course_name_map: dict[int, str] = {}
    for sid, course in course_rows:
        courses_by_student.setdefault(sid, []).append(course)
        course_name_map[course.id] = course.name

    # 3. Assignments due in the past week
    all_course_ids = list(course_name_map.keys())
    week_assignments: list[Assignment] = []
    if all_course_ids:
        week_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.course_id.in_(all_course_ids),
                Assignment.due_date.isnot(None),
                Assignment.due_date >= week_start,
                Assignment.due_date < week_end,
            )
            .all()
        )

    assignment_ids = [a.id for a in week_assignments]
    sa_status: dict[tuple[int, int], StudentAssignment] = {}
    if assignment_ids and student_ids:
        sa_rows = (
            db.query(StudentAssignment)
            .filter(
                StudentAssignment.student_id.in_(student_ids),
                StudentAssignment.assignment_id.in_(assignment_ids),
            )
            .all()
        )
        for sa in sa_rows:
            sa_status[(sa.student_id, sa.assignment_id)] = sa

    student_ids_by_course: dict[int, list[int]] = {}
    for sid, course in course_rows:
        student_ids_by_course.setdefault(course.id, []).append(sid)

    # 4. Study guide counts per child (last 7 days)
    study_counts: dict[int, int] = {}
    if child_user_ids:
        sc_rows = (
            db.query(StudyGuide.user_id, sa_func.count())
            .filter(
                StudyGuide.user_id.in_(child_user_ids),
                StudyGuide.created_at >= week_start,
                StudyGuide.archived_at.is_(None),
            )
            .group_by(StudyGuide.user_id)
            .all()
        )
        study_counts = {uid: cnt for uid, cnt in sc_rows}

    # 5. Quiz results per child (last 7 days)
    quiz_data: dict[int, list[float]] = {}
    if child_user_ids:
        qr_rows = (
            db.query(QuizResult.user_id, QuizResult.percentage)
            .filter(
                QuizResult.user_id.in_(child_user_ids),
                QuizResult.completed_at >= week_start,
            )
            .all()
        )
        for uid, pct in qr_rows:
            quiz_data.setdefault(uid, []).append(pct)

    # 6. Streak info per child
    streak_data: dict[int, dict] = {}
    for _, user in child_rows:
        try:
            student_record = db.query(Student).filter(Student.user_id == user.id).first()
            if student_record:
                streak_data[user.id] = StreakService.get_streak_info(db, student_record.id)
        except Exception:
            streak_data[user.id] = {"current_streak": 0, "longest_streak": 0, "tier_label": "Getting Started"}

    # 7. Upcoming deadlines (next 7 days)
    upcoming_assignments: list[Assignment] = []
    if all_course_ids:
        upcoming_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.course_id.in_(all_course_ids),
                Assignment.due_date.isnot(None),
                Assignment.due_date >= week_end,
                Assignment.due_date < upcoming_end,
            )
            .order_by(Assignment.due_date.asc())
            .all()
        )

    upcoming_tasks_by_user: dict[int, list[Task]] = {}
    for uid, user_tasks in tasks_by_user.items():
        upcoming = [
            t for t in user_tasks
            if t.due_date and _aware(t.due_date) >= week_end
            and _aware(t.due_date) < upcoming_end
            and not t.is_completed
        ]
        if upcoming:
            upcoming_tasks_by_user[uid] = upcoming

    # ── Build per-child reports ──

    child_reports: list[ChildReport] = []

    for student, user in child_rows:
        user_tasks = tasks_by_user.get(user.id, [])

        # Tasks completed this week
        week_tasks = [
            t for t in user_tasks
            if t.due_date and _aware(t.due_date) >= week_start and _aware(t.due_date) < week_end
        ]
        completed_tasks = [t for t in week_tasks if t.is_completed]
        task_info = ReportChildTask(
            completed=len(completed_tasks),
            total=len(week_tasks),
        )

        # Assignments
        child_course_ids = {c.id for c in courses_by_student.get(student.id, [])}
        child_week_assignments = [a for a in week_assignments if a.course_id in child_course_ids]
        submitted_count = 0
        for a in child_week_assignments:
            sa = sa_status.get((student.id, a.id))
            if sa and sa.status in ("submitted", "graded"):
                submitted_count += 1
        assignment_info = ReportChildAssignment(
            submitted=submitted_count,
            due=len(child_week_assignments),
        )

        # Study guides
        sg_count = study_counts.get(user.id, 0)

        # Quiz scores
        user_quiz_pcts = quiz_data.get(user.id, [])
        quiz_info = ReportChildQuiz(
            quiz_count=len(user_quiz_pcts),
            average_percentage=round(sum(user_quiz_pcts) / len(user_quiz_pcts), 1) if user_quiz_pcts else None,
        )

        # Streak
        user_streak = streak_data.get(user.id, {})
        streak_info = ReportChildStreak(
            current_streak=user_streak.get("current_streak", 0),
            longest_streak=user_streak.get("longest_streak", 0),
            tier_label=user_streak.get("tier_label", "Getting Started"),
        )

        # Upcoming deadlines
        deadlines: list[ReportUpcomingDeadline] = []
        child_upcoming_assignments = [a for a in upcoming_assignments if a.course_id in child_course_ids]
        for a in child_upcoming_assignments[:5]:
            deadlines.append(ReportUpcomingDeadline(
                id=a.id,
                title=a.title,
                due_date=_aware(a.due_date).date().isoformat() if a.due_date else None,
                item_type="assignment",
                course_name=course_name_map.get(a.course_id),
            ))
        for t in upcoming_tasks_by_user.get(user.id, [])[:5]:
            deadlines.append(ReportUpcomingDeadline(
                id=t.id,
                title=t.title,
                due_date=_aware(t.due_date).date().isoformat() if t.due_date else None,
                item_type="task",
                course_name=course_name_map.get(t.course_id) if t.course_id else None,
            ))

        # Engagement score
        engagement = _compute_engagement_score(
            tasks_completed=task_info.completed,
            tasks_total=task_info.total,
            assignments_submitted=assignment_info.submitted,
            assignments_due=assignment_info.due,
            study_guides=sg_count,
            quiz_count=quiz_info.quiz_count,
            streak_days=streak_info.current_streak,
        )

        # Highlight sentence
        parts = []
        if task_info.total > 0:
            parts.append(f"{task_info.completed}/{task_info.total} tasks done")
        if assignment_info.due > 0:
            parts.append(f"{assignment_info.submitted}/{assignment_info.due} assignments submitted")
        if sg_count > 0:
            parts.append(f"{sg_count} study guide{'s' if sg_count != 1 else ''} created")
        if quiz_info.quiz_count > 0:
            parts.append(f"avg quiz score {quiz_info.average_percentage}%")
        if streak_info.current_streak > 0:
            parts.append(f"{streak_info.current_streak}-day streak")
        highlight = ", ".join(parts) if parts else "No activity this week"

        child_reports.append(ChildReport(
            student_id=student.id,
            full_name=user.full_name,
            grade_level=student.grade_level,
            tasks=task_info,
            assignments=assignment_info,
            study_guides_created=sg_count,
            quizzes=quiz_info,
            streak=streak_info,
            upcoming_deadlines=deadlines,
            engagement_score=engagement,
            highlight=highlight,
        ))

    # Family engagement score (average of children)
    family_score = 0
    if child_reports:
        family_score = round(sum(c.engagement_score for c in child_reports) / len(child_reports))

    # Overall summary
    total_completed = sum(c.tasks.completed for c in child_reports)
    total_tasks = sum(c.tasks.total for c in child_reports)
    total_guides = sum(c.study_guides_created for c in child_reports)
    total_quizzes = sum(c.quizzes.quiz_count for c in child_reports)
    summary_parts = []
    if total_tasks > 0:
        summary_parts.append(f"{total_completed}/{total_tasks} tasks completed")
    if total_guides > 0:
        summary_parts.append(f"{total_guides} study guide{'s' if total_guides != 1 else ''} created")
    if total_quizzes > 0:
        summary_parts.append(f"{total_quizzes} quiz{'zes' if total_quizzes != 1 else ''} taken")
    overall = ". ".join(summary_parts) + "." if summary_parts else "A quiet week!"

    week_start_str = week_start.date().isoformat()
    share_token = generate_share_token(parent_user_id, week_start_str)
    share_url = f"https://www.classbridge.ca/report/{share_token}"

    return WeeklyFamilyReportResponse(
        week_start=week_start_str,
        week_end=week_end.date().isoformat(),
        greeting=f"Hi {first_name}, here's your family's weekly report card",
        children=child_reports,
        family_engagement_score=family_score,
        overall_summary=overall,
        share_url=share_url,
    )


def _engagement_color(score: int) -> str:
    """Return a hex color for the engagement score badge."""
    if score >= 80:
        return "#059669"  # green
    if score >= 50:
        return "#d97706"  # amber
    return "#dc2626"  # red


def _engagement_label(score: int) -> str:
    """Return a label for the engagement score."""
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Needs Attention"


def _streak_emoji_text(tier_label: str) -> str:
    """Return a text streak indicator for the tier."""
    tier_map = {
        "Legendary": "LEGENDARY",
        "On Fire": "ON FIRE",
        "Blazing": "BLAZING",
        "Warming Up": "WARMING UP",
        "Getting Started": "",
    }
    return tier_map.get(tier_label, "")


def render_report_email_html(
    report: WeeklyFamilyReportResponse,
    unsubscribe_url: str | None = None,
) -> str:
    """Render the weekly family report card as branded HTML email."""

    children_html = ""
    for child in report.children:
        grade_label = f" (Grade {child.grade_level})" if child.grade_level else ""

        # Engagement badge
        eng_color = _engagement_color(child.engagement_score)
        eng_label = _engagement_label(child.engagement_score)
        engagement_badge = (
            f'<span style="display:inline-block;background:{eng_color};color:#ffffff;'
            f'font-size:11px;padding:3px 10px;border-radius:10px;margin-left:8px;'
            f'font-weight:600;">{child.engagement_score}% - {eng_label}</span>'
        )

        # Stats grid
        quiz_avg = f" (avg {child.quizzes.average_percentage}%)" if child.quizzes.average_percentage else ""
        streak_tier = _streak_emoji_text(child.streak.tier_label)
        streak_tier_html = f' <span style="color:#4f46e5;font-weight:600;font-size:11px;">{streak_tier}</span>' if streak_tier else ""

        stats_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
          <tr>
            <td style="padding:8px 12px;background:#f0f0ff;border-radius:8px;width:50%;vertical-align:top;">
              <div style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">Tasks</div>
              <div style="color:#1f2937;font-size:18px;font-weight:700;">{child.tasks.completed}/{child.tasks.total}</div>
            </td>
            <td style="width:8px;"></td>
            <td style="padding:8px 12px;background:#f0f0ff;border-radius:8px;width:50%;vertical-align:top;">
              <div style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">Assignments</div>
              <div style="color:#1f2937;font-size:18px;font-weight:700;">{child.assignments.submitted}/{child.assignments.due}</div>
            </td>
          </tr>
          <tr><td colspan="3" style="height:8px;"></td></tr>
          <tr>
            <td style="padding:8px 12px;background:#f0f0ff;border-radius:8px;width:50%;vertical-align:top;">
              <div style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">Study Guides</div>
              <div style="color:#1f2937;font-size:18px;font-weight:700;">{child.study_guides_created}</div>
            </td>
            <td style="width:8px;"></td>
            <td style="padding:8px 12px;background:#f0f0ff;border-radius:8px;width:50%;vertical-align:top;">
              <div style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">Quizzes</div>
              <div style="color:#1f2937;font-size:18px;font-weight:700;">{child.quizzes.quiz_count}{quiz_avg}</div>
            </td>
          </tr>
          <tr><td colspan="3" style="height:8px;"></td></tr>
          <tr>
            <td colspan="3" style="padding:8px 12px;background:#f0f0ff;border-radius:8px;vertical-align:top;">
              <div style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">Study Streak</div>
              <div style="color:#1f2937;font-size:18px;font-weight:700;">{child.streak.current_streak} days{streak_tier_html}</div>
              <div style="color:#9ca3af;font-size:12px;">Longest: {child.streak.longest_streak} days</div>
            </td>
          </tr>
        </table>
        """

        # Upcoming deadlines
        deadlines_html = ""
        if child.upcoming_deadlines:
            items = "".join(
                f'<li style="color:#4b5563;margin:4px 0;font-size:13px;">'
                f'{d.title}'
                f'{" (" + d.course_name + ")" if d.course_name else ""}'
                f' &mdash; {d.due_date or "N/A"}'
                f'</li>'
                for d in child.upcoming_deadlines[:5]
            )
            deadlines_html = (
                f'<div style="margin-top:12px;">'
                f'<strong style="color:#4338ca;font-size:13px;">Upcoming This Week:</strong>'
                f'<ul style="margin:4px 0 0 16px;padding:0;">{items}</ul>'
                f'</div>'
            )

        children_html += f"""
        <div style="margin-bottom:24px;padding:20px;background:#f9fafb;border-radius:12px;border-left:4px solid #4f46e5;">
          <h3 style="margin:0 0 4px 0;color:#1f2937;">{child.full_name}{grade_label}{engagement_badge}</h3>
          <p style="margin:0 0 8px 0;color:#6b7280;font-size:13px;">{child.highlight}</p>
          {stats_html}
          {deadlines_html}
        </div>
        """

    # Family engagement score banner
    family_color = _engagement_color(report.family_engagement_score)
    family_label = _engagement_label(report.family_engagement_score)

    body_html = f"""
    <h2 style="color:#1f2937;margin:0 0 4px 0;">Weekly Family Report Card</h2>
    <p style="color:#6b7280;margin:0 0 24px 0;font-size:14px;">{report.week_start} &mdash; {report.week_end}</p>
    <p style="color:#4b5563;margin:0 0 24px 0;">{report.greeting}</p>

    <div style="margin-bottom:24px;padding:16px 20px;background:{family_color};border-radius:12px;text-align:center;">
      <div style="color:#ffffff;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Family Engagement Score</div>
      <div style="color:#ffffff;font-size:36px;font-weight:800;line-height:1.2;">{report.family_engagement_score}%</div>
      <div style="color:#ffffffcc;font-size:14px;">{family_label}</div>
    </div>

    {children_html}

    <div style="margin-top:16px;padding:12px 16px;background:#eef2ff;border-radius:8px;color:#4338ca;font-size:14px;">
      {report.overall_summary}
    </div>

    <p style="margin-top:24px;text-align:center;">
      <a href="https://www.classbridge.ca/dashboard" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">View Dashboard</a>
    </p>
    """

    # Share link
    if report.share_url:
        body_html += f"""
    <p style="margin-top:16px;text-align:center;">
      <a href="{report.share_url}" style="color:#4f46e5;font-size:13px;text-decoration:underline;">Share this report with family</a>
    </p>
    """

    if unsubscribe_url:
        body_html += f"""
    <p style="text-align:center;font-size:12px;color:#999;margin-top:24px;">
      <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe from these emails</a>
    </p>
    """

    return wrap_branded_email(body_html)


async def send_weekly_report_email(db: Session, parent_user_id: int) -> bool:
    """Generate and send the weekly family report card email to a parent."""
    parent = db.query(User).filter(User.id == parent_user_id).first()
    if not parent or not parent.email:
        return False

    # Respect notification preferences — default to opted-in
    if not getattr(parent, "email_notifications", True):
        logger.debug("Skipping weekly report for user %d (email_notifications=False)", parent_user_id)
        return False

    from app.core.security import get_unsubscribe_url

    report = generate_weekly_report(db, parent_user_id)
    unsub_url = get_unsubscribe_url(parent_user_id)
    html = render_report_email_html(report, unsubscribe_url=unsub_url)
    subject = f"Weekly Family Report Card - {report.week_start} to {report.week_end}"

    return await send_email(parent.email, subject, html)
