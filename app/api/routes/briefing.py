"""Daily Briefing endpoint for parents."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.task import Task
from app.models.user import User, UserRole
from app.api.deps import require_role
from app.schemas.briefing import (
    DailyBriefingResponse,
    HelpMyKidRequest,
    HelpMyKidResponse,
)
from app.services.ai_service import generate_study_guide
from app.services.ai_usage import check_ai_usage, increment_ai_usage
from app.services.audit_service import log_action
from app.services.briefing_service import get_daily_briefing

logger = get_logger(__name__)

router = APIRouter(prefix="/briefing", tags=["Briefing"])


@router.get("/daily", response_model=DailyBriefingResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def daily_briefing(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get the daily briefing for a parent — overdue tasks, due today, upcoming assignments per child."""
    return get_daily_briefing(db, current_user.id)


@router.post("/help-my-kid", response_model=HelpMyKidResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def help_my_kid(
    request: Request,
    body: HelpMyKidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Generate a study guide for a parent's child from an overdue/due-today item."""

    # 1. Verify the parent owns this child
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == body.student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=403, detail="This student is not linked to your account")

    # Get the student's user_id (the study guide will be created for the student)
    student = db.query(Student).filter(Student.id == body.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Look up the task or assignment
    title = "Study Guide"
    description = ""
    course_name = "General"
    due_date: str | None = None
    assignment_id: int | None = None
    course_id: int | None = None

    if body.item_type == "task":
        task = db.query(Task).filter(Task.id == body.item_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        title = f"Study Guide: {task.title}"
        description = task.description or task.title
        due_date = str(task.due_date) if task.due_date else None
        course_id = task.course_id
        if task.course_id:
            course = db.query(Course).filter(Course.id == task.course_id).first()
            if course:
                course_name = course.name

    elif body.item_type == "assignment":
        assignment = db.query(Assignment).filter(Assignment.id == body.item_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        title = f"Study Guide: {assignment.title}"
        description = assignment.description or assignment.title
        due_date = str(assignment.due_date) if assignment.due_date else None
        assignment_id = assignment.id
        course_id = assignment.course_id
        if assignment.course_id:
            course = db.query(Course).filter(Course.id == assignment.course_id).first()
            if course:
                course_name = course.name
    else:
        raise HTTPException(status_code=400, detail="item_type must be 'task' or 'assignment'")

    # 3. Check AI usage for the parent
    check_ai_usage(current_user, db)

    # 4. Generate the study guide via AI
    try:
        content = await generate_study_guide(
            assignment_title=title,
            assignment_description=description,
            course_name=course_name,
            due_date=due_date,
        )
    except Exception as e:
        logger.error("Help My Kid study guide generation failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"AI generation failed: {type(e).__name__}")

    # 5. Save the study guide for the student
    increment_ai_usage(current_user, db, generation_type="study_guide")

    study_guide = StudyGuide(
        user_id=student.user_id,
        assignment_id=assignment_id,
        course_id=course_id,
        title=title,
        content=content,
        guide_type="study_guide",
    )
    db.add(study_guide)
    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="create",
        resource_type="study_guide",
        resource_id=study_guide.id,
        details={"source": "help_my_kid", "student_id": body.student_id},
    )
    db.commit()
    db.refresh(study_guide)

    return HelpMyKidResponse(study_guide_id=study_guide.id, title=study_guide.title)
