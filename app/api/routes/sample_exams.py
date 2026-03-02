"""Sample Exam upload and AI assessment routes (#577).

Routes:
  POST  /api/sample-exams/upload          — Upload exam file + trigger AI assessment
  GET   /api/sample-exams/                — List exams (RBAC filtered)
  GET   /api/sample-exams/{id}            — Get exam with full assessment
  DELETE /api/sample-exams/{id}           — Delete (creator or admin only)
  POST  /api/sample-exams/{id}/assess     — Re-run AI assessment on existing exam
  GET   /api/sample-exams/{id}/practice   — Extract questions for practice mode
  PATCH /api/sample-exams/{id}/publish    — Toggle is_public
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.sample_exam import SampleExam
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.core.config import settings
from app.services.file_processor import process_file, FileProcessingError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sample-exams", tags=["Sample Exams"])

MAX_UPLOAD_SIZE = settings.max_upload_size_mb * 1024 * 1024


# ---------------------------------------------------------------------------
# AI assessment helper
# ---------------------------------------------------------------------------

async def _run_ai_assessment(exam: SampleExam, db: Session) -> None:
    """Generate an AI quality assessment for the given exam and persist results."""
    from app.services.ai_service import generate_content

    if not exam.original_content:
        logger.warning("No content to assess for exam %s", exam.id)
        return

    content = exam.original_content
    if len(content) > 3000:
        content = content[:3000]

    prompt = f"""You are an expert educator reviewing a {exam.exam_type} exam. Analyze this exam and provide a JSON assessment with this exact structure:
{{
  "overall_score": 78,
  "summary": "Brief 2-3 sentence overall assessment",
  "strengths": ["Clear question wording", "Good difficulty range"],
  "weaknesses": ["No partial marks indicated", "Some questions are ambiguous"],
  "curriculum_coverage": {{
    "breadth": "good",
    "depth": "fair",
    "gaps": ["Missing calculus integration", "No word problems"],
    "overlap": ["Questions 3 and 7 test the same concept"]
  }},
  "difficulty_analysis": {{
    "distribution": {{"easy": 30, "medium": 50, "hard": 20}},
    "appropriate_for_level": true,
    "suggestions": ["Add more medium-difficulty questions"]
  }},
  "question_quality": {{
    "total_questions": 10,
    "clear_questions": 8,
    "ambiguous_questions": [3, 7],
    "improvement_suggestions": [
      {{"question_number": 3, "issue": "Vague wording", "suggestion": "Specify units required"}}
    ]
  }},
  "recommendations": [
    "Add marking rubric",
    "Include formula sheet reference",
    "Balance question types (add short-answer)"
  ]
}}

