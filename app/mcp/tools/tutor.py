"""
MCP AI Tutor Agent Tools for ClassBridge.

Exposes 3 FastAPI endpoints at /api/mcp/tools/tutor/... that allow LLM clients
to create personalised study plans (auto-creating Task records), get
prioritised study recommendations, and analyse study effectiveness.

RBAC:
  - Student: can only access their own data (student_id must match their Student record)
  - Parent:  can access their linked children
  - Teacher: can access enrolled students (effectiveness endpoint only)
  - Admin:   unrestricted
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.grade_entry import GradeEntry
from app.models.quiz_result import QuizResult
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.task import Task, TaskPriority
from app.models.user import User, UserRole
from app.services.ai_service import generate_content

router = APIRouter(prefix="/api/mcp/tools/tutor", tags=["mcp-tutor"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class StudyPlanRequest(BaseModel):
    student_id: Optional[int] = None
    goal: Optional[str] = Field(None, max_length=500)
    days: int = Field(7, ge=1, le=30)
    hours_per_day: float = Field(2.0, ge=0.5, le=12.0)
    focus_courses: Optional[list[int]] = None


class StudyPlanResponse(BaseModel):
    plan_markdown: str
    tasks_created: int
    student_id: int


class RecommendationsRequest(BaseModel):
    student_id: Optional[int] = None
    time_available: int = Field(30, ge=5, le=240, description="Minutes available to study")


class Recommendation(BaseModel):
    priority: int
    title: str
    description: str
    estimated_minutes: int
    category: str  # e.g. "overdue_assignment", "weak_area", "study_streak"


class RecommendationsResponse(BaseModel):
    student_id: int
    time_available: int
    recommendations: list[Recommendation]


class EffectivenessRequest(BaseModel):
    student_id: Optional[int] = None
    period: str = Field("7d", pattern=r"^\d+d$")


class TopicStatus(BaseModel):
    topic: str
    current_score: Optional[float] = None
    previous_score: Optional[float] = None
    trend: str  # "improved", "stagnated", "declining", "new"


class EffectivenessResponse(BaseModel):
    student_id: int
    period: str
    quiz_attempts_current: int
    quiz_attempts_previous: int
    avg_score_current: Optional[float] = None
    avg_score_previous: Optional[float] = None
    overall_trend: str  # "improving", "stable", "declining", "insufficient_data"
    topic_breakdown: list[TopicStatus]
    ai_analysis: str


# ---------------------------------------------------------------------------
# Helper: resolve student record with RBAC
# ---------------------------------------------------------------------------


def _resolve_student(
    student_id: Optional[int],
    current_user: User,
    db: Session,
    allow_teacher: bool = False,
) -> Student:
    """Return the Student record the current user may access.

    If student_id is None, defaults to the student record of current_user.
    Raises 403/404 on access denial or missing record.
    """
    if current_user.has_role(UserRole.ADMIN):
        # Admins can access any student
        if student_id is None:
            raise HTTPException(status_code=400, detail="Admins must provide student_id")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        if student_id is not None and student.id != student_id:
            raise HTTPException(status_code=403, detail="Students can only access their own data")
        return student

    if current_user.has_role(UserRole.PARENT):
        # Must supply student_id and it must be one of their children
        if student_id is None:
            # Default to first linked child
            child_row = (
                db.query(parent_students.c.student_id)
                .filter(parent_students.c.parent_id == current_user.id)
                .first()
            )
            if not child_row:
                raise HTTPException(status_code=404, detail="No linked children found")
            student_id = child_row.student_id
        # Verify ownership
        link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student_id,
            )
            .first()
        )
        if not link:
            raise HTTPException(status_code=403, detail="Access denied: not your child")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    if allow_teacher and current_user.has_role(UserRole.TEACHER):
        if student_id is None:
            raise HTTPException(status_code=400, detail="Teachers must provide student_id")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        # Verify teacher has at least one shared course with the student
        shared = (
            db.query(student_courses)
            .join(Course, Course.id == student_courses.c.course_id)
            .filter(
                student_courses.c.student_id == student.id,
                Course.teacher_id == current_user.id,
            )
            .first()
        )
        if not shared:
            raise HTTPException(status_code=403, detail="No shared courses with this student")
        return student

    raise HTTPException(status_code=403, detail="Insufficient permissions")


# ---------------------------------------------------------------------------
# Endpoint: create_study_plan
# ---------------------------------------------------------------------------


@router.post("/study-plan", response_model=StudyPlanResponse, operation_id="mcp_create_study_plan")
async def create_study_plan(
    req: StudyPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a personalised multi-day study plan and auto-create Task records."""
    student = _resolve_student(req.student_id, current_user, db, allow_teacher=False)

    # ---- Aggregate context ----
    now = datetime.now(tz=timezone.utc)
    week_ahead = now + timedelta(days=req.days)

    # 1. Upcoming assignments
    upcoming_assignments = (
        db.query(Assignment)
        .join(Course, Course.id == Assignment.course_id)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(
            student_courses.c.student_id == student.id,
            Assignment.due_date >= now,
            Assignment.due_date <= week_ahead,
        )
        .order_by(Assignment.due_date)
        .limit(20)
        .all()
    )
    if req.focus_courses:
        upcoming_assignments = [a for a in upcoming_assignments if a.course_id in req.focus_courses]

    # 2. Recent quiz results (last 30 days) — identify weak areas
    thirty_days_ago = now - timedelta(days=30)
    quiz_results = (
        db.query(QuizResult)
        .filter(
            QuizResult.user_id == student.user_id,
            QuizResult.completed_at >= thirty_days_ago,
        )
        .order_by(QuizResult.completed_at.desc())
        .limit(30)
        .all()
    )
    weak_topics: list[str] = []
    for qr in quiz_results:
        if qr.percentage < 70:
            guide = db.query(StudyGuide).filter(StudyGuide.id == qr.study_guide_id).first()
            if guide:
                weak_topics.append(f"{guide.title} ({qr.percentage:.0f}%)")

    # 3. Existing study guides
    study_guides = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == student.user_id,
            StudyGuide.archived_at.is_(None),
            StudyGuide.guide_type == "study_guide",
        )
        .order_by(StudyGuide.created_at.desc())
        .limit(10)
        .all()
    )

    # 4. Recent grades
    grade_entries = (
        db.query(GradeEntry)
        .filter(
            GradeEntry.student_id == student.id,
            GradeEntry.is_published == True,  # noqa: E712
        )
        .order_by(GradeEntry.created_at.desc())
        .limit(10)
        .all()
    )

    # ---- Build prompt ----
    assignments_text = "\n".join(
        f"- {a.title} (due: {a.due_date.strftime('%Y-%m-%d') if a.due_date else 'TBD'}, course: {a.course.name if a.course else 'Unknown'})"
        for a in upcoming_assignments
    ) or "No upcoming assignments"

    weak_text = "\n".join(f"- {t}" for t in weak_topics[:10]) or "None identified"

    guides_text = "\n".join(f"- {g.title}" for g in study_guides[:5]) or "No existing guides"

    grades_text = "\n".join(
        f"- {ge.course.name if ge.course else 'Unknown'}: {ge.grade}% ({ge.term or 'recent'})"
        for ge in grade_entries[:5]
    ) or "No grades on record"

    goal_text = f"Student goal: {req.goal}" if req.goal else ""

    prompt = f"""Create a {req.days}-day personalised study plan for a student.

{goal_text}
Available study time: {req.hours_per_day} hours per day
Plan period: {now.strftime('%Y-%m-%d')} to {week_ahead.strftime('%Y-%m-%d')}

UPCOMING ASSIGNMENTS:
{assignments_text}

WEAK AREAS (recent quiz scores below 70%):
{weak_text}

EXISTING STUDY MATERIALS:
{guides_text}

RECENT GRADES:
{grades_text}

Generate a structured study plan in Markdown. For each day include:
- Specific tasks labelled "Day N: <task description>" OR bullet items starting with "- [ ] "
- Time estimates
- Which assignment or topic it addresses

Focus on addressing weak areas and upcoming deadlines first.
Keep each day's tasks achievable within {req.hours_per_day} hours.
End the plan with a brief motivation message."""

    plan_markdown = await generate_content(
        prompt,
        system_prompt=(
            "You are an expert educational tutor who creates personalised, actionable study plans. "
            "Be specific, encouraging, and realistic about the time required for each task."
        ),
        max_tokens=2500,
    )

    # ---- Parse tasks and create Task records ----
    tasks_created = 0
    day_pattern = re.compile(r"^#+\s*Day\s+(\d+)[:\s](.+)", re.IGNORECASE)
    bullet_pattern = re.compile(r"^[-*]\s+\[?\s*\]?\s*(.+)")

    current_day_offset = 0
    for line in plan_markdown.splitlines():
        line = line.strip()
        day_match = day_pattern.match(line)
        bullet_match = bullet_pattern.match(line) if not day_match else None

        if day_match:
            current_day_offset = int(day_match.group(1)) - 1
            task_title = day_match.group(2).strip()[:255]
        elif bullet_match:
            task_title = bullet_match.group(1).strip()[:255]
        else:
            continue

        if not task_title:
            continue

        due = now + timedelta(days=current_day_offset)
        task = Task(
            created_by_user_id=student.user_id,
            assigned_to_user_id=student.user_id,
            title=task_title,
            description=f"Auto-generated by AI study plan ({now.strftime('%Y-%m-%d')})",
            due_date=due,
            priority=TaskPriority.MEDIUM.value,
            category="study_plan",
        )
        db.add(task)
        tasks_created += 1

        # Cap at days * 3 tasks to avoid flooding
        if tasks_created >= req.days * 3:
            break

    db.commit()

    return StudyPlanResponse(
        plan_markdown=plan_markdown,
        tasks_created=tasks_created,
        student_id=student.id,
    )


