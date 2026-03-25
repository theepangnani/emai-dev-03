from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.course import Course, student_courses
from app.schemas.student import StudentCreate, StudentResponse
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/students", tags=["Students"])


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


@router.get("/{student_id}/streak")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_student_streak(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """Get a student's streak info. Parent must be linked to the student (#2224)."""
    if current_user.role == UserRole.PARENT:
        link = db.query(parent_students).filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        ).first()
        if not link:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your child or student not found",
            )

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    from app.services.streak_service import StreakService
    return StreakService.get_streak_info(db, student.user_id)
