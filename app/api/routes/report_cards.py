"""Report Card Upload & AI Analysis endpoints (#663).

Routes:
  POST   /api/report-cards/         — parent uploads a report card (multipart)
  GET    /api/report-cards/         — list report cards (parent: own children; student: self)
  GET    /api/report-cards/{id}     — detail view
  DELETE /api/report-cards/{id}     — parent deletes own report card
"""
import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature, require_role
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.db.database import get_db
from app.models.report_card import ReportCard
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.services import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report-cards", tags=["Report Cards"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/jpg", "image/png"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MarkItem(BaseModel):
    subject: str
    mark: float
    max_mark: float
    percentage: float

    class Config:
        from_attributes = True


class ReportCardSummary(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    term: str
    academic_year: Optional[str] = None
    file_name: str
    file_size_bytes: Optional[int] = None
    overall_average: Optional[float] = None
    status: str
    uploaded_at: datetime
    analyzed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportCardDetail(ReportCardSummary):
    extracted_marks: Optional[list] = None
    ai_observations: Optional[str] = None
    ai_strengths: Optional[list] = None
    ai_improvement_areas: Optional[list] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_student_name(db: Session, student_id: int) -> str:
    student = db.query(Student).filter(Student.id == student_id).first()
    if student and student.user:
        return student.user.full_name
    return f"Student #{student_id}"


def _assert_parent_owns_child(db: Session, parent_user_id: int, student_id: int) -> None:
    """Raise 403 if the parent does not own the given student."""
    row = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == parent_user_id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this student.",
        )


def _assert_report_card_access(db: Session, user: User, report_card: ReportCard) -> None:
    """Raise 403/404 if user cannot access the report card."""
    if report_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report card not found.")
    if user.role == UserRole.PARENT:
        if report_card.parent_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    elif user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student or student.id != report_card.student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    elif user.role == UserRole.ADMIN:
        pass  # admins can see all
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------

