import logging
import secrets
from datetime import datetime, timedelta, date, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import insert, or_, and_, func as sa_func

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students, student_teachers, RelationshipType
from app.models.course import Course, student_courses
from app.models.assignment import Assignment
from pydantic import BaseModel as PydanticBaseModel
from app.models.study_guide import StudyGuide
from app.models.task import Task
from app.models.message import Conversation, Message
from app.models.invite import Invite, InviteType
from app.api.deps import require_role
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, add_inspiration_to_email
from app.core.config import settings
from app.core.security import UNUSABLE_PASSWORD_HASH
from app.schemas.parent import (
    ChildSummary, ChildOverview, LinkChildRequest, CreateChildRequest,
    ChildUpdateRequest, DiscoveredChild, DiscoverChildrenResponse,
    LinkChildrenBulkRequest, ChildHighlight, ParentDashboardResponse,
    LinkTeacherRequest, LinkedTeacher,
)
from app.schemas.course import CourseResponse
from app.schemas.assignment import AssignmentResponse
from app.services.google_classroom import list_courses, list_course_students
from app.api.routes.google_classroom import _sync_courses_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parent", tags=["Parent"])


@router.get("/children", response_model=list[ChildSummary])
def list_children(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List all children linked to the current parent."""
    rows = (
        db.query(Student, parent_students.c.relationship_type)
        .options(selectinload(Student.user))
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    )

    # Batch-fetch course counts and active task counts for all children
    student_ids = [s.id for s, _ in rows]
    user_ids = [s.user_id for s, _ in rows]

    course_counts: dict[int, int] = {}
    task_counts: dict[int, int] = {}

    if student_ids:
        cc_rows = (
            db.query(student_courses.c.student_id, sa_func.count())
            .filter(student_courses.c.student_id.in_(student_ids))
            .group_by(student_courses.c.student_id)
            .all()
        )
        course_counts = {sid: cnt for sid, cnt in cc_rows}

        tc_rows = (
            db.query(Task.assigned_to_user_id, sa_func.count())
            .filter(
                Task.assigned_to_user_id.in_(user_ids),
                Task.is_completed == False,  # noqa: E712
                Task.archived_at.is_(None),
            )
            .group_by(Task.assigned_to_user_id)
            .all()
        )
        task_counts = {uid: cnt for uid, cnt in tc_rows}

    result = []
    for student, rel_type in rows:
        user = student.user
        result.append(ChildSummary(
            student_id=student.id,
            user_id=student.user_id,
            full_name=user.full_name if user else "Unknown",
            email=user.email if user else None,
            grade_level=student.grade_level,
            school_name=student.school_name,
            date_of_birth=student.date_of_birth,
            phone=student.phone,
            address=student.address,
            city=student.city,
            province=student.province,
            postal_code=student.postal_code,
            notes=student.notes,
            relationship_type=rel_type.value if rel_type else None,
            course_count=course_counts.get(student.id, 0),
            active_task_count=task_counts.get(student.user_id, 0),
        ))

    log_action(db, user_id=current_user.id, action="read", resource_type="children", details={"count": len(result)})
    db.commit()
    return result


@router.get("/dashboard", response_model=ParentDashboardResponse)
def get_parent_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Aggregated parent dashboard: children, overdue/due-today counts, unread messages, tasks."""
    from app.models.teacher import Teacher as TeacherModel

    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    # 1. Load children (eager-load user relationship)
    child_rows = (
        db.query(Student, parent_students.c.relationship_type)
        .options(selectinload(Student.user))
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    )

    children = []
    child_highlights = []
    all_assignments = []
    all_course_ids = set()

    # Pre-fetch active task counts per child user_id
    _child_user_ids = [s.user_id for s, _ in child_rows]
    _task_count_map: dict[int, int] = {}
    if _child_user_ids:
        _tc = (
            db.query(Task.assigned_to_user_id, sa_func.count())
            .filter(
                Task.assigned_to_user_id.in_(_child_user_ids),
                Task.is_completed == False,  # noqa: E712
                Task.archived_at.is_(None),
            )
            .group_by(Task.assigned_to_user_id)
            .all()
        )
        _task_count_map = {uid: cnt for uid, cnt in _tc}

    # Batch-fetch all courses for all children in one query
    _all_student_ids = [s.id for s, _ in child_rows]
    _all_courses: list[tuple[int, Course]] = []
    if _all_student_ids:
        _all_courses = (
            db.query(student_courses.c.student_id, Course)
            .join(Course, Course.id == student_courses.c.course_id)
            .filter(student_courses.c.student_id.in_(_all_student_ids))
            .all()
        )
    _courses_by_student: dict[int, list[Course]] = {}
    for sid, course in _all_courses:
        _courses_by_student.setdefault(sid, []).append(course)
        all_course_ids.add(course.id)

    # Batch-fetch all teachers referenced by courses
    _teacher_ids = {c.teacher_id for _, c in _all_courses if c.teacher_id}
    _teacher_map: dict[int, TeacherModel] = {}
    if _teacher_ids:
        _teachers = (
            db.query(TeacherModel)
            .options(selectinload(TeacherModel.user))
            .filter(TeacherModel.id.in_(_teacher_ids))
            .all()
        )
        _teacher_map = {t.id: t for t in _teachers}

    # Batch-fetch all assignments for all course_ids
    _all_assignments: list[Assignment] = []
    if all_course_ids:
        _all_assignments = (
            db.query(Assignment)
            .filter(Assignment.course_id.in_(all_course_ids))
            .order_by(Assignment.due_date.desc())
            .all()
        )
    _assignments_by_course: dict[int, list[Assignment]] = {}
    for a in _all_assignments:
        _assignments_by_course.setdefault(a.course_id, []).append(a)

    for student, rel_type in child_rows:
        user = student.user
        courses = _courses_by_student.get(student.id, [])
        course_ids = [c.id for c in courses]

        children.append(ChildSummary(
            student_id=student.id,
            user_id=student.user_id,
            full_name=user.full_name if user else "Unknown",
            email=user.email if user else None,
            grade_level=student.grade_level,
            school_name=student.school_name,
            date_of_birth=student.date_of_birth,
            phone=student.phone,
            address=student.address,
            city=student.city,
            province=student.province,
            postal_code=student.postal_code,
            notes=student.notes,
            relationship_type=rel_type.value if rel_type else None,
            course_count=len(courses),
            active_task_count=_task_count_map.get(student.user_id, 0),
        ))

        # Build courses with teacher info (using batch-fetched teacher map)
        courses_with_teachers = []
        for course in courses:
            teacher_name = None
            teacher_email = None
            if course.teacher_id:
                teacher = _teacher_map.get(course.teacher_id)
                if teacher:
                    if teacher.is_shadow:
                        teacher_name = teacher.full_name
                        teacher_email = teacher.google_email
                    elif teacher.user:
                        teacher_name = teacher.user.full_name
                        teacher_email = teacher.user.email
            courses_with_teachers.append({
                "id": course.id, "name": course.name,
                "description": course.description, "subject": course.subject,
                "google_classroom_id": course.google_classroom_id,
                "teacher_id": course.teacher_id, "created_at": course.created_at,
                "teacher_name": teacher_name, "teacher_email": teacher_email,
            })

        # Get assignments for this child's courses (from batch-fetched data)
        child_assignments = []
        for cid in course_ids:
            child_assignments.extend(_assignments_by_course.get(cid, []))
        all_assignments.extend(child_assignments)

        # Count overdue/due-today assignments
        overdue_items = []
        due_today_items = []
        for a in child_assignments:
            if not a.due_date:
                continue
            course = next((c for c in courses if c.id == a.course_id), None)
            item = {"title": a.title, "type": "assignment", "course_name": course.name if course else "", "due_date": str(a.due_date)}
            if a.due_date < today_start:
                overdue_items.append(item)
            elif today_start <= a.due_date < today_end:
                due_today_items.append(item)

        child_highlights.append(ChildHighlight(
            student_id=student.id,
            user_id=student.user_id,
            full_name=user.full_name if user else "Unknown",
            grade_level=student.grade_level,
            overdue_count=len(overdue_items),
            due_today_count=len(due_today_items),
            courses=courses_with_teachers,
            overdue_items=overdue_items,
            due_today_items=due_today_items,
        ))

    # 2. Get tasks (created by or assigned to parent, plus assigned to children)
    child_user_ids = [c.user_id for c in children]
    task_filters = [
        Task.created_by_user_id == current_user.id,
        Task.assigned_to_user_id == current_user.id,
    ]
    if child_user_ids:
        task_filters.append(Task.assigned_to_user_id.in_(child_user_ids))

    tasks = (
        db.query(Task)
        .filter(or_(*task_filters), Task.archived_at.is_(None))
        .all()
    )

    # Count overdue tasks and add to highlights
    total_overdue = sum(h.overdue_count for h in child_highlights)
    total_due_today = sum(h.due_today_count for h in child_highlights)
    for t in tasks:
        if t.is_completed:
            continue
        if t.due_date and t.due_date < today_start:
            total_overdue += 1
        elif t.due_date and today_start <= t.due_date < today_end:
            total_due_today += 1

    # Build task response dicts — batch-fetch all user IDs referenced by tasks
    _task_user_ids = set()
    for t in tasks:
        _task_user_ids.add(t.created_by_user_id)
        if t.assigned_to_user_id:
            _task_user_ids.add(t.assigned_to_user_id)
    _task_user_map: dict[int, User] = {}
    if _task_user_ids:
        for u in db.query(User).filter(User.id.in_(_task_user_ids)).all():
            _task_user_map[u.id] = u

    task_dicts = []
    for t in tasks:
        creator = _task_user_map.get(t.created_by_user_id)
        assignee = _task_user_map.get(t.assigned_to_user_id) if t.assigned_to_user_id else None
        raw_priority = t.priority
        if hasattr(raw_priority, "value"):
            raw_priority = raw_priority.value
        normalized = str(raw_priority).lower() if raw_priority else "medium"
        if normalized not in {"low", "medium", "high"}:
            normalized = "medium"
        task_dicts.append({
            "id": t.id, "title": t.title, "description": t.description,
            "due_date": str(t.due_date) if t.due_date else None,
            "is_completed": t.is_completed, "completed_at": str(t.completed_at) if t.completed_at else None,
            "archived_at": str(t.archived_at) if t.archived_at else None,
            "priority": normalized, "category": t.category,
            "created_by_user_id": t.created_by_user_id,
            "assigned_to_user_id": t.assigned_to_user_id,
            "creator_name": creator.full_name if creator else "Unknown",
            "assignee_name": assignee.full_name if assignee else None,
            "course_id": t.course_id, "course_content_id": t.course_content_id,
            "study_guide_id": t.study_guide_id,
            "created_at": str(t.created_at) if t.created_at else None,
            "updated_at": str(t.updated_at) if t.updated_at else None,
        })

    # 3. Unread messages
    conversations = (
        db.query(Conversation)
        .filter(or_(
            Conversation.participant_1_id == current_user.id,
            Conversation.participant_2_id == current_user.id,
        ))
        .all()
    )
    conv_ids = [c.id for c in conversations]
    unread_messages = 0
    if conv_ids:
        unread_messages = (
            db.query(Message)
            .filter(
                Message.conversation_id.in_(conv_ids),
                Message.sender_id != current_user.id,
                Message.is_read == False,
            )
            .count()
        )

    # 4. Google status
    google_connected = bool(current_user.google_access_token)

    return ParentDashboardResponse(
        children=children,
        google_connected=google_connected,
        unread_messages=unread_messages,
        total_overdue=total_overdue,
        total_due_today=total_due_today,
        total_tasks=len(tasks),
        child_highlights=child_highlights,
        all_assignments=all_assignments,
        all_tasks=task_dicts,
    )


@router.post("/children/create", response_model=ChildSummary)
def create_child(
    request: CreateChildRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Create a new child (student) with just a name. Email is optional."""
    invite_link = None

    # If email is provided, check it's not already taken by a non-student
    if request.email:
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="An account with this email already exists. Use 'Link Child' instead.")

    # Create student user (email may be None)
    student_user = User(
        email=request.email,
        hashed_password=UNUSABLE_PASSWORD_HASH,
        full_name=request.full_name,
        role=UserRole.STUDENT,
    )
    db.add(student_user)
    db.flush()

    # Create invite if email is provided so child can set their password
    if request.email:
        token = secrets.token_urlsafe(32)
        invite = Invite(
            email=request.email,
            invite_type=InviteType.STUDENT,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            invited_by_user_id=current_user.id,
            metadata_json={"relationship_type": request.relationship_type},
        )
        db.add(invite)
        db.flush()
        invite_link = f"{settings.frontend_url}/accept-invite?token={token}"

        # Send invite email to the child
        try:
            invite_html = f"""
                <h2>You've been invited to ClassBridge</h2>
                <p><strong>{current_user.full_name}</strong> has added you as a student on ClassBridge.</p>
                <p>Click the link below to set your password and get started:</p>
                <p><a href="{invite_link}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">Create My Account</a></p>
                <p style="color:#666;font-size:14px;">This invite expires in 30 days.</p>
                """
            invite_html = add_inspiration_to_email(invite_html, db, "student")
            send_email_sync(
                to_email=request.email,
                subject=f"{current_user.full_name} invited you to ClassBridge",
                html_content=invite_html,
            )
        except Exception as e:
            logger.warning(f"Failed to send invite email to {request.email}: {e}")

    # Create Student record
    student = Student(user_id=student_user.id)
    db.add(student)
    db.flush()

    # Link parent to student
    rel_type = RelationshipType(request.relationship_type)
    db.execute(
        insert(parent_students).values(
            parent_id=current_user.id,
            student_id=student.id,
            relationship_type=rel_type,
        )
    )
    db.commit()

    return ChildSummary(
        student_id=student.id,
        user_id=student.user_id,
        full_name=student_user.full_name,
        email=student_user.email,
        grade_level=student.grade_level,
        school_name=student.school_name,
        relationship_type=rel_type.value,
        invite_link=invite_link,
    )


@router.post("/children/link", response_model=ChildSummary)
def link_child(
    request: LinkChildRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Link a student to the current parent by email. Auto-creates student if not found."""
    invite_link = None

    # Look for existing user with this email
    existing_user = db.query(User).filter(User.email == request.student_email).first()

    if existing_user and existing_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=400,
            detail="This email belongs to a non-student account",
        )

    if existing_user:
        student_user = existing_user
    else:
        # Auto-create student account (no password — child sets it via invite link)
        full_name = request.full_name or request.student_email.split("@")[0]
        student_user = User(
            email=request.student_email,
            hashed_password=UNUSABLE_PASSWORD_HASH,
            full_name=full_name,
            role=UserRole.STUDENT,
        )
        db.add(student_user)
        db.flush()

        # Create invite so child can set their password
        token = secrets.token_urlsafe(32)
        invite = Invite(
            email=request.student_email,
            invite_type=InviteType.STUDENT,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            invited_by_user_id=current_user.id,
            metadata_json={"relationship_type": request.relationship_type},
        )
        db.add(invite)
        db.flush()
        invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
        logger.info(f"Auto-created student account for {request.student_email}, invite token generated")

        # Send invite email to the child
        try:
            invite_html = f"""
                <h2>You've been invited to ClassBridge</h2>
                <p><strong>{current_user.full_name}</strong> has added you as a student on ClassBridge.</p>
                <p>Click the link below to set your password and get started:</p>
                <p><a href="{invite_link}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">Create My Account</a></p>
                <p style="color:#666;font-size:14px;">This invite expires in 30 days.</p>
                """
            invite_html = add_inspiration_to_email(invite_html, db, "student")
            send_email_sync(
                to_email=request.student_email,
                subject=f"{current_user.full_name} invited you to ClassBridge",
                html_content=invite_html,
            )
        except Exception as e:
            logger.warning(f"Failed to send invite email to {request.student_email}: {e}")

    # Find or create the Student record
    student = db.query(Student).filter(Student.user_id == student_user.id).first()
    if not student:
        student = Student(user_id=student_user.id)
        db.add(student)
        db.flush()

    # Check if already linked to this parent
    existing_link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student.id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(status_code=400, detail="This student is already linked to your account")

    # Insert into join table
    rel_type = RelationshipType(request.relationship_type)
    db.execute(
        insert(parent_students).values(
            parent_id=current_user.id,
            student_id=student.id,
            relationship_type=rel_type,
        )
    )
    db.commit()

    return ChildSummary(
        student_id=student.id,
        user_id=student.user_id,
        full_name=student_user.full_name,
        email=student_user.email,
        grade_level=student.grade_level,
        school_name=student.school_name,
        relationship_type=rel_type.value,
        invite_link=invite_link,
    )


@router.post("/children/discover-google", response_model=DiscoverChildrenResponse)
def discover_children_google(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Discover children via Google Classroom courses."""
    if not current_user.google_access_token:
        return DiscoverChildrenResponse(discovered=[], google_connected=False, courses_searched=0)

    logger.info(f"Parent {current_user.id} ({current_user.email}) starting Google discovery, has_refresh_token={bool(current_user.google_refresh_token)}")
    try:
        courses, credentials = list_courses(
            current_user.google_access_token,
            current_user.google_refresh_token,
        )
        logger.info(f"Parent {current_user.id} found {len(courses)} Google Classroom courses")
    except Exception as e:
        logger.warning(f"Failed to list Google courses for parent {current_user.id}: {e}", exc_info=True)
        return DiscoverChildrenResponse(discovered=[], google_connected=True, courses_searched=0)

    # Update tokens if refreshed
    if credentials.token != current_user.google_access_token:
        current_user.google_access_token = credentials.token
        if credentials.refresh_token:
            current_user.google_refresh_token = credentials.refresh_token
        db.commit()

    # Collect student emails from all courses
    student_emails: dict[str, list[str]] = {}  # email -> list of course names
    student_names: dict[str, str] = {}  # email -> full name from Google profile
    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name", "Unknown Course")
        if not course_id:
            continue
        try:
            students, credentials = list_course_students(
                current_user.google_access_token,
                course_id,
                current_user.google_refresh_token,
            )
            for s in students:
                profile = s.get("profile", {})
                email = profile.get("emailAddress", "").lower()
                if email:
                    student_emails.setdefault(email, []).append(course_name)
                    if email not in student_names:
                        name = profile.get("name", {})
                        full_name = name.get("fullName", "") or email.split("@")[0]
                        student_names[email] = full_name
        except Exception as e:
            logger.warning(f"Failed to list students for course {course_id}: {e}")
            continue

    if not student_emails:
        return DiscoverChildrenResponse(discovered=[], google_connected=True, courses_searched=len(courses))

    # Match against existing student users
    matched_users = (
        db.query(User)
        .filter(User.email.in_(list(student_emails.keys())), User.role == UserRole.STUDENT)
        .all()
    )
    matched_emails = {u.email.lower() for u in matched_users}

    # Auto-create student accounts for emails not yet in ClassBridge
    unmatched_emails = set(student_emails.keys()) - matched_emails
    for email in unmatched_emails:
        # Skip if a non-student user already has this email
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            continue

        full_name = student_names.get(email, email.split("@")[0])
        new_user = User(
            email=email,
            hashed_password=UNUSABLE_PASSWORD_HASH,
            full_name=full_name,
            role=UserRole.STUDENT,
        )
        db.add(new_user)
        db.flush()

        new_student = Student(user_id=new_user.id)
        db.add(new_student)
        db.flush()

        # Create invite so child can set their password
        token = secrets.token_urlsafe(32)
        invite = Invite(
            email=email,
            invite_type=InviteType.STUDENT,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            invited_by_user_id=current_user.id,
            metadata_json={"relationship_type": "guardian"},
        )
        db.add(invite)
        db.flush()
        logger.info(f"Auto-created student account for {email} via Google Classroom discovery")

        matched_users.append(new_user)

    db.commit()

    discovered = []
    for user in matched_users:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        already_linked = False
        if student:
            existing_link = (
                db.query(parent_students)
                .filter(
                    parent_students.c.parent_id == current_user.id,
                    parent_students.c.student_id == student.id,
                )
                .first()
            )
            already_linked = existing_link is not None

        discovered.append(DiscoveredChild(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            google_courses=student_emails.get(user.email.lower(), []),
            already_linked=already_linked,
        ))

    return DiscoverChildrenResponse(
        discovered=discovered,
        google_connected=True,
        courses_searched=len(courses),
    )


@router.post("/children/link-bulk", response_model=list[ChildSummary])
def link_children_bulk(
    request: LinkChildrenBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Link multiple students to the current parent."""
    rel_type = RelationshipType(request.relationship_type)
    linked = []
    for user_id in request.user_ids:
        student_user = (
            db.query(User)
            .filter(User.id == user_id, User.role == UserRole.STUDENT)
            .first()
        )
        if not student_user:
            continue

        student = db.query(Student).filter(Student.user_id == user_id).first()
        if not student:
            student = Student(user_id=user_id)
            db.add(student)
            db.flush()

        # Skip if already linked
        existing_link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student.id,
            )
            .first()
        )
        if existing_link:
            continue

        db.execute(
            insert(parent_students).values(
                parent_id=current_user.id,
                student_id=student.id,
                relationship_type=rel_type,
            )
        )
        db.flush()

        linked.append(ChildSummary(
            student_id=student.id,
            user_id=student.user_id,
            full_name=student_user.full_name,
            email=student_user.email,
            grade_level=student.grade_level,
            school_name=student.school_name,
            relationship_type=rel_type.value,
        ))

    db.commit()
    return linked


