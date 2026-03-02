"""Mock Exam API routes — AI-generated teacher exams (#667).

Routes:
  POST   /api/mock-exams/generate                     — teacher generates exam (preview only)
  POST   /api/mock-exams/                             — teacher saves a generated exam
  POST   /api/mock-exams/{id}/assign                  — assign exam to students
  GET    /api/mock-exams/                             — list exams (role-scoped)
  GET    /api/mock-exams/{id}                         — exam detail (correct_index hidden for students)
  PATCH  /api/mock-exams/assignments/{id}/submit      — student submits answers
"""
import json
import logging
from datetime import datetime, date, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.course import Course, student_courses
from app.models.notification import Notification, NotificationType
from app.models.mock_exam import MockExam, MockExamAssignment
from app.api.deps import get_current_user, require_feature, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.services.ai_service import generate_content
from app.services.notification_service import send_multi_channel_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mock-exams", tags=["Mock Exams"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class GenerateExamRequest(BaseModel):
    course_id: int
    topic: str = Field(..., min_length=1, max_length=500)
    num_questions: int = Field(10, ge=10, le=40)
    difficulty: str = Field("medium", pattern="^(easy|medium|hard)$")
    time_limit_minutes: int = Field(60, ge=5, le=300)


class QuestionItem(BaseModel):
    question: str
    options: list[str] = Field(..., min_items=4, max_items=4)
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str


class SaveExamRequest(BaseModel):
    course_id: int
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    questions: list[QuestionItem]
    time_limit_minutes: int = Field(60, ge=5, le=300)
    total_marks: int | None = None  # auto-computed if omitted


class AssignExamRequest(BaseModel):
    student_ids: list[int] | str  # list of IDs or "all"
    due_date: date | None = None


class SubmitAnswersRequest(BaseModel):
    answers: list[int]
    time_taken_seconds: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _exam_response(exam: MockExam, include_answers: bool = True) -> dict[str, Any]:
    questions = exam.questions or []
    if not include_answers:
        questions = [
            {k: v for k, v in q.items() if k != "correct_index"}
            for q in questions
        ]
    return {
        "id": exam.id,
        "teacher_user_id": exam.teacher_user_id,
        "course_id": exam.course_id,
        "course_name": exam.course.name if exam.course else None,
        "title": exam.title,
        "description": exam.description,
        "questions": questions,
        "num_questions": len(questions),
        "time_limit_minutes": exam.time_limit_minutes,
        "total_marks": exam.total_marks,
        "is_published": exam.is_published,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
        "assignment_count": len(exam.assignments) if exam.assignments else 0,
        "completed_count": sum(1 for a in (exam.assignments or []) if a.status == "completed"),
    }


def _assignment_response(assignment: MockExamAssignment, include_answers: bool = True) -> dict[str, Any]:
    exam = assignment.exam
    questions = (exam.questions if exam else []) or []
    if not include_answers and assignment.status != "completed":
        questions = [
            {k: v for k, v in q.items() if k != "correct_index"}
            for q in questions
        ]

    student_name: str | None = None
    if assignment.student and assignment.student.user:
        student_name = assignment.student.user.full_name

    return {
        "id": assignment.id,
        "exam_id": assignment.exam_id,
        "exam_title": exam.title if exam else None,
        "course_id": exam.course_id if exam else None,
        "course_name": exam.course.name if (exam and exam.course) else None,
        "time_limit_minutes": exam.time_limit_minutes if exam else None,
        "total_marks": exam.total_marks if exam else None,
        "num_questions": len(questions),
        "questions": questions,
        "student_id": assignment.student_id,
        "student_name": student_name,
        "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
        "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
        "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
        "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
        "answers": assignment.answers,
        "score": assignment.score,
        "time_taken_seconds": assignment.time_taken_seconds,
        "status": assignment.status,
    }


# ---------------------------------------------------------------------------
# POST /generate  — AI generation (preview only, not saved)
# ---------------------------------------------------------------------------

