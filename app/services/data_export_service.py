"""Service for generating user data exports (PIPEDA Right of Access)."""
import json
import logging
import os
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.user import User
from app.models.student import Student, parent_students
from app.models.message import Conversation, Message
from app.models.notification import Notification
from app.models.study_guide import StudyGuide
from app.models.quiz_result import QuizResult
from app.models.task import Task
from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.teacher_communication import TeacherCommunication
from app.models.invite import Invite
from app.models.analytics import GradeRecord
from app.models.data_export import DataExportRequest

logger = logging.getLogger(__name__)

EXPORT_DIR = os.path.join(settings.upload_dir, "exports")


def _ensure_export_dir() -> None:
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _serialize_datetime(obj: object) -> object:
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _collect_user_profile(db: Session, user: User) -> dict:
    """Collect basic user profile data."""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value if user.role else None,
        "roles": user.roles,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "email_notifications": user.email_notifications,
        "assignment_reminder_days": user.assignment_reminder_days,
        "task_reminder_days": user.task_reminder_days,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _collect_student_data(db: Session, user: User) -> dict | None:
    """Collect student profile + linked parents."""
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if not student:
        return None
    return {
        "id": student.id,
        "grade_level": student.grade_level,
        "school_name": student.school_name,
        "parent_email": student.parent_email,
        "date_of_birth": student.date_of_birth,
        "phone": student.phone,
        "address": student.address,
        "city": student.city,
        "province": student.province,
        "postal_code": student.postal_code,
        "notes": student.notes,
        "created_at": student.created_at,
    }


def _collect_children_data(db: Session, user: User) -> list[dict]:
    """Collect linked children data for parent users."""
    rows = db.query(parent_students).filter(
        parent_students.c.parent_id == user.id
    ).all()
    children = []
    for row in rows:
        student = db.query(Student).filter(Student.id == row.student_id).first()
        if student and student.user:
            child_user = db.query(User).filter(User.id == student.user_id).first()
            children.append({
                "student_id": student.id,
                "name": child_user.full_name if child_user else None,
                "grade_level": student.grade_level,
                "school_name": student.school_name,
                "relationship_type": str(row.relationship_type) if row.relationship_type else None,
            })
    return children


def _collect_messages(db: Session, user: User) -> list[dict]:
    """Collect all messages sent or received by user."""
    conversations = db.query(Conversation).filter(
        (Conversation.participant_1_id == user.id) |
        (Conversation.participant_2_id == user.id)
    ).all()

    messages = []
    for conv in conversations:
        conv_messages = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(Message.created_at).all()
        for msg in conv_messages:
            messages.append({
                "conversation_id": conv.id,
                "conversation_subject": conv.subject,
                "sender_id": msg.sender_id,
                "is_sender": msg.sender_id == user.id,
                "content": msg.content,
                "is_read": msg.is_read,
                "created_at": msg.created_at,
            })
    return messages


def _collect_study_guides(db: Session, user: User) -> list[dict]:
    """Collect all study materials created by/for user."""
    guides = db.query(StudyGuide).filter(
        StudyGuide.user_id == user.id
    ).order_by(StudyGuide.created_at.desc()).all()
    return [
        {
            "id": g.id,
            "title": g.title,
            "content": g.content,
            "guide_type": g.guide_type,
            "focus_prompt": g.focus_prompt,
            "version": g.version,
            "created_at": g.created_at,
            "archived_at": g.archived_at,
        }
        for g in guides
    ]


def _collect_quiz_results(db: Session, user: User) -> list[dict]:
    """Collect quiz results."""
    results = db.query(QuizResult).filter(
        QuizResult.user_id == user.id
    ).order_by(QuizResult.completed_at.desc()).all()
    return [
        {
            "id": r.id,
            "study_guide_id": r.study_guide_id,
            "score": r.score,
            "total_questions": r.total_questions,
            "percentage": r.percentage,
            "answers_json": r.answers_json,
            "attempt_number": r.attempt_number,
            "time_taken_seconds": r.time_taken_seconds,
            "completed_at": r.completed_at,
        }
        for r in results
    ]