@router.get("/children/{student_id}/overview", response_model=ChildOverview)
def get_child_overview(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get detailed overview of a linked child's courses, assignments, and study materials."""
    # Verify parent-student link exists
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get child's courses via student_courses join table
    courses = (
        db.query(Course)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(student_courses.c.student_id == student.id)
        .all()
    )

    # Get assignments for those courses
    course_ids = [c.id for c in courses]
    assignments = []
    if course_ids:
        assignments = (
            db.query(Assignment)
            .filter(Assignment.course_id.in_(course_ids))
            .order_by(Assignment.due_date.desc())
            .all()
        )

    # Count study guides for the child's user account
    study_guides_count = (
        db.query(StudyGuide)
        .filter(StudyGuide.user_id == student.user_id)
        .count()
    )

    # Batch-fetch teachers for all courses
    from app.models.teacher import Teacher as TeacherModel
    _t_ids = {c.teacher_id for c in courses if c.teacher_id}
    _t_map: dict[int, TeacherModel] = {}
    if _t_ids:
        for t in db.query(TeacherModel).options(selectinload(TeacherModel.user)).filter(TeacherModel.id.in_(_t_ids)).all():
            _t_map[t.id] = t

    courses_with_teachers = []
    for course in courses:
        teacher_name = None
        teacher_email = None
        if course.teacher_id:
            teacher = _t_map.get(course.teacher_id)
            if teacher:
                if teacher.is_shadow:
                    teacher_name = teacher.full_name
                    teacher_email = teacher.google_email
                elif teacher.user:
                    teacher_name = teacher.user.full_name
                    teacher_email = teacher.user.email
        courses_with_teachers.append({
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "subject": course.subject,
            "google_classroom_id": course.google_classroom_id,
            "teacher_id": course.teacher_id,
            "created_at": course.created_at,
            "teacher_name": teacher_name,
            "teacher_email": teacher_email,
        })

    user = student.user
    google_connected = bool(user.google_access_token) if user else False
    log_action(db, user_id=current_user.id, action="read", resource_type="student", resource_id=student_id)
    db.commit()
    return ChildOverview(
        student_id=student.id,
        user_id=student.user_id,
        full_name=user.full_name if user else "Unknown",
        grade_level=student.grade_level,
        google_connected=google_connected,
        courses=courses_with_teachers,
        assignments=assignments,
        study_guides_count=study_guides_count,
    )


@router.patch("/children/{student_id}", response_model=ChildSummary)
def update_child(
    student_id: int,
    request: ChildUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Update a linked child's profile information."""
    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    user = student.user

    if request.full_name is not None and user:
        user.full_name = request.full_name
    if request.email is not None and user:
        # Check email uniqueness
        existing = db.query(User).filter(User.email == request.email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use by another account")
        user.email = request.email
    if request.grade_level is not None:
        student.grade_level = request.grade_level
    if request.school_name is not None:
        student.school_name = request.school_name
    if request.date_of_birth is not None:
        student.date_of_birth = request.date_of_birth
    if request.phone is not None:
        student.phone = request.phone
    if request.address is not None:
        student.address = request.address
    if request.city is not None:
        student.city = request.city
    if request.province is not None:
        student.province = request.province
    if request.postal_code is not None:
        student.postal_code = request.postal_code
    if request.notes is not None:
        student.notes = request.notes

    db.commit()
    db.refresh(student)

    return ChildSummary(
        student_id=student.id,
        user_id=student.user_id,
        full_name=user.full_name if user else "Unknown",
        email=user.email if user else None,
        grade_level=student.grade_level,
        school_name=student.school_name,
        date_of_birth=student.date_of_birth,
        phone=student.phone,
        address=student.address,
        city=student.city,
        province=student.province,
        postal_code=student.postal_code,
        notes=student.notes,
        relationship_type=link.relationship_type.value if link.relationship_type else None,
    )


@router.post("/children/{student_id}/sync-courses")
def sync_child_courses(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Trigger course sync for a linked child using the child's Google tokens."""
    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    child_user = student.user
    if not child_user or not child_user.google_access_token:
        raise HTTPException(status_code=400, detail="Child has not connected Google Classroom yet")

    synced = _sync_courses_for_user(child_user, db)
    return {
        "message": f"Synced {len(synced)} courses for {child_user.full_name}",
        "courses": synced,
    }


class AssignCoursesRequest(PydanticBaseModel):
    course_ids: list[int]


@router.post("/children/{student_id}/courses")
def assign_courses_to_child(
    student_id: int,
    request: AssignCoursesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Assign courses to a linked child. Parent must own the courses or they must be public."""
    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    assigned = []
    for course_id in request.course_ids:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            continue

        # Parent can assign their own courses or public courses
        if course.is_private and course.created_by_user_id != current_user.id:
            continue

        # Check if already enrolled
        existing = (
            db.query(student_courses)
            .filter(
                student_courses.c.student_id == student.id,
                student_courses.c.course_id == course.id,
            )
            .first()
        )
        if existing:
            continue

        db.execute(
            insert(student_courses).values(
                student_id=student.id,
                course_id=course.id,
            )
        )
        assigned.append({"course_id": course.id, "course_name": course.name})

    db.commit()
    return {"message": f"Assigned {len(assigned)} courses", "assigned": assigned}


@router.delete("/children/{student_id}/courses/{course_id}")
def unassign_course_from_child(
    student_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Remove a course from a linked child."""
    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    from sqlalchemy import delete
    result = db.execute(
        delete(student_courses).where(
            student_courses.c.student_id == student.id,
            student_courses.c.course_id == course_id,
        )
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Course not assigned to this student")

    return {"message": "Course removed from student"}


# ── Teacher Linking ─────────────────────────────────────────────


@router.post("/children/{student_id}/teachers", response_model=LinkedTeacher)
def link_teacher_to_child(
    student_id: int,
    request: LinkTeacherRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Link a teacher to a child by email so the parent can message them directly."""
    import os
    from app.models.teacher import Teacher
    from app.models.notification import Notification, NotificationType

    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get child's display name
    child_user = db.query(User).filter(User.id == student.user_id).first()
    child_name = child_user.full_name if child_user else "your child"

    # Find teacher user by email
    teacher_user = db.query(User).filter(User.email == request.teacher_email).first()
    teacher_user_id = teacher_user.id if teacher_user else None
    teacher_name = request.teacher_name

    if teacher_user:
        # If the user exists, use their name unless overridden
        if not teacher_name:
            teacher_name = teacher_user.full_name
        # Must be a teacher role
        if not teacher_user.has_role(UserRole.TEACHER):
            raise HTTPException(status_code=400, detail="This user is not a teacher")

    # Check if already linked
    existing = (
        db.query(student_teachers)
        .filter(
            student_teachers.c.student_id == student_id,
            student_teachers.c.teacher_email == request.teacher_email,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="This teacher is already linked to this child")

    # Insert the link
    db.execute(
        insert(student_teachers).values(
            student_id=student_id,
            teacher_user_id=teacher_user_id,
            teacher_name=teacher_name or request.teacher_email.split("@")[0],
            teacher_email=request.teacher_email,
            added_by_user_id=current_user.id,
        )
    )
    db.commit()

    # Get the inserted row
    row = (
        db.query(student_teachers)
        .filter(
            student_teachers.c.student_id == student_id,
            student_teachers.c.teacher_email == request.teacher_email,
        )
        .first()
    )

    log_action(db, user_id=current_user.id, action="create", resource_type="student_teacher_link",
               details={"student_id": student_id, "teacher_email": request.teacher_email})
    db.commit()

    # ── Email handling ─────────────────────────────────────────
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")

    if teacher_user:
        # Teacher exists → send notification email + in-app notification
        try:
            tpl_path = os.path.join(template_dir, "teacher_linked_notification.html")
            with open(tpl_path, "r") as f:
                html = f.read()
            html = (html
                .replace("{{teacher_name}}", teacher_user.full_name)
                .replace("{{parent_name}}", current_user.full_name)
                .replace("{{child_name}}", child_name)
                .replace("{{app_url}}", settings.frontend_url))
            html = add_inspiration_to_email(html, db, "teacher")
            send_email_sync(
                to_email=teacher_user.email,
                subject=f"{current_user.full_name} connected with you on ClassBridge",
                html_content=html,
            )
            logger.info(f"Teacher linked notification email sent to {teacher_user.email}")
        except Exception as e:
            logger.warning(f"Failed to send teacher linked notification: {e}")

        # In-app notification
        try:
            db.add(Notification(
                user_id=teacher_user.id,
                type=NotificationType.SYSTEM,
                title="New Parent Connection",
                content=f"{current_user.full_name} linked you as a teacher for {child_name}",
                link="/messages",
            ))
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to create teacher notification: {e}")
    else:
        # Teacher not in system → create invite + send invitation email
        try:
            # Check for existing pending invite
            existing_invite = (
                db.query(Invite)
                .filter(
                    Invite.email == request.teacher_email,
                    Invite.invite_type == InviteType.TEACHER,
                    Invite.accepted_at.is_(None),
                    Invite.expires_at > datetime.now(timezone.utc),
                )
                .first()
            )
            if not existing_invite:
                token = secrets.token_urlsafe(32)
                invite = Invite(
                    email=request.teacher_email,
                    invite_type=InviteType.TEACHER,
                    token=token,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    invited_by_user_id=current_user.id,
                    metadata_json={"student_id": student_id, "child_name": child_name},
                )
                db.add(invite)
                db.commit()

                invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
            else:
                invite_link = f"{settings.frontend_url}/accept-invite?token={existing_invite.token}"

            tpl_path = os.path.join(template_dir, "teacher_invite.html")
            with open(tpl_path, "r") as f:
                html = f.read()
            html = (html
                .replace("{{parent_name}}", current_user.full_name)
                .replace("{{child_name}}", child_name)
                .replace("{{invite_link}}", invite_link))
            html = add_inspiration_to_email(html, db, "teacher")
            send_email_sync(
                to_email=request.teacher_email,
                subject=f"{current_user.full_name} invited you to ClassBridge",
                html_content=html,
            )
            logger.info(f"Teacher invite email sent to {request.teacher_email}")
        except Exception as e:
            logger.warning(f"Failed to send teacher invite email: {e}")

    return LinkedTeacher(
        id=row.id,
        student_id=row.student_id,
        teacher_user_id=row.teacher_user_id,
        teacher_name=row.teacher_name,
        teacher_email=row.teacher_email,
        added_by_user_id=row.added_by_user_id,
        created_at=row.created_at,
    )


@router.get("/children/{student_id}/teachers", response_model=list[LinkedTeacher])
def list_linked_teachers(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List all teachers manually linked to a child."""
    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    rows = (
        db.query(student_teachers)
        .filter(student_teachers.c.student_id == student_id)
        .all()
    )

    return [
        LinkedTeacher(
            id=r.id,
            student_id=r.student_id,
            teacher_user_id=r.teacher_user_id,
            teacher_name=r.teacher_name,
            teacher_email=r.teacher_email,
            added_by_user_id=r.added_by_user_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/children/{student_id}/teachers/{link_id}")
def unlink_teacher_from_child(
    student_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Remove a manually linked teacher from a child."""
    from sqlalchemy import delete

    # Verify parent-student link
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    result = db.execute(
        delete(student_teachers).where(
            student_teachers.c.id == link_id,
            student_teachers.c.student_id == student_id,
        )
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Teacher link not found")

    log_action(db, user_id=current_user.id, action="delete", resource_type="student_teacher_link",
               details={"student_id": student_id, "link_id": link_id})
    db.commit()

    return {"message": "Teacher unlinked from student"}
