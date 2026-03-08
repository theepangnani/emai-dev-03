"""
Parent AI endpoints — briefing notes and responsible AI tools for parents.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.models.quiz_result import QuizResult
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.schemas.parent_ai import (
    PracticeProblem,
    PracticeProblemsRequest,
    PracticeProblemsResponse,
    ReadinessCheckRequest,
    ReadinessCheckResponse,
    ReadinessItem,
    WeakSpot,
    WeakSpotsRequest,
    WeakSpotsResponse,
)
from app.services.ai_service import generate_content, generate_parent_briefing
from app.services.ai_usage import check_ai_usage, increment_ai_usage

logger = get_logger(__name__)

router = APIRouter(prefix="/parent-ai", tags=["Parent AI"])


# ── Schemas ──────────────────────────────────────

class BriefingNoteCreate(BaseModel):
    course_content_id: int
    student_id: int | None = None
    student_user_id: int | None = None


class BriefingNoteResponse(BaseModel):
    id: int
    user_id: int
    course_id: int | None
    course_content_id: int | None
    title: str
    content: str
    guide_type: str
    created_at: str
    course_name: str | None = None
    student_name: str | None = None

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────

def _verify_parent_child(db: Session, parent_user_id: int, student_id: int) -> tuple[Student, User]:
    """Verify the parent has access to this student. Returns (student, child_user)."""
    row = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(
            parent_students.c.parent_id == parent_user_id,
            Student.id == student_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found or not linked to your account")
    return row


def _get_linked_student_ids(db: Session, parent_id: int) -> list[int]:
    """Get all student IDs linked to a parent."""
    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == parent_id,
    ).all()
    return [r[0] for r in rows]


# ── Briefing Notes Endpoints ────────────────────────────────────

@router.post("/briefing-notes", response_model=BriefingNoteResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def create_briefing_note(
    request: Request,
    body: BriefingNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Generate a parent-friendly briefing note for a course material."""
    # Resolve student_id from either student_id or student_user_id
    student_id = body.student_id
    if not student_id and body.student_user_id:
        s = db.query(Student).filter(Student.user_id == body.student_user_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Student not found")
        student_id = s.id
    if not student_id:
        raise HTTPException(status_code=400, detail="Either student_id or student_user_id is required")

    student, child_user = _verify_parent_child(db, current_user.id, student_id)

    cc = db.query(CourseContent).filter(CourseContent.id == body.course_content_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Course content not found")

    course = db.query(Course).filter(Course.id == cc.course_id).first()
    course_name = course.name if course else "Unknown Course"

    source_text = cc.text_content or cc.description or ""
    if not source_text.strip():
        raise HTTPException(
            status_code=400,
            detail="This material has no text content to generate a briefing from.",
        )

    check_ai_usage(current_user, db)

    student_name = child_user.full_name

    logger.info(
        "Generating parent briefing | parent=%s | student=%s | content=%s",
        current_user.id, student_id, body.course_content_id,
    )
    ai_content = await generate_parent_briefing(
        topic_title=cc.title,
        course_name=course_name,
        source_content=source_text[:8000],
        student_name=student_name,
    )

    guide = StudyGuide(
        user_id=current_user.id,
        course_id=cc.course_id,
        course_content_id=cc.id,
        title=f"Parent Briefing: {cc.title}",
        content=ai_content,
        guide_type="parent_briefing",
    )
    db.add(guide)
    db.flush()

    increment_ai_usage(current_user, db, generation_type="parent_briefing", course_material_id=cc.id)

    return BriefingNoteResponse(
        id=guide.id,
        user_id=guide.user_id,
        course_id=guide.course_id,
        course_content_id=guide.course_content_id,
        title=guide.title,
        content=guide.content,
        guide_type=guide.guide_type,
        created_at=guide.created_at.isoformat() if guide.created_at else "",
        course_name=course_name,
        student_name=student_name,
    )


@router.get("/briefing-notes", response_model=list[BriefingNoteResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_briefing_notes(
    request: Request,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List all parent briefing notes. Optionally filter by student_id."""
    query = db.query(StudyGuide).filter(
        StudyGuide.user_id == current_user.id,
        StudyGuide.guide_type == "parent_briefing",
        StudyGuide.archived_at.is_(None),
    )

    if student_id:
        _verify_parent_child(db, current_user.id, student_id)
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            course_ids = [c.id for c in student.courses]
            if course_ids:
                query = query.filter(StudyGuide.course_id.in_(course_ids))
            else:
                return []

    guides = query.order_by(StudyGuide.created_at.desc()).all()

    results = []
    linked_sids = _get_linked_student_ids(db, current_user.id)
    for g in guides:
        course_name = g.course.name if g.course else None
        student_name = None
        if g.course_id and linked_sids:
            enrolled = db.query(Student).join(
                student_courses, Student.id == student_courses.c.student_id
            ).filter(
                student_courses.c.course_id == g.course_id,
                Student.id.in_(linked_sids),
            ).first()
            if enrolled:
                su = db.query(User).filter(User.id == enrolled.user_id).first()
                student_name = su.full_name if su else None

        results.append(BriefingNoteResponse(
            id=g.id,
            user_id=g.user_id,
            course_id=g.course_id,
            course_content_id=g.course_content_id,
            title=g.title,
            content=g.content,
            guide_type=g.guide_type,
            created_at=g.created_at.isoformat() if g.created_at else "",
            course_name=course_name,
            student_name=student_name,
        ))

    return results


@router.delete("/briefing-notes/{note_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_briefing_note(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Archive (soft-delete) a parent briefing note."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == note_id,
        StudyGuide.user_id == current_user.id,
        StudyGuide.guide_type == "parent_briefing",
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Briefing note not found")
    guide.archived_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Briefing note archived"}



# ── 1. Weak Spots ──

@router.post("/weak-spots", response_model=WeakSpotsResponse)
async def analyze_weak_spots(
    body: WeakSpotsRequest,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    """Analyze a child's quiz results and grades to identify weak topics."""
    check_ai_usage(current_user, db)

    student, child_user = _verify_parent_child(db, current_user.id, body.student_id)

    # Gather quiz results
    quiz_query = (
        db.query(QuizResult, StudyGuide)
        .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
        .filter(QuizResult.user_id == child_user.id)
    )
    if body.course_id:
        quiz_query = quiz_query.filter(StudyGuide.course_id == body.course_id)
    quiz_rows = quiz_query.order_by(QuizResult.completed_at.desc()).limit(50).all()

    # Gather assignment grades
    grade_query = (
        db.query(StudentAssignment, Assignment)
        .join(Assignment, Assignment.id == StudentAssignment.assignment_id)
        .filter(
            StudentAssignment.student_id == student.id,
            StudentAssignment.grade.isnot(None),
        )
    )
    if body.course_id:
        grade_query = grade_query.filter(Assignment.course_id == body.course_id)
    grade_rows = grade_query.order_by(Assignment.due_date.desc()).limit(50).all()

    course_name = None
    if body.course_id:
        course = db.query(Course).filter(Course.id == body.course_id).first()
        course_name = course.name if course else None

    # Build data summary for AI
    quiz_lines = []
    for qr, sg in quiz_rows:
        quiz_lines.append(
            f"- Quiz: \"{sg.title}\" | Score: {qr.score}/{qr.total_questions} ({qr.percentage:.0f}%)"
        )

    grade_lines = []
    for sa, asn in grade_rows:
        max_pts = asn.max_points or 100
        pct = (sa.grade / max_pts * 100) if max_pts else 0
        grade_lines.append(
            f"- Assignment: \"{asn.title}\" | Grade: {sa.grade}/{max_pts} ({pct:.0f}%)"
        )

    if not quiz_lines and not grade_lines:
        return WeakSpotsResponse(
            student_name=child_user.full_name,
            course_name=course_name,
            weak_spots=[],
            summary="No quiz results or graded assignments found yet. Once your child completes quizzes and assignments, weak spots will be identified here.",
            total_quizzes_analyzed=0,
            total_assignments_analyzed=0,
        )

    data_block = ""
    if quiz_lines:
        data_block += "QUIZ RESULTS:\n" + "\n".join(quiz_lines) + "\n\n"
    if grade_lines:
        data_block += "ASSIGNMENT GRADES:\n" + "\n".join(grade_lines) + "\n"

    prompt = f"""Analyze the following academic data for a student and identify weak spots (topics where they are struggling).

{data_block}

Respond with a JSON object in this exact format:
{{
  "summary": "1-2 sentence overall summary for the parent",
  "weak_spots": [
    {{
      "topic": "Topic name",
      "severity": "high|medium|low",
      "detail": "Brief explanation of the weakness",
      "quiz_score_summary": "e.g. 2/5 quizzes below 70%",
      "suggested_action": "What the parent can encourage the child to do"
    }}
  ]
}}

Rules:
- severity: "high" = consistently below 60%, "medium" = 60-75%, "low" = 75-85%
- suggested_action must encourage ACTIVE LEARNING (practice, review, re-do problems) — never suggest giving answers
- Return at most 5 weak spots, ordered by severity (worst first)
- If the student is doing well overall, return an empty weak_spots list with an encouraging summary
- Return ONLY the JSON, no other text."""

    system_prompt = (
        "You are an educational analyst helping parents understand their child's academic progress. "
        "Be honest but supportive. Focus on actionable insights."
    )

    raw = await generate_content(prompt, system_prompt, max_tokens=1000, temperature=0.3)
    increment_ai_usage(current_user, db, generation_type="parent_weak_spots")

    # Parse AI response
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse weak-spots AI response, returning raw")
        return WeakSpotsResponse(
            student_name=child_user.full_name,
            course_name=course_name,
            weak_spots=[],
            summary=raw[:500],
            total_quizzes_analyzed=len(quiz_rows),
            total_assignments_analyzed=len(grade_rows),
        )

    weak_spots = [
        WeakSpot(
            topic=ws.get("topic", "Unknown"),
            severity=ws.get("severity", "medium"),
            detail=ws.get("detail", ""),
            quiz_score_summary=ws.get("quiz_score_summary"),
            suggested_action=ws.get("suggested_action", ""),
        )
        for ws in parsed.get("weak_spots", [])
    ]

    return WeakSpotsResponse(
        student_name=child_user.full_name,
        course_name=course_name,
        weak_spots=weak_spots,
        summary=parsed.get("summary", ""),
        total_quizzes_analyzed=len(quiz_rows),
        total_assignments_analyzed=len(grade_rows),
    )


# ── 2. Readiness Check ──

@router.post("/readiness-check", response_model=ReadinessCheckResponse)
async def check_readiness(
    body: ReadinessCheckRequest,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    """Check if a child has studied enough for a specific assignment — pure SQL, no AI cost."""
    student, child_user = _verify_parent_child(db, current_user.id, body.student_id)

    assignment = db.query(Assignment).filter(Assignment.id == body.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    course_name = course.name if course else "Unknown"

    items: list[ReadinessItem] = []
    score = 0

    # 1. Study guides created for this assignment
    guide_count = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == child_user.id,
            StudyGuide.assignment_id == assignment.id,
            StudyGuide.guide_type == "study_guide",
            StudyGuide.archived_at.is_(None),
        )
        .count()
    )
    if guide_count > 0:
        items.append(ReadinessItem(label="Study guide created", status="done", detail=f"{guide_count} guide(s) generated"))
        score += 1
    else:
        items.append(ReadinessItem(label="Study guide created", status="missing", detail="No study guide generated for this assignment"))

    # 2. Quizzes taken on related study guides
    quiz_results = (
        db.query(QuizResult)
        .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
        .filter(
            QuizResult.user_id == child_user.id,
            StudyGuide.assignment_id == assignment.id,
        )
        .all()
    )
    if quiz_results:
        best_pct = max(qr.percentage for qr in quiz_results)
        attempts = len(quiz_results)
        if best_pct >= 80:
            items.append(ReadinessItem(label="Practice quizzes", status="done", detail=f"{attempts} attempt(s), best score: {best_pct:.0f}%"))
            score += 2
        else:
            items.append(ReadinessItem(label="Practice quizzes", status="partial", detail=f"{attempts} attempt(s), best score: {best_pct:.0f}% (aim for 80%+)"))
            score += 1
    else:
        items.append(ReadinessItem(label="Practice quizzes", status="missing", detail="No practice quizzes taken for this assignment"))

    # 3. Flashcards created
    flashcard_count = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == child_user.id,
            StudyGuide.assignment_id == assignment.id,
            StudyGuide.guide_type == "flashcards",
            StudyGuide.archived_at.is_(None),
        )
        .count()
    )
    if flashcard_count > 0:
        items.append(ReadinessItem(label="Flashcards reviewed", status="done", detail=f"{flashcard_count} flashcard set(s) created"))
        score += 1
    else:
        items.append(ReadinessItem(label="Flashcards reviewed", status="missing", detail="No flashcards created for this assignment"))

    # 4. Assignment submission status
    submission = (
        db.query(StudentAssignment)
        .filter(
            StudentAssignment.student_id == student.id,
            StudentAssignment.assignment_id == assignment.id,
        )
        .first()
    )
    if submission and submission.status in ("submitted", "graded"):
        items.append(ReadinessItem(label="Assignment submitted", status="done", detail=f"Status: {submission.status}"))
        score += 1
    else:
        items.append(ReadinessItem(label="Assignment submitted", status="missing", detail="Not yet submitted"))

    # Convert score (0-5) to readiness (1-5)
    readiness = max(1, min(5, score))

    summaries = {
        1: "Your child hasn't started preparing for this assignment yet.",
        2: "Your child has begun preparing but has more work to do.",
        3: "Your child is making good progress on preparation.",
        4: "Your child is well-prepared and almost ready.",
        5: "Your child appears fully prepared for this assignment!",
    }

    return ReadinessCheckResponse(
        student_name=child_user.full_name,
        assignment_title=assignment.title,
        course_name=course_name,
        readiness_score=readiness,
        summary=summaries[readiness],
        items=items,
    )


# ── 3. Practice Problems ──

@router.post("/practice-problems", response_model=PracticeProblemsResponse)
async def generate_practice_problems(
    body: PracticeProblemsRequest,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    """Generate practice problems for a child based on a topic. Problems only — no answers."""
    check_ai_usage(current_user, db)

    student, child_user = _verify_parent_child(db, current_user.id, body.student_id)

    # Verify the student is enrolled in this course
    enrolled = (
        db.query(student_courses)
        .filter(
            student_courses.c.student_id == student.id,
            student_courses.c.course_id == body.course_id,
        )
        .first()
    )
    if not enrolled:
        raise HTTPException(status_code=404, detail="Student is not enrolled in this course")

    course = db.query(Course).filter(Course.id == body.course_id).first()
    course_name = course.name if course else "Unknown"

    # Get child's grade level for age-appropriate problems
    grade_level = student.grade_level or "unknown"

    prompt = f"""Generate 7 practice problems for a Grade {grade_level} student on the topic: "{body.topic}"
Course: {course_name}

Rules:
- Problems should require the student to THINK and WORK through them
- Do NOT include answers or solutions
- Include a short hint for each problem to guide thinking (not give away the answer)
- Vary difficulty: 2 easy, 3 medium, 2 challenging
- Make problems age-appropriate for the grade level

Respond with a JSON object:
{{
  "problems": [
    {{
      "number": 1,
      "question": "Problem text here",
      "hint": "A small hint to guide thinking"
    }}
  ],
  "instructions": "Brief instructions for the student (1-2 sentences encouraging them to try each problem)"
}}

Return ONLY the JSON, no other text."""

    system_prompt = (
        "You are an expert K-12 tutor creating practice problems. "
        "Problems must require active work — never give away answers. "
        "Encourage learning through struggle and discovery."
    )

    raw = await generate_content(prompt, system_prompt, max_tokens=1500, temperature=0.6)
    increment_ai_usage(current_user, db, generation_type="parent_practice_problems")

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse practice-problems AI response")
        raise HTTPException(status_code=502, detail="Failed to generate practice problems. Please try again.")

    problems = [
        PracticeProblem(
            number=p.get("number", i + 1),
            question=p.get("question", ""),
            hint=p.get("hint"),
        )
        for i, p in enumerate(parsed.get("problems", []))
    ]

    return PracticeProblemsResponse(
        student_name=child_user.full_name,
        course_name=course_name,
        topic=body.topic,
        problems=problems,
        instructions=parsed.get("instructions", "Work through each problem carefully. Show your work!"),
    )
