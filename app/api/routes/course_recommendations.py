"""AI Course Recommendations and University Pathway Alignment (#503, #506).

Routes:
  POST  /api/recommendations/courses                  — generate AI course recommendations
  GET   /api/recommendations/courses/{plan_id}        — get latest cached recommendations
  GET   /api/recommendations/university-pathways      — map plan courses to university program requirements
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.academic_plan import AcademicPlan, PlanCourse
from app.models.course_recommendation import CourseRecommendation
from app.models.grade_entry import GradeEntry
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.services.ai_service import generate_content
from app.data.university_programs import UNIVERSITY_PROGRAMS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Course Recommendations"])

# ---------------------------------------------------------------------------
# Simple in-memory cache: { plan_id -> (generated_at, CourseRecommendation.id) }
# Avoids re-generating AI content within 1 hour of the last generation.
# ---------------------------------------------------------------------------
_recommendation_cache: dict[int, datetime] = {}
_CACHE_TTL = timedelta(hours=1)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class GenerateRecommendationsRequest(BaseModel):
    plan_id: int
    student_id: Optional[int] = None
    goal: str = Field(..., pattern="^(university|college|workplace|undecided)$")
    interests: list[str] = Field(default_factory=list)
    target_programs: Optional[list[str]] = None


class RecommendationItem(BaseModel):
    course_code: str
    course_name: str
    grade_level: int
    reason: str
    priority: str  # "high" | "medium" | "low"

    class Config:
        from_attributes = True


class RecommendationsResponse(BaseModel):
    id: int
    plan_id: int
    student_id: int
    goal: str
    recommendations: list[RecommendationItem]
    overall_advice: Optional[str]
    generated_at: str
    cached: bool = False

    class Config:
        from_attributes = True


class PathwayProgramResult(BaseModel):
    name: str
    universities: list[str]
    required_courses: list[str]
    covered: list[str]
    missing: list[str]
    recommended_courses: list[str]
    recommended_covered: list[str]
    readiness_pct: float
    min_average: Optional[int]
    notes: str


class UniversityPathwaysResponse(BaseModel):
    plan_id: int
    programs: list[PathwayProgramResult]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_student_for_user(db: Session, current_user: User, student_id: Optional[int]) -> Student:
    """Resolve the target student, enforcing access control."""
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        # Students can only request their own data
        if student_id and student_id != student.id:
            raise HTTPException(status_code=403, detail="Access denied")
        return student

    if current_user.has_role(UserRole.PARENT):
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for parents")
        # Verify parent-student link
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Not linked to this student")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    if current_user.has_role(UserRole.ADMIN):
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for admins")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    raise HTTPException(status_code=403, detail="Access denied")


def _get_plan(db: Session, plan_id: int, student: Student) -> AcademicPlan:
    """Load an academic plan, ensuring it belongs to the student."""
    plan = db.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Academic plan not found")
    if plan.student_id != student.id:
        raise HTTPException(status_code=403, detail="Access denied to this plan")
    return plan


def _build_plan_summary(plan: AcademicPlan) -> str:
    """Build a human-readable summary of the plan's courses for the AI prompt."""
    lines = []
    courses_by_grade: dict[int, list[PlanCourse]] = {}
    for pc in plan.plan_courses:
        courses_by_grade.setdefault(pc.grade_level, []).append(pc)

    for grade in sorted(courses_by_grade.keys()):
        semester_courses: dict[int, list[str]] = {}
        for pc in courses_by_grade[grade]:
            sem = pc.semester or 1
            semester_courses.setdefault(sem, []).append(
                f"{pc.course_code} ({pc.course_name})"
            )
        for sem in sorted(semester_courses.keys()):
            lines.append(f"  Grade {grade} Semester {sem}: {', '.join(semester_courses[sem])}")

    return "\n".join(lines) if lines else "  No courses planned yet"


def _get_strong_subjects(db: Session, student: Student) -> list[str]:
    """Return subject areas where the student has performed well (>=75%)."""
    entries = (
        db.query(GradeEntry)
        .filter(
            GradeEntry.student_id == student.id,
            GradeEntry.is_published == True,
            GradeEntry.grade != None,
        )
        .all()
    )
    if not entries:
        return []

    subject_scores: dict[str, list[float]] = {}
    for entry in entries:
        if entry.course and entry.grade is not None:
            # Use course name as rough subject area
            subject = entry.course.name
            subject_scores.setdefault(subject, []).append(entry.grade)

    strong = []
    for subject, scores in subject_scores.items():
        avg = sum(scores) / len(scores)
        if avg >= 75:
            strong.append(f"{subject} ({avg:.0f}%)")

    return strong


def _serialize_rec(rec: CourseRecommendation) -> RecommendationsResponse:
    recs_raw = rec.recommendations or []
    items = []
    for r in recs_raw:
        items.append(RecommendationItem(
            course_code=r.get("course_code", ""),
            course_name=r.get("course_name", ""),
            grade_level=int(r.get("grade_level", 11)),
            reason=r.get("reason", ""),
            priority=r.get("priority", "medium"),
        ))
    return RecommendationsResponse(
        id=rec.id,
        plan_id=rec.plan_id,
        student_id=rec.student_id,
        goal=rec.goal,
        recommendations=items,
        overall_advice=rec.overall_advice,
        generated_at=rec.generated_at.isoformat() if rec.generated_at else "",
        cached=False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/courses", response_model=RecommendationsResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def generate_course_recommendations(
    request: Request,
    body: GenerateRecommendationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN)),
):
    """Generate AI-powered course recommendations for a student's academic plan.

    Uses the student's current plan, grades, goal pathway, interests, and
    target programs to suggest 5-8 courses via Claude.
    """
    student = _get_student_for_user(db, current_user, body.student_id)
    plan = _get_plan(db, body.plan_id, student)

    # Check cache — return existing result if < 1 hour old
    cached_ts = _recommendation_cache.get(body.plan_id)
    if cached_ts and (datetime.now(timezone.utc) - cached_ts.replace(tzinfo=timezone.utc)) < _CACHE_TTL:
        existing = (
            db.query(CourseRecommendation)
            .filter(
                CourseRecommendation.plan_id == body.plan_id,
                CourseRecommendation.goal == body.goal,
            )
            .order_by(CourseRecommendation.generated_at.desc())
            .first()
        )
        if existing:
            result = _serialize_rec(existing)
            result.cached = True
            return result

    # Build AI prompt
    plan_summary = _build_plan_summary(plan)
    strong_subjects = _get_strong_subjects(db, student)
    strong_subjects_str = (
        ", ".join(strong_subjects) if strong_subjects else "Not enough grade data available"
    )
    interests_str = ", ".join(body.interests) if body.interests else "Not specified"
    target_programs_str = (
        ", ".join(body.target_programs) if body.target_programs else "Not specified"
    )

    # List all course codes already in the plan to avoid duplication
    existing_codes = {pc.course_code for pc in plan.plan_courses}
    existing_codes_str = ", ".join(sorted(existing_codes)) if existing_codes else "None"

    prompt = f"""You are an Ontario high school guidance counselor. Based on this student's academic plan and goals, recommend 5-8 courses they should take.

Student info:
- Current plan courses:
{plan_summary}
- Courses already in plan (do NOT recommend these): {existing_codes_str}
- Strong subjects (based on grades): {strong_subjects_str}
- Goal pathway: {body.goal}
- Interests: {interests_str}
- Target university/college programs: {target_programs_str}

Recommend courses that:
1. Fill gaps in Ontario compulsory credit requirements (English, Math, Science, etc.)
2. Strengthen the student for their stated goal pathway
3. Are appropriate prerequisites for their target programs
4. Are NOT already in their plan
5. Are realistic Ontario high school course codes (e.g. MHF4U, ENG4U, ICS3U, etc.)

Return ONLY a JSON object with this exact structure:
{{"recommendations": [{{"course_code": "MHF4U", "course_name": "Advanced Functions", "grade_level": 12, "reason": "Required for university STEM programs", "priority": "high"}}], "overall_advice": "Brief 2-3 sentence overall guidance for this student."}}

Priority must be "high", "medium", or "low".
Return ONLY the JSON — no markdown, no explanation."""

    system_prompt = (
        "You are an expert Ontario high school guidance counselor. "
        "You know all Ontario Ministry of Education course codes and admission requirements. "
        "Always return valid JSON only."
    )

    logger.info(
        "Generating course recommendations | plan_id=%s | student_id=%s | goal=%s",
        body.plan_id, student.id, body.goal,
    )

    raw_content = await generate_content(prompt, system_prompt, max_tokens=1500, temperature=0.4)

    # Parse AI response
    try:
        # Strip possible markdown code fences
        clean = raw_content.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            clean = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        parsed = json.loads(clean)
        recs_list = parsed.get("recommendations", [])
        overall_advice = parsed.get("overall_advice", "")
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Failed to parse AI recommendation response: %s | raw=%s", exc, raw_content[:500])
        raise HTTPException(
            status_code=502,
            detail="AI returned an unexpected response format. Please try again.",
        )

    # Persist to DB
    rec = CourseRecommendation(
        plan_id=body.plan_id,
        student_id=student.id,
        goal=body.goal,
        interests=body.interests,
        target_programs=body.target_programs,
        recommendations=recs_list,
        overall_advice=overall_advice,
        generated_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Update cache
    _recommendation_cache[body.plan_id] = datetime.utcnow()

    return _serialize_rec(rec)


@router.get("/courses/{plan_id}", response_model=RecommendationsResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_latest_recommendations(
    request: Request,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent AI recommendations for a plan if generated within the last hour."""
    # Determine student access
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
    elif current_user.has_role(UserRole.PARENT):
        # Allow if plan belongs to one of the parent's children
        plan = db.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == plan.student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Access denied")
        student = db.query(Student).filter(Student.id == plan.student_id).first()
    elif current_user.has_role(UserRole.ADMIN):
        plan = db.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        student = db.query(Student).filter(Student.id == plan.student_id).first()
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    rec = (
        db.query(CourseRecommendation)
        .filter(CourseRecommendation.plan_id == plan_id)
        .order_by(CourseRecommendation.generated_at.desc())
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="No recommendations found for this plan")

    # Check freshness
    cutoff = datetime.utcnow() - _CACHE_TTL
    is_cached = rec.generated_at >= cutoff if rec.generated_at else False

    result = _serialize_rec(rec)
    result.cached = is_cached
    return result


@router.get("/university-pathways", response_model=UniversityPathwaysResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_university_pathways(
    request: Request,
    plan_id: int = Query(..., description="Academic plan ID to analyse"),
    programs: Optional[str] = Query(
        None,
        description="Comma-separated list of program names to check (e.g. 'Computer Science,Engineering'). "
                    "Omit to check all programs.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Map a student's academic plan against Ontario university admission requirements.

    Returns per-program gap analysis: which required courses are covered, which
    are missing, and a readiness percentage.
    """
    # Resolve access
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        plan = _get_plan(db, plan_id, student)
    elif current_user.has_role(UserRole.PARENT):
        plan = db.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == plan.student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.has_role(UserRole.ADMIN):
        plan = db.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    # Collect all course codes in the plan
    plan_codes: set[str] = {pc.course_code.upper() for pc in plan.plan_courses}

    # Determine which programs to evaluate
    if programs:
        requested_names = [p.strip() for p in programs.split(",") if p.strip()]
    else:
        requested_names = list(UNIVERSITY_PROGRAMS.keys())

    results: list[PathwayProgramResult] = []

    for program_name in requested_names:
        prog = UNIVERSITY_PROGRAMS.get(program_name)
        if prog is None:
            # Try case-insensitive lookup
            for key in UNIVERSITY_PROGRAMS:
                if key.lower() == program_name.lower():
                    prog = UNIVERSITY_PROGRAMS[key]
                    program_name = key
                    break
        if prog is None:
            # Unknown program — skip gracefully
            continue

        required = [c.upper() for c in prog.get("required_courses", [])]
        recommended = [c.upper() for c in prog.get("recommended_courses", [])]

        covered = [c for c in required if c in plan_codes]
        missing = [c for c in required if c not in plan_codes]

        rec_covered = [c for c in recommended if c in plan_codes]

        # Readiness: based on required courses covered, with bonus for recommended
        if required:
            req_pct = len(covered) / len(required) * 100
        else:
            req_pct = 100.0

        # Bonus: up to 10 points for recommended courses
        if recommended:
            rec_bonus = (len(rec_covered) / len(recommended)) * 10.0
        else:
            rec_bonus = 0.0

        readiness_pct = min(100.0, round(req_pct * 0.9 + rec_bonus, 1))

        # Build notes string
        if not missing:
            notes = (
                f"All required courses are covered. "
                f"{len(rec_covered)}/{len(recommended)} recommended courses are in the plan."
            )
        else:
            missing_str = ", ".join(missing)
            notes = (
                f"Missing required course(s): {missing_str}. "
                f"{len(rec_covered)}/{len(recommended)} recommended courses are in the plan."
            )
        if prog.get("description"):
            notes += f" {prog['description']}"

        results.append(
            PathwayProgramResult(
                name=program_name,
                universities=prog.get("universities", []),
                required_courses=required,
                covered=covered,
                missing=missing,
                recommended_courses=recommended,
                recommended_covered=rec_covered,
                readiness_pct=readiness_pct,
                min_average=prog.get("min_average"),
                notes=notes,
            )
        )

    # Sort by readiness descending so the best-matched programs appear first
    results.sort(key=lambda r: r.readiness_pct, reverse=True)

    return UniversityPathwaysResponse(plan_id=plan_id, programs=results)
