"""Parent AI Insights API routes (#581).

Routes:
  POST   /api/ai-insights/generate                    — Generate insight for a student
  GET    /api/ai-insights/                            — List insights for accessible students
  GET    /api/ai-insights/{id}                        — Get full insight
  DELETE /api/ai-insights/{id}                        — Delete (parent/admin only)
  GET    /api/ai-insights/student/{student_id}/latest — Latest insight for a student
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.db.database import get_db
from app.models.ai_insight import AIInsight
from app.models.assignment import Assignment
from app.models.exam_prep_plan import ExamPrepPlan
from app.models.grade_entry import GradeEntry
from app.models.quiz_result import QuizResult
from app.models.report_card import ReportCard
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.services import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-insights", tags=["AI Insights"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class GenerateInsightRequest(BaseModel):
    student_id: int
    insight_type: str = "on_demand"  # weekly | monthly | on_demand


class AIInsightResponse(BaseModel):
    id: int
    student_id: int
    insight_type: str
    summary: str
    strengths: list[str] | None = None
    concerns: list[str] | None = None
    recommendations: list[str] | None = None
    subject_analysis: dict[str, Any] | None = None
    learning_style_note: str | None = None
    parent_actions: list[str] | None = None
    generated_at: str
    period_start: str | None = None
    period_end: str | None = None

    model_config = {"from_attributes": True}


# ─── RBAC helpers ─────────────────────────────────────────────────────────────

def _verify_parent_or_admin_access(db: Session, user: User, student_id: int) -> Student:
    """Verify user can access this student's insights. Returns the student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if user.has_role(UserRole.ADMIN):
        return student

    if user.has_role(UserRole.PARENT):
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == user.id,
                parent_students.c.student_id == student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Not authorized to access insights for this student")
        return student

    raise HTTPException(status_code=403, detail="Only parents and admins can access AI insights")


def _get_accessible_student_ids(db: Session, user: User) -> list[int]:
    """Return student IDs the user can view insights for."""
    if user.has_role(UserRole.ADMIN):
        return [row.id for row in db.query(Student.id).all()]
    if user.has_role(UserRole.PARENT):
        rows = db.execute(
            parent_students.select().where(parent_students.c.parent_id == user.id)
        ).fetchall()
        return [row.student_id for row in rows]
    return []


# ─── Data gathering helpers ────────────────────────────────────────────────────

def _gather_quiz_data(db: Session, student: Student) -> dict[str, Any]:
    """Gather quiz performance data for the student."""
    quiz_data: dict[str, list[float]] = {}
    try:
        rows = (
            db.query(QuizResult.percentage, StudyGuide.title)
            .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
            .filter(QuizResult.user_id == student.user_id)
            .order_by(QuizResult.completed_at.desc())
            .limit(30)
            .all()
        )
        for pct, title in rows:
            if title:
                quiz_data.setdefault(title, []).append(pct)
    except Exception as exc:
        logger.warning("Could not load quiz data for student %s: %s", student.id, exc)
    return {title: round(sum(scores) / len(scores), 1) for title, scores in quiz_data.items()}


def _gather_grade_entries(db: Session, student: Student) -> list[dict[str, Any]]:
    """Gather teacher grade entries for the student."""
    entries: list[dict[str, Any]] = []
    try:
        rows = (
            db.query(GradeEntry)
            .filter(GradeEntry.student_id == student.id, GradeEntry.is_published == True)  # noqa: E712
            .order_by(GradeEntry.created_at.desc())
            .limit(30)
            .all()
        )
        for row in rows:
            course_name = None
            try:
                if row.course:
                    course_name = row.course.name
            except Exception:
                pass
            entries.append({
                "grade": row.grade,
                "max_grade": row.max_grade,
                "feedback": row.feedback,
                "term": row.term,
                "course": course_name,
                "letter_grade": row.letter_grade,
            })
    except Exception as exc:
        logger.warning("Could not load grade entries for student %s: %s", student.id, exc)
    return entries


def _gather_report_card_data(db: Session, student: Student) -> list[dict[str, Any]]:
    """Gather report card marks for the student."""
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