# ---------------------------------------------------------------------------
# Endpoint: get_study_recommendations
# ---------------------------------------------------------------------------


@router.post("/recommendations", response_model=RecommendationsResponse, operation_id="mcp_get_study_recommendations")
async def get_study_recommendations(
    req: RecommendationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return top 3 prioritised study recommendations for the student."""
    student = _resolve_student(req.student_id, current_user, db, allow_teacher=False)
    now = datetime.now(tz=timezone.utc)

    # 1. Overdue assignments
    overdue = (
        db.query(Assignment)
        .join(Course, Course.id == Assignment.course_id)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(
            student_courses.c.student_id == student.id,
            Assignment.due_date < now,
        )
        .order_by(Assignment.due_date)
        .limit(5)
        .all()
    )

    # 2. Recent weak quiz areas
    seven_days_ago = now - timedelta(days=7)
    weak_results = (
        db.query(QuizResult, StudyGuide)
        .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
        .filter(
            QuizResult.user_id == student.user_id,
            QuizResult.completed_at >= seven_days_ago,
            QuizResult.percentage < 70,
        )
        .order_by(QuizResult.percentage)
        .limit(5)
        .all()
    )

    # 3. Study streak
    streak = student.study_streak_days or 0

    # Build AI prompt
    overdue_text = "\n".join(
        f"- {a.title} (was due {a.due_date.strftime('%Y-%m-%d') if a.due_date else 'unknown'})"
        for a in overdue
    ) or "None"
    weak_text = "\n".join(
        f"- {guide.title}: {qr.percentage:.0f}%"
        for qr, guide in weak_results
    ) or "None"

    prompt = f"""A student has {req.time_available} minutes available to study right now.

Study streak: {streak} day(s)

Overdue assignments:
{overdue_text}

Recently poor quiz performance (below 70%):
{weak_text}

Return EXACTLY 3 prioritised study recommendations as a JSON array with this structure:
[
  {{
    "priority": 1,
    "title": "Short action title",
    "description": "1-2 sentence explanation of what to do and why",
    "estimated_minutes": 20,
    "category": "overdue_assignment"
  }}
]

category must be one of: overdue_assignment, weak_area, study_streak, review, general
Return ONLY the JSON array, no other text."""

    ai_response = await generate_content(
        prompt,
        system_prompt="You are a study coach who gives concise, actionable recommendations. Return only valid JSON.",
        max_tokens=600,
        temperature=0.4,
    )

    # Parse AI response
    try:
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?|```", "", ai_response).strip()
        recs_data = json.loads(cleaned)
        recommendations = [Recommendation(**r) for r in recs_data[:3]]
    except Exception:
        # Fallback: return a single generic recommendation
        recommendations = [
            Recommendation(
                priority=1,
                title="Review your study materials",
                description="Open your most recent study guide and review the key concepts.",
                estimated_minutes=min(req.time_available, 30),
                category="general",
            )
        ]

    return RecommendationsResponse(
        student_id=student.id,
        time_available=req.time_available,
        recommendations=recommendations,
    )


# ---------------------------------------------------------------------------
# Endpoint: analyze_study_effectiveness
# ---------------------------------------------------------------------------


@router.post("/effectiveness", response_model=EffectivenessResponse, operation_id="mcp_analyze_study_effectiveness")
async def analyze_study_effectiveness(
    req: EffectivenessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyse quiz score trends across a period and return an AI effectiveness report."""
    student = _resolve_student(req.student_id, current_user, db, allow_teacher=True)
    now = datetime.now(tz=timezone.utc)

    # Parse period (e.g. "7d" -> 7 days)
    days = int(req.period.rstrip("d"))
    period_start = now - timedelta(days=days)
    prev_period_start = period_start - timedelta(days=days)

    # Current period quiz results
    current_results = (
        db.query(QuizResult, StudyGuide)
        .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
        .filter(
            QuizResult.user_id == student.user_id,
            QuizResult.completed_at >= period_start,
        )
        .all()
    )

    # Previous period quiz results
    prev_results = (
        db.query(QuizResult, StudyGuide)
        .join(StudyGuide, StudyGuide.id == QuizResult.study_guide_id)
        .filter(
            QuizResult.user_id == student.user_id,
            QuizResult.completed_at >= prev_period_start,
            QuizResult.completed_at < period_start,
        )
        .all()
    )

    def _avg(results: list) -> Optional[float]:
        if not results:
            return None
        return round(sum(qr.percentage for qr, _ in results) / len(results), 1)

    avg_current = _avg(current_results)
    avg_prev = _avg(prev_results)

    # Overall trend
    if avg_current is None:
        overall_trend = "insufficient_data"
    elif avg_prev is None:
        overall_trend = "insufficient_data"
    elif avg_current >= avg_prev + 5:
        overall_trend = "improving"
    elif avg_current <= avg_prev - 5:
        overall_trend = "declining"
    else:
        overall_trend = "stable"

    # Topic breakdown: group by study guide title
    current_by_topic: dict[str, list[float]] = {}
    for qr, guide in current_results:
        current_by_topic.setdefault(guide.title, []).append(qr.percentage)

    prev_by_topic: dict[str, list[float]] = {}
    for qr, guide in prev_results:
        prev_by_topic.setdefault(guide.title, []).append(qr.percentage)

    topic_breakdown: list[TopicStatus] = []
    all_topics = set(current_by_topic) | set(prev_by_topic)
    for topic in list(all_topics)[:15]:
        curr_scores = current_by_topic.get(topic, [])
        prev_scores = prev_by_topic.get(topic, [])
        curr_avg = round(sum(curr_scores) / len(curr_scores), 1) if curr_scores else None
        prev_avg = round(sum(prev_scores) / len(prev_scores), 1) if prev_scores else None
        if curr_avg is None:
            trend = "stagnated"
        elif prev_avg is None:
            trend = "new"
        elif curr_avg >= prev_avg + 5:
            trend = "improved"
        elif curr_avg <= prev_avg - 5:
            trend = "declining"
        else:
            trend = "stagnated"
        topic_breakdown.append(TopicStatus(topic=topic, current_score=curr_avg, previous_score=prev_avg, trend=trend))

    # Sort: declining first, then stagnated, then improved
    trend_order = {"declining": 0, "stagnated": 1, "new": 2, "improved": 3}
    topic_breakdown.sort(key=lambda t: trend_order.get(t.trend, 99))

    # AI analysis
    topic_summary = "\n".join(
        f"- {t.topic}: {t.current_score}% (prev: {t.previous_score}%) [{t.trend}]"
        for t in topic_breakdown
    ) or "No quiz data for this period"

    prompt = f"""Analyse a student's study effectiveness over the last {days} days.

Current period ({days} days): {len(current_results)} quiz attempts, avg score: {avg_current}%
Previous period ({days} days): {len(prev_results)} quiz attempts, avg score: {avg_prev}%
Overall trend: {overall_trend}

Topic breakdown:
{topic_summary}

Write a concise (3-5 sentence) effectiveness analysis that:
1. Summarises overall progress
2. Highlights the most improved and most concerning topics
3. Gives 1-2 specific, actionable suggestions to improve weak areas
Use encouraging but honest language suitable for a K-12 student."""

    ai_analysis = await generate_content(
        prompt,
        system_prompt="You are a supportive educational coach providing concise, actionable study effectiveness feedback.",
        max_tokens=400,
        temperature=0.5,
    )

    return EffectivenessResponse(
        student_id=student.id,
        period=req.period,
        quiz_attempts_current=len(current_results),
        quiz_attempts_previous=len(prev_results),
        avg_score_current=avg_current,
        avg_score_previous=avg_prev,
        overall_trend=overall_trend,
        topic_breakdown=topic_breakdown,
        ai_analysis=ai_analysis,
    )