@router.post("/generate")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_exam(
    request: Request,
    body: GenerateExamRequest,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """Generate AI MCQ questions for a mock exam (preview). Does not persist."""
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Map num_questions to allowed values
    num_q = max(10, min(40, body.num_questions))
    # Round to nearest 10
    num_q = round(num_q / 10) * 10

    prompt = (
        f"Generate {num_q} multiple-choice exam questions for a {body.difficulty} level exam on:\n"
        f"Course: {course.name}\n"
        f"Topic: {body.topic}\n\n"
        f"Return a JSON array only (no extra text, no markdown fences):\n"
        f'[{{"question": str, "options": [str, str, str, str], "correct_index": 0-3, "explanation": str}}]\n\n'
        f"Make questions progressively harder. Explanation should be 1-2 sentences. "
        f"Ensure correct_index (0, 1, 2, or 3) accurately identifies which option is correct."
    )

    system_prompt = (
        "You are an expert exam writer creating high-quality multiple-choice questions for "
        "educational assessments. Return ONLY a valid JSON array with no markdown formatting. "
        "Each question must have exactly 4 options and a correct_index (0-3)."
    )

    try:
        raw = await generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4000,
            temperature=0.6,
            user=current_user,
        )
    except Exception as e:
        logger.error(f"AI exam generation failed: {e}")
        raise HTTPException(status_code=503, detail="AI generation failed. Please try again.")

    # Strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()

    try:
        questions = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON array from response
        import re
        match = re.search(r'\[[\s\S]*\]', raw)
        if match:
            try:
                questions = json.loads(match.group(0))
            except json.JSONDecodeError:
                raise HTTPException(status_code=422, detail="AI returned invalid JSON. Please retry.")
        else:
            raise HTTPException(status_code=422, detail="AI returned invalid JSON. Please retry.")

    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=422, detail="AI did not return valid questions. Please retry.")

    # Validate and clean each question
    cleaned = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        question_text = str(q.get("question", "")).strip()
        options = q.get("options", [])
        correct_index = q.get("correct_index", 0)
        explanation = str(q.get("explanation", "")).strip()

        if not question_text or not isinstance(options, list) or len(options) < 4:
            continue
        if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
            correct_index = 0

        cleaned.append({
            "question": question_text,
            "options": [str(o).strip() for o in options[:4]],
            "correct_index": correct_index,
            "explanation": explanation,
        })

    if not cleaned:
        raise HTTPException(status_code=422, detail="Could not parse AI questions. Please retry.")

    suggested_title = f"{course.name} — {body.topic} Mock Exam"

    return {
        "course_id": body.course_id,
        "course_name": course.name,
        "topic": body.topic,
        "difficulty": body.difficulty,
        "time_limit_minutes": body.time_limit_minutes,
        "suggested_title": suggested_title,
        "questions": cleaned,
        "num_questions": len(cleaned),
        "total_marks": len(cleaned),
    }


