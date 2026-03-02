"""Exam Preparation Engine API routes (#576).

Routes:
  POST   /api/exam-prep/generate   — generate a personalized AI prep plan
  GET    /api/exam-prep/           — list plans for current user's students
  GET    /api/exam-prep/{id}       — full plan detail
  DELETE /api/exam-prep/{id}       — archive plan
"""

import json
import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.db.database import get_db
from app.models.course import Course
from app.models.exam_prep_plan import ExamPrepPlan
from app.models.grade_entry import GradeEntry
from app.models.quiz_result import QuizResult
from app.models.report_card import ReportCard
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.services import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exam-prep", tags=["Exam Prep"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ExamPrepGenerateRequest(BaseModel):
    title: str
    student_id: int | None = None       # required for parent, optional for student
    course_id: int | None = None
    exam_date: date | None = None


class WeakArea(BaseModel):
    topic: str
    confidence_pct: int
    source: str  # quiz | test | teacher_grade


class StudyDay(BaseModel):
    day: str
    tasks: list[str]


class Resource(BaseModel):
    type: str   # review | practice | memorize
    title: str
    study_guide_id: int | None = None


class ExamPrepPlanResponse(BaseModel):
    id: int
    student_id: int
    course_id: int | None
    course_name: str | None
    exam_date: date | None
    title: str
    weak_areas: list[dict] | None
    study_schedule: list[dict] | None
    recommended_resources: list[dict] | None
    ai_advice: str | None
    status: str
    generated_at: datetime

    model_config = {"from_attributes": True}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_student(db: Session, current_user: User, student_id: int | None) -> Student:
    """Resolve which student to act on, enforcing RBAC."""
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        if student_id and student.id != student_id:
            raise HTTPException(status_code=403, detail="Students can only access their own plans")
        return student

    if current_user.has_role(UserRole.PARENT):
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for parent users")
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Not authorized to manage plans for this student")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    if current_user.has_role(UserRole.ADMIN):
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for admin users")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    raise HTTPException(status_code=403, detail="Insufficient permissions")


def _get_accessible_student_ids(db: Session, user: User) -> list[int]:
    """Return student IDs the user is allowed to view plans for."""
    if user.has_role(UserRole.ADMIN):
        return [s.id for s in db.query(Student.id).all()]

    if user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == user.id).first()
        return [student.id] if student else []

    if user.has_role(UserRole.PARENT):
        rows = db.execute(
            parent_students.select().where(parent_students.c.parent_id == user.id)
        ).fetchall()
        return [row.student_id for row in rows]

    return []


