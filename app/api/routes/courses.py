from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student
from app.schemas.course import CourseCreate, CourseResponse
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse)
def create_course(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """Create a new course. Teachers are auto-assigned as the course teacher."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher profile not found",
        )

    course_dict = course_data.model_dump()
    course_dict["teacher_id"] = teacher.id
    course = Course(**course_dict)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/", response_model=list[CourseResponse])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Course).all()


@router.get("/teaching", response_model=list[CourseResponse])
def list_teaching_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """List courses taught by the current teacher."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        return []
    return db.query(Course).filter(Course.teacher_id == teacher.id).all()


@router.get("/enrolled/me", response_model=list[CourseResponse])
def list_my_enrolled_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """List all courses the current student is enrolled in."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        return []
    return student.courses


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course


@router.post("/{course_id}/enroll", status_code=status.HTTP_200_OK)
def enroll_in_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Enroll the current student in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )

    # Check if already enrolled
    if course in student.courses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already enrolled in this course",
        )

    student.courses.append(course)
    db.commit()

    return {"message": "Successfully enrolled in course", "course_id": course_id, "course_name": course.name}


@router.delete("/{course_id}/enroll", status_code=status.HTTP_200_OK)
def unenroll_from_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Unenroll the current student from a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )

    if course not in student.courses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enrolled in this course",
        )

    student.courses.remove(course)
    db.commit()

    return {"message": "Successfully unenrolled from course", "course_id": course_id}


@router.get("/{course_id}/students")
def list_course_students(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """List all students enrolled in a course (teacher only)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    # Verify teacher owns this course
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher or course.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the teacher of this course",
        )

    return [
        {
            "student_id": s.id,
            "user_id": s.user_id,
            "full_name": s.user.full_name,
            "email": s.user.email,
            "grade_level": s.grade_level,
        }
        for s in course.students
    ]