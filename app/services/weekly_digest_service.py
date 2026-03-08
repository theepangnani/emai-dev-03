"""Service that builds the Weekly Progress Pulse digest for parents."""

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
from app.schemas.weekly_digest import (
    ChildDigest,
    DigestChildAssignment,
    DigestChildTask,
    DigestOverdueItem,
    DigestQuizScore,
    WeeklyDigestResponse,
)
from app.services.email_service import send_email, wrap_branded_email


def _aware(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


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
        highlight = ", ".join(parts) if parts else "No activity this week"

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


def render_digest_email_html(digest: WeeklyDigestResponse) -> str:
    """Render the weekly digest as branded HTML email."""

    children_html = ""
    for child in digest.children:
        overdue_html = ""
        if child.overdue_items:
            items = "".join(
                f'<li style="color:#dc2626;margin:4px 0;">{o.title} (due {o.due_date or "N/A"})</li>'
                for o in child.overdue_items
            )
            overdue_html = (
                '<div style="margin-top:12px;">'
                '<strong style="color:#dc2626;">Overdue:</strong>'
                f'<ul style="margin:4px 0 0 16px;padding:0;">{items}</ul>'
                '</div>'
            )

        quiz_html = ""
        if child.quiz_scores.quiz_count > 0:
            quiz_html = (
                f'<div style="margin-top:4px;">Quizzes taken: {child.quiz_scores.quiz_count}'
                f' (avg {child.quiz_scores.average_percentage}%)</div>'
            )

        children_html += f"""
        <div style="margin-bottom:24px;padding:16px;background:#f9fafb;border-radius:12px;border-left:4px solid #4f46e5;">
          <h3 style="margin:0 0 8px 0;color:#1f2937;">{child.full_name}</h3>
          <div style="color:#4b5563;font-size:14px;line-height:1.6;">
            <div>Tasks: {child.tasks.completed}/{child.tasks.total} completed</div>
            <div>Assignments: {child.assignments.submitted}/{child.assignments.due} submitted</div>
            <div>Study guides created: {child.study_guides_created}</div>
            {quiz_html}
          </div>
          {overdue_html}
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
      <a href="https://www.classbridge.ca/dashboard"
         style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">
        View Dashboard
      </a>
    </p>
    """

    return wrap_branded_email(body_html)


async def send_weekly_digest_email(db: Session, parent_user_id: int) -> bool:
    """Generate and send the weekly digest email to a parent."""
    parent = db.query(User).filter(User.id == parent_user_id).first()
    if not parent or not parent.email:
        return False

    digest = generate_weekly_digest(db, parent_user_id)
    html = render_digest_email_html(digest)
    subject = f"Weekly Progress Pulse - {digest.week_start} to {digest.week_end}"

    return await send_email(parent.email, subject, html)
