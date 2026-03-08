"""Parent AI endpoints — briefing notes generated for parents."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.services.ai_service import generate_parent_briefing
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


# ── Endpoints ────────────────────────────────────

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
