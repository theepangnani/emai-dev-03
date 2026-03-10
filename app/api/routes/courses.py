import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy.orm import Session
from sqlalchemy import insert

from app.db.database import get_db
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.course import Course, student_courses
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student, parent_students
from app.models.invite import Invite, InviteType
from app.models.broadcast import Broadcast
from app.models.notification import Notification, NotificationType
from app.models.message import Conversation, Message
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, TeacherCourseManagementResponse, AddStudentRequest
from app.api.deps import get_current_user, require_role, can_access_course
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, send_emails_batch, add_inspiration_to_email, wrap_branded_email
from app.core.config import settings
from app.domains.education.services import EducationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["Courses"])


def generate_class_code(db: Session, length: int = 6) -> str:
    """Generate a unique 6-character uppercase alphanumeric class code."""
    import string
    import random
    chars = string.ascii_uppercase + string.digits
    for _ in range(100):  # max attempts
        code = ''.join(random.choices(chars, k=length))
        existing = db.query(Course).filter(Course.class_code == code).first()
        if not existing:
            return code
    raise RuntimeError("Unable to generate unique class code after 100 attempts")

_template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


def get_or_create_default_course(db: Session, user: User) -> Course:
    """Get or create the default 'Main Class' for a user."""
    course = db.query(Course).filter(
        Course.created_by_user_id == user.id,
        Course.is_default == True,  # noqa: E712
    ).first()
    if course:
        return course
    course = Course(
        name="Main Class",
        description="Default class for materials not assigned to a specific class",
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


@router.get("/teachers/search")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def search_teachers(
    request: Request,
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search teachers by name or email. Returns both platform and shadow teachers."""
    results = []
    query = db.query(Teacher)
    teachers = query.all()
    q_lower = q.strip().lower()
    for t in teachers:
        name = None
        email = None
        if t.is_shadow:
            name = t.full_name
            email = t.google_email
        elif t.user:
            name = t.user.full_name
            email = t.user.email
        if not name:
            continue
        if q_lower and q_lower not in (name or "").lower() and q_lower not in (email or "").lower():
            continue
        results.append({
            "id": t.id,
            "name": name,
            "email": email,
            "is_shadow": t.is_shadow,
        })
    return results[:20]


@router.get("/students/search")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def search_students_for_course(
    request: Request,
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search students by name or email for course enrollment."""
    from app.models.user import User as UserModel
    results = []
    students = db.query(Student).all()
    q_lower = q.strip().lower()
    for s in students:
        user = db.query(UserModel).filter(UserModel.id == s.user_id).first()
        if not user:
            continue
        name = user.full_name or ""
        email = user.email or ""
        if q_lower and q_lower not in name.lower() and q_lower not in email.lower():
            continue
        results.append({
            "id": s.id,
            "user_id": user.id,
            "name": name,
            "email": email,
        })
    return results[:20]


@router.post("/", response_model=CourseResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_course(
    request: Request,
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new course. Parents, students, and teachers can all create courses."""
    if not any(current_user.has_role(r) for r in [UserRole.TEACHER, UserRole.PARENT, UserRole.STUDENT, UserRole.ADMIN]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create courses")

    course_dict = course_data.model_dump(exclude={"teacher_id", "teacher_email", "student_ids", "new_teacher_name", "new_teacher_email"})
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

    # Handle inline teacher creation
    if course_data.new_teacher_name:
        new_teacher = Teacher(
            is_shadow=not bool(course_data.new_teacher_email),
            is_platform_user=bool(course_data.new_teacher_email),
            full_name=course_data.new_teacher_name.strip(),
            google_email=course_data.new_teacher_email.strip().lower() if course_data.new_teacher_email else None,
        )
        db.add(new_teacher)
        db.flush()
        course_dict["teacher_id"] = new_teacher.id
        course_dict["is_private"] = False

        # Send invitation if email provided
        if course_data.new_teacher_email:
            email = course_data.new_teacher_email.strip().lower()
            existing_invite = db.query(Invite).filter(
                Invite.email == email,
                Invite.invite_type == InviteType.TEACHER,
                Invite.accepted_at.is_(None),
            ).first()
            if not existing_invite:
                token = secrets.token_urlsafe(32)
                invite = Invite(
                    email=email,
                    invite_type=InviteType.TEACHER,
                    token=token,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    invited_by_user_id=current_user.id,
                    metadata_json={"source": "create_class_inline"},
                )
                db.add(invite)
                db.flush()
                invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
                try:
                    body = (
                        f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">You\'re invited to teach on ClassBridge</h2>'
                        f'<p style="color:#333;line-height:1.6;margin:0 0 24px 0;"><strong>{current_user.full_name}</strong> invited you to join ClassBridge as a teacher.</p>'
                        f'<a href="{invite_link}" style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;padding:14px 28px;border-radius:8px;font-weight:600;font-size:16px;">Accept Invitation</a>'
                    )
                    html = wrap_branded_email(body)
                    html = add_inspiration_to_email(html, db, "teacher")
                    send_email_sync(email, f"{current_user.full_name} invited you to teach on ClassBridge", html)
                except Exception as e:
                    logger.warning(f"Failed to send teacher invite email to {email}: {e}")

    course_dict["class_code"] = generate_class_code(db)
    course = Course(**course_dict)
    db.add(course)
    db.flush()

    # Handle existing teacher_id from request
    if course_data.teacher_id and not course.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == course_data.teacher_id).first()
        if teacher:
            course.teacher_id = teacher.id
            course.is_private = False

    # Resolve teacher by email if provided and no teacher_id yet
    if course_data.teacher_email and not course.teacher_id:
        teacher_id = _resolve_teacher_by_email(db, course_data.teacher_email, current_user, course)
        if teacher_id:
            course.teacher_id = teacher_id
            course.is_private = False

    # Enroll students
    if course_data.student_ids:
        for sid in course_data.student_ids:
            student = db.query(Student).filter(Student.id == sid).first()
            if student:
                already = db.execute(
                    student_courses.select().where(
                        student_courses.c.student_id == student.id,
                        student_courses.c.course_id == course.id,
                    )
                ).first()
                if not already:
                    db.execute(insert(student_courses).values(student_id=student.id, course_id=course.id))

    log_action(db, user_id=current_user.id, action="create", resource_type="course", resource_id=course.id, details={"name": course.name})
    db.commit()
    db.refresh(course)
    return course


@router.get("/", response_model=list[CourseResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_courses(
    request: Request,
    classroom_type: str | None = Query(
        None,
        description='Filter by classroom type: "school", "private", or "manual"',
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List courses visible to the current user (respects privacy).

    Optional query parameter classroom_type filters by type.
    """
    education_service = EducationService(db)
    courses = education_service.get_visible_courses(current_user)
    if classroom_type:
        from app.models.course import VALID_CLASSROOM_TYPES
        if classroom_type not in VALID_CLASSROOM_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Invalid classroom_type. Must be one of: school, private, manual",
            )
        courses = [c for c in courses if c.classroom_type == classroom_type]
    return courses


@router.get("/teaching", response_model=list[CourseResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_teaching_courses(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """List courses taught by the current teacher."""
    education_service = EducationService(db)
    return education_service.get_teaching_courses(current_user)


@router.get("/teaching/management", response_model=list[TeacherCourseManagementResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_teaching_courses_management(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """List courses taught by the current teacher with enriched management data (#947).

    Returns assignment count, material count, last activity, and source badge info.
    """
    from sqlalchemy import func as sa_func
    from app.models.assignment import Assignment
    from app.models.course_content import CourseContent

    education_service = EducationService(db)
    courses = education_service.get_teaching_courses(current_user)

    if not courses:
        return []

    course_ids = [c.id for c in courses]

    # Batch-query assignment counts per course
    assignment_counts = dict(
        db.query(Assignment.course_id, sa_func.count(Assignment.id))
        .filter(Assignment.course_id.in_(course_ids))
        .group_by(Assignment.course_id)
        .all()
    )

    # Batch-query material counts per course (non-archived only)
    material_counts = dict(
        db.query(CourseContent.course_id, sa_func.count(CourseContent.id))
        .filter(CourseContent.course_id.in_(course_ids), CourseContent.archived_at.is_(None))
        .group_by(CourseContent.course_id)
        .all()
    )

    # Batch-query last activity (max of assignment created_at and material created_at)
    last_assignment = dict(
        db.query(Assignment.course_id, sa_func.max(Assignment.created_at))
        .filter(Assignment.course_id.in_(course_ids))
        .group_by(Assignment.course_id)
        .all()
    )
    last_material = dict(
        db.query(CourseContent.course_id, sa_func.max(CourseContent.created_at))
        .filter(CourseContent.course_id.in_(course_ids))
        .group_by(CourseContent.course_id)
        .all()
    )

    results = []
    for course in courses:
        # Determine source
        if course.google_classroom_id:
            source = "google"
        elif course.created_by_user_id and course.created_by_user_id != current_user.id:
            # Created by someone else (likely admin or parent) and assigned to this teacher
            creator = course.created_by
            if creator and creator.role == UserRole.ADMIN:
                source = "admin"
            else:
                source = "manual"
        else:
            source = "manual"

        # Compute last activity
        last_a = last_assignment.get(course.id)
        last_m = last_material.get(course.id)
        last_activity = None
        if last_a and last_m:
            last_activity = max(last_a, last_m)
        elif last_a:
            last_activity = last_a
        elif last_m:
            last_activity = last_m

        results.append(TeacherCourseManagementResponse(
            id=course.id,
            name=course.name,
            description=course.description,
            subject=course.subject,
            google_classroom_id=course.google_classroom_id,
            class_code=course.class_code,
            classroom_type=course.classroom_type,
            teacher_id=course.teacher_id,
            teacher_name=course.teacher_name,
            created_by_user_id=course.created_by_user_id,
            is_private=course.is_private,
            is_default=course.is_default,
            student_count=course.student_count,
            assignment_count=assignment_counts.get(course.id, 0),
            material_count=material_counts.get(course.id, 0),
            last_activity=last_activity,
            source=source,
            created_at=course.created_at,
        ))

    return results


@router.get("/created/me", response_model=list[CourseResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_my_created_courses(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List courses created by the current user."""
    return db.query(Course).filter(Course.created_by_user_id == current_user.id).all()


@router.get("/enrolled/me", response_model=list[CourseResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_my_enrolled_courses(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """List all courses the current student is enrolled in."""
    education_service = EducationService(db)
    return education_service.get_enrolled_courses(current_user)


@router.get("/default", response_model=CourseResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_default_course(
    request: Request,
    student_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get or create the default 'My Materials' course for the current user.

    Parents can pass ``student_user_id`` to get/create the default course
    for a specific child instead of themselves.
    """
    target_user = current_user
    if student_user_id and current_user.has_role(UserRole.PARENT):
        child = db.query(User).filter(User.id == student_user_id).first()
        if child:
            target_user = child
    return get_or_create_default_course(db, target_user)


@router.get("/lookup", response_model=CourseResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def lookup_course_by_code(
    request: Request,
    code: str = Query(..., min_length=1, max_length=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Look up a course by its shareable class code."""
    course = db.query(Course).filter(Course.class_code == code.upper()).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No course found with that class code",
        )
    return course


@router.get("/{course_id}", response_model=CourseResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_course(
    request: Request,
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_course(
    request: Request,
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


@router.delete("/{course_id}", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_course(
    request: Request,
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a course. Only the creator or an admin can delete."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if course.created_by_user_id != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course creator or an admin can delete this course",
        )
    if course.google_classroom_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a Google Classroom synced course",
        )

    log_action(db, user_id=current_user.id, action="delete", resource_type="course", resource_id=course_id, details={"name": course.name})
    db.delete(course)
    db.commit()
    return {"message": f"Course '{course.name}' has been deleted"}


@router.post("/{course_id}/enroll", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def enroll_in_course(
    request: Request,
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def unenroll_from_course(
    request: Request,
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
    education_service = EducationService(db)
    if not education_service.can_manage_course(current_user, course):
        raise HTTPException(status_code=403, detail="You do not have permission to manage this course roster")


@router.get("/{course_id}/students")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_course_students(
    request: Request,
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def add_student_to_course(
    request: Request,
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
                student_body = (
                    f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">You\'ve been enrolled in {course.name}</h2>'
                    f'<p style="color:#333;line-height:1.6;margin:0 0 24px 0;"><strong>{current_user.full_name}</strong> added you to <strong>{course.name}</strong> on ClassBridge.</p>'
                    f'<a href="{settings.frontend_url}/courses/{course.id}" style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;padding:14px 28px;border-radius:8px;font-weight:600;font-size:16px;">View Course</a>'
                )
                student_html = wrap_branded_email(student_body)
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
                    parent_body = (
                        f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">{user.full_name} was enrolled in a new course</h2>'
                        f'<p style="color:#333;line-height:1.6;margin:0 0 24px 0;"><strong>{current_user.full_name}</strong> added <strong>{user.full_name}</strong> to <strong>{course.name}</strong> on ClassBridge.</p>'
                        f'<a href="{settings.frontend_url}/courses/{course.id}" style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;padding:14px 28px;border-radius:8px;font-weight:600;font-size:16px;">View Course</a>'
                    )
                    parent_html = wrap_branded_email(parent_body)
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


@router.post("/{course_id}/invite-student")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def invite_student_to_course(
    request: Request,
    course_id: int,
    body: AddStudentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invite a student to a course (alias for add_student_to_course).

    Teacher-friendly endpoint name for the invite flow.
    """
    return add_student_to_course(request, course_id, body, db, current_user)


@router.delete("/{course_id}/students/{student_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def remove_student_from_course(
    request: Request,
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


# ── Teacher Course Announcements ─────────────────────────────

class AnnouncementRequest(PydanticBaseModel):
    subject: str
    body: str


def _get_or_create_conversation(db: Session, user_a_id: int, user_b_id: int, subject: str | None = None) -> Conversation:
    """Find or create a conversation between two users."""
    from sqlalchemy import or_, and_
    conv = db.query(Conversation).filter(
        or_(
            and_(Conversation.participant_1_id == user_a_id, Conversation.participant_2_id == user_b_id),
            and_(Conversation.participant_1_id == user_b_id, Conversation.participant_2_id == user_a_id),
        )
    ).first()
    if not conv:
        conv = Conversation(participant_1_id=user_a_id, participant_2_id=user_b_id, subject=subject)
        db.add(conv)
        db.flush()
    return conv


@router.post("/{course_id}/announce")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def send_course_announcement(
    request: Request,
    course_id: int,
    data: AnnouncementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an announcement to all parents of students in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _require_course_manager(db, current_user, course)

    # Find all parents of enrolled students
    parent_ids = set()
    for student in course.students:
        rows = db.execute(
            parent_students.select().where(parent_students.c.student_id == student.id)
        ).fetchall()
        for row in rows:
            parent_ids.add(row.parent_id)

    if not parent_ids:
        raise HTTPException(status_code=400, detail="No parents found for students in this course")

    parent_users = db.query(User).filter(User.id.in_(parent_ids), User.is_active == True).all()  # noqa: E712

    # Create broadcast record
    broadcast = Broadcast(
        sender_id=current_user.id,
        subject=data.subject,
        body=data.body,
        recipient_count=len(parent_users),
        email_count=0,
    )
    db.add(broadcast)
    db.flush()

    # Create in-app notifications + conversation messages
    message_content = f"[{course.name} Announcement] {data.subject}\n\n{data.body}"
    for parent in parent_users:
        db.add(Notification(
            user_id=parent.id,
            type=NotificationType.SYSTEM,
            title=f"{course.name}: {data.subject}",
            content=data.body[:200],
        ))
        conv = _get_or_create_conversation(db, current_user.id, parent.id, subject=data.subject)
        db.add(Message(
            conversation_id=conv.id,
            sender_id=current_user.id,
            content=message_content,
        ))

    # Extract email data before commit
    email_recipients = [(u.email, u.full_name) for u in parent_users if u.email]
    db.commit()

    # Send emails
    import html as _html
    email_batch = []
    for email, name in email_recipients:
        body = (
            f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">{_html.escape(course.name)}: {_html.escape(data.subject)}</h2>'
            f'<p style="color:#666;font-size:14px;margin:0 0 16px 0;">From {_html.escape(current_user.full_name)}</p>'
            f'<div style="padding:16px;background:#f8f9fa;border-radius:8px;margin:0 0 16px 0;">'
            f'<p style="font-size:15px;line-height:1.6;margin:0;">{_html.escape(data.body).replace(chr(10), "<br>")}</p>'
            f'</div>'
        )
        html_body = wrap_branded_email(body)
        html_body = add_inspiration_to_email(html_body, db, "parent")
        email_batch.append((email, f"{course.name}: {data.subject}", html_body))

    email_count = send_emails_batch(email_batch) if email_batch else 0
    broadcast.email_count = email_count
    db.commit()

    logger.info("Course announcement %d: sent to %d parents (%d emails) for course %s",
                broadcast.id, len(parent_users), email_count, course.name)

    return {
        "recipient_count": len(parent_users),
        "email_count": email_count,
        "course_name": course.name,
    }