def _gather_assignment_data(db: Session, student: Student) -> dict[str, Any]:
    """Gather assignment completion and overdue info for the last 30 days."""
    overdue_count = 0
    completion_rate = 0.0
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        # Get all assignments for courses the student is enrolled in
        # Check overdue by looking at due_date < today with no submission
        from app.models.course import student_courses
        enrolled_course_ids = [
            row.course_id
            for row in db.execute(
                student_courses.select().where(student_courses.c.student_id == student.id)
            ).fetchall()
        ]
        if enrolled_course_ids:
            total_due = (
                db.query(Assignment)
                .filter(
                    Assignment.course_id.in_(enrolled_course_ids),
                    Assignment.due_date >= cutoff,
                    Assignment.due_date != None,  # noqa: E711
                )
                .count()
            )
            today = datetime.utcnow()
            overdue = (
                db.query(Assignment)
                .filter(
                    Assignment.course_id.in_(enrolled_course_ids),
                    Assignment.due_date < today,
                    Assignment.due_date >= cutoff,
                )
                .count()
            )
            overdue_count = overdue
            if total_due > 0:
                completion_rate = round(((total_due - overdue) / total_due) * 100, 1)
    except Exception as exc:
        logger.warning("Could not load assignment data for student %s: %s", student.id, exc)
    return {"overdue": overdue_count, "completion_rate": completion_rate}


def _gather_study_guide_count(db: Session, student: Student) -> int:
    """Count study guides created this month for the student."""
    count = 0
    try:
        first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        count = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.user_id == student.user_id,
                StudyGuide.created_at >= first_of_month,
            )
            .count()
        )
    except Exception as exc:
        logger.warning("Could not load study guide count for student %s: %s", student.id, exc)
    return count


def _gather_exam_prep_summary(db: Session, student: Student) -> str:
    """Get latest exam prep weak areas summary."""
    try:
        latest_plan = (
            db.query(ExamPrepPlan)
            .filter(ExamPrepPlan.student_id == student.id, ExamPrepPlan.status == "active")
            .order_by(ExamPrepPlan.generated_at.desc())
            .first()
        )
        if latest_plan and latest_plan.weak_areas:
            weak = latest_plan.weak_areas
            if isinstance(weak, str):
                weak = json.loads(weak)
            if isinstance(weak, list) and weak:
                topics = [w.get("topic", "") for w in weak[:3] if isinstance(w, dict)]
                return f"Weak areas from exam prep: {', '.join(t for t in topics if t)}"
    except Exception as exc:
        logger.warning("Could not load exam prep data for student %s: %s", student.id, exc)
    return "No exam prep data available"


# ─── AI prompt builder ─────────────────────────────────────────────────────────

