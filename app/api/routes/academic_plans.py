"""Academic Plan API routes (#501, #502).

Routes:
  POST   /api/academic-plans/                         — create plan
  GET    /api/academic-plans/                         — list plans (scoped to user)
  GET    /api/academic-plans/{plan_id}                — plan detail with courses
  PUT    /api/academic-plans/{plan_id}                — update name/notes/status
  DELETE /api/academic-plans/{plan_id}                — delete plan
  POST   /api/academic-plans/{plan_id}/courses        — add course (prereq validated)
  DELETE /api/academic-plans/{plan_id}/courses/{id}   — remove course
  GET    /api/academic-plans/{plan_id}/validate       — OSSD graduation check
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.academic_plan import AcademicPlan, PlanCourse
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_feature
from app.schemas.academic_plan import (
    AcademicPlanCreate,
    AcademicPlanResponse,
    AcademicPlanUpdate,
    PlanCourseCreate,
    PlanCourseResponse,
    ValidationResultResponse,
)
from app.services import graduation_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/academic-plans", tags=["Academic Plans"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_student_for_user(db: Session, user: User, student_id: int | None) -> Student:
    """Resolve which student the caller is acting on; enforce RBAC."""
    if user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        if student_id and student.id != student_id:
            raise HTTPException(status_code=403, detail="Students can only access their own plans")
        return student

    if user.has_role(UserRole.PARENT):
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for parent users")
        # Verify the parent is linked to this student
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == user.id,
                parent_students.c.student_id == student_id,
            )
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Not authorized to manage plans for this student")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    if user.has_role(UserRole.ADMIN):
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    raise HTTPException(status_code=403, detail="Insufficient permissions")


def _get_plan_with_access(db: Session, plan_id: int, user: User) -> AcademicPlan:
    """Load a plan and verify the caller has access to it."""
    plan = db.query(AcademicPlan).filter(AcademicPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Academic plan not found")

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


def _get_accessible_student_ids(db: Session, user: User) -> list[int]:
    """Return the student IDs the user is allowed to see plans for."""
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


def _fetch_catalog_course(db: Session, course_code: str) -> dict[str, Any] | None:
    """Try to load course details from the course_catalog table (Stream A model).

    Returns a dict with keys: course_name, subject_area, credit_value, pathway,
    prerequisites (list[str]).  Returns None if the table or course does not exist.
    """
    try:
        from sqlalchemy import text
        row = db.execute(
            text(
                "SELECT course_name, subject_area, credit_value, pathway, prerequisites "
                "FROM course_catalog WHERE course_code = :code LIMIT 1"
            ),
            {"code": course_code.upper()},
        ).fetchone()
        if not row:
            return None
        prereq_raw = row[4] if len(row) > 4 else None
        prereqs: list[str] = []
        if prereq_raw:
            import json
            try:
                parsed = json.loads(prereq_raw)
                if isinstance(parsed, list):
                    prereqs = [str(p) for p in parsed]
                elif isinstance(parsed, str):
                    prereqs = [parsed]
            except (ValueError, TypeError):
                # Possibly a comma-separated string
                prereqs = [p.strip() for p in str(prereq_raw).split(",") if p.strip()]

        return {
            "course_name": row[0] or course_code,
            "subject_area": row[1],
            "credit_value": float(row[2]) if row[2] is not None else 1.0,
            "pathway": row[3],
            "prerequisites": prereqs,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POST /  — create plan
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AcademicPlanResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_plan(
    request: Request,
    body: AcademicPlanCreate,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new multi-year academic plan for a student.

    Parent or student roles allowed.  student_id defaults to the caller's own
    student profile when the caller is a student.
    """
    if not any(current_user.has_role(r) for r in (UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    student = _get_student_for_user(db, current_user, body.student_id)

    plan = AcademicPlan(
        student_id=student.id,
        created_by_user_id=current_user.id,
        name=body.name,
        start_grade=body.start_grade,
        target_graduation_year=body.target_graduation_year,
        notes=body.notes,
        status="draft",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    logger.info(f"Academic plan created: id={plan.id} student={student.id} by user={current_user.id}")
    return plan


# ---------------------------------------------------------------------------
# GET /  — list plans
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[AcademicPlanResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_plans(
    request: Request,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List academic plans scoped to the current user's accessible students."""
    student_ids = _get_accessible_student_ids(db, current_user)
    if not student_ids:
        return []

    plans = (
        db.query(AcademicPlan)
        .filter(AcademicPlan.student_id.in_(student_ids))
        .order_by(AcademicPlan.created_at.desc())
        .all()
    )
    return plans


# ---------------------------------------------------------------------------
# GET /{plan_id}  — plan detail
# ---------------------------------------------------------------------------

@router.get("/{plan_id}", response_model=AcademicPlanResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_plan(
    request: Request,
    plan_id: int,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full plan detail including all plan_courses."""
    plan = _get_plan_with_access(db, plan_id, current_user)
    return plan


# ---------------------------------------------------------------------------
# PUT /{plan_id}  — update plan metadata
# ---------------------------------------------------------------------------

@router.put("/{plan_id}", response_model=AcademicPlanResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_plan(
    request: Request,
    plan_id: int,
    body: AcademicPlanUpdate,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update name, notes, status or target_graduation_year of a plan."""
    plan = _get_plan_with_access(db, plan_id, current_user)

    if body.name is not None:
        plan.name = body.name
    if body.status is not None:
        plan.status = body.status
    if body.notes is not None:
        plan.notes = body.notes
    if body.target_graduation_year is not None:
        plan.target_graduation_year = body.target_graduation_year

    db.commit()
    db.refresh(plan)

    logger.info(f"Academic plan updated: id={plan.id} by user={current_user.id}")
    return plan


# ---------------------------------------------------------------------------
# DELETE /{plan_id}  — delete plan
# ---------------------------------------------------------------------------

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def delete_plan(
    request: Request,
    plan_id: int,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an academic plan and all its courses (cascade)."""
    plan = _get_plan_with_access(db, plan_id, current_user)
    db.delete(plan)
    db.commit()
    logger.info(f"Academic plan deleted: id={plan_id} by user={current_user.id}")


# ---------------------------------------------------------------------------
# POST /{plan_id}/courses  — add a course
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/courses", status_code=status.HTTP_201_CREATED, response_model=PlanCourseResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def add_course(
    request: Request,
    plan_id: int,
    body: PlanCourseCreate,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a course to an academic plan.

    - Validates prerequisites against completed courses in this plan.
    - Fetches course details from course_catalog table when available.
    - Raises 409 if the course code is already in the plan.
    """
    plan = _get_plan_with_access(db, plan_id, current_user)

    course_code = body.course_code.upper()

    # Duplicate check
    existing = (
        db.query(PlanCourse)
        .filter(PlanCourse.plan_id == plan_id, PlanCourse.course_code == course_code)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{course_code} is already in this plan",
        )

    # Fetch catalog data
    catalog_data = _fetch_catalog_course(db, course_code)

    # Resolve course_name
    course_name = (
        body.course_name
        or (catalog_data and catalog_data.get("course_name"))
        or course_code
    )

    subject_area = body.subject_area or (catalog_data and catalog_data.get("subject_area"))
    credit_value = body.credit_value if body.credit_value is not None else (
        (catalog_data and catalog_data.get("credit_value")) or 1.0
    )
    pathway = body.pathway or (catalog_data and catalog_data.get("pathway"))

    # Build catalog lookup dict for prereq checking
    catalog_lookup: dict[str, Any] = {}
    if catalog_data:
        catalog_lookup[course_code] = catalog_data

    # Prerequisite check — only against completed courses in the plan
    completed_codes = [
        pc.course_code
        for pc in plan.plan_courses
        if pc.status == "completed"
    ]
    can_take, reason = graduation_engine.check_prerequisites(
        course_code, completed_codes, catalog_lookup
    )
    if not can_take:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason or f"Prerequisites not met for {course_code}",
        )

    # Determine compulsory status
    is_compulsory = body.is_compulsory
    compulsory_category = body.compulsory_category
    if is_compulsory is None:
        resolved_cat = graduation_engine._resolve_compulsory_category(
            course_code, subject_area, compulsory_category
        )
        if resolved_cat:
            is_compulsory = True
            compulsory_category = resolved_cat
        else:
            is_compulsory = False

    plan_course = PlanCourse(
        plan_id=plan_id,
        course_code=course_code,
        course_name=course_name,
        subject_area=subject_area,
        grade_level=body.grade_level,
        semester=body.semester,
        credit_value=credit_value,
        pathway=pathway,
        status=body.status,
        final_mark=body.final_mark,
        is_compulsory=is_compulsory,
        compulsory_category=compulsory_category,
    )
    db.add(plan_course)
    db.commit()
    db.refresh(plan_course)

    logger.info(
        f"Course added to plan: plan={plan_id} course={course_code} "
        f"grade={body.grade_level} sem={body.semester} by user={current_user.id}"
    )
    return plan_course


# ---------------------------------------------------------------------------
# DELETE /{plan_id}/courses/{plan_course_id}  — remove a course
# ---------------------------------------------------------------------------

@router.delete("/{plan_id}/courses/{plan_course_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def remove_course(
    request: Request,
    plan_id: int,
    plan_course_id: int,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a course entry from an academic plan."""
    plan = _get_plan_with_access(db, plan_id, current_user)

    course = (
        db.query(PlanCourse)
        .filter(PlanCourse.id == plan_course_id, PlanCourse.plan_id == plan_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found in this plan")

    db.delete(course)
    db.commit()
    logger.info(f"Course removed from plan: plan={plan_id} course_id={plan_course_id}")


# ---------------------------------------------------------------------------
# GET /{plan_id}/validate  — OSSD graduation requirements check
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/validate", response_model=ValidationResultResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def validate_plan(
    request: Request,
    plan_id: int,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run OSSD graduation requirements validation against all plan courses.

    Returns a full ValidationResult: credit breakdown, missing requirements,
    warnings, fulfilled requirements, and suggested courses to fill gaps.
    """
    plan = _get_plan_with_access(db, plan_id, current_user)

    result = graduation_engine.validate_plan(plan.plan_courses)
    suggested = graduation_engine.suggest_missing_compulsory(plan.plan_courses)

    return ValidationResultResponse(
        is_valid=result.is_valid,
        total_credits=result.total_credits,
        compulsory_credits=result.compulsory_credits,
        elective_credits=result.elective_credits,
        completion_pct=result.completion_pct,
        missing_requirements=result.missing_requirements,
        warnings=result.warnings,
        fulfilled_requirements=result.fulfilled_requirements,
        suggested_courses=suggested,
    )