def _get_plan_with_access(db: Session, plan_id: int, user: User) -> ExamPrepPlan:
    """Load a plan and verify the caller has access."""
    plan = db.query(ExamPrepPlan).filter(ExamPrepPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Exam prep plan not found")

    if user.has_role(UserRole.ADMIN):
        return plan

    if user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student or plan.student_id != student.id:
            raise HTTPException(status_code=403, detail="Access denied")
        return plan

    if user.has_role(UserRole.PARENT):
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == user.id,
                parent_students.c.student_id == plan.student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Access denied")
        return plan

    raise HTTPException(status_code=403, detail="Access denied")


def _build_plan_response(plan: ExamPrepPlan, db: Session) -> dict[str, Any]:
    """Build a serializable dict for an ExamPrepPlan."""
    course_name = None
    if plan.course_id:
        try:
            course = db.query(Course).filter(Course.id == plan.course_id).first()
            if course:
                course_name = course.name
        except Exception:
            pass

    return {
        "id": plan.id,
        "student_id": plan.student_id,
        "course_id": plan.course_id,
        "course_name": course_name,
        "exam_date": plan.exam_date.isoformat() if plan.exam_date else None,
        "title": plan.title,
        "weak_areas": plan.weak_areas,
        "study_schedule": plan.study_schedule,
        "recommended_resources": plan.recommended_resources,
        "ai_advice": plan.ai_advice,
        "status": plan.status,
        "generated_at": plan.generated_at.isoformat() if plan.generated_at else None,
    }


# ─── Gather student performance data ──────────────────────────────────────────

def _gather_quiz_data(db: Session, student: Student) -> dict[str, float]:
    """Return {study_guide_title: avg_percentage} for this student's quiz history."""
    quiz_data: dict[str, list[float]] = {}
    try:
        rows = (
            db.query(QuizResult.percentage, StudyGuide.title)
            .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
            .filter(QuizResult.user_id == student.user_id)
            .order_by(QuizResult.completed_at.desc())
            .limit(100)
            .all()
        )
        for pct, title in rows:
            if title:
                quiz_data.setdefault(title, []).append(pct)
    except Exception as exc:
        logger.warning("Could not load quiz data for student %s: %s", student.id, exc)
    return {title: round(sum(scores) / len(scores), 1) for title, scores in quiz_data.items()}


def _gather_report_card_data(db: Session, student: Student) -> list[dict[str, Any]]:
    """Return extracted marks from the most recent report card."""
    marks: list[dict[str, Any]] = []
    try:
        latest_card = (
            db.query(ReportCard)
            .filter(ReportCard.student_id == student.id, ReportCard.status == "analyzed")
            .order_by(ReportCard.analyzed_at.desc())
            .first()
        )
        if latest_card and latest_card.extracted_marks:
            raw = latest_card.extracted_marks
            if isinstance(raw, str):
                raw = json.loads(raw)
            if isinstance(raw, list):
                marks = raw
    except Exception as exc:
        logger.warning("Could not load report card data for student %s: %s", student.id, exc)
    return marks


def _gather_grade_entries(db: Session, student: Student, course_id: int | None) -> list[dict[str, Any]]:
    """Return recent teacher-entered grade records for this student."""
    entries: list[dict[str, Any]] = []
    try:
        query = (
            db.query(GradeEntry)
            .filter(GradeEntry.student_id == student.id, GradeEntry.is_published == True)  # noqa: E712
        )
        if course_id:
            query = query.filter(GradeEntry.course_id == course_id)
        rows = query.order_by(GradeEntry.created_at.desc()).limit(20).all()
        for row in rows:
            entries.append({
                "grade": row.grade,
                "max_grade": row.max_grade,
                "feedback": row.feedback,
                "term": row.term,
            })
    except Exception as exc:
        logger.warning("Could not load grade entries for student %s: %s", student.id, exc)
    return entries


# ─── AI Prompt Builder ────────────────────────────────────────────────────────

def _build_ai_prompt(
    course_name: str | None,
    exam_date_str: str,
    quiz_summary: dict[str, float],
    report_card_marks: list[dict[str, Any]],
    grade_entries: list[dict[str, Any]],
    study_streak: int,
) -> str:
    # Format quiz summary
    if quiz_summary:
        quiz_lines = [f"  - {title}: {avg}%" for title, avg in list(quiz_summary.items())[:10]]
        quiz_text = "\n".join(quiz_lines)
    else:
        quiz_text = "  No quiz data available"

    # Format report card marks
    if report_card_marks:
        rc_lines = []
        for m in report_card_marks[:8]:
            subj = m.get("subject", "Unknown")
            pct = m.get("percentage") or m.get("mark")
            rc_lines.append(f"  - {subj}: {pct}")
        marks_text = "\n".join(rc_lines)
    else:
        marks_text = "  No report card data available"

    # Format grade entries
    if grade_entries:
        ge_lines = []
        for g in grade_entries[:6]:
            if g.get("grade") is not None:
                max_g = g.get("max_grade") or 100
                pct = round((g["grade"] / max_g) * 100, 1) if max_g else g["grade"]
                term = g.get("term") or "recent"
                ge_lines.append(f"  - {term}: {pct}%")
                if g.get("feedback"):
                    ge_lines.append(f"    Teacher note: {g['feedback'][:100]}")
        grade_text = "\n".join(ge_lines) if ge_lines else "  No grade entries available"
    else:
        grade_text = "  No grade entries available"

    return f"""You are a personalized exam prep coach for an Ontario high school student.

Student data:
- Course: {course_name or "General / Multiple Subjects"}
- Exam date: {exam_date_str}
- Study streak: {study_streak} days

Quiz performance (topic: average score%):
{quiz_text}

Recent report card marks:
{marks_text}

Teacher-entered grades:
{grade_text}

Generate a personalized exam prep plan that addresses the student's weak areas. Return valid JSON ONLY (no markdown, no extra text):
{{
  "weak_areas": [
    {{"topic": "string", "confidence_pct": 0-100, "source": "quiz|test|teacher_grade"}}
  ],
  "study_schedule": [
    {{"day": "Day 1", "tasks": ["task1", "task2"]}}
  ],
  "recommended_resources": [
    {{"type": "review|practice|memorize", "title": "string"}}
  ],
  "ai_advice": "2-3 paragraphs in markdown, encouraging but realistic"
}}

Requirements:
- weak_areas: 3-6 specific topics the student needs to work on, ordered by priority
- study_schedule: 7 to 14 days of daily tasks, each day having 2-4 actionable tasks
- recommended_resources: 4-6 specific resources tailored to the weak areas
- ai_advice: Markdown text with practical advice, motivational tone, specific to this student's data
- If no quiz/grade data is available, generate a general plan based on the course subject"""


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/generate", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_exam_prep_plan(
    request: Request,
    body: ExamPrepGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a personalized AI exam prep plan for a student.

    Gathers quiz history, report card marks, and teacher grades,
    then uses AI to create a targeted study plan.
    """
    if not any(current_user.has_role(r) for r in (UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    student = _resolve_student(db, current_user, body.student_id)

    # Resolve course name
    course_name: str | None = None
    if body.course_id:
        try:
            course = db.query(Course).filter(Course.id == body.course_id).first()
            if course:
                course_name = course.name
        except Exception:
            pass

    exam_date_str = body.exam_date.isoformat() if body.exam_date else "upcoming"

    # Gather performance data
    quiz_summary = _gather_quiz_data(db, student)
    report_card_marks = _gather_report_card_data(db, student)
    grade_entries = _gather_grade_entries(db, student, body.course_id)
    study_streak = student.study_streak_days or 0

    # Build and send AI prompt
    prompt = _build_ai_prompt(
        course_name=course_name,
        exam_date_str=exam_date_str,
        quiz_summary=quiz_summary,
        report_card_marks=report_card_marks,
        grade_entries=grade_entries,
        study_streak=study_streak,
    )

    system_prompt = (
        "You are an expert Ontario high school exam preparation coach. "
        "Generate highly personalized, actionable study plans in valid JSON format only. "
        "Do not wrap JSON in markdown code blocks. Return only the raw JSON object."
    )

    try:
        raw_response = await ai_service.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=3000,
            temperature=0.6,
            user=current_user,
        )
    except Exception as exc:
        logger.error("AI generation failed for exam prep plan: %s", exc)
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again.")

    # Parse AI response
    weak_areas = None
    study_schedule = None
    recommended_resources = None
    ai_advice = None

    try:
        # Strip markdown code fences if the model returned them
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        parsed: dict[str, Any] = json.loads(cleaned)
        weak_areas = parsed.get("weak_areas")
        study_schedule = parsed.get("study_schedule")
        recommended_resources = parsed.get("recommended_resources")
        ai_advice = parsed.get("ai_advice")
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Could not parse AI response as JSON: %s — storing raw text", exc)
        ai_advice = raw_response  # graceful fallback

    # Save to database
    plan = ExamPrepPlan(
        student_id=student.id,
        created_by_user_id=current_user.id,
        course_id=body.course_id,
        exam_date=body.exam_date,
        title=body.title,
        weak_areas=weak_areas,
        study_schedule=study_schedule,
        recommended_resources=recommended_resources,
        ai_advice=ai_advice,
        status="active",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    logger.info(
        "Exam prep plan generated: id=%s student=%s course=%s by user=%s",
        plan.id, student.id, body.course_id, current_user.id,
    )
    return _build_plan_response(plan, db)


@router.get("/")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_exam_prep_plans(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List exam prep plans for the current user's accessible students."""
    student_ids = _get_accessible_student_ids(db, current_user)
    if not student_ids:
        return []

    plans = (
        db.query(ExamPrepPlan)
        .filter(
            ExamPrepPlan.student_id.in_(student_ids),
            ExamPrepPlan.status != "archived",
        )
        .order_by(ExamPrepPlan.generated_at.desc())
        .all()
    )
    return [_build_plan_response(p, db) for p in plans]


@router.get("/{plan_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_exam_prep_plan(
    request: Request,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full plan detail."""
    plan = _get_plan_with_access(db, plan_id, current_user)
    return _build_plan_response(plan, db)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def archive_exam_prep_plan(
    request: Request,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive (soft-delete) an exam prep plan."""
    plan = _get_plan_with_access(db, plan_id, current_user)
    plan.status = "archived"
    db.commit()
    logger.info("Exam prep plan archived: id=%s by user=%s", plan_id, current_user.id)