def _build_insight_prompt(
    student_name: str,
    streak: int,
    longest: int,
    quiz_summary: dict[str, float],
    grade_entries: list[dict[str, Any]],
    assignment_data: dict[str, Any],
    report_card_marks: list[dict[str, Any]],
    guide_count: int,
    exam_prep_summary: str,
) -> str:
    # Format quiz summary
    if quiz_summary:
        quiz_lines = [f"  - {title}: {avg}% average" for title, avg in list(quiz_summary.items())[:10]]
        quiz_text = "\n".join(quiz_lines)
    else:
        quiz_text = "  No quiz data available"

    # Format grade summary
    if grade_entries:
        grade_lines = []
        for g in grade_entries[:10]:
            course = g.get("course") or "Unknown subject"
            if g.get("grade") is not None:
                max_g = g.get("max_grade") or 100
                pct = round((g["grade"] / max_g) * 100, 1) if max_g else g["grade"]
                letter = g.get("letter_grade") or ""
                grade_lines.append(f"  - {course}: {pct}% {letter}".strip())
        grade_text = "\n".join(grade_lines) if grade_lines else "  No teacher grades available"
    else:
        grade_text = "  No teacher grades available"

    # Format report card
    if report_card_marks:
        rc_lines = []
        for m in report_card_marks[:8]:
            subj = m.get("subject", "Unknown")
            pct = m.get("percentage") or m.get("mark")
            if pct is not None:
                rc_lines.append(f"  - {subj}: {pct}")
        report_card_text = "\n".join(rc_lines) if rc_lines else "  No report card data available"
    else:
        report_card_text = "  No report card data available"

    return f"""You are an educational advisor helping a parent understand their child's academic performance.
Analyze this data and return a JSON response with EXACTLY this structure:

{{
  "summary": "2-3 sentence overall assessment of the student's current academic state",
  "strengths": [
    "Strong quiz performance in Mathematics (avg 87%)",
    "Consistent study streak of 12 days showing good habits"
  ],
  "concerns": [
    "English Literature quiz scores declining (from 72% to 58% over 3 attempts)",
    "3 overdue assignments in the past 2 weeks"
  ],
  "recommendations": [
    "Schedule a focused review session for English Literature this week",
    "Review the 3 overdue assignments with your child today"
  ],
  "subject_analysis": {{
    "Mathematics": {{"trend": "improving", "avg_score": 87, "note": "Strong conceptual understanding"}},
    "English": {{"trend": "declining", "avg_score": 63, "note": "Needs attention"}}
  }},
  "learning_style_note": "Student engages most with quiz-based learning materials. Consider requesting more practice tests.",
  "parent_actions": [
    "Ask your child to show you their Math quiz scores this week — celebrate the 87% average",
    "Set aside 30 minutes Sunday to review the 3 overdue assignments together",
    "Message the English teacher to ask about extra support resources"
  ]
}}

Student data:
- Name: {student_name}
- Study streak: {streak} days (longest: {longest} days)
- Quiz performance (last 30 results):
{quiz_text}
- Teacher grades:
{grade_text}
- Assignments: {assignment_data['overdue']} overdue, {assignment_data['completion_rate']}% completion rate (last 30 days)
- Report card marks:
{report_card_text}
- Study guides created this month: {guide_count}
- Exam prep: {exam_prep_summary}

Return ONLY the JSON object. No markdown, no extra text."""


# ─── Response serializer ───────────────────────────────────────────────────────

