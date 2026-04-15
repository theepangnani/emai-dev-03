"""ASGF (AI Study-Guide Flow) endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.models.course import Course, student_courses
from app.models.task import Task
from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asgf", tags=["ASGF"])


class ChildItem(BaseModel):
    id: str
    name: str
    grade: str
    board: str

    class Config:
        from_attributes = True


class CourseItem(BaseModel):
    id: str
    name: str
    teacher: str

    class Config:
        from_attributes = True


class TaskItem(BaseModel):
    id: str
    title: str
    due_date: str

    class Config:
        from_attributes = True


class ASGFContextDataResponse(BaseModel):
    children: list[ChildItem]
    courses: list[CourseItem]
    upcoming_tasks: list[TaskItem]


@router.get("/context-data", response_model=ASGFContextDataResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_context_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return children, courses, and upcoming tasks for the ASGF context panel."""
    children_out: list[ChildItem] = []
    courses_out: list[CourseItem] = []
    tasks_out: list[TaskItem] = []

    role = current_user.role
    if hasattr(role, "value"):
        role = role.value

    # --- Children (parent only) ---
    if role == "parent":
        rows = (
            db.query(Student)
            .options(selectinload(Student.user))
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        for s in rows:
            children_out.append(
                ChildItem(
                    id=str(s.id),
                    name=s.user.full_name if s.user else f"Student #{s.id}",
                    grade=str(s.grade_level) if s.grade_level is not None else "",
                    board=s.school_name or "",
                )
            )

    # --- Courses ---
    # For parents, gather courses across all linked children.
    # For students, gather their own enrolled courses.
    # For teachers, gather courses they teach.
    student_ids: list[int] = []
    if role == "parent":
        student_ids = [int(c.id) for c in children_out]
    elif role == "student":
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            student_ids = [student.id]

    if student_ids:
        course_rows = (
            db.query(Course)
            .join(student_courses, student_courses.c.course_id == Course.id)
            .filter(student_courses.c.student_id.in_(student_ids))
            .options(selectinload(Course.teacher))
            .distinct()
            .all()
        )
    elif role == "teacher":
        from app.models.teacher import Teacher

        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_rows = (
                db.query(Course)
                .filter(Course.teacher_id == teacher.id)
                .options(selectinload(Course.teacher))
                .all()
            )
        else:
            course_rows = []
    else:
        course_rows = []

    for c in course_rows:
        courses_out.append(
            CourseItem(
                id=str(c.id),
                name=c.name,
                teacher=c.teacher_name or "",
            )
        )

    # --- Upcoming tasks ---
    now = datetime.now(timezone.utc)
    # Fetch tasks assigned to the current user or their children
    task_user_ids = [current_user.id]
    if role == "parent" and children_out:
        child_user_rows = (
            db.query(Student.user_id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        task_user_ids.extend(uid for (uid,) in child_user_rows)

    upcoming = (
        db.query(Task)
        .filter(
            Task.assigned_to_user_id.in_(task_user_ids),
            Task.is_completed == False,  # noqa: E712
            Task.archived_at.is_(None),
            Task.due_date.isnot(None),
            Task.due_date >= now,
        )
        .order_by(Task.due_date.asc())
        .limit(20)
        .all()
    )

    for t in upcoming:
        due_str = ""
        if t.due_date:
            due_str = t.due_date.strftime("%Y-%m-%d") if hasattr(t.due_date, "strftime") else str(t.due_date)
        tasks_out.append(
            TaskItem(
                id=str(t.id),
                title=t.title,
                due_date=due_str,
            )
        )

    return ASGFContextDataResponse(
        children=children_out,
        courses=courses_out,
        upcoming_tasks=tasks_out,
    )
