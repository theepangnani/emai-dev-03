"""Service that builds the Daily Briefing for parents."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func as sa_func
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.task import Task
from app.models.user import User
from app.schemas.briefing import (
    BriefingAssignment,
    BriefingTask,
    ChildBriefing,
    DailyBriefingResponse,
)


def _aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (SQLite may return naive)."""
    if dt is None:
        return dt
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _time_greeting(name: str) -> str:
    hour = datetime.now(timezone.utc).hour
    if hour < 12:
        return f"Good morning, {name}"
    elif hour < 17:
        return f"Good afternoon, {name}"
    return f"Good evening, {name}"


def get_daily_briefing(db: Session, parent_user_id: int) -> DailyBriefingResponse:
    """Build the daily briefing for a parent across all linked children."""

    parent = db.query(User).filter(User.id == parent_user_id).first()
    first_name = (parent.full_name or "").split()[0] if parent else "there"

    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    week_ahead = today_start + timedelta(days=7)
    week_ago = today_start - timedelta(days=7)

    # Load children
    child_rows = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(parent_students.c.parent_id == parent_user_id)
        .all()
    )

    if not child_rows:
        return DailyBriefingResponse(
            date=today_start.date().isoformat(),
            greeting=_time_greeting(first_name),
        )

    student_ids = [s.id for s, _ in child_rows]
    child_user_ids = [u.id for _, u in child_rows]

    # ── Batch queries ──

    # 1. Tasks (overdue + due today) assigned to children
    tasks = (
        db.query(Task)
        .filter(
            Task.assigned_to_user_id.in_(child_user_ids),
            Task.is_completed == False,  # noqa: E712
            Task.archived_at.is_(None),
            Task.due_date.isnot(None),
            Task.due_date < week_ahead,
        )
        .all()
    )

    # Build task lookup by assignee user_id
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

    # 3. Assignments due in next 7 days for children's courses
    all_course_ids = list(course_name_map.keys())
    upcoming_assignments: list[Assignment] = []
    if all_course_ids:
        upcoming_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.course_id.in_(all_course_ids),
                Assignment.due_date.isnot(None),
                Assignment.due_date >= today_start,
                Assignment.due_date < week_ahead,
            )
            .order_by(Assignment.due_date.asc())
            .all()
        )

    # 4. StudentAssignment status for these assignments
    assignment_ids = [a.id for a in upcoming_assignments]
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

    # Map course_id → student_ids
    student_ids_by_course: dict[int, list[int]] = {}
    for sid, course in course_rows:
        student_ids_by_course.setdefault(course.id, []).append(sid)

    # 5. Study guide counts per child (last 7 days)
    study_counts: dict[int, int] = {}
    if child_user_ids:
        sc_rows = (
            db.query(StudyGuide.user_id, sa_func.count())
            .filter(
                StudyGuide.user_id.in_(child_user_ids),
                StudyGuide.created_at >= week_ago,
                StudyGuide.archived_at.is_(None),
            )
            .group_by(StudyGuide.user_id)
            .all()
        )
        study_counts = {uid: cnt for uid, cnt in sc_rows}

    # ── Build per-child briefings ──

    total_overdue = 0
    total_due_today = 0
    total_upcoming = 0
    child_briefings: list[ChildBriefing] = []

    for student, user in child_rows:
        overdue_tasks: list[BriefingTask] = []
        due_today_tasks: list[BriefingTask] = []

        for t in tasks_by_user.get(user.id, []):
            due = _aware(t.due_date)
            course_name = course_name_map.get(t.course_id) if t.course_id else None
            bt = BriefingTask(
                id=t.id,
                title=t.title,
                due_date=due,
                priority=t.priority or "medium",
                course_name=course_name,
            )
            if due < today_start:
                bt.is_overdue = True
                overdue_tasks.append(bt)
            elif due < today_end:
                due_today_tasks.append(bt)

        # Upcoming assignments for this student's courses
        child_course_ids = {c.id for c in courses_by_student.get(student.id, [])}
        child_upcoming: list[BriefingAssignment] = []
        for a in upcoming_assignments:
            if a.course_id not in child_course_ids:
                continue
            sa = sa_status.get((student.id, a.id))
            status = sa.status if sa else "pending"
            is_late = sa.is_late if sa else False
            child_upcoming.append(BriefingAssignment(
                id=a.id,
                title=a.title,
                due_date=_aware(a.due_date),
                course_name=course_name_map.get(a.course_id, "Unknown"),
                max_points=a.max_points,
                status=status,
                is_late=is_late,
            ))

        needs_attention = len(overdue_tasks) > 0

        total_overdue += len(overdue_tasks)
        total_due_today += len(due_today_tasks)
        total_upcoming += len(child_upcoming)

        child_briefings.append(ChildBriefing(
            student_id=student.id,
            full_name=user.full_name,
            grade_level=student.grade_level,
            overdue_tasks=overdue_tasks,
            due_today_tasks=due_today_tasks,
            upcoming_assignments=child_upcoming,
            recent_study_count=study_counts.get(user.id, 0),
            needs_attention=needs_attention,
        ))

    return DailyBriefingResponse(
        date=today_start.date().isoformat(),
        greeting=_time_greeting(first_name),
        children=child_briefings,
        total_overdue=total_overdue,
        total_due_today=total_due_today,
        total_upcoming=total_upcoming,
        attention_needed=total_overdue > 0,
    )