def _collect_tasks(db: Session, user: User) -> list[dict]:
    """Collect tasks created by or assigned to user."""
    tasks = db.query(Task).filter(
        (Task.created_by_user_id == user.id) |
        (Task.assigned_to_user_id == user.id)
    ).order_by(Task.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "due_date": t.due_date,
            "priority": t.priority,
            "category": t.category,
            "is_completed": t.is_completed,
            "completed_at": t.completed_at,
            "created_at": t.created_at,
        }
        for t in tasks
    ]


def _collect_notifications(db: Session, user: User) -> list[dict]:
    """Collect all notifications."""
    notifs = db.query(Notification).filter(
        Notification.user_id == user.id
    ).order_by(Notification.created_at.desc()).all()
    return [
        {
            "id": n.id,
            "type": n.type if n.type else None,
            "title": n.title,
            "content": n.content,
            "link": n.link,
            "read": n.read,
            "created_at": n.created_at,
        }
        for n in notifs
    ]


def _collect_courses(db: Session, user: User) -> list[dict]:
    """Collect courses the user is associated with."""
    # Check student enrollment
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if student:
        courses = db.query(Course).join(
            student_courses,
            student_courses.c.course_id == Course.id
        ).filter(
            student_courses.c.student_id == student.id
        ).all()
    else:
        courses = db.query(Course).filter(
            Course.created_by_user_id == user.id
        ).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "subject": c.subject,
            "classroom_type": c.classroom_type,
            "created_at": c.created_at,
        }
        for c in courses
    ]


def _collect_grades(db: Session, user: User) -> list[dict]:
    """Collect grade records for the user's student profile."""
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if not student:
        return []
    grades = db.query(GradeRecord).filter(
        GradeRecord.student_id == student.id
    ).order_by(GradeRecord.recorded_at.desc()).all()
    return [
        {
            "id": g.id,
            "course_id": g.course_id,
            "assignment_id": g.assignment_id,
            "grade": g.grade,
            "max_grade": g.max_grade,
            "percentage": g.percentage,
            "source": g.source,
            "recorded_at": g.recorded_at,
        }
        for g in grades
    ]


def _collect_assignments(db: Session, user: User) -> list[dict]:
    """Collect student assignment submissions."""
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if not student:
        return []
    submissions = db.query(StudentAssignment).filter(
        StudentAssignment.student_id == student.id
    ).all()
    result = []
    for sa in submissions:
        assignment = db.query(Assignment).filter(Assignment.id == sa.assignment_id).first()
        result.append({
            "assignment_title": assignment.title if assignment else None,
            "grade": sa.grade,
            "status": sa.status,
            "submitted_at": sa.submitted_at,
            "is_late": sa.is_late,
            "submission_notes": sa.submission_notes,
        })
    return result


def _collect_teacher_communications(db: Session, user: User) -> list[dict]:
    """Collect teacher communication records."""
    comms = db.query(TeacherCommunication).filter(
        TeacherCommunication.user_id == user.id
    ).order_by(TeacherCommunication.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "type": c.type if c.type else None,
            "subject": c.subject,
            "body": c.body,
            "snippet": c.snippet,
            "sender_email": c.sender_email,
            "sender_name": c.sender_name,
            "course_name": c.course_name,
            "received_at": c.received_at,
            "created_at": c.created_at,
        }
        for c in comms
    ]


def generate_export(db: Session, export_request: DataExportRequest) -> str:
    """Generate a ZIP file containing all user data.

    Returns the path to the generated ZIP file.
    """
    _ensure_export_dir()

    user = db.query(User).filter(User.id == export_request.user_id).first()
    if not user:
        raise ValueError(f"User {export_request.user_id} not found")

    # Collect all data
    export_data = {
        "export_metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user.id,
            "user_email": user.email,
            "format_version": "1.0",
        },
        "profile": _collect_user_profile(db, user),
        "student_profile": _collect_student_data(db, user),
        "children": _collect_children_data(db, user),
        "courses": _collect_courses(db, user),
        "assignments": _collect_assignments(db, user),
        "grades": _collect_grades(db, user),
        "study_guides": _collect_study_guides(db, user),
        "quiz_results": _collect_quiz_results(db, user),
        "messages": _collect_messages(db, user),
        "tasks": _collect_tasks(db, user),
        "notifications": _collect_notifications(db, user),
        "teacher_communications": _collect_teacher_communications(db, user),
    }

    # Create ZIP
    zip_filename = f"data_export_{user.id}_{export_request.download_token[:8]}.zip"
    zip_path = os.path.join(EXPORT_DIR, zip_filename)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write each section as a separate JSON file
        for section_name, section_data in export_data.items():
            if section_data is None:
                continue
            json_content = json.dumps(
                section_data, indent=2, default=_serialize_datetime, ensure_ascii=False
            )
            zf.writestr(f"{section_name}.json", json_content)

        # Include uploaded course content files if they exist
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            from app.models.course_content import CourseContent
            contents = db.query(CourseContent).join(
                Course, CourseContent.course_id == Course.id
            ).join(
                student_courses,
                student_courses.c.course_id == Course.id
            ).filter(
                student_courses.c.student_id == student.id,
                CourseContent.file_path.isnot(None)
            ).all()

            for content in contents:
                if content.file_path and os.path.exists(content.file_path):
                    archive_name = f"files/{content.original_filename or os.path.basename(content.file_path)}"
                    zf.write(content.file_path, archive_name)

    logger.info("Generated data export for user %d: %s", user.id, zip_path)
    return zip_path