# ---------------------------------------------------------------------------
# POST /  — save exam
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def save_exam(
    request: Request,
    body: SaveExamRequest,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """Save a generated exam. Sets is_published=False by default."""
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    questions_data = [q.dict() for q in body.questions]
    total_marks = body.total_marks if body.total_marks is not None else len(questions_data)

    exam = MockExam(
        teacher_user_id=current_user.id,
        course_id=body.course_id,
        title=body.title,
        description=body.description,
        questions=questions_data,
        time_limit_minutes=body.time_limit_minutes,
        total_marks=total_marks,
        is_published=False,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    logger.info(f"Mock exam saved: id={exam.id} teacher={current_user.id} course={body.course_id}")
    return _exam_response(exam, include_answers=True)


# ---------------------------------------------------------------------------
# POST /{id}/assign  — assign to students
# ---------------------------------------------------------------------------

@router.post("/{exam_id}/assign", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def assign_exam(
    request: Request,
    exam_id: int,
    body: AssignExamRequest,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """Assign a mock exam to individual students or all course students."""
    exam = db.query(MockExam).filter(MockExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.teacher_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your exam")

    # Resolve student IDs
    if body.student_ids == "all":
        # All students enrolled in the exam's course
        enrolled_students = (
            db.query(Student)
            .join(student_courses, Student.id == student_courses.c.student_id)
            .filter(student_courses.c.course_id == exam.course_id)
            .all()
        )
        student_ids = [s.id for s in enrolled_students]
    else:
        student_ids = body.student_ids

    if not student_ids:
        raise HTTPException(status_code=400, detail="No students to assign to")

    created = []
    skipped = 0
    for sid in student_ids:
        student = db.query(Student).filter(Student.id == sid).first()
        if not student:
            skipped += 1
            continue

        # Check duplicate
        existing = (
            db.query(MockExamAssignment)
            .filter(
                MockExamAssignment.exam_id == exam_id,
                MockExamAssignment.student_id == sid,
            )
            .first()
        )
        if existing:
            skipped += 1
            continue

        assignment = MockExamAssignment(
            exam_id=exam_id,
            student_id=sid,
            due_date=body.due_date,
            status="assigned",
        )
        db.add(assignment)
        db.flush()  # get assignment.id

        # Send in-app notification to student
        if student.user:
            try:
                send_multi_channel_notification(
                    db=db,
                    recipient=student.user,
                    sender=current_user,
                    title=f"New Mock Exam: {exam.title}",
                    content=(
                        f"You have been assigned a mock exam: '{exam.title}'. "
                        f"Time limit: {exam.time_limit_minutes} minutes. "
                        + (f"Due: {body.due_date}" if body.due_date else "No due date.")
                    ),
                    notification_type=NotificationType.ASSESSMENT_UPCOMING,
                    link=f"/exams/{assignment.id}",
                    channels=["in_app"],
                    source_type="mock_exam",
                    source_id=exam.id,
                )
            except Exception as e:
                logger.warning(f"Failed to notify student {sid}: {e}")

        created.append(assignment.id)

    # Mark exam as published
    exam.is_published = True
    db.commit()

    logger.info(
        f"Exam {exam_id} assigned to {len(created)} students; {skipped} skipped"
    )
    return {
        "exam_id": exam_id,
        "assigned_count": len(created),
        "skipped_count": skipped,
        "assignment_ids": created,
    }


# ---------------------------------------------------------------------------
# GET /  — list exams
# ---------------------------------------------------------------------------

@router.get("/")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_exams(
    request: Request,
    course_id: int | None = Query(None),
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List exams. Teachers see their own exams. Students see assigned exams."""
    if current_user.role == UserRole.TEACHER:
        q = db.query(MockExam).filter(MockExam.teacher_user_id == current_user.id)
        if course_id:
            q = q.filter(MockExam.course_id == course_id)
        exams = q.order_by(MockExam.created_at.desc()).all()
        return [_exam_response(e, include_answers=True) for e in exams]

    elif current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            return []

        q = (
            db.query(MockExamAssignment)
            .join(MockExam, MockExamAssignment.exam_id == MockExam.id)
            .filter(MockExamAssignment.student_id == student.id)
        )
        if course_id:
            q = q.filter(MockExam.course_id == course_id)

        assignments = q.order_by(MockExamAssignment.assigned_at.desc()).all()
        return [_assignment_response(a, include_answers=False) for a in assignments]

    else:
        raise HTTPException(status_code=403, detail="Access denied")


# ---------------------------------------------------------------------------
# GET /{id}  — exam detail
# ---------------------------------------------------------------------------

@router.get("/{exam_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_exam(
    request: Request,
    exam_id: int,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exam detail. Students only get correct_index after completion."""
    if current_user.role == UserRole.TEACHER:
        exam = db.query(MockExam).filter(
            MockExam.id == exam_id,
            MockExam.teacher_user_id == current_user.id,
        ).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")
        return _exam_response(exam, include_answers=True)

    elif current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=403, detail="Student profile not found")

        assignment = (
            db.query(MockExamAssignment)
            .filter(
                MockExamAssignment.id == exam_id,  # exam_id param is actually assignment_id for students
                MockExamAssignment.student_id == student.id,
            )
            .first()
        )
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        include_answers = assignment.status == "completed"
        return _assignment_response(assignment, include_answers=include_answers)

    else:
        raise HTTPException(status_code=403, detail="Access denied")


# ---------------------------------------------------------------------------
# GET /assignments/{id}  — assignment detail by assignment ID
# ---------------------------------------------------------------------------

@router.get("/assignments/{assignment_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_assignment(
    request: Request,
    assignment_id: int,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific assignment by ID (used by ExamPage)."""
    assignment = db.query(MockExamAssignment).filter(
        MockExamAssignment.id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student or assignment.student_id != student.id:
            raise HTTPException(status_code=403, detail="Access denied")

        include_answers = assignment.status == "completed"

        # Mark as in_progress if starting for the first time
        if assignment.status == "assigned":
            assignment.status = "in_progress"
            assignment.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(assignment)

        return _assignment_response(assignment, include_answers=include_answers)

    elif current_user.role == UserRole.TEACHER:
        exam = db.query(MockExam).filter(
            MockExam.id == assignment.exam_id,
            MockExam.teacher_user_id == current_user.id,
        ).first()
        if not exam:
            raise HTTPException(status_code=403, detail="Access denied")
        return _assignment_response(assignment, include_answers=True)

    raise HTTPException(status_code=403, detail="Access denied")


# ---------------------------------------------------------------------------
# PATCH /assignments/{id}/submit  — student submits answers
# ---------------------------------------------------------------------------

@router.patch("/assignments/{assignment_id}/submit")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def submit_exam(
    request: Request,
    assignment_id: int,
    body: SubmitAnswersRequest,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Student submits exam answers. Computes score and notifies teacher."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=403, detail="Student profile not found")

    assignment = db.query(MockExamAssignment).filter(
        MockExamAssignment.id == assignment_id,
        MockExamAssignment.student_id == student.id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.status == "completed":
        raise HTTPException(status_code=400, detail="Exam already submitted")

    exam = assignment.exam
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    questions = exam.questions or []
    answers = body.answers

    # Compute score
    correct = 0
    if questions and answers:
        for i, q in enumerate(questions):
            if i < len(answers) and answers[i] == q.get("correct_index"):
                correct += 1

    score = (correct / len(questions) * 100) if questions else 0.0

    assignment.answers = answers
    assignment.score = round(score, 2)
    assignment.time_taken_seconds = body.time_taken_seconds
    assignment.completed_at = datetime.now(timezone.utc)
    assignment.status = "completed"

    db.commit()
    db.refresh(assignment)

    # Notify the teacher
    teacher_user = db.query(User).filter(User.id == exam.teacher_user_id).first()
    if teacher_user:
        try:
            send_multi_channel_notification(
                db=db,
                recipient=teacher_user,
                sender=current_user,
                title=f"Exam Submitted: {exam.title}",
                content=(
                    f"{current_user.full_name} completed '{exam.title}' "
                    f"with a score of {score:.1f}% "
                    f"({correct}/{len(questions)} correct) "
                    f"in {body.time_taken_seconds // 60}m {body.time_taken_seconds % 60}s."
                ),
                notification_type=NotificationType.GRADE_POSTED,
                link=f"/teacher/exams",
                channels=["in_app"],
                source_type="mock_exam",
                source_id=exam.id,
            )
        except Exception as e:
            logger.warning(f"Failed to notify teacher after exam submit: {e}")

    logger.info(
        f"Exam {exam.id} submitted by student {student.id}: "
        f"score={score:.1f}% ({correct}/{len(questions)})"
    )

    return _assignment_response(assignment, include_answers=True)


# ---------------------------------------------------------------------------
# DELETE /{id}  — teacher deletes exam
# ---------------------------------------------------------------------------

@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def delete_exam(
    request: Request,
    exam_id: int,
    _flag=Depends(require_feature("ai_mock_exams")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
):
    """Delete a mock exam (cascade deletes assignments)."""
    exam = db.query(MockExam).filter(
        MockExam.id == exam_id,
        MockExam.teacher_user_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    db.delete(exam)
    db.commit()
    logger.info(f"Exam {exam_id} deleted by teacher {current_user.id}")
