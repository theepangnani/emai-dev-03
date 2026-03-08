"""Routes for the 'Is My Kid Ready?' Readiness Assessment feature."""

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.models.notification import Notification, NotificationType
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.api.deps import require_role, get_current_user
from app.schemas.readiness import (
    ReadinessCheckCreate,
    ReadinessCheckResponse,
    ReadinessQuestion,
    ReadinessSubmitRequest,
    ReadinessReportResponse,
    ReadinessListItem,
    TopicBreakdown,
    AnswerSubmission,
)
from app.services.ai_service import generate_content
from app.services.ai_usage import check_ai_usage, increment_ai_usage

logger = get_logger(__name__)

router = APIRouter(prefix="/readiness-check", tags=["Readiness Assessment"])


def _verify_parent_child(db: Session, parent_id: int, student_id: int) -> tuple[Student, User]:
    """Verify parent-child link and return (Student, child_user)."""
    row = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(
            parent_students.c.parent_id == parent_id,
            Student.id == student_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found or not linked to your account")
    return row


def _verify_student_course(db: Session, student_id: int, course_id: int) -> Course:
    """Verify student is enrolled in the course."""
    course = (
        db.query(Course)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(
            student_courses.c.student_id == student_id,
            Course.id == course_id,
        )
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or student not enrolled")
    return course


def _get_course_content_text(db: Session, course_id: int) -> str:
    """Gather course content text for AI prompt context."""
    contents = (
        db.query(CourseContent)
        .filter(
            CourseContent.course_id == course_id,
            CourseContent.archived_at.is_(None),
        )
        .order_by(CourseContent.created_at.desc())
        .limit(5)
        .all()
    )
    if not contents:
        return ""
    parts = []
    for c in contents:
        parts.append(f"Title: {c.title}\n{c.content[:2000] if c.content else ''}")
    return "\n---\n".join(parts)


@router.post("", response_model=ReadinessCheckResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def create_readiness_check(
    request: Request,
    body: ReadinessCheckCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Parent creates a readiness assessment for their child."""
    # Verify parent-child link
    student, child_user = _verify_parent_child(db, current_user.id, body.student_id)

    # Verify student enrolled in course
    course = _verify_student_course(db, student.id, body.course_id)

    # Check AI credits
    check_ai_usage(current_user, db)

    # Gather course content for context
    content_text = _get_course_content_text(db, course.id)

    topic_instruction = ""
    if body.topic:
        topic_instruction = f"\nFocus the questions specifically on: {body.topic}"

    prompt = f"""Generate exactly 5 diagnostic assessment questions for a student in the course "{course.name}".
{topic_instruction}

Course content for context:
{content_text[:4000] if content_text else "No specific course materials available. Generate grade-appropriate questions for this course topic."}

Create exactly:
- 2 multiple choice questions (4 options each, labeled A/B/C/D)
- 2 short answer questions
- 1 application/scenario question

Return ONLY valid JSON in this format:
[
  {{
    "id": 1,
    "type": "multiple_choice",
    "question": "Question text?",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"]
  }},
  {{
    "id": 2,
    "type": "multiple_choice",
    "question": "Question text?",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"]
  }},
  {{
    "id": 3,
    "type": "short_answer",
    "question": "Question text?"
  }},
  {{
    "id": 4,
    "type": "short_answer",
    "question": "Question text?"
  }},
  {{
    "id": 5,
    "type": "application",
    "question": "Scenario or application question text?"
  }}
]

Return ONLY the JSON array."""

    system_prompt = (
        "You are an expert educational assessment designer. Create clear, age-appropriate "
        "diagnostic questions that accurately gauge a student's understanding of the material. "
        "Questions should range from basic recall to higher-order thinking. Always return valid JSON."
    )

    raw = await generate_content(prompt, system_prompt, max_tokens=1500, temperature=0.5)

    # Parse the JSON from AI response
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        questions_data = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error("Failed to parse AI readiness questions: %s | raw=%s", e, raw[:200])
        raise HTTPException(status_code=500, detail="Failed to generate assessment questions. Please try again.")

    # Save as study guide with guide_type='readiness'
    guide = StudyGuide(
        user_id=child_user.id,
        course_id=course.id,
        title=f"Readiness Check: {course.name}" + (f" - {body.topic}" if body.topic else ""),
        content=json.dumps({
            "questions": questions_data,
            "parent_user_id": current_user.id,
            "student_id": student.id,
            "topic": body.topic,
        }),
        guide_type="readiness",
    )
    db.add(guide)
    db.flush()

    # Create notification for student
    notification = Notification(
        user_id=child_user.id,
        type=NotificationType.SYSTEM,
        title="New Readiness Check",
        content=f"Your parent has created a readiness check for {course.name}. Please complete it!",
        link=f"/readiness-check/{guide.id}",
    )
    db.add(notification)

    # Deduct AI credits
    increment_ai_usage(current_user, db, generation_type="readiness_check")

    questions = [
        ReadinessQuestion(
            id=q["id"],
            type=q["type"],
            question=q["question"],
            options=q.get("options"),
        )
        for q in questions_data
    ]

    return ReadinessCheckResponse(
        id=guide.id,
        student_id=student.id,
        course_id=course.id,
        topic=body.topic,
        questions=questions,
        created_at=guide.created_at,
    )


@router.post("/{assessment_id}/submit")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def submit_readiness_check(
    request: Request,
    assessment_id: int,
    body: ReadinessSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student submits answers to a readiness assessment."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == assessment_id,
        StudyGuide.guide_type == "readiness",
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Verify the current user is the student assigned
    if guide.user_id != current_user.id:
        # Also allow the parent who created it
        data = json.loads(guide.content)
        if data.get("parent_user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to submit this assessment")

    data = json.loads(guide.content)
    if data.get("report"):
        raise HTTPException(status_code=400, detail="Assessment already submitted")

    questions = data["questions"]

    # Check AI credits for the student (or parent)
    check_ai_usage(current_user, db)

    # Build evaluation prompt
    qa_text = ""
    for ans in body.answers:
        q = next((q for q in questions if q["id"] == ans.question_id), None)
        if q:
            qa_text += f"\nQuestion {q['id']} ({q['type']}): {q['question']}\nStudent Answer: {ans.answer}\n"

    course = db.query(Course).filter(Course.id == guide.course_id).first()
    course_name = course.name if course else "Unknown Course"

    prompt = f"""Evaluate a student's answers on a readiness assessment for "{course_name}".
{f'Topic focus: {data.get("topic")}' if data.get("topic") else ''}

Questions and Answers:
{qa_text}

Provide a detailed gap analysis. Return ONLY valid JSON:
{{
  "overall_score": <1-5 integer>,
  "summary": "2-3 sentence overall assessment",
  "topic_breakdown": [
    {{
      "topic": "Topic area name",
      "score": <1-5>,
      "status": "strong|developing|needs_work",
      "feedback": "Specific feedback for this area"
    }}
  ],
  "suggestions": [
    "Specific actionable suggestion 1",
    "Specific actionable suggestion 2",
    "Specific actionable suggestion 3"
  ]
}}

Score guide: 5=Excellent, 4=Good, 3=Developing, 2=Below expectations, 1=Significant gaps.
Return ONLY the JSON object."""

    system_prompt = (
        "You are an expert educational assessor. Evaluate student answers fairly and constructively. "
        "Identify specific strengths and gaps. Provide actionable, encouraging suggestions for improvement. "
        "Always return valid JSON."
    )

    raw = await generate_content(prompt, system_prompt, max_tokens=1500, temperature=0.3)

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        report = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error("Failed to parse AI readiness report: %s | raw=%s", e, raw[:200])
        raise HTTPException(status_code=500, detail="Failed to evaluate answers. Please try again.")

    # Store answers and report in the guide content
    data["answers"] = [{"question_id": a.question_id, "answer": a.answer} for a in body.answers]
    data["report"] = report
    from datetime import datetime, timezone
    data["completed_at"] = datetime.now(timezone.utc).isoformat()
    guide.content = json.dumps(data)

    # Notify the parent
    parent_user_id = data.get("parent_user_id")
    if parent_user_id:
        child_user = db.query(User).filter(User.id == guide.user_id).first()
        child_name = child_user.full_name if child_user else "Your child"
        notification = Notification(
            user_id=parent_user_id,
            type=NotificationType.SYSTEM,
            title="Readiness Check Complete",
            content=f"{child_name} has completed the readiness check for {course_name}. View the report!",
            link=f"/readiness-check/{guide.id}/report",
        )
        db.add(notification)

    increment_ai_usage(current_user, db, generation_type="readiness_evaluation")

    return {"message": "Assessment submitted", "id": guide.id, "overall_score": report.get("overall_score")}


@router.get("/{assessment_id}/report", response_model=ReadinessReportResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_readiness_report(
    request: Request,
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parent (or student) views the gap analysis report."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == assessment_id,
        StudyGuide.guide_type == "readiness",
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Assessment not found")

    data = json.loads(guide.content)

    # Authorization: parent who created or student assigned
    if guide.user_id != current_user.id and data.get("parent_user_id") != current_user.id:
        # Also allow admin
        if current_user.role != UserRole.ADMIN.value and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Not authorized to view this report")

    report = data.get("report")
    if not report:
        raise HTTPException(status_code=400, detail="Assessment not yet completed")

    # Get student and course info
    child_user = db.query(User).filter(User.id == guide.user_id).first()
    course = db.query(Course).filter(Course.id == guide.course_id).first()

    questions = [
        ReadinessQuestion(
            id=q["id"], type=q["type"], question=q["question"], options=q.get("options")
        )
        for q in data.get("questions", [])
    ]
    answers = [
        AnswerSubmission(question_id=a["question_id"], answer=a["answer"])
        for a in data.get("answers", [])
    ] if data.get("answers") else None

    return ReadinessReportResponse(
        id=guide.id,
        student_id=data.get("student_id", 0),
        student_name=child_user.full_name if child_user else "Unknown",
        course_name=course.name if course else "Unknown",
        topic=data.get("topic"),
        overall_score=report["overall_score"],
        summary=report["summary"],
        topic_breakdown=[TopicBreakdown(**t) for t in report.get("topic_breakdown", [])],
        suggestions=report.get("suggestions", []),
        questions=questions,
        answers=answers,
        created_at=guide.created_at,
        completed_at=data.get("completed_at"),
    )


@router.get("", response_model=list[ReadinessListItem])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def list_readiness_checks(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List readiness checks relevant to the current user."""
    guides = (
        db.query(StudyGuide)
        .filter(StudyGuide.guide_type == "readiness")
        .order_by(StudyGuide.created_at.desc())
        .all()
    )

    items = []
    for g in guides:
        data = json.loads(g.content)
        # Filter: only show if current user is the parent or the student
        if g.user_id != current_user.id and data.get("parent_user_id") != current_user.id:
            continue

        child_user = db.query(User).filter(User.id == g.user_id).first()
        course = db.query(Course).filter(Course.id == g.course_id).first()
        report = data.get("report")

        items.append(ReadinessListItem(
            id=g.id,
            student_name=child_user.full_name if child_user else "Unknown",
            course_name=course.name if course else "Unknown",
            topic=data.get("topic"),
            overall_score=report["overall_score"] if report else None,
            status="completed" if report else "pending",
            created_at=g.created_at,
        ))

    return items