def process_export_request(db: Session, export_request_id: int) -> None:
    """Process a data export request (called by background job)."""
    export_request = db.query(DataExportRequest).filter(
        DataExportRequest.id == export_request_id
    ).first()

    if not export_request:
        logger.error("Export request %d not found", export_request_id)
        return

    if export_request.status != "pending":
        logger.warning("Export request %d already processed (status=%s)",
                        export_request_id, export_request.status)
        return

    export_request.status = "processing"
    db.commit()

    try:
        zip_path = generate_export(db, export_request)
        export_request.file_path = zip_path
        export_request.status = "completed"
        export_request.completed_at = datetime.now(timezone.utc)
        export_request.expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        db.commit()

        # Send email notification
        user = db.query(User).filter(User.id == export_request.user_id).first()
        if user and user.email:
            _send_export_ready_email(user, export_request.download_token)

        logger.info("Export request %d completed successfully", export_request_id)

    except Exception as e:
        logger.error("Export request %d failed: %s", export_request_id, e)
        db.rollback()
        export_request = db.query(DataExportRequest).filter(
            DataExportRequest.id == export_request_id
        ).first()
        if export_request:
            export_request.status = "failed"
            export_request.error_message = str(e)[:500]
            db.commit()


def _send_export_ready_email(user: User, download_token: str) -> None:
    """Send email notification that export is ready for download."""
    try:
        from app.services.email_service import send_email_sync, wrap_branded_email

        download_url = f"{settings.frontend_url}/settings/data-export?token={download_token}"
        body = f"""
        <h2 style="color:#1f2937;margin:0 0 16px;">Your Data Export is Ready</h2>
        <p style="color:#4b5563;line-height:1.6;">
            Hi {user.full_name},
        </p>
        <p style="color:#4b5563;line-height:1.6;">
            Your personal data export has been generated and is ready for download.
            The download link will expire in 48 hours.
        </p>
        <div style="text-align:center;margin:24px 0;">
            <a href="{download_url}"
               style="display:inline-block;padding:12px 32px;background:#4f46e5;color:white;
                      text-decoration:none;border-radius:8px;font-weight:600;">
                Download Your Data
            </a>
        </div>
        <p style="color:#9ca3af;font-size:13px;">
            If you did not request this export, please contact support.
        </p>
        """
        html = wrap_branded_email(body)
        send_email_sync(user.email, "Your ClassBridge Data Export is Ready", html)
    except Exception as e:
        logger.warning("Failed to send export ready email to %s: %s", user.email, e)


def cleanup_expired_exports(db: Session) -> int:
    """Remove expired export files and records. Returns count of cleaned up exports."""
    now = datetime.now(timezone.utc)
    expired = db.query(DataExportRequest).filter(
        DataExportRequest.expires_at.isnot(None),
        DataExportRequest.expires_at < now,
    ).all()

    count = 0
    for export in expired:
        if export.file_path and os.path.exists(export.file_path):
            try:
                os.remove(export.file_path)
                logger.info("Removed expired export file: %s", export.file_path)
            except OSError as e:
                logger.warning("Failed to remove export file %s: %s", export.file_path, e)
        export.status = "expired"
        export.file_path = None
        count += 1

    if count:
        db.commit()
        logger.info("Cleaned up %d expired export(s)", count)

    return count
