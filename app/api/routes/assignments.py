import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.notification import Notification, NotificationType
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    SubmissionResponse,
    SubmissionListItem,
)
from app.api.deps import get_current_user, can_access_course
from app.services.feature_flag_service import is_feature_enabled
from app.services.storage_service import save_file, get_file_path, delete_file
from app.services.task_sync_service import (
    handle_assignment_deleted,
    handle_assignment_submitted,
)

logger = logging.getLogger(__name__)

# File upload constraints for submissions
MAX_SUBMISSION_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".txt"}

router = APIRouter(prefix="/assignments", tags=["Assignments"])


def _get_accessible_course_ids(db: Session, user: User) -> list[int] | None:
    """Return course IDs accessible to the user, or None for admin (all access)."""
    if user.role == UserRole.ADMIN:
        return None  # Admin can see all

    ids: set[int] = set()

    # Courses created by the user
    created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
    ids.update(r[0] for r in created)

    # Public courses
    public = db.query(Course.id).filter(Course.is_private == False).all()  # noqa: E712
    ids.update(r[0] for r in public)

    if user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            taught = db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ids.update(r[0] for r in taught)

    elif user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            ids.update(c.id for c in student.courses)

    elif user.role == UserRole.PARENT:
        child_sids = [
            r[0] for r in db.query(parent_students.c.student_id).filter(
                parent_students.c.parent_id == user.id
            ).all()
        ]
        if child_sids:
            enrolled = db.query(student_courses.c.course_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            ids.update(r[0] for r in enrolled)

    return list(ids)


def _require_course_write(db: Session, user: User, course_id: int) -> Course:
    """Verify the user can write assignments to the course. Returns the course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if user.has_role(UserRole.ADMIN):
        return course

    if course.created_by_user_id == user.id:
        return course

    if user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher and course.teacher_id == teacher.id:
            return course

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the course teacher or creator can manage assignments",
    )


def _notify_enrolled_students(db: Session, course: Course, assignment: Assignment, actor_name: str):
    """Send in-app notification to all enrolled students."""
    enrolled_user_ids = (
        db.query(Student.user_id)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .filter(student_courses.c.course_id == course.id)
        .all()
    )
    for (uid,) in enrolled_user_ids:
        db.add(Notification(
            user_id=uid,
            type=NotificationType.ASSIGNMENT_DUE,
            title=f"New assignment in {course.name}",
            content=f"{actor_name} posted \"{assignment.title}\"",
            link=f"/courses/{course.id}",
        ))


def _assignment_eager_options():
    """SQLAlchemy options to eager-load Assignment relationships (avoids N+1)."""
    return [selectinload(Assignment.course)]


def _submission_eager_options():
    """SQLAlchemy options to eager-load StudentAssignment relationships (avoids N+1)."""
    return [
        selectinload(StudentAssignment.assignment).selectinload(Assignment.course),
        selectinload(StudentAssignment.student).selectinload(Student.user),
    ]


def _to_response(assignment: Assignment) -> dict:
    """Convert assignment to response dict with course_name."""
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "course_id": assignment.course_id,
        "course_name": assignment.course.name if assignment.course else None,
        "google_classroom_id": assignment.google_classroom_id,
        "due_date": assignment.due_date,
        "max_points": assignment.max_points,
        "created_at": assignment.created_at,
    }


@router.post("/", response_model=AssignmentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_assignment(
    request: Request,
    assignment_data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an assignment. Must have write access to the course."""
    course = _require_course_write(db, current_user, assignment_data.course_id)

    assignment = Assignment(**assignment_data.model_dump())
    db.add(assignment)
    db.flush()

    _notify_enrolled_students(db, course, assignment, current_user.full_name)
    db.commit()
    assignment = (
        db.query(Assignment)
        .options(*_assignment_eager_options())
        .filter(Assignment.id == assignment.id)
        .first()
    )
    return _to_response(assignment)


@router.put("/{assignment_id}", response_model=AssignmentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_assignment(
    request: Request,
    assignment_id: int,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _require_course_write(db, current_user, assignment.course_id)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(assignment, key, value)

    db.commit()
    assignment = (
        db.query(Assignment)
        .options(*_assignment_eager_options())
        .filter(Assignment.id == assignment.id)
        .first()
    )
    return _to_response(assignment)


@router.delete("/{assignment_id}", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_assignment(
    request: Request,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _require_course_write(db, current_user, assignment.course_id)

    # CB-TASKSYNC-001 I7: soft-cancel linked Tasks before the Assignment row is gone.
    # Run BEFORE delete so the linked Task rows can still resolve the assignment
    # reference if needed, and to avoid any race with a concurrent sync.
    if is_feature_enabled("task_sync_enabled"):
        try:
            cancelled = handle_assignment_deleted(db, assignment.id)
            logger.info(
                "task_sync.delete_hook | cancelled=%d assignment_id=%s",
                cancelled, assignment.id,
            )
        except Exception:
            logger.exception(
                "task_sync.delete_hook | failed | assignment_id=%s", assignment.id,
            )

    db.delete(assignment)
    db.commit()
    return {"detail": "Assignment deleted"}


@router.get("/", response_model=list[AssignmentResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_assignments(
    request: Request,
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List assignments scoped to accessible courses."""
    query = db.query(Assignment)

    if course_id:
        if not can_access_course(db, current_user, course_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")
        query = query.filter(Assignment.course_id == course_id)
    else:
        accessible = _get_accessible_course_ids(db, current_user)
        if accessible is not None:  # None means admin (all access)
            query = query.filter(Assignment.course_id.in_(accessible))

    assignments = query.options(*_assignment_eager_options()).order_by(Assignment.due_date.asc().nullslast(), Assignment.created_at.desc()).all()
    return [_to_response(a) for a in assignments]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_assignment(
    request: Request,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an assignment. Must have access to its course."""
    assignment = (
        db.query(Assignment)
        .options(*_assignment_eager_options())
        .filter(Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if not can_access_course(db, current_user, assignment.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    return _to_response(assignment)


# ── Submission endpoints (#839) ─────────────────────────────

def _get_or_create_student_assignment(
    db: Session, student_id: int, assignment_id: int
) -> StudentAssignment:
    """Get or create a StudentAssignment row for the student/assignment pair."""
    sa = (
        db.query(StudentAssignment)
        .filter(
            StudentAssignment.student_id == student_id,
            StudentAssignment.assignment_id == assignment_id,
        )
        .first()
    )
    if not sa:
        sa = StudentAssignment(student_id=student_id, assignment_id=assignment_id)
        db.add(sa)
        db.flush()
    return sa


def _to_submission_response(sa: StudentAssignment) -> dict:
    """Convert StudentAssignment to submission response dict."""
    assignment = sa.assignment
    student = sa.student
    return {
        "id": sa.id,
        "student_id": sa.student_id,
        "assignment_id": sa.assignment_id,
        "status": sa.status,
        "submitted_at": sa.submitted_at,
        "grade": sa.grade,
        "submission_file_name": sa.submission_file_name,
        "submission_notes": sa.submission_notes,
        "is_late": sa.is_late or False,
        "assignment_title": assignment.title if assignment else None,
        "course_name": assignment.course.name if assignment and assignment.course else None,
        "student_name": student.user.full_name if student and student.user else None,
        "has_file": bool(sa.submission_file_path),
    }


@router.post("/{assignment_id}/submit", response_model=SubmissionResponse)
@limiter.limit("5/minute")
async def submit_assignment(
    request: Request,
    assignment_id: int,
    file: UploadFile = File(None),
    notes: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit (or resubmit) work for an assignment. Students only."""
    # Must be a student
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can submit assignments",
        )

    # Get the assignment
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    # Verify student has access to the course
    if not can_access_course(db, current_user, assignment.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    # Get student record
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    # Must provide either a file or notes
    if not file and not notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a file or notes for your submission",
        )

    # Get or create StudentAssignment
    sa = _get_or_create_student_assignment(db, student.id, assignment_id)

    # Handle file upload
    if file and file.filename:
        # Validate extension
        import os
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        file_content = await file.read()
        if len(file_content) > MAX_SUBMISSION_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds {MAX_SUBMISSION_SIZE // (1024 * 1024)} MB limit",
            )

        # Delete previous submission file if resubmitting
        if sa.submission_file_path:
            try:
                delete_file(sa.submission_file_path)
            except Exception as e:
                logger.warning("Failed to delete previous submission file %s: %s", sa.submission_file_path, e)

        stored_path = save_file(file_content, file.filename)
        sa.submission_file_path = stored_path
        sa.submission_file_name = file.filename

    # Update notes (always overwrite on resubmission)
    if notes is not None:
        sa.submission_notes = notes

    # Set status and timestamp
    now = datetime.now(timezone.utc)
    sa.status = "submitted"
    sa.submitted_at = now

    # Check late submission
    if assignment.due_date:
        due = assignment.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        sa.is_late = now > due
    else:
        sa.is_late = False

    db.commit()
    sa = (
        db.query(StudentAssignment)
        .options(*_submission_eager_options())
        .filter(StudentAssignment.id == sa.id)
        .first()
    )

    # CB-TASKSYNC-001 I7: auto-complete linked Task on submit.
    # `handle_assignment_submitted` commits internally (per I3 contract).
    if is_feature_enabled("task_sync_enabled"):
        try:
            handle_assignment_submitted(db, assignment.id, current_user.id, now)
        except Exception:
            logger.exception(
                "task_sync.submit_hook | failed | assignment_id=%s", assignment.id,
            )

    # Notify the course teacher
    try:
        course = assignment.course
        if course and course.teacher_id:
            teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
            if teacher and teacher.user_id:
                late_tag = " (late)" if sa.is_late else ""
                db.add(Notification(
                    user_id=teacher.user_id,
                    type=NotificationType.ASSIGNMENT_DUE,
                    title=f"Submission received{late_tag}",
                    content=f"{current_user.full_name} submitted \"{assignment.title}\"",
                    link=f"/courses/{course.id}",
                ))
                db.commit()
    except Exception as e:
        logger.warning("Failed to notify teacher of submission: %s", e)

    return _to_submission_response(sa)


@router.get("/{assignment_id}/submission", response_model=SubmissionResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_submission(
    request: Request,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's submission for an assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if not can_access_course(db, current_user, assignment.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    # Students see their own submission
    if current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
        sa = (
            db.query(StudentAssignment)
            .options(*_submission_eager_options())
            .filter(
                StudentAssignment.student_id == student.id,
                StudentAssignment.assignment_id == assignment_id,
            )
            .first()
        )
        if not sa:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No submission found")
        return _to_submission_response(sa)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Use /submissions endpoint for teacher/admin view",
    )


@router.get("/{assignment_id}/submissions", response_model=list[SubmissionListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_submissions(
    request: Request,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all submissions for an assignment. Teachers, course creators, and admins only."""
    assignment = (
        db.query(Assignment)
        .options(*_assignment_eager_options())
        .filter(Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    # Only teachers/creators/admins can see all submissions
    if not current_user.has_role(UserRole.ADMIN):
        course = assignment.course
        is_creator = course and course.created_by_user_id == current_user.id
        is_course_teacher = False
        if current_user.role == UserRole.TEACHER:
            teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
            if teacher and course and course.teacher_id == teacher.id:
                is_course_teacher = True
        if not is_creator and not is_course_teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the course teacher or creator can view all submissions",
            )

    submissions = (
        db.query(StudentAssignment)
        .options(*_submission_eager_options())
        .filter(StudentAssignment.assignment_id == assignment_id)
        .all()
    )

    result = []
    for sa in submissions:
        student_name = ""
        if sa.student and sa.student.user:
            student_name = sa.student.user.full_name or ""
        result.append({
            "student_id": sa.student_id,
            "student_name": student_name,
            "status": sa.status,
            "submitted_at": sa.submitted_at,
            "is_late": sa.is_late or False,
            "grade": sa.grade,
            "has_file": bool(sa.submission_file_path),
        })
    return result


@router.get("/{assignment_id}/submission/download")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def download_submission_file(
    request: Request,
    assignment_id: int,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a submission file.

    Students download their own. Teachers/admins specify student_id.
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if not can_access_course(db, current_user, assignment.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    # Determine which student's submission to download
    target_student_id = student_id
    if current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
        target_student_id = student.id
    elif not target_student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="student_id is required for non-student users",
        )

    sa = (
        db.query(StudentAssignment)
        .filter(
            StudentAssignment.student_id == target_student_id,
            StudentAssignment.assignment_id == assignment_id,
        )
        .first()
    )
    if not sa or not sa.submission_file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No submission file found")

    file_abs = get_file_path(sa.submission_file_path)
    if not file_abs.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    return FileResponse(
        path=str(file_abs),
        filename=sa.submission_file_name or sa.submission_file_path,
        media_type="application/octet-stream",
    )
