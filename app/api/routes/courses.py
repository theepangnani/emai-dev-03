from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/courses", tags=["Courses"])


def get_or_create_default_course(db: Session, user: User) -> Course:
    """Get or create the default 'Main Course' for a user."""
    course = db.query(Course).filter(
        Course.created_by_user_id == user.id,
        Course.is_default == True,  # noqa: E712
    ).first()
    if course:
        return course
    course = Course(
        name="Main Course",
        description="Default course for materials not assigned to a specific course",
        created_by_user_id=user.id,
        is_private=True,
        is_default=True,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.post("/", response_model=CourseResponse)
def create_course(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new course. Parents, students, and teachers can all create courses."""
    if current_user.role not in (UserRole.TEACHER, UserRole.PARENT, UserRole.STUDENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create courses")

    course_dict = course_data.model_dump(exclude={"teacher_id"})
    course_dict["created_by_user_id"] = current_user.id

    if current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            course_dict["teacher_id"] = teacher.id
        course_dict["is_private"] = False
    elif current_user.role == UserRole.PARENT:
        course_dict["is_private"] = True
    elif current_user.role == UserRole.STUDENT:
        course_dict["is_private"] = True

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
    """List courses visible to the current user (respects privacy)."""
    from sqlalchemy import or_
    from app.models.student import parent_students

    # Public courses are visible to all
    filters = [Course.is_private == False]  # noqa: E712

    # Users can always see courses they created
    filters.append(Course.created_by_user_id == current_user.id)

    if current_user.role == UserRole.STUDENT:
        # Students can see courses they're enrolled in
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            enrolled_ids = [c.id for c in student.courses]
            if enrolled_ids:
                filters.append(Course.id.in_(enrolled_ids))

    elif current_user.role == UserRole.PARENT:
        # Parents can see courses assigned to their children
        child_student_ids = (
            db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        child_sids = [r[0] for r in child_student_ids]
        if child_sids:
            enrolled_course_ids = (
                db.query(student_courses.c.course_id)
                .filter(student_courses.c.student_id.in_(child_sids))
                .all()
            )
            ecids = [r[0] for r in enrolled_course_ids]
            if ecids:
                filters.append(Course.id.in_(ecids))

    elif current_user.role == UserRole.ADMIN:
        # Admins see everything
        return db.query(Course).all()

    return db.query(Course).filter(or_(*filters)).all()


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


@router.get("/created/me", response_model=list[CourseResponse])
def list_my_created_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List courses created by the current user."""
    return db.query(Course).filter(Course.created_by_user_id == current_user.id).all()


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


@router.get("/default", response_model=CourseResponse)
def get_default_course(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get or create the default 'My Materials' course for the current user."""
    return get_or_create_default_course(db, current_user)


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


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    data: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a course. Only the creator or an admin can update."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if course.created_by_user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course creator or an admin can update this course",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)

    db.commit()
    db.refresh(course)
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