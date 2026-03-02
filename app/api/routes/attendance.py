"""Attendance tracking API endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.teacher import Teacher
from app.schemas.attendance import (
    AttendanceRecordCreate,
    BulkAttendanceCreate,
    AttendanceResponse,
    AttendanceSummary,
    CourseAttendanceReport,
    BulkAttendanceResponse,
)
from app.services.attendance import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])
_service = AttendanceService()


def _get_teacher_for_user(user: User, db: Session) -> Optional[Teacher]:
    """Return the Teacher record linked to this user, or None."""
    return db.query(Teacher).filter(Teacher.user_id == user.id).first()


def _assert_teacher_owns_course(teacher: Optional[Teacher], course_id: int, db: Session) -> None:
    """Raise 403 if the teacher doesn't own the course."""
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher profile not found")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage attendance for this course",
        )


# ---------------------------------------------------------------------------
# POST /api/attendance/ — single record (teacher/admin)
# ---------------------------------------------------------------------------

@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_200_OK)
def mark_single_attendance(
    payload: AttendanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Mark attendance for a single student in a course."""
    if current_user.has_role(UserRole.TEACHER):
        teacher = _get_teacher_for_user(current_user, db)
        _assert_teacher_owns_course(teacher, payload.course_id, db)
    return _service.mark_attendance(
        teacher_id=current_user.id,
        student_id=payload.student_id,
        course_id=payload.course_id,
        record_date=payload.date,
        status=payload.status,
        note=payload.note,
        db=db,
    )


# ---------------------------------------------------------------------------
# POST /api/attendance/bulk — bulk mark for whole class (teacher/admin)
# ---------------------------------------------------------------------------

@router.post("/bulk", response_model=BulkAttendanceResponse, status_code=status.HTTP_200_OK)
def bulk_mark_attendance(
    payload: BulkAttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Mark attendance for all students in a course on a given date."""
    if current_user.has_role(UserRole.TEACHER):
        teacher = _get_teacher_for_user(current_user, db)
        _assert_teacher_owns_course(teacher, payload.course_id, db)
    result = _service.bulk_mark(
        teacher_id=current_user.id,
        course_id=payload.course_id,
        record_date=payload.date,
        records=payload.records,
        db=db,
    )
    return BulkAttendanceResponse(**result)


# ---------------------------------------------------------------------------
# GET /api/attendance/course/{id} — today's class attendance (teacher/admin)
# ---------------------------------------------------------------------------

@router.get("/course/{course_id}", response_model=list[AttendanceResponse])
def get_course_attendance(
    course_id: int,
    record_date: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Return all attendance records for a course on a specific date (defaults to today)."""
    if record_date is None:
        record_date = date.today()
    if current_user.has_role(UserRole.TEACHER):
        teacher = _get_teacher_for_user(current_user, db)
        _assert_teacher_owns_course(teacher, course_id, db)
    return _service.get_course_attendance(course_id=course_id, record_date=record_date, db=db)


# ---------------------------------------------------------------------------
# GET /api/attendance/student/{id}/summary — student summary (teacher/parent/admin)
# ---------------------------------------------------------------------------

@router.get("/student/{student_id}/summary", response_model=AttendanceSummary)
def get_student_summary(
    student_id: int,
    course_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.PARENT, UserRole.ADMIN)),
):
    """Return attendance summary for a student."""
    if current_user.has_role(UserRole.PARENT):
        # Parents can only view their own linked children
        try:
            return _service.get_parent_child_attendance(
                parent_id=current_user.id,
                student_id=student_id,
                db=db,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _service.get_student_summary(
        student_id=student_id,
        db=db,
        course_id=course_id,
        start_date=start_date,
        end_date=end_date,
    )


# ---------------------------------------------------------------------------
# GET /api/attendance/course/{id}/report — course report (teacher/admin)
# ---------------------------------------------------------------------------

@router.get("/course/{course_id}/report", response_model=CourseAttendanceReport)
def get_course_report(
    course_id: int,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Return full attendance report for a course within a date range."""
    if current_user.has_role(UserRole.TEACHER):
        teacher = _get_teacher_for_user(current_user, db)
        _assert_teacher_owns_course(teacher, course_id, db)
    if start is None:
        from datetime import timedelta
        start = date.today() - timedelta(days=30)
    if end is None:
        end = date.today()
    try:
        return _service.get_course_report(
            course_id=course_id,
            start_date=start,
            end_date=end,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /api/attendance/my-summary — student views own attendance
# ---------------------------------------------------------------------------

@router.get("/my-summary", response_model=AttendanceSummary)
def get_my_summary(
    course_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Student retrieves their own attendance summary."""
    return _service.get_student_summary(
        student_id=current_user.id,
        db=db,
        course_id=course_id,
        start_date=start_date,
        end_date=end_date,
    )


# ---------------------------------------------------------------------------
# GET /api/attendance/parent/{student_id} — parent views child summary
# ---------------------------------------------------------------------------

@router.get("/parent/{student_id}", response_model=AttendanceSummary)
def get_parent_child_summary(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Parent retrieves attendance summary for one of their linked children."""
    try:
        return _service.get_parent_child_attendance(
            parent_id=current_user.id,
            student_id=student_id,
            db=db,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