def _serialize_insight(insight: AIInsight) -> dict[str, Any]:
    def _parse_json_field(val: str | None) -> Any:
        if not val:
            return None
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except Exception:
            return val

    return {
        "id": insight.id,
        "student_id": insight.student_id,
        "insight_type": insight.insight_type,
        "summary": insight.summary,
        "strengths": _parse_json_field(insight.strengths),
        "concerns": _parse_json_field(insight.concerns),
        "recommendations": _parse_json_field(insight.recommendations),
        "subject_analysis": _parse_json_field(insight.subject_analysis),
        "learning_style_note": insight.learning_style_note,
        "parent_actions": _parse_json_field(insight.parent_actions),
        "generated_at": insight.generated_at.isoformat() if insight.generated_at else None,
        "period_start": insight.period_start.isoformat() if insight.period_start else None,
        "period_end": insight.period_end.isoformat() if insight.period_end else None,
    }


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/generate", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def generate_insight(
    request: Request,
    body: GenerateInsightRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a holistic AI insight for a student.

    Aggregates quiz history, teacher grades, report card marks, assignment
    completion, study streak, and exam prep data — then uses AI to produce
    a structured insight with strengths, concerns, subject trends, and
    actionable parent items.
    """
    student = _verify_parent_or_admin_access(db, current_user, body.student_id)

    # Resolve student name
    student_name = "this student"
    try:
        if student.user:
            student_name = student.user.full_name or student_name
    except Exception:
        pass

    # Gather all performance data
    quiz_summary = _gather_quiz_data(db, student)
    grade_entries = _gather_grade_entries(db, student)
    report_card_marks = _gather_report_card_data(db, student)
    assignment_data = _gather_assignment_data(db, student)
    guide_count = _gather_study_guide_count(db, student)
    exam_prep_summary = _gather_exam_prep_summary(db, student)

    streak = student.study_streak_days or 0
    longest = student.longest_streak or 0

    # Save raw data snapshot for audit
    data_snapshot = {
        "quiz_summary": quiz_summary,
        "grade_entries": grade_entries[:10],
        "report_card_marks": report_card_marks[:8],
        "assignment_data": assignment_data,
        "guide_count": guide_count,
        "exam_prep_summary": exam_prep_summary,
        "streak": streak,
        "longest_streak": longest,
    }

    # Build and send AI prompt
    prompt = _build_insight_prompt(
        student_name=student_name,
        streak=streak,
        longest=longest,
        quiz_summary=quiz_summary,
        grade_entries=grade_entries,
        assignment_data=assignment_data,
        report_card_marks=report_card_marks,
        guide_count=guide_count,
        exam_prep_summary=exam_prep_summary,
    )

    system_prompt = (
        "You are an expert educational advisor specializing in K-12 academic performance analysis. "
        "Generate holistic, empathetic, and actionable insights for parents in valid JSON format only. "
        "Do not wrap JSON in markdown code blocks. Return only the raw JSON object."
    )

    try:
        raw_response = await ai_service.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=2500,
            temperature=0.6,
            user=current_user,
        )
    except Exception as exc:
        logger.error("AI generation failed for insight: %s", exc)
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again.")

    # Parse AI response
    summary = "AI analysis completed."
    strengths = None
    concerns = None
    recommendations = None
    subject_analysis = None
    learning_style_note = None
    parent_actions = None

    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        parsed: dict[str, Any] = json.loads(cleaned)
        summary = parsed.get("summary", summary)
        strengths = parsed.get("strengths")
        concerns = parsed.get("concerns")
        recommendations = parsed.get("recommendations")
        subject_analysis = parsed.get("subject_analysis")
        learning_style_note = parsed.get("learning_style_note")
        parent_actions = parsed.get("parent_actions")
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Could not parse AI insight response as JSON: %s — storing raw summary", exc)
        summary = raw_response[:500] if raw_response else summary

    # Save to database
    def _to_json(val: Any) -> str | None:
        if val is None:
            return None
        if isinstance(val, str):
            return val
        return json.dumps(val)

    insight = AIInsight(
        student_id=student.id,
        generated_by_user_id=current_user.id,
        insight_type=body.insight_type,
        summary=summary,
        strengths=_to_json(strengths),
        concerns=_to_json(concerns),
        recommendations=_to_json(recommendations),
        subject_analysis=_to_json(subject_analysis),
        learning_style_note=learning_style_note,
        parent_actions=_to_json(parent_actions),
        data_snapshot_json=json.dumps(data_snapshot),
        generated_at=datetime.utcnow(),
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    logger.info(
        "AI insight generated: id=%s student=%s type=%s by user=%s",
        insight.id, student.id, body.insight_type, current_user.id,
    )
    return _serialize_insight(insight)


@router.get("/student/{student_id}/latest")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_latest_insight(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent insight for a student.

    Used for the Parent Dashboard widget. Returns {exists: false} if none.
    """
    _verify_parent_or_admin_access(db, current_user, student_id)

    insight = (
        db.query(AIInsight)
        .filter(AIInsight.student_id == student_id)
        .order_by(AIInsight.generated_at.desc())
        .first()
    )
    if not insight:
        return {"exists": False}

    result = _serialize_insight(insight)
    result["exists"] = True
    return result


@router.get("/")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_insights(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List insights for the current parent's children (or all for admin)."""
    student_ids = _get_accessible_student_ids(db, current_user)
    if not student_ids:
        return []

    insights = (
        db.query(AIInsight)
        .filter(AIInsight.student_id.in_(student_ids))
        .order_by(AIInsight.generated_at.desc())
        .all()
    )
    return [_serialize_insight(i) for i in insights]


@router.get("/{insight_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_insight(
    request: Request,
    insight_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a specific insight by ID."""
    insight = db.query(AIInsight).filter(AIInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    # Verify access
    _verify_parent_or_admin_access(db, current_user, insight.student_id)
    return _serialize_insight(insight)


@router.delete("/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_insight(
    request: Request,
    insight_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an insight (parent/admin only)."""
    insight = db.query(AIInsight).filter(AIInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    _verify_parent_or_admin_access(db, current_user, insight.student_id)
    db.delete(insight)
    db.commit()
    logger.info("AI insight deleted: id=%s by user=%s", insight_id, current_user.id)
