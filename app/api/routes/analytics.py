from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AIInsightRequest,
    AIInsightResponse,
    GradeListResponse,
    GradeSummaryResponse,
    GradeSyncResponse,
    GradeTrendResponse,
    ProgressReportResponse,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_student_or_403(db: Session, student_id: int, current_user: User) -> Student:
    """Load a student and verify the current user has access."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if current_user.has_role(UserRole.ADMIN):
        return student

    # Student viewing own data
    if current_user.has_role(UserRole.STUDENT) and student.user_id == current_user.id:
        return student

    # Parent viewing linked child
    if current_user.has_role(UserRole.PARENT):
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student.id,
        ).first()
        if link:
            return student

    # Teacher viewing student in their course
    if current_user.has_role(UserRole.TEACHER):
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            in_course = (
                db.query(student_courses.c.student_id)
                .join(Course, Course.id == student_courses.c.course_id)
                .filter(
                    student_courses.c.student_id == student.id,
                    Course.teacher_id == teacher.id,
                )
                .first()
            )
            if in_course:
                return student

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this student's grades")


def _resolve_student_id(db: Session, student_id: int | None, current_user: User) -> int:
    """Resolve the student_id — students default to themselves."""
    if student_id:
        return student_id

    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            return student.id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="student_id is required",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/grades", response_model=GradeListResponse)
def list_grades(
    student_id: int | None = None,
    course_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List graded assignments for a student, optionally filtered by course."""
    from app.services.analytics_service import get_graded_assignments

    sid = _resolve_student_id(db, student_id, current_user)
    _get_student_or_403(db, sid, current_user)

    grades, total = get_graded_assignments(db, sid, course_id=course_id, limit=limit, offset=offset)
    return {"grades": grades, "total": total}


@router.get("/summary", response_model=GradeSummaryResponse)
def get_summary(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Overall grade summary with per-course averages."""
    from app.services.analytics_service import compute_summary

    sid = _resolve_student_id(db, student_id, current_user)
    _get_student_or_403(db, sid, current_user)

    return compute_summary(db, sid)


@router.get("/trends", response_model=GradeTrendResponse)
def get_trends(
    student_id: int | None = None,
    course_id: int | None = None,
    days: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grade trend data points over time."""
    from app.services.analytics_service import compute_trend_points

    sid = _resolve_student_id(db, student_id, current_user)
    _get_student_or_403(db, sid, current_user)

    points, trend = compute_trend_points(db, sid, course_id=course_id, days=days)
    return {"points": points, "trend": trend}


@router.post("/ai-insights", response_model=AIInsightResponse)
async def get_ai_insights(
    body: AIInsightRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """On-demand AI insight generation for a student's performance."""
    from app.services.analytics_service import generate_ai_insight

    _get_student_or_403(db, body.student_id, current_user)

    insight = await generate_ai_insight(db, body.student_id, focus_area=body.focus_area)
    return {"insight": insight, "generated_at": datetime.utcnow()}


@router.get("/reports/weekly", response_model=ProgressReportResponse)
def get_weekly_report(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get or generate cached weekly progress report."""
    from app.services.analytics_service import get_or_create_weekly_report

    sid = _resolve_student_id(db, student_id, current_user)
    _get_student_or_403(db, sid, current_user)

    return get_or_create_weekly_report(db, sid)


@router.post("/sync-grades", response_model=GradeSyncResponse)
def sync_grades(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a manual grade sync from Google Classroom."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Classroom not connected. Please connect your Google account first.",
        )

    from app.services.grade_sync_service import sync_grades_for_student

    sid = _resolve_student_id(db, student_id, current_user)
    student = _get_student_or_403(db, sid, current_user)

    result = sync_grades_for_student(current_user, student, db)

    synced = result["synced"]
    errors = result["errors"]
    if errors:
        message = f"Synced {synced} grade(s) with {errors} error(s)"
    else:
        message = f"Synced {synced} grade(s) from Google Classroom"

    return {"synced": synced, "errors": errors, "message": message}
