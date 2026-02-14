import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import insert

from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student, parent_students
from app.models.invite import Invite, InviteType
from app.models.notification import Notification, NotificationType
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, AddStudentRequest
from app.api.deps import get_current_user, require_role, can_access_course
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, add_inspiration_to_email
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["Courses"])

_template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


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


def _resolve_teacher_by_email(db: Session, email: str, inviter: User, course: Course) -> int | None:
    """Look up teacher by email. If exists, return teacher.id. If not, create invite and return None."""
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.has_role(UserRole.TEACHER):
            raise HTTPException(status_code=400, detail=f"{email} is not a teacher account")
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(status_code=400, detail=f"Teacher profile not found for {email}")
        return teacher.id

    # Check for existing pending invite
    existing = db.query(Invite).filter(
        Invite.email == email,
        Invite.invite_type == InviteType.TEACHER,
        Invite.accepted_at.is_(None),
    ).first()
    if not existing:
        token = secrets.token_urlsafe(32)
        invite = Invite(
            email=email,
            invite_type=InviteType.TEACHER,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            invited_by_user_id=inviter.id,
            metadata_json={"course_id": course.id},
        )
        db.add(invite)
        db.flush()
        invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
        try:
            tpl_path = os.path.join(_template_dir, "teacher_course_invite.html")
            with open(tpl_path, "r") as f:
                html = f.read()
            html = (html
                .replace("{{inviter_name}}", inviter.full_name)
                .replace("{{course_name}}", course.name)
                .replace("{{invite_link}}", invite_link))
            html = add_inspiration_to_email(html, db, "teacher")
            send_email_sync(
                to_email=email,
                subject=f"{inviter.full_name} invited you to teach on ClassBridge",
                html_content=html,
            )
        except Exception as e:
            logger.warning(f"Failed to send teacher course invite email to {email}: {e}")
    return None


