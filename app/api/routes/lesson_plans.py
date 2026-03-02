"""Lesson Plans API routes — TeachAssist-compatible lesson planning for Ontario teachers.

Routes:
  GET    /api/lesson-plans/           — list teacher's plans (filter: plan_type, course_id, grade_level)
  POST   /api/lesson-plans/           — create plan
  GET    /api/lesson-plans/templates  — list public/shared templates
  GET    /api/lesson-plans/{id}       — get single plan
  PUT    /api/lesson-plans/{id}       — update plan
  DELETE /api/lesson-plans/{id}       — delete plan
  POST   /api/lesson-plans/{id}/duplicate    — duplicate a plan
  POST   /api/lesson-plans/{id}/ai-generate  — AI-fill learning goals + 3-part lesson
  POST   /api/lesson-plans/import     — import from TeachAssist XML or CSV file
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_feature, require_role
from app.models.lesson_plan import LessonPlan, LessonPlanType
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.schemas.lesson_plan import LessonPlanCreate, LessonPlanUpdate
from app.services.teachassist_parser import (
    parse_teachassist_csv,
    parse_teachassist_xml,
    deserialise_dict_field,
    deserialise_list_field,
    serialise_dict_field,
    serialise_list_field,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_teacher_or_admin = require_role(UserRole.TEACHER, UserRole.ADMIN)


def _get_teacher(db: Session, user: User) -> Teacher:
    """Return the Teacher record for the current user, or 404."""
    teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    return teacher


def _get_plan_for_teacher(db: Session, plan_id: int, teacher_id: int) -> LessonPlan:
    """Return a lesson plan owned by the teacher, or 404."""
    plan = (
        db.query(LessonPlan)
        .filter(LessonPlan.id == plan_id, LessonPlan.teacher_id == teacher_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return plan


def _serialize(plan: LessonPlan) -> dict:
    """Convert ORM model to API response dict, deserialising JSON fields."""
    return {
        "id": plan.id,
        "teacher_id": plan.teacher_id,
        "course_id": plan.course_id,
        "plan_type": plan.plan_type.value if plan.plan_type else None,
        "title": plan.title,
        "strand": plan.strand,
        "unit_number": plan.unit_number,
        "grade_level": plan.grade_level,
        "subject_code": plan.subject_code,
        "big_ideas": deserialise_list_field(plan.big_ideas),
        "curriculum_expectations": deserialise_list_field(plan.curriculum_expectations),
        "overall_expectations": deserialise_list_field(plan.overall_expectations),
        "specific_expectations": deserialise_list_field(plan.specific_expectations),
        "learning_goals": deserialise_list_field(plan.learning_goals),
        "success_criteria": deserialise_list_field(plan.success_criteria),
        "three_part_lesson": deserialise_dict_field(plan.three_part_lesson),
        "assessment_for_learning": plan.assessment_for_learning,
        "assessment_of_learning": plan.assessment_of_learning,
        "differentiation": deserialise_dict_field(plan.differentiation),
        "materials_resources": deserialise_list_field(plan.materials_resources),
        "cross_curricular": deserialise_list_field(plan.cross_curricular),
        "duration_minutes": plan.duration_minutes,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "is_template": plan.is_template or False,
        "imported_from": plan.imported_from,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


def _apply_payload(plan: LessonPlan, data: dict) -> None:
    """Apply a payload dict (from create/update/import) to an ORM instance."""
    scalar_fields = {
        "plan_type", "title", "course_id", "strand", "unit_number",
        "grade_level", "subject_code", "assessment_for_learning",
        "assessment_of_learning", "duration_minutes", "start_date",
        "end_date", "is_template", "imported_from",
    }
    json_list_fields = {
        "big_ideas", "curriculum_expectations", "overall_expectations",
        "specific_expectations", "learning_goals", "success_criteria",
        "materials_resources", "cross_curricular",
    }
    json_dict_fields = {"three_part_lesson", "differentiation"}

    for field in scalar_fields:
        if field in data and data[field] is not None:
            value = data[field]
            if field == "plan_type" and isinstance(value, str):
                try:
                    value = LessonPlanType(value)
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid plan_type: {value}"
                    )
            setattr(plan, field, value)

    for field in json_list_fields:
        if field in data:
            setattr(plan, field, serialise_list_field(data[field] or []))

    for field in json_dict_fields:
        if field in data:
            raw = data[field]
            if isinstance(raw, dict):
                setattr(plan, field, serialise_dict_field(raw))
            elif raw is None:
                setattr(plan, field, None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/templates")
def list_templates(
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    _current_user: User = Depends(_teacher_or_admin),
):
    """List public lesson plan templates (is_template=True)."""
    plans = (
        db.query(LessonPlan)
        .filter(LessonPlan.is_template == True)  # noqa: E712
        .order_by(LessonPlan.updated_at.desc())
        .all()
    )
    return [_serialize(p) for p in plans]


@router.get("/")
def list_lesson_plans(
    _flag=Depends(require_feature("lesson_planner")),
    plan_type: Optional[str] = Query(None),
    course_id: Optional[int] = Query(None),
    grade_level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """List the current teacher's lesson plans with optional filters."""
    teacher = _get_teacher(db, current_user)

    q = db.query(LessonPlan).filter(LessonPlan.teacher_id == teacher.id)

    if plan_type:
        try:
            q = q.filter(LessonPlan.plan_type == LessonPlanType(plan_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid plan_type: {plan_type}")

    if course_id is not None:
        q = q.filter(LessonPlan.course_id == course_id)

    if grade_level:
        q = q.filter(LessonPlan.grade_level == grade_level)

    plans = q.order_by(LessonPlan.updated_at.desc()).all()
    return [_serialize(p) for p in plans]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_lesson_plan(
    payload: LessonPlanCreate,
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Create a new lesson plan."""
    teacher = _get_teacher(db, current_user)

    plan = LessonPlan(teacher_id=teacher.id, imported_from="manual")
    _apply_payload(plan, payload.model_dump(exclude_unset=False))
    db.add(plan)
    db.commit()
    db.refresh(plan)
    logger.info("Created lesson plan %d for teacher %d", plan.id, teacher.id)
    return _serialize(plan)


@router.get("/{plan_id}")
def get_lesson_plan(
    plan_id: int,
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Get a single lesson plan."""
    teacher = _get_teacher(db, current_user)
    plan = _get_plan_for_teacher(db, plan_id, teacher.id)
    return _serialize(plan)


@router.put("/{plan_id}")
def update_lesson_plan(
    plan_id: int,
    payload: LessonPlanUpdate,
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Update a lesson plan (full or partial)."""
    teacher = _get_teacher(db, current_user)
    plan = _get_plan_for_teacher(db, plan_id, teacher.id)

    update_data = payload.model_dump(exclude_unset=True)
    _apply_payload(plan, update_data)

    db.commit()
    db.refresh(plan)
    return _serialize(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson_plan(
    plan_id: int,
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Permanently delete a lesson plan."""
    teacher = _get_teacher(db, current_user)
    plan = _get_plan_for_teacher(db, plan_id, teacher.id)
    db.delete(plan)
    db.commit()
    logger.info("Deleted lesson plan %d for teacher %d", plan_id, teacher.id)


@router.post("/{plan_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_lesson_plan(
    plan_id: int,
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Duplicate a lesson plan, creating a new copy owned by the current teacher."""
    teacher = _get_teacher(db, current_user)

    # Teachers may duplicate their own plans OR any template
    plan = (
        db.query(LessonPlan)
        .filter(
            LessonPlan.id == plan_id,
        )
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    if plan.teacher_id != teacher.id and not plan.is_template:
        raise HTTPException(status_code=403, detail="Cannot duplicate another teacher's non-template plan")

    new_plan = LessonPlan(
        teacher_id=teacher.id,
        course_id=plan.course_id,
        plan_type=plan.plan_type,
        title=f"Copy of {plan.title}",
        strand=plan.strand,
        unit_number=plan.unit_number,
        grade_level=plan.grade_level,
        subject_code=plan.subject_code,
        big_ideas=plan.big_ideas,
        curriculum_expectations=plan.curriculum_expectations,
        overall_expectations=plan.overall_expectations,
        specific_expectations=plan.specific_expectations,
        learning_goals=plan.learning_goals,
        success_criteria=plan.success_criteria,
        three_part_lesson=plan.three_part_lesson,
        assessment_for_learning=plan.assessment_for_learning,
        assessment_of_learning=plan.assessment_of_learning,
        differentiation=plan.differentiation,
        materials_resources=plan.materials_resources,
        cross_curricular=plan.cross_curricular,
        duration_minutes=plan.duration_minutes,
        start_date=plan.start_date,
        end_date=plan.end_date,
        is_template=False,
        imported_from=plan.imported_from,
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    logger.info("Duplicated plan %d -> %d for teacher %d", plan_id, new_plan.id, teacher.id)
    return _serialize(new_plan)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_lesson_plans(
    file: UploadFile = File(...),
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Import lesson plans from a TeachAssist XML or CSV export file.

    Accepts:
      - .xml files: TeachAssist UnitPlan or LongRangePlan XML format
      - .csv files: tabular format with TeachAssist-style column headers

    Returns the list of created LessonPlan records.
    """
    teacher = _get_teacher(db, current_user)

    content = await file.read()
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".xml") or (file.content_type or "").lower() in (
            "application/xml", "text/xml"
        ):
            raw_plans = parse_teachassist_xml(content)
        elif filename.endswith(".csv") or (file.content_type or "").lower() == "text/csv":
            raw_plans = parse_teachassist_csv(content)
        else:
            # Try XML first, then CSV
            try:
                raw_plans = parse_teachassist_xml(content)
            except ValueError:
                raw_plans = parse_teachassist_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not raw_plans:
        raise HTTPException(status_code=400, detail="No lesson plans found in file")

    created: list[dict] = []
    for raw in raw_plans:
        plan = LessonPlan(teacher_id=teacher.id)
        _apply_payload(plan, raw)
        db.add(plan)
        db.flush()  # get id before serialising
        created.append(_serialize(plan))

    db.commit()
    logger.info("Imported %d lesson plan(s) for teacher %d", len(created), teacher.id)
    return {"imported": len(created), "plans": created}


@router.post("/{plan_id}/ai-generate")
async def ai_generate_lesson_plan(
    plan_id: int,
    _flag=Depends(require_feature("lesson_planner")),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_or_admin),
):
    """Use AI (GPT-4o-mini / Claude) to fill in learning goals, success criteria,
    and the 3-part lesson structure for a plan that lacks them.

    Input fields used: title, strand, grade_level, curriculum_expectations, subject_code.
    Output fields written: learning_goals, success_criteria, three_part_lesson.
    """
    teacher = _get_teacher(db, current_user)
    plan = _get_plan_for_teacher(db, plan_id, teacher.id)

    # Build context for the AI prompt
    title = plan.title or "Untitled"
    grade = plan.grade_level or "unspecified grade"
    subject = plan.subject_code or "unspecified subject"
    strand = plan.strand or ""
    expectations = deserialise_list_field(plan.curriculum_expectations)
    expectations_text = "\n".join(f"- {e}" for e in expectations) if expectations else "Not specified"

    prompt = (
        f"You are an experienced Ontario teacher creating a lesson plan.\n\n"
        f"Lesson: {title}\n"
        f"Grade: {grade}\n"
        f"Subject/Course Code: {subject}\n"
        f"Strand: {strand}\n"
        f"Curriculum Expectations:\n{expectations_text}\n\n"
        "Please generate the following in valid JSON format (no markdown, just the JSON object):\n"
        "{\n"
        '  "learning_goals": ["Students will be able to...", "..."],\n'
        '  "success_criteria": ["I can...", "..."],\n'
        '  "three_part_lesson": {\n'
        '    "minds_on": "Hook activity or warm-up to activate prior knowledge (5-10 min)...",\n'
        '    "action": "Main instructional activity (40-50 min)...",\n'
        '    "consolidation": "Exit ticket, discussion, or consolidation activity (10-15 min)..."\n'
        "  }\n"
        "}\n\n"
        "Use Ontario curriculum language. Learning goals should start with 'Students will...'. "
        "Success criteria should start with 'I can...'. "
        "Be specific and practical."
    )

    system_prompt = (
        "You are an Ontario certified teacher with expertise in curriculum design and "
        "the Ontario curriculum framework. You create clear, practical lesson plans that "
        "align with Ontario curriculum expectations and use the 3-part lesson structure "
        "(Minds On, Action, Consolidation). Always respond with valid JSON only."
    )

    try:
        from app.services.ai_service import generate_content
        raw_response = await generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.7,
            user=current_user,
        )
    except Exception as exc:
        logger.error("AI generation failed for plan %d: %s", plan_id, exc)
        raise HTTPException(status_code=503, detail="AI generation failed. Please try again.")

    # Parse the JSON response
    try:
        # Strip markdown code fences if present
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        ai_data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("AI response parse error for plan %d: %s | response: %.200s", plan_id, exc, raw_response)
        raise HTTPException(status_code=502, detail="AI returned an unparseable response. Please try again.")

    # Update the plan with AI-generated content
    if "learning_goals" in ai_data and isinstance(ai_data["learning_goals"], list):
        plan.learning_goals = serialise_list_field(ai_data["learning_goals"])

    if "success_criteria" in ai_data and isinstance(ai_data["success_criteria"], list):
        plan.success_criteria = serialise_list_field(ai_data["success_criteria"])

    if "three_part_lesson" in ai_data and isinstance(ai_data["three_part_lesson"], dict):
        plan.three_part_lesson = serialise_dict_field(ai_data["three_part_lesson"])

    if plan.imported_from != "teachassist":
        plan.imported_from = "ai_generated"

    db.commit()
    db.refresh(plan)
    logger.info("AI-generated fields for plan %d", plan_id)
    return _serialize(plan)
