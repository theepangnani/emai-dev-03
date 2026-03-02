from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.course import Course, student_courses
from app.models.assignment import StudentAssignment, Assignment
from app.schemas.student import StudentCreate, StudentResponse
from app.schemas.assignment import SubmissionResponse
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/students", tags=["Students"])


# ── Streak Schemas ──────────────────────────────────────────────

class StudyActivityResponse(BaseModel):
    study_streak_days: int
    last_study_date: date | None
    longest_streak: int
    streak_updated: bool  # True if streak actually changed

    class Config:
        from_attributes = True


@router.post("/", response_model=StudentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_student(
    request: Request,
    student_data: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a student record. Admin only (parents use /parent/children/create)."""
    student = Student(**student_data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/", response_model=list[StudentResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_students(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    """List students. Admin sees all; teachers see students in their courses."""
    if current_user.role == UserRole.ADMIN:
        return db.query(Student).all()

    # Teacher: only students enrolled in their courses
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        return []

    course_ids = [
        r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
    ]
    if not course_ids:
        return []

    student_ids = {
        r[0] for r in db.query(student_courses.c.student_id).filter(
            student_courses.c.course_id.in_(course_ids)
        ).all()
    }
    if not student_ids:
        return []

    return db.query(Student).filter(Student.id.in_(student_ids)).all()


@router.get("/me", response_model=StudentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_my_student_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's own student profile."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile found")
    return student


@router.get("/{student_id}", response_model=StudentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_student(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a student. Access: admin, teacher (course), parent (linked), student (own)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Admin sees all
    if current_user.role == UserRole.ADMIN:
        return student

    # Student sees own profile
    if current_user.role == UserRole.STUDENT and student.user_id == current_user.id:
        return student

    # Parent sees linked children
    if current_user.role == UserRole.PARENT:
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if link:
            return student

    # Teacher sees students in their courses
    if current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_ids = [
                r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ]
            if course_ids:
                enrolled = db.query(student_courses).filter(
                    student_courses.c.student_id == student_id,
                    student_courses.c.course_id.in_(course_ids),
                ).first()
                if enrolled:
                    return student

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.post("/study-activity", response_model=StudyActivityResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def record_study_activity(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Record that the student studied today. Updates streak counters.

    - If last_study_date is today: no change (idempotent)
    - If last_study_date is yesterday: increment streak
    - If last_study_date is older (or null): reset streak to 1
    - Always updates longest_streak if current exceeds it
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile found")

    today = date.today()
    yesterday = today - timedelta(days=1)
    streak_updated = False

    if student.last_study_date == today:
        # Already recorded today — idempotent, return current state
        pass
    elif student.last_study_date == yesterday:
        # Consecutive day — extend streak
        student.study_streak_days = (student.study_streak_days or 0) + 1
        student.last_study_date = today
        streak_updated = True
    else:
        # Gap or first time — reset streak to 1
        student.study_streak_days = 1
        student.last_study_date = today
        streak_updated = True

    # Update longest streak
    if student.study_streak_days > (student.longest_streak or 0):
        student.longest_streak = student.study_streak_days
        streak_updated = True

    if streak_updated:
        db.commit()
        db.refresh(student)

    return StudyActivityResponse(
        study_streak_days=student.study_streak_days or 0,
        last_study_date=student.last_study_date,
        longest_streak=student.longest_streak or 0,
        streak_updated=streak_updated,
    )


@router.get("/streak", response_model=StudyActivityResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_streak(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Get the current student's streak data."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile found")

    return StudyActivityResponse(
        study_streak_days=student.study_streak_days or 0,
        last_study_date=student.last_study_date,
        longest_streak=student.longest_streak or 0,
        streak_updated=False,
    )


@router.get("/{student_id}/submissions", response_model=list[SubmissionResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_student_submissions(
    request: Request,
    student_id: int,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all submissions for a student. Accessible by the student themselves, their linked parents, teachers, and admins."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Access control
    if current_user.role == UserRole.ADMIN:
        pass  # Admin can see all
    elif current_user.role == UserRole.STUDENT:
        if student.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.PARENT:
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if not link:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_ids = [
                r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ]
            enrolled = db.query(student_courses).filter(
                student_courses.c.student_id == student_id,
                student_courses.c.course_id.in_(course_ids),
            ).first() if course_ids else None
            if not enrolled:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    query = db.query(StudentAssignment).filter(
        StudentAssignment.student_id == student_id,
    )
    if status_filter:
        query = query.filter(StudentAssignment.status == status_filter)

    submissions = query.order_by(StudentAssignment.submitted_at.desc().nullslast()).offset(offset).limit(limit).all()

    result = []
    for sa in submissions:
        assignment = sa.assignment
        result.append(SubmissionResponse(
            id=sa.id,
            student_id=sa.student_id,
            assignment_id=sa.assignment_id,
            status=sa.status,
            submitted_at=sa.submitted_at,
            grade=sa.grade,
            submission_file_name=sa.submission_file_name,
            submission_notes=sa.submission_notes,
            is_late=sa.is_late or False,
            assignment_title=assignment.title if assignment else None,
            course_name=assignment.course.name if assignment and assignment.course else None,
            student_name=student.user.full_name if student and student.user else None,
            has_file=bool(sa.submission_file_path),
        ))

    return result
