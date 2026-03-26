"""Service that builds the Weekly Progress Pulse digest for parents."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func as sa_func
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.quiz_result import QuizResult
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.study_session import StudySession
from app.models.task import Task
from app.models.user import User
from app.models.xp import XpLedger, XpSummary
from app.schemas.weekly_digest import (
    ChildDigest,
    DigestChildAssignment,
    DigestChildTask,
    DigestOverdueItem,
    DigestQuizScore,
    WeeklyDigestResponse,
)
from app.services.email_service import send_email, wrap_branded_email
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


def _aware(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _build_conversation_starter(
    child_name: str, guide: "StudyGuide | None"
) -> str | None:
    """Build a conversation starter from the child's most recent study guide.

    Returns a sentence like:
        "Emma studied Cell Division this week — ask her:
         What did you find most interesting about Cell Division?"
    """
    if guide is None:
        return None

    first_name = (child_name or "").split()[0]
    topic = guide.title
    return (
        f"{first_name} studied {topic} this week "
        f"— ask them: What did you find most interesting about {topic}?"
    )


def _generate_encouragement(child_name: str, xp: int, streak: int, quizzes: int, study_mins: int) -> str | None:
    """Generate a one-sentence AI encouragement for a child's weekly activity.

    Returns None if no meaningful activity or if the AI call fails.
    """
    first_name = (child_name or "").split()[0]
    if xp == 0 and streak == 0 and quizzes == 0 and study_mins == 0:
        return None

    parts = []
    if xp > 0:
        parts.append(f"earned {xp} XP")
    if streak > 0:
        parts.append(f"has a {streak}-day streak")
    if quizzes > 0:
        parts.append(f"completed {quizzes} quizzes")
    if study_mins > 0:
        parts.append(f"studied for {study_mins} minutes")
    activity = ", ".join(parts)

    try:
        from app.core.config import settings
        import openai

        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write one short, warm encouragement sentence for a parent's "
                        "weekly email about their child's learning progress. "
                        "Keep it under 25 words. Be positive and specific."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{first_name} {activity} this week.",
                },
            ],
            max_tokens=60,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.warning("AI encouragement generation failed for %s", first_name)
        return None


def generate_weekly_digest(db: Session, parent_user_id: int) -> WeeklyDigestResponse:
    """Build the weekly digest data for a parent across all linked children."""

    parent = db.query(User).filter(User.id == parent_user_id).first()
    first_name = (parent.full_name or "").split()[0] if parent else "there"

    now = datetime.now(timezone.utc)
    week_end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_start = week_end - timedelta(days=7)

    # Load children
    child_rows = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(parent_students.c.parent_id == parent_user_id)
        .all()
    )

    if not child_rows:
        return WeeklyDigestResponse(
            week_start=week_start.date().isoformat(),
            week_end=week_end.date().isoformat(),
            greeting=f"Hi {first_name}",
            overall_summary="No children linked to your account yet.",
        )

    student_ids = [s.id for s, _ in child_rows]
    child_user_ids = [u.id for _, u in child_rows]

    # ── Batch queries ──

    # 1. Tasks for children in the past 7 days
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

    # 5. Most recent study guide per child (for conversation starters)
    recent_guides: dict[int, StudyGuide] = {}
    if child_user_ids:
        for uid in child_user_ids:
            guide = (
                db.query(StudyGuide)
                .filter(
                    StudyGuide.user_id == uid,
                    StudyGuide.created_at >= week_start,
                    StudyGuide.archived_at.is_(None),
                    StudyGuide.guide_type == "study_guide",
                )
                .order_by(StudyGuide.created_at.desc())
                .first()
            )
            if guide:
                recent_guides[uid] = guide

    # 6. Quiz results per child (last 7 days)
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

    # 7. XP earned per child (last 7 days) (#2228)
    xp_earned_data: dict[int, int] = {}
    if child_user_ids:
        xp_rows = (
            db.query(XpLedger.student_id, sa_func.sum(XpLedger.xp_awarded))
            .filter(
                XpLedger.student_id.in_(child_user_ids),
                XpLedger.created_at >= week_start,
            )
            .group_by(XpLedger.student_id)
            .all()
        )
        xp_earned_data = {uid: int(total) for uid, total in xp_rows}

    # 8. Current streak per child (#2228)
    streak_data: dict[int, int] = {}
    if child_user_ids:
        streak_rows = (
            db.query(XpSummary.student_id, XpSummary.current_streak)
            .filter(XpSummary.student_id.in_(child_user_ids))
            .all()
        )
        streak_data = {uid: streak for uid, streak in streak_rows}

    # 9. Study time per child in minutes (last 7 days) (#2228)
    study_time_data: dict[int, int] = {}
    if child_user_ids:
        st_rows = (
            db.query(
                StudySession.student_id,
                sa_func.sum(StudySession.duration_seconds),
            )
            .filter(
                StudySession.student_id.in_(child_user_ids),
                StudySession.created_at >= week_start,
            )
            .group_by(StudySession.student_id)
            .all()
        )
        study_time_data = {uid: int(total) // 60 for uid, total in st_rows}

    # ── Build per-child digests ──

    child_digests: list[ChildDigest] = []

    for student, user in child_rows:
        user_tasks = tasks_by_user.get(user.id, [])

        # Tasks: completed this week vs total with due dates this week
        week_tasks = [
            t for t in user_tasks
            if t.due_date and _aware(t.due_date) >= week_start and _aware(t.due_date) < week_end
        ]
        completed_tasks = [t for t in week_tasks if t.is_completed]
        task_info = DigestChildTask(
            completed=len(completed_tasks),
            total=len(week_tasks),
        )

        # Assignments for this child's courses
        child_course_ids = {c.id for c in courses_by_student.get(student.id, [])}
        child_week_assignments = [a for a in week_assignments if a.course_id in child_course_ids]
        submitted_count = 0
        for a in child_week_assignments:
            sa = sa_status.get((student.id, a.id))
            if sa and sa.status in ("submitted", "graded"):
                submitted_count += 1
        assignment_info = DigestChildAssignment(
            submitted=submitted_count,
            due=len(child_week_assignments),
        )

        # Study guides
        sg_count = study_counts.get(user.id, 0)

        # Quiz scores
        user_quiz_pcts = quiz_data.get(user.id, [])
        quiz_info = DigestQuizScore(
            quiz_count=len(user_quiz_pcts),
            average_percentage=round(sum(user_quiz_pcts) / len(user_quiz_pcts), 1) if user_quiz_pcts else None,
        )

        # Overdue items (tasks + assignments still pending past due date)
        overdue_items: list[DigestOverdueItem] = []
        for t in user_tasks:
            if t.due_date and _aware(t.due_date) < week_end and not t.is_completed:
                overdue_items.append(DigestOverdueItem(
                    id=t.id,
                    title=t.title,
                    due_date=_aware(t.due_date).date().isoformat() if t.due_date else None,
                    item_type="task",
                ))
        for a in child_week_assignments:
            sa = sa_status.get((student.id, a.id))
            if (not sa or sa.status == "pending") and a.due_date and _aware(a.due_date) < week_end:
                overdue_items.append(DigestOverdueItem(
                    id=a.id,
                    title=a.title,
                    due_date=_aware(a.due_date).date().isoformat() if a.due_date else None,
                    item_type="assignment",
                ))

        # Gamification data (#2228)
        child_xp = xp_earned_data.get(user.id, 0)
        child_streak = streak_data.get(user.id, 0)
        child_study_mins = study_time_data.get(user.id, 0)

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
        if child_xp > 0:
            parts.append(f"{child_xp} XP earned")
        if child_streak > 0:
            parts.append(f"{child_streak}-day streak")
        if child_study_mins > 0:
            parts.append(f"{child_study_mins} min studied")
        highlight = ", ".join(parts) if parts else "No activity this week"

        # Conversation starter based on most recent study guide
        conversation_starter = _build_conversation_starter(
            user.full_name, recent_guides.get(user.id)
        )

        # AI encouragement sentence (#2228)
        encouragement = _generate_encouragement(
            user.full_name, child_xp, child_streak,
            quiz_info.quiz_count, child_study_mins,
        )

        child_digests.append(ChildDigest(
            student_id=student.id,
            full_name=user.full_name,
            grade_level=student.grade_level,
            tasks=task_info,
            assignments=assignment_info,
            study_guides_created=sg_count,
            quiz_scores=quiz_info,
            overdue_items=overdue_items,
            highlight=highlight,
            conversation_starter=conversation_starter,
            xp_earned=child_xp,
            current_streak=child_streak,
            study_minutes=child_study_mins,
            encouragement=encouragement,
        ))

    # Overall summary
    total_completed = sum(c.tasks.completed for c in child_digests)
    total_tasks = sum(c.tasks.total for c in child_digests)
    total_overdue = sum(len(c.overdue_items) for c in child_digests)
    summary_parts = []
    if total_tasks > 0:
        summary_parts.append(f"{total_completed}/{total_tasks} tasks completed")
    if total_overdue > 0:
        summary_parts.append(f"{total_overdue} item{'s' if total_overdue != 1 else ''} still overdue")
    overall = ". ".join(summary_parts) + "." if summary_parts else "A quiet week!"

    return WeeklyDigestResponse(
        week_start=week_start.date().isoformat(),
        week_end=week_end.date().isoformat(),
        greeting=f"Hi {first_name}, here's your Weekly Progress Pulse",
        children=child_digests,
        overall_summary=overall,
    )


def render_digest_email_html(
    digest: WeeklyDigestResponse, unsubscribe_url: str | None = None
) -> str:
    """Render the weekly digest as branded HTML email."""

    children_html = ""
    for child in digest.children:
        overdue_html = ""
        if child.overdue_items:
            items = "".join(
                f'<li style="color:#dc2626;margin:4px 0;">{o.title} (due {o.due_date or "N/A"})</li>'
                for o in child.overdue_items
            )
            overdue_html = f'<div style="margin-top:12px;"><strong style="color:#dc2626;">Overdue:</strong><ul style="margin:4px 0 0 16px;padding:0;">{items}</ul></div>'

        quiz_html = ""
        if child.quiz_scores.quiz_count > 0:
            quiz_html = f'<div style="margin-top:4px;">Quizzes taken: {child.quiz_scores.quiz_count} (avg {child.quiz_scores.average_percentage}%)</div>'

        # Gamification badges row (#2228)
        badges_html = ""
        badge_items = []
        if child.current_streak > 0:
            flame = "&#128293;"  # fire emoji
            badge_items.append(
                f'<td style="text-align:center;padding:8px 12px;">'
                f'<div style="font-size:24px;">{flame}</div>'
                f'<div style="font-size:12px;color:#4b5563;margin-top:2px;">{child.current_streak}-day streak</div>'
                f'</td>'
            )
        if child.xp_earned > 0:
            star = "&#11088;"  # star emoji
            badge_items.append(
                f'<td style="text-align:center;padding:8px 12px;">'
                f'<div style="font-size:24px;">{star}</div>'
                f'<div style="font-size:12px;color:#4b5563;margin-top:2px;">{child.xp_earned} XP</div>'
                f'</td>'
            )
        if child.study_minutes > 0:
            clock = "&#9201;"  # timer emoji
            badge_items.append(
                f'<td style="text-align:center;padding:8px 12px;">'
                f'<div style="font-size:24px;">{clock}</div>'
                f'<div style="font-size:12px;color:#4b5563;margin-top:2px;">{child.study_minutes} min</div>'
                f'</td>'
            )
        if badge_items:
            badges_html = (
                '<table cellpadding="0" cellspacing="0" style="margin:12px auto 0 auto;">'
                f'<tr>{"".join(badge_items)}</tr></table>'
            )

        # AI encouragement (#2228)
        encouragement_html = ""
        if child.encouragement:
            encouragement_html = (
                f'<div style="margin-top:12px;padding:10px 14px;background:#ecfdf5;'
                f'border-radius:8px;color:#065f46;font-size:13px;font-style:italic;">'
                f'{child.encouragement}</div>'
            )

        children_html += f"""
        <div style="margin-bottom:24px;padding:16px;background:#f9fafb;border-radius:12px;border-left:4px solid #4f46e5;">
          <h3 style="margin:0 0 8px 0;color:#1f2937;">{child.full_name}</h3>
          {badges_html}
          <div style="color:#4b5563;font-size:14px;line-height:1.6;margin-top:12px;">
            <div>Tasks: {child.tasks.completed}/{child.tasks.total} completed</div>
            <div>Assignments: {child.assignments.submitted}/{child.assignments.due} submitted</div>
            <div>Study guides created: {child.study_guides_created}</div>
            {quiz_html}
          </div>
          {overdue_html}
          {encouragement_html}
          {f'<div style="margin-top:12px;padding:10px 14px;background:#fef3c7;border-radius:8px;color:#92400e;font-size:13px;">{child.conversation_starter}</div>' if child.conversation_starter else ""}
        </div>
        """

    body_html = f"""
    <h2 style="color:#1f2937;margin:0 0 4px 0;">Weekly Progress Pulse</h2>
    <p style="color:#6b7280;margin:0 0 24px 0;font-size:14px;">{digest.week_start} &mdash; {digest.week_end}</p>
    <p style="color:#4b5563;margin:0 0 24px 0;">{digest.greeting}</p>
    {children_html}
    <div style="margin-top:16px;padding:12px 16px;background:#eef2ff;border-radius:8px;color:#4338ca;font-size:14px;">
      {digest.overall_summary}
    </div>
    <p style="margin-top:24px;text-align:center;">
      <a href="https://www.classbridge.ca/dashboard" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">View Dashboard</a>
    </p>
    <p style="margin-top:12px;text-align:center;">
      <a href="mailto:?subject=Check%20out%20how%20the%20kids%20are%20doing%20on%20ClassBridge&body=I%20just%20got%20this%20weekly%20report%20from%20ClassBridge%20%E2%80%94%20it%20tracks%20the%20kids%27%20learning%20progress%21%0A%0Ahttps%3A%2F%2Fwww.classbridge.ca" style="display:inline-block;padding:10px 20px;background:#f3f4f6;color:#4f46e5;text-decoration:none;border-radius:8px;font-weight:600;border:1px solid #e5e7eb;">Forward to Family</a>
    </p>
    """

    if unsubscribe_url:
        body_html += f"""
    <p style="text-align:center;font-size:12px;color:#999;margin-top:24px;">
      <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe from these emails</a>
    </p>
    """

    return wrap_branded_email(body_html)


def _translate_safe(text: str, target_language: str) -> str:
    """Translate text, falling back to original on any error."""
    try:
        return TranslationService.translate(text, target_language)
    except Exception:
        logger.warning("Translation failed, using English fallback")
        return text


def _translate_digest(digest: WeeklyDigestResponse, target_language: str) -> WeeklyDigestResponse:
    """Translate key digest text fields in-place and return the digest."""
    if not target_language or target_language == "en":
        return digest

    digest.greeting = _translate_safe(digest.greeting, target_language)
    digest.overall_summary = _translate_safe(digest.overall_summary, target_language)

    for child in digest.children:
        child.highlight = _translate_safe(child.highlight, target_language)
        if child.conversation_starter:
            child.conversation_starter = _translate_safe(
                child.conversation_starter, target_language
            )
        if child.encouragement:
            child.encouragement = _translate_safe(
                child.encouragement, target_language
            )

    return digest


async def send_weekly_digest_email(db: Session, parent_user_id: int) -> bool:
    """Generate and send the weekly digest email to a parent."""
    parent = db.query(User).filter(User.id == parent_user_id).first()
    if not parent or not parent.email:
        return False

    from app.core.security import get_unsubscribe_url

    digest = generate_weekly_digest(db, parent_user_id)

    lang = getattr(parent, "preferred_language", "en") or "en"
    if lang != "en":
        digest = _translate_digest(digest, lang)

    unsub_url = get_unsubscribe_url(parent_user_id)
    html = render_digest_email_html(digest, unsubscribe_url=unsub_url)
    subject = f"Weekly Progress Pulse - {digest.week_start} to {digest.week_end}"

    if lang != "en":
        subject = _translate_safe(subject, lang)

    return await send_email(parent.email, subject, html)