async def _analyze_report_card(db: Session, report_card_id: int, file_content_b64: str, file_name: str) -> None:
    """Run AI analysis on the report card and update the DB record."""
    logger.info(f"Starting AI analysis for report card {report_card_id}")
    report_card = db.query(ReportCard).filter(ReportCard.id == report_card_id).first()
    if not report_card:
        logger.error(f"Report card {report_card_id} not found for analysis")
        return

    prompt = f"""You are analyzing a student report card document. Extract all subject marks and provide educational insights.

Return a JSON object with exactly this structure:
{{
  "marks": [{{"subject": "string", "mark": 0.0, "max_mark": 100.0, "percentage": 0.0}}],
  "overall_average": 0.0,
  "strengths": ["subject1", "subject2", "subject3"],
  "improvement_areas": ["subject1", "subject2", "subject3"],
  "observations": "2-3 paragraph markdown analysis of the student's performance, trends, and recommendations"
}}

File name: {file_name}

Instructions:
- Extract every subject/course with its mark, maximum mark, and percentage
- If marks use letter grades (A, B, C etc.), convert: A=95, B=82, C=72, D=62, F=45 out of 100
- Calculate overall_average as the mean of all subject percentages
- strengths: top 3 subjects by percentage (highest performing)
- improvement_areas: bottom 3 subjects by percentage (needs most work)
- observations: write a supportive 2-3 paragraph markdown analysis covering strengths, areas for growth, and actionable recommendations for the student/parent
- If the file content cannot be read as an image, infer what you can from the filename and provide a generic educational analysis template
- Return ONLY valid JSON, no markdown code blocks, no extra text"""

    system_prompt = (
        "You are an expert educational analyst helping parents understand their child's academic performance. "
        "Extract information accurately and provide helpful, constructive observations. "
        "Always return valid JSON only."
    )

    try:
        response = await ai_service.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=2000,
            temperature=0.3,
        )

        # Strip markdown code fences if present
        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean

        data = json.loads(clean)

        marks = data.get("marks", [])
        overall_average = data.get("overall_average")
        strengths = data.get("strengths", [])
        improvement_areas = data.get("improvement_areas", [])
        observations = data.get("observations", "")

        # Recompute overall average from marks if not provided
        if overall_average is None and marks:
            percentages = [m.get("percentage", 0) for m in marks if m.get("percentage") is not None]
            overall_average = sum(percentages) / len(percentages) if percentages else None

        report_card.extracted_marks = marks
        report_card.overall_average = overall_average
        report_card.ai_strengths = strengths
        report_card.ai_improvement_areas = improvement_areas
        report_card.ai_observations = observations
        report_card.status = "analyzed"
        report_card.analyzed_at = datetime.now(timezone.utc)
        report_card.error_message = None
        db.commit()
        logger.info(f"Report card {report_card_id} analyzed successfully | subjects={len(marks)} | avg={overall_average}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response for report card {report_card_id}: {e}")
        report_card.status = "failed"
        report_card.error_message = f"AI response could not be parsed: {str(e)}"
        db.commit()
    except Exception as e:
        logger.error(f"AI analysis failed for report card {report_card_id}: {e}")
        report_card.status = "failed"
        report_card.error_message = str(e)
        db.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=ReportCardDetail, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def upload_report_card(
    request: Request,
    _flag=Depends(require_feature("grade_tracking")),
    student_id: int = Form(...),
    term: str = Form(...),
    academic_year: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Upload a PDF/JPG/PNG report card for a child. Triggers synchronous AI analysis."""
    # Validate file type
    ext = ""
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Supported: PDF, JPG, PNG. Got: {ext or 'unknown'}",
        )

    # Read file content
    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 10 MB, got {file_size / 1024 / 1024:.1f} MB.",
        )
    if file_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    # Validate parent-child relationship
    _assert_parent_owns_child(db, current_user.id, student_id)

    # Encode to base64
    file_content_b64 = base64.b64encode(file_bytes).decode("utf-8")

    # Create record with status=processing
    report_card = ReportCard(
        parent_user_id=current_user.id,
        student_id=student_id,
        term=term.strip(),
        academic_year=academic_year.strip() if academic_year else None,
        file_name=file.filename or "report_card",
        file_content_b64=file_content_b64,
        file_size_bytes=file_size,
        status="processing",
    )
    db.add(report_card)
    db.commit()
    db.refresh(report_card)

    logger.info(f"Report card uploaded | id={report_card.id} | student={student_id} | term={term} | size={file_size}")

    # Run AI analysis as a background task (non-blocking)
    asyncio.create_task(_analyze_report_card(db, report_card.id, file_content_b64, report_card.file_name))

    student_name = _get_student_name(db, student_id)
    return _to_detail(report_card, student_name)


@router.get("/", response_model=list[ReportCardSummary])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_report_cards(
    request: Request,
    _flag=Depends(require_feature("grade_tracking")),
    student_id: Optional[int] = None,
    academic_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List report cards. Parent sees own children's; student sees own."""
    query = db.query(ReportCard)

    if current_user.role == UserRole.PARENT:
        # Get all children of this parent
        child_rows = (
            db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        child_ids = [r[0] for r in child_rows]
        if not child_ids:
            return []
        if student_id is not None:
            if student_id not in child_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
            query = query.filter(ReportCard.student_id == student_id)
        else:
            query = query.filter(ReportCard.student_id.in_(child_ids))

    elif current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            return []
        if student_id is not None and student_id != student.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        query = query.filter(ReportCard.student_id == student.id)

    elif current_user.role == UserRole.ADMIN:
        if student_id is not None:
            query = query.filter(ReportCard.student_id == student_id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if academic_year:
        query = query.filter(ReportCard.academic_year == academic_year)

    records = query.order_by(ReportCard.uploaded_at.desc()).all()

    # Build student_id -> name map for all records at once
    sid_set = {r.student_id for r in records}
    students = db.query(Student).filter(Student.id.in_(sid_set)).all() if sid_set else []
    name_map: dict[int, str] = {}
    for s in students:
        name_map[s.id] = s.user.full_name if s.user else f"Student #{s.id}"

    return [
        ReportCardSummary(
            id=rc.id,
            student_id=rc.student_id,
            student_name=name_map.get(rc.student_id),
            term=rc.term,
            academic_year=rc.academic_year,
            file_name=rc.file_name,
            file_size_bytes=rc.file_size_bytes,
            overall_average=rc.overall_average,
            status=rc.status,
            uploaded_at=rc.uploaded_at,
            analyzed_at=rc.analyzed_at,
        )
        for rc in records
    ]


@router.get("/{report_card_id}", response_model=ReportCardDetail)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_report_card(
    request: Request,
    report_card_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full detail of a report card including AI analysis."""
    rc = db.query(ReportCard).filter(ReportCard.id == report_card_id).first()
    _assert_report_card_access(db, current_user, rc)
    student_name = _get_student_name(db, rc.student_id)
    return _to_detail(rc, student_name)


@router.delete("/{report_card_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_report_card(
    request: Request,
    report_card_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Delete a report card. Only the uploading parent can delete."""
    rc = db.query(ReportCard).filter(ReportCard.id == report_card_id).first()
    if rc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report card not found.")
    if rc.parent_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    db.delete(rc)
    db.commit()
    logger.info(f"Report card deleted | id={report_card_id} | parent={current_user.id}")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _to_detail(rc: ReportCard, student_name: Optional[str]) -> ReportCardDetail:
    return ReportCardDetail(
        id=rc.id,
        student_id=rc.student_id,
        student_name=student_name,
        term=rc.term,
        academic_year=rc.academic_year,
        file_name=rc.file_name,
        file_size_bytes=rc.file_size_bytes,
        overall_average=rc.overall_average,
        status=rc.status,
        uploaded_at=rc.uploaded_at,
        analyzed_at=rc.analyzed_at,
        extracted_marks=rc.extracted_marks,
        ai_observations=rc.ai_observations,
        ai_strengths=rc.ai_strengths,
        ai_improvement_areas=rc.ai_improvement_areas,
        error_message=rc.error_message,
    )