Exam content:
{content}"""

    try:
        raw_response = await generate_content(
            prompt=prompt,
            system_prompt="You are an expert educator. Respond with valid JSON only, no markdown fences.",
            max_tokens=2000,
            temperature=0.3,
        )

        # Strip markdown code fences if present
        cleaned = raw_response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        # Validate it's parseable JSON
        json.loads(cleaned)

        exam.assessment_json = cleaned
        exam.assessment_generated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exam)
        logger.info("AI assessment completed for exam %s", exam.id)

    except json.JSONDecodeError as e:
        logger.error("AI assessment JSON parse failed for exam %s: %s", exam.id, e)
        # Store raw response anyway so it's not lost
        exam.assessment_json = json.dumps({
            "overall_score": 0,
            "summary": "Assessment parsing failed — raw AI response stored.",
            "strengths": [],
            "weaknesses": ["AI response was not valid JSON"],
            "curriculum_coverage": {"breadth": "poor", "depth": "poor", "gaps": [], "overlap": []},
            "difficulty_analysis": {"distribution": {"easy": 0, "medium": 0, "hard": 0}, "appropriate_for_level": False, "suggestions": []},
            "question_quality": {"total_questions": 0, "clear_questions": 0, "ambiguous_questions": [], "improvement_suggestions": []},
            "recommendations": ["Re-run assessment"],
            "_raw": raw_response[:500],
        })
        exam.assessment_generated_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.error("AI assessment failed for exam %s: %s", exam.id, e)


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

def _get_visible_exam_ids(db: Session, user: User) -> list[int] | None:
    """Return a list of visible exam IDs for RBAC filtering.

    Returns None to indicate "all exams" (admin case).
    """
    if user.has_role(UserRole.ADMIN):
        return None  # admin sees all

    if user.has_role(UserRole.TEACHER):
        # Teacher: own exams + public exams in their courses
        from app.models.teacher import Teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        teacher_course_ids: list[int] = []
        if teacher:
            rows = db.query(Course.id).filter(
                (Course.created_by_user_id == user.id) | (Course.teacher_id == teacher.id)
            ).all()
        else:
            rows = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        teacher_course_ids = [r[0] for r in rows]

        own_ids = [
            r[0] for r in db.query(SampleExam.id).filter(
                SampleExam.created_by_user_id == user.id
            ).all()
        ]
        if teacher_course_ids:
            public_in_course = [
                r[0] for r in db.query(SampleExam.id).filter(
                    SampleExam.is_public.is_(True),
                    SampleExam.course_id.in_(teacher_course_ids),
                ).all()
            ]
        else:
            public_in_course = []
        return list(set(own_ids + public_in_course))

    # Student or Parent: only is_public exams in enrolled courses
    if user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == user.id).first()
        enrolled_course_ids: list[int] = []
        if student:
            enrolled_course_ids = [c.id for c in student.courses]
    elif user.has_role(UserRole.PARENT):
        child_rows = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == user.id
        ).all()
        child_sids = [r[0] for r in child_rows]
        enrolled_course_ids = []
        if child_sids:
            enrolled_rows = db.query(student_courses.c.course_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            enrolled_course_ids = [r[0] for r in enrolled_rows]
    else:
        enrolled_course_ids = []

    if not enrolled_course_ids:
        return []

    visible = [
        r[0] for r in db.query(SampleExam.id).filter(
            SampleExam.is_public.is_(True),
            SampleExam.course_id.in_(enrolled_course_ids),
        ).all()
    ]
    return visible


def _exam_to_dict(exam: SampleExam) -> dict[str, Any]:
    """Convert a SampleExam ORM object to a plain dict for JSON serialisation."""
    assessment_data = None
    if exam.assessment_json:
        try:
            assessment_data = json.loads(exam.assessment_json)
        except json.JSONDecodeError:
            assessment_data = None

    return {
        "id": exam.id,
        "created_by_user_id": exam.created_by_user_id,
        "course_id": exam.course_id,
        "title": exam.title,
        "description": exam.description,
        "file_name": exam.file_name,
        "original_content": exam.original_content,
        "exam_type": exam.exam_type,
        "difficulty_level": exam.difficulty_level,
        "is_public": exam.is_public,
        "assessment": assessment_data,
        "assessment_generated_at": (
            exam.assessment_generated_at.isoformat()
            if exam.assessment_generated_at
            else None
        ),
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
        "updated_at": exam.updated_at.isoformat() if exam.updated_at else None,
        "course_name": exam.course.name if exam.course else None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
async def upload_sample_exam(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    course_id: int = Form(None),
    exam_type: str = Form("sample"),
    assess_on_upload: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an exam file (PDF/DOC/DOCX/image), extract text, and optionally
    run an AI quality assessment immediately.

    Allowed exam_type values: sample | practice | past
    """
    if not current_user.has_role(UserRole.TEACHER) and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can upload sample exams",
        )

    # Validate exam_type
    valid_exam_types = {"sample", "practice", "past"}
    exam_type_normalized = exam_type.strip().lower()
    if exam_type_normalized not in valid_exam_types:
        exam_type_normalized = "sample"

    # Validate course if provided
    if course_id is not None:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Read file and check size
    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit",
        )
    if len(file_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    filename = file.filename or "unknown"

    # Extract text from the uploaded file
    extracted_text = ""
    try:
        extracted_text = process_file(file_content, filename)
    except FileProcessingError as e:
        logger.warning("Text extraction failed for %s: %s", filename, e)
    except Exception as e:
        logger.warning("Unexpected error during text extraction for %s: %s", filename, e)

    # Persist the record
    exam = SampleExam(
        created_by_user_id=current_user.id,
        course_id=course_id,
        title=title.strip(),
        description=description.strip() or None,
        original_content=extracted_text or None,
        file_name=filename,
        exam_type=exam_type_normalized,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    # Run AI assessment synchronously if requested
    if assess_on_upload and extracted_text:
        await _run_ai_assessment(exam, db)
        db.refresh(exam)

    return _exam_to_dict(exam)


@router.get("/")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_sample_exams(
    request: Request,
    course_id: int = Query(None, description="Filter by course ID"),
    exam_type: str = Query(None, description="Filter by exam type (sample/practice/past)"),
    is_public: bool = Query(None, description="Filter by is_public flag"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sample exams visible to the current user (RBAC filtered)."""
    visible_ids = _get_visible_exam_ids(db, current_user)

    query = db.query(SampleExam)
    if visible_ids is not None:
        if not visible_ids:
            return {"total": 0, "items": [], "offset": offset, "limit": limit}
        query = query.filter(SampleExam.id.in_(visible_ids))

    if course_id is not None:
        query = query.filter(SampleExam.course_id == course_id)
    if exam_type is not None:
        query = query.filter(SampleExam.exam_type == exam_type.strip().lower())
    if is_public is not None:
        query = query.filter(SampleExam.is_public.is_(is_public))

    total = query.count()
    exams = query.order_by(SampleExam.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [_exam_to_dict(e) for e in exams],
        "offset": offset,
        "limit": limit,
    }


@router.get("/{exam_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_sample_exam(
    request: Request,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single sample exam with full assessment details."""
    exam = db.query(SampleExam).filter(SampleExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample exam not found")

    # RBAC: admin always, creator always, others check visibility list
    if not current_user.has_role(UserRole.ADMIN) and exam.created_by_user_id != current_user.id:
        visible_ids = _get_visible_exam_ids(db, current_user)
        if visible_ids is not None and exam_id not in visible_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _exam_to_dict(exam)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def delete_sample_exam(
    request: Request,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sample exam. Only the creator or admin may delete."""
    exam = db.query(SampleExam).filter(SampleExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample exam not found")

    if exam.created_by_user_id != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or admin can delete this exam",
        )

    db.delete(exam)
    db.commit()


@router.post("/{exam_id}/assess")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def reassess_sample_exam(
    request: Request,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run AI assessment on an existing exam."""
    exam = db.query(SampleExam).filter(SampleExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample exam not found")

    if exam.created_by_user_id != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not exam.original_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content available to assess. Please re-upload the exam file.",
        )

    await _run_ai_assessment(exam, db)
    db.refresh(exam)
    return _exam_to_dict(exam)


@router.get("/{exam_id}/practice")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_practice_mode(
    request: Request,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract individual questions from exam content for student practice mode.

    Questions are identified by lines matching ``^\\d+\\.`` or ``^Q\\d+``.
    """
    exam = db.query(SampleExam).filter(SampleExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample exam not found")

    # RBAC: admin/creator always, students/parents need visibility
    if not current_user.has_role(UserRole.ADMIN) and exam.created_by_user_id != current_user.id:
        visible_ids = _get_visible_exam_ids(db, current_user)
        if visible_ids is not None and exam_id not in visible_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    questions: list[str] = []
    if exam.original_content:
        lines = exam.original_content.splitlines()
        current_q: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Detect question start: "1." or "Q1" or "Q 1" patterns
            is_question_start = bool(
                re.match(r"^\d{1,3}\.", stripped)
                or re.match(r"^Q\s*\d+", stripped, re.IGNORECASE)
            )
            if is_question_start:
                if current_q:
                    questions.append(" ".join(current_q))
                current_q = [stripped]
            elif current_q:
                # Continuation of current question (but stop at section headers or answer lines)
                is_answer = bool(re.match(r"^[Aa]nswer[s]?\s*[:.]", stripped))
                is_section = bool(re.match(r"^(section|part|instructions?|name|date|class)\s*[:.]?", stripped, re.IGNORECASE))
                if not is_answer and not is_section:
                    current_q.append(stripped)

        if current_q:
            questions.append(" ".join(current_q))

    return {
        "exam_id": exam.id,
        "title": exam.title,
        "questions": questions,
        "question_count": len(questions),
    }


@router.patch("/{exam_id}/publish")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def toggle_publish(
    request: Request,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle is_public for the exam (teacher/admin only)."""
    if not current_user.has_role(UserRole.TEACHER) and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher or admin access required")

    exam = db.query(SampleExam).filter(SampleExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample exam not found")

    if exam.created_by_user_id != current_user.id and not current_user.has_role(UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator can change visibility")

    exam.is_public = not exam.is_public
    db.commit()
    db.refresh(exam)
    return {"id": exam.id, "is_public": exam.is_public}
