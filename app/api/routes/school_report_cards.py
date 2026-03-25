"""School Report Card Upload & AI Analysis routes (#2286)."""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.school_report_card import SchoolReportCard, SchoolReportCardAnalysis
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.school_report_card import (
    CareerPathResponse,
    FullAnalysisResponse,
    SchoolReportCardListItem,
    SchoolReportCardResponse,
    UploadReportCardResponse,
)
from app.services.ai_usage import check_ai_usage, increment_ai_usage
from app.services.file_processor import process_file
from app.services.storage_limits import check_upload_allowed, record_upload
from app.services.storage_service import save_file

logger = get_logger(__name__)

router = APIRouter(prefix="/school-report-cards", tags=["school-report-cards"])

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_UPLOAD_SIZE = settings.max_upload_size_mb * 1024 * 1024


# ── Helpers ──────────────────────────────────────────────────


def _verify_parent_child(db: Session, parent_user_id: int, student_id: int) -> Student:
    """Verify parent-child relationship. Returns Student or raises 403."""
    student = (
        db.query(Student)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(
            parent_students.c.parent_id == parent_user_id,
            Student.id == student_id,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=403, detail="Not your child or student not found")
    return student


def _build_full_analysis_response(analysis: SchoolReportCardAnalysis) -> FullAnalysisResponse:
    """Build FullAnalysisResponse from a DB analysis record."""
    try:
        content = json.loads(analysis.content)
    except (json.JSONDecodeError, TypeError):
        content = {}
    return FullAnalysisResponse(
        id=analysis.id,
        report_card_id=analysis.report_card_id or 0,
        analysis_type=analysis.analysis_type,
        teacher_feedback_summary=content.get("teacher_feedback_summary", ""),
        grade_analysis=content.get("grade_analysis", []),
        learning_skills=content.get("learning_skills", {"ratings": [], "summary": ""}),
        improvement_areas=content.get("improvement_areas", []),
        parent_tips=content.get("parent_tips", []),
        overall_summary=content.get("overall_summary", ""),
        created_at=analysis.created_at.isoformat() if analysis.created_at else "",
    )


def _build_career_path_response(analysis: SchoolReportCardAnalysis, num_cards: int) -> CareerPathResponse:
    """Build CareerPathResponse from a DB analysis record."""
    try:
        content = json.loads(analysis.content)
    except (json.JSONDecodeError, TypeError):
        content = {}
    return CareerPathResponse(
        id=analysis.id,
        student_id=analysis.student_id,
        strengths=content.get("strengths", []),
        grade_trends=content.get("grade_trends", []),
        career_suggestions=content.get("career_suggestions", []),
        overall_assessment=content.get("overall_assessment", ""),
        report_cards_analyzed=num_cards,
        created_at=analysis.created_at.isoformat() if analysis.created_at else "",
    )


def _verify_report_card_ownership(
    db: Session, parent_user_id: int, report_card_id: int, is_admin: bool = False,
) -> SchoolReportCard:
    """Verify parent owns this report card via student relationship."""
    rc = db.query(SchoolReportCard).filter(
        SchoolReportCard.id == report_card_id,
        SchoolReportCard.archived_at.is_(None),
    ).first()
    if not rc:
        raise HTTPException(status_code=404, detail="Report card not found")
    if not is_admin:
        _verify_parent_child(db, parent_user_id, rc.student_id)
    return rc


def _get_file_extension(filename: str) -> str:
    """Extract lowercase file extension without the dot."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


# ── 1. Upload Report Cards ──────────────────────────────────


@router.post("/upload", response_model=UploadReportCardResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def upload_report_cards(
    request: Request,
    files: list[UploadFile] = File(...),
    student_id: int = Form(...),
    school_name: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Upload one or more report card files (PDF or image) for a student."""
    student = _verify_parent_child(db, current_user.id, student_id)

    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files per upload. Please reduce the number of files.",
        )

    uploaded: list[SchoolReportCardResponse] = []
    failures: list[dict] = []

    for f in files:
        filename = f.filename or "unknown"
        ext = _get_file_extension(filename)

        if ext not in ALLOWED_EXTENSIONS:
            failures.append({"filename": filename, "error": f"Invalid file type '.{ext}'. Allowed: PDF, JPG, PNG."})
            continue

        content = await f.read()

        if len(content) > MAX_UPLOAD_SIZE:
            failures.append({"filename": filename, "error": f"File size exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit."})
            continue

        try:
            check_upload_allowed(current_user, len(content))
        except HTTPException as e:
            failures.append({"filename": filename, "error": e.detail})
            continue

        stored_path = save_file(content, filename)

        # Extract text from the file
        text_content = None
        try:
            text_content = process_file(content, filename)
        except Exception as e:
            logger.warning("Text extraction failed for %s: %s", filename, e)

        # Auto-extract metadata from text
        extracted_meta: dict = {}
        if text_content:
            try:
                from app.services.school_report_card_service import extract_metadata
                extracted_meta = extract_metadata(text_content) or {}
            except Exception as e:
                logger.warning("Metadata extraction failed for %s: %s", filename, e)

        rc = SchoolReportCard(
            student_id=student_id,
            uploaded_by_user_id=current_user.id,
            file_path=stored_path,
            original_filename=filename,
            file_size=len(content),
            mime_type=f.content_type,
            text_content=text_content,
            school_name=school_name or extracted_meta.get("school_name", ""),
            grade_level=extracted_meta.get("grade_level", ""),
            term=extracted_meta.get("term", ""),
            report_date=extracted_meta.get("report_date"),
        )
        db.add(rc)
        db.flush()

        # Upload to GCS if enabled
        if settings.use_gcs:
            try:
                from app.services import gcs_service
                _gcs_path = f"report-cards/{rc.id}/{filename}"
                gcs_service.upload_file(_gcs_path, content, f.content_type or "application/octet-stream")
                rc.gcs_path = _gcs_path
            except Exception as e:
                logger.warning("GCS upload failed for report card %d: %s", rc.id, e)

        record_upload(db, current_user, len(content))

        uploaded.append(SchoolReportCardResponse(
            id=rc.id,
            student_id=rc.student_id,
            original_filename=filename,
            term=rc.term,
            grade_level=rc.grade_level,
            school_name=rc.school_name,
            report_date=str(rc.report_date) if rc.report_date else None,
            school_year=rc.school_year,
            has_text_content=bool(text_content),
            has_analysis=False,
            created_at=rc.created_at.isoformat() if rc.created_at else "",
        ))

    db.commit()

    logger.info(
        "Report card upload | parent=%s | student=%s | uploaded=%d | failed=%d",
        current_user.id, student_id, len(uploaded), len(failures),
    )

    return UploadReportCardResponse(uploaded=uploaded, failures=failures, total_uploaded=len(uploaded))


# ── 2. List Report Cards ────────────────────────────────────


@router.get("/{student_id}", response_model=list[SchoolReportCardListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_report_cards(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """List all report cards for a student."""
    if current_user.role != UserRole.ADMIN:
        _verify_parent_child(db, current_user.id, student_id)

    cards = (
        db.query(SchoolReportCard)
        .filter(
            SchoolReportCard.student_id == student_id,
            SchoolReportCard.archived_at.is_(None),
        )
        .order_by(SchoolReportCard.report_date.desc(), SchoolReportCard.created_at.desc())
        .all()
    )

    # Check which cards have analyses
    analysis_card_ids = set()
    if cards:
        card_ids = [c.id for c in cards]
        rows = (
            db.query(SchoolReportCardAnalysis.report_card_id)
            .filter(
                SchoolReportCardAnalysis.report_card_id.in_(card_ids),
                SchoolReportCardAnalysis.analysis_type == "full",
            )
            .all()
        )
        analysis_card_ids = {r[0] for r in rows}

    return [
        SchoolReportCardListItem(
            id=c.id,
            original_filename=c.original_filename,
            school_name=c.school_name,
            grade_level=c.grade_level,
            term=c.term,
            report_date=str(c.report_date) if c.report_date else None,
            school_year=c.school_year,
            has_analysis=c.id in analysis_card_ids,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in cards
    ]


# ── 3. Get Cached Analysis ──────────────────────────────────


@router.get("/{report_card_id}/analysis")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_analysis(
    request: Request,
    report_card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """Get cached analysis for a report card, or null if not yet analyzed."""
    is_admin = current_user.role == UserRole.ADMIN
    _verify_report_card_ownership(db, current_user.id, report_card_id, is_admin=is_admin)

    analysis = (
        db.query(SchoolReportCardAnalysis)
        .filter(
            SchoolReportCardAnalysis.report_card_id == report_card_id,
            SchoolReportCardAnalysis.analysis_type == "full",
        )
        .first()
    )

    if not analysis:
        return {"analysis": None}

    return _build_full_analysis_response(analysis)


# ── 4. Trigger Analysis ─────────────────────────────────────


@router.post("/{report_card_id}/analyze", response_model=FullAnalysisResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def analyze_report_card(
    request: Request,
    report_card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Trigger AI analysis of a report card."""
    rc = _verify_report_card_ownership(db, current_user.id, report_card_id)

    # Cache check: return existing analysis if available
    existing = (
        db.query(SchoolReportCardAnalysis)
        .filter(
            SchoolReportCardAnalysis.report_card_id == report_card_id,
            SchoolReportCardAnalysis.analysis_type == "full",
        )
        .first()
    )
    if existing:
        return _build_full_analysis_response(existing)

    # Validate text content
    if not rc.text_content or len(rc.text_content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Report card has insufficient text content for analysis. Please ensure the file was readable.",
        )

    check_ai_usage(current_user, db)

    # Get student info for context
    student = db.query(Student).filter(Student.id == rc.student_id).first()
    student_user = None
    if student:
        student_user = db.query(User).filter(User.id == student.user_id).first()
    student_name = student_user.full_name if student_user else "Student"
    grade_level = student.grade_level if student else rc.grade_level or ""

    logger.info(
        "Analyzing report card | parent=%s | report_card=%s | student=%s",
        current_user.id, report_card_id, rc.student_id,
    )

    from app.services.school_report_card_service import analyze_report_card as svc_analyze
    result = await svc_analyze(
        text_content=rc.text_content,
        student_name=student_name,
        grade_level=grade_level,
        school_name=rc.school_name or "",
        term=rc.term or "",
    )

    from app.services.ai_service import get_last_ai_usage
    _usage = get_last_ai_usage() or {}

    content_hash = hashlib.sha256(rc.text_content.encode()).hexdigest()

    analysis = SchoolReportCardAnalysis(
        report_card_id=report_card_id,
        student_id=rc.student_id,
        analysis_type="full",
        content=json.dumps(result),
        content_hash=content_hash,
        ai_model=_usage.get("model_name"),
        prompt_tokens=_usage.get("prompt_tokens"),
        completion_tokens=_usage.get("completion_tokens"),
        estimated_cost_usd=_usage.get("estimated_cost_usd"),
    )
    db.add(analysis)

    increment_ai_usage(current_user, db, generation_type="report_card_analysis", **_usage)

    db.commit()
    db.refresh(analysis)

    return _build_full_analysis_response(analysis)


# ── 5. Career Path Analysis ─────────────────────────────────


@router.post("/{student_id}/career-path", response_model=CareerPathResponse)
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def career_path_analysis(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Generate career path suggestions based on all report cards for a student."""
    student = _verify_parent_child(db, current_user.id, student_id)

    # Load all non-archived report cards
    cards = (
        db.query(SchoolReportCard)
        .filter(
            SchoolReportCard.student_id == student_id,
            SchoolReportCard.archived_at.is_(None),
        )
        .all()
    )

    cards_with_text = [c for c in cards if c.text_content]
    if not cards_with_text:
        raise HTTPException(
            status_code=400,
            detail="No report cards with readable text found. Please upload at least one report card first.",
        )

    # Compute combined hash for cache key
    combined_text = "||".join(sorted([c.text_content for c in cards_with_text]))
    combined_hash = hashlib.sha256(combined_text.encode()).hexdigest()

    # Cache check: look for career_path analysis with matching content_hash
    existing = (
        db.query(SchoolReportCardAnalysis)
        .filter(
            SchoolReportCardAnalysis.student_id == student_id,
            SchoolReportCardAnalysis.analysis_type == "career_path",
            SchoolReportCardAnalysis.content_hash == combined_hash,
        )
        .first()
    )
    if existing:
        return _build_career_path_response(existing, len(cards_with_text))

    # Load existing full analyses for these report cards
    card_ids = [c.id for c in cards_with_text]
    analyses = (
        db.query(SchoolReportCardAnalysis)
        .filter(
            SchoolReportCardAnalysis.report_card_id.in_(card_ids),
            SchoolReportCardAnalysis.analysis_type == "full",
        )
        .all()
    )
    analysis_data = []
    for a in analyses:
        try:
            analysis_data.append(json.loads(a.content))
        except (json.JSONDecodeError, TypeError):
            pass

    check_ai_usage(current_user, db)

    student_user = db.query(User).filter(User.id == student.user_id).first()
    student_name = student_user.full_name if student_user else "Student"
    grade_level = student.grade_level or ""

    logger.info(
        "Generating career path | parent=%s | student=%s | cards=%d",
        current_user.id, student_id, len(cards_with_text),
    )

    from app.services.school_report_card_service import generate_career_path as svc_career
    result = await svc_career(
        analyses=analysis_data,
        student_name=student_name,
        grade_level=grade_level,
    )

    from app.services.ai_service import get_last_ai_usage
    _usage = get_last_ai_usage() or {}

    analysis = SchoolReportCardAnalysis(
        report_card_id=None,
        student_id=student_id,
        analysis_type="career_path",
        content=json.dumps(result),
        content_hash=combined_hash,
        ai_model=_usage.get("model_name"),
        prompt_tokens=_usage.get("prompt_tokens"),
        completion_tokens=_usage.get("completion_tokens"),
        estimated_cost_usd=_usage.get("estimated_cost_usd"),
    )
    db.add(analysis)

    increment_ai_usage(current_user, db, generation_type="career_path_analysis", **_usage)

    db.commit()
    db.refresh(analysis)

    return _build_career_path_response(analysis, len(cards_with_text))


# ── 6. Soft Delete ───────────────────────────────────────────


@router.delete("/{report_card_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_report_card(
    request: Request,
    report_card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Soft-delete (archive) a report card."""
    rc = _verify_report_card_ownership(db, current_user.id, report_card_id)

    rc.archived_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Report card archived | parent=%s | report_card=%s", current_user.id, report_card_id)

    return {"status": "deleted"}