@router.post("/", response_model=CourseResponse)
def create_course(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new course. Parents, students, and teachers can all create courses."""
    if not any(current_user.has_role(r) for r in [UserRole.TEACHER, UserRole.PARENT, UserRole.STUDENT, UserRole.ADMIN]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create courses")

    course_dict = course_data.model_dump(exclude={"teacher_id", "teacher_email"})
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
    db.flush()

    # Resolve teacher by email if provided and no teacher_id yet
    if course_data.teacher_email and not course.teacher_id:
        teacher_id = _resolve_teacher_by_email(db, course_data.teacher_email, current_user, course)
        if teacher_id:
            course.teacher_id = teacher_id
            course.is_private = False

    log_action(db, user_id=current_user.id, action="create", resource_type="course", resource_id=course.id, details={"name": course.name})
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
    if not can_access_course(db, current_user, course_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
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
    if course.created_by_user_id != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course creator or an admin can update this course",
        )

    update_data = data.model_dump(exclude_unset=True)
    teacher_email = update_data.pop("teacher_email", None)
    for field, value in update_data.items():
        setattr(course, field, value)

    # Handle teacher assignment/unassignment by email
    if teacher_email is not None:
        if teacher_email.strip() == "":
            course.teacher_id = None
        else:
            teacher_id = _resolve_teacher_by_email(db, teacher_email, current_user, course)
            if teacher_id:
                course.teacher_id = teacher_id
                course.is_private = False

    db.flush()
    log_action(db, user_id=current_user.id, action="update", resource_type="course", resource_id=course_id)
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

    if course.is_private:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This course is private and does not allow self-enrollment",
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


def _require_course_manager(db: Session, current_user: User, course: Course):
    """Check that current_user is the course teacher, admin, or course creator."""
    if current_user.has_role(UserRole.ADMIN):
        return
    if course.created_by_user_id == current_user.id:
        return
    if current_user.has_role(UserRole.TEACHER):
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher and course.teacher_id == teacher.id:
            return
    raise HTTPException(status_code=403, detail="You do not have permission to manage this course roster")


@router.get("/{course_id}/students")
def list_course_students(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all students enrolled in a course (teacher, admin, or course creator)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _require_course_manager(db, current_user, course)

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


@router.post("/{course_id}/students")
def add_student_to_course(
    course_id: int,
    body: AddStudentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a student to a course by email. If student doesn't exist, send invite."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _require_course_manager(db, current_user, course)

    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if user:
        if not user.has_role(UserRole.STUDENT):
            raise HTTPException(status_code=400, detail=f"{email} is not a student account")
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(status_code=400, detail=f"Student profile not found for {email}")

        # Check already enrolled
        already = db.execute(
            student_courses.select().where(
                student_courses.c.student_id == student.id,
                student_courses.c.course_id == course.id,
            )
        ).first()
        if already:
            raise HTTPException(status_code=400, detail="Student is already enrolled in this course")

        db.execute(insert(student_courses).values(student_id=student.id, course_id=course.id))

        # Send in-app notification to student
        db.add(Notification(
            user_id=user.id,
            type=NotificationType.SYSTEM,
            title=f"Enrolled in {course.name}",
            content=f"{current_user.full_name} added you to {course.name}",
            link=f"/courses/{course.id}",
        ))

        # Email notification to student (#254)
        if user.email and getattr(user, 'email_notifications', True):
            try:
                student_html = f"""
                <h2>You've been enrolled in {course.name}</h2>
                <p><strong>{current_user.full_name}</strong> added you to <strong>{course.name}</strong> on ClassBridge.</p>
                <p><a href="{settings.frontend_url}/courses/{course.id}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">View Course</a></p>
                """
                student_html = add_inspiration_to_email(student_html, db, "student")
                send_email_sync(user.email, f"Enrolled in {course.name} — ClassBridge", student_html)
            except Exception as e:
                logger.warning(f"Failed to send enrollment email to student {user.email}: {e}")

        # Notify parents (#238)
        parent_rows = db.execute(
            parent_students.select().where(parent_students.c.student_id == student.id)
        ).fetchall()
        for row in parent_rows:
            parent_user = db.query(User).filter(User.id == row.parent_id).first()
            if not parent_user:
                continue
            db.add(Notification(
                user_id=parent_user.id,
                type=NotificationType.SYSTEM,
                title=f"{user.full_name} enrolled in {course.name}",
                content=f"{current_user.full_name} added {user.full_name} to {course.name}",
                link=f"/courses/{course.id}",
            ))
            if parent_user.email and getattr(parent_user, 'email_notifications', True):
                try:
                    parent_html = f"""
                    <h2>{user.full_name} was enrolled in a new course</h2>
                    <p><strong>{current_user.full_name}</strong> added <strong>{user.full_name}</strong> to <strong>{course.name}</strong> on ClassBridge.</p>
                    <p><a href="{settings.frontend_url}/courses/{course.id}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">View Course</a></p>
                    """
                    parent_html = add_inspiration_to_email(parent_html, db, "parent")
                    send_email_sync(parent_user.email, f"{user.full_name} enrolled in {course.name} — ClassBridge", parent_html)
                except Exception as e:
                    logger.warning(f"Failed to send enrollment email to parent {parent_user.email}: {e}")

        db.commit()

        return {
            "student_id": student.id,
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "grade_level": student.grade_level,
        }

    # User doesn't exist — create invite with course context
    existing_invite = db.query(Invite).filter(
        Invite.email == email,
        Invite.invite_type == InviteType.STUDENT,
        Invite.accepted_at.is_(None),
    ).first()
    if not existing_invite:
        token = secrets.token_urlsafe(32)
        invite = Invite(
            email=email,
            invite_type=InviteType.STUDENT,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            invited_by_user_id=current_user.id,
            metadata_json={"course_id": course.id},
        )
        db.add(invite)
        db.flush()
        invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
        try:
            tpl_path = os.path.join(_template_dir, "student_course_invite.html")
            with open(tpl_path, "r") as f:
                html = f.read()
            html = (html
                .replace("{{inviter_name}}", current_user.full_name)
                .replace("{{course_name}}", course.name)
                .replace("{{invite_link}}", invite_link))
            html = add_inspiration_to_email(html, db, "student")
            send_email_sync(
                to_email=email,
                subject=f"{current_user.full_name} invited you to join {course.name} on ClassBridge",
                html_content=html,
            )
        except Exception as e:
            logger.warning(f"Failed to send student course invite email to {email}: {e}")
    db.commit()
    return {"invited": True, "message": f"Invitation sent to {email}"}


@router.delete("/{course_id}/students/{student_id}")
def remove_student_from_course(
    course_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a student from a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _require_course_manager(db, current_user, course)

    row = db.execute(
        student_courses.select().where(
            student_courses.c.student_id == student_id,
            student_courses.c.course_id == course_id,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Student is not enrolled in this course")

    db.execute(
        student_courses.delete().where(
            student_courses.c.student_id == student_id,
            student_courses.c.course_id == course_id,
        )
    )
    db.commit()
    return {"message": "Student removed from course"}