import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import or_, and_, func as sa_func
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.db.database import get_db
from app.models.study_guide import StudyGuide
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.course_content import CourseContent
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.study import (
    StudyGuideCreate,
    StudyGuideUpdate,
    StudyGuideResponse,
    QuizGenerateRequest,
    QuizResponse,
    QuizQuestion,
    FlashcardGenerateRequest,
    FlashcardSetResponse,
    Flashcard,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from app.api.deps import get_current_user
from app.services.ai_service import generate_study_guide, generate_quiz, generate_flashcards
from app.services.file_processor import (
    process_file,
    get_supported_formats,
    FileProcessingError,
    MAX_FILE_SIZE,
)

router = APIRouter(prefix="/study", tags=["Study Tools"])


# ============================================
# Helper Functions
# ============================================


def enforce_study_guide_limit(db: Session, user: User) -> None:
    """Enforce role-based study guide limit. Deletes oldest guides when limit reached."""
    limit = (
        settings.max_study_guides_per_parent
        if user.role == UserRole.PARENT
        else settings.max_study_guides_per_student
    )
    count = db.query(StudyGuide).filter(StudyGuide.user_id == user.id).count()
    if count >= limit:
        guides_to_delete = count - limit + 1
        oldest_guides = (
            db.query(StudyGuide)
            .filter(StudyGuide.user_id == user.id)
            .order_by(StudyGuide.created_at.asc())
            .limit(guides_to_delete)
            .all()
        )
        for guide in oldest_guides:
            db.delete(guide)


def compute_content_hash(title: str, guide_type: str, assignment_id: int | None = None) -> str:
    """Compute a hash for duplicate detection based on title + guide_type + assignment_id."""
    key = f"{title.strip().lower()}|{guide_type}|{assignment_id or ''}"
    return hashlib.sha256(key.encode()).hexdigest()


def get_version_info(db: Session, regenerate_from_id: int, user_id: int):
    """Get version info for regeneration. Returns (root_guide_id, next_version)."""
    original = db.query(StudyGuide).filter(
        StudyGuide.id == regenerate_from_id,
        StudyGuide.user_id == user_id,
    ).first()
    if not original:
        raise HTTPException(status_code=404, detail="Original study guide not found")

    # Find the root guide (version 1)
    root_id = original.parent_guide_id if original.parent_guide_id else original.id

    # Find max version in the chain
    max_version = (
        db.query(sa_func.max(StudyGuide.version))
        .filter(
            or_(
                StudyGuide.id == root_id,
                StudyGuide.parent_guide_id == root_id,
            )
        )
        .scalar()
    ) or 1

    return root_id, max_version + 1


def get_student_enrolled_course_ids(db: Session, user_id: int) -> list[int]:
    """Get course IDs for a student's enrolled courses."""
    student = db.query(Student).filter(Student.user_id == user_id).first()
    if not student:
        return []
    return [c.id for c in student.courses]


def get_linked_children_user_ids(db: Session, parent_id: int) -> list[int]:
    """Get user_ids of all children linked to a parent."""
    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == parent_id
    ).all()
    student_ids = [r[0] for r in rows]
    if not student_ids:
        return []
    students = db.query(Student.user_id).filter(Student.id.in_(student_ids)).all()
    return [s[0] for s in students]


def strip_json_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from AI responses."""
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


def ensure_course_and_content(
    db: Session, user: User, title: str, text_content: str | None,
    course_id: int | None, course_content_id: int | None,
) -> tuple[int, int]:
    """Ensure a course + course_content exist for a study guide.

    Returns (course_id, course_content_id).  If course_content_id is already
    provided it is returned as-is.  If course_id is missing the user's default
    'My Materials' course is created/fetched.  A new CourseContent row is
    always created when course_content_id is None.
    """
    from app.api.routes.courses import get_or_create_default_course

    # Resolve existing course_content
    if course_content_id:
        cc = db.query(CourseContent).filter(CourseContent.id == course_content_id).first()
        if cc:
            return cc.course_id, cc.id

    # Resolve course
    if course_id:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            course = get_or_create_default_course(db, user)
    else:
        course = get_or_create_default_course(db, user)

    # Create CourseContent
    cc = CourseContent(
        course_id=course.id,
        title=title,
        text_content=text_content,
        content_type="other",
        created_by_user_id=user.id,
    )
    db.add(cc)
    db.flush()  # get cc.id without committing
    return course.id, cc.id


def find_recent_duplicate(
    db: Session, user_id: int, content_hash: str, seconds: int = 60
) -> StudyGuide | None:
    """Return an existing study guide if one with the same hash was created recently."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == user_id,
            StudyGuide.content_hash == content_hash,
            StudyGuide.created_at >= cutoff,
        )
        .order_by(StudyGuide.created_at.desc())
        .first()
    )


# ============================================
# Duplicate Detection
# ============================================


@router.post("/check-duplicate", response_model=DuplicateCheckResponse)
def check_duplicate(
    request: DuplicateCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a similar study guide already exists before generating."""
    # Check by assignment_id + guide_type (most specific)
    if request.assignment_id:
        existing = db.query(StudyGuide).filter(
            StudyGuide.user_id == current_user.id,
            StudyGuide.assignment_id == request.assignment_id,
            StudyGuide.guide_type == request.guide_type,
        ).order_by(StudyGuide.version.desc()).first()
        if existing:
            return DuplicateCheckResponse(
                exists=True,
                existing_guide=existing,
                message=f"A {request.guide_type.replace('_', ' ')} already exists for this assignment (v{existing.version})",
            )

    # Check by title + guide_type (fallback)
    title = request.title
    if title:
        existing = db.query(StudyGuide).filter(
            StudyGuide.user_id == current_user.id,
            StudyGuide.title.ilike(f"%{title.strip()}%"),
            StudyGuide.guide_type == request.guide_type,
        ).order_by(StudyGuide.version.desc()).first()
        if existing:
            return DuplicateCheckResponse(
                exists=True,
                existing_guide=existing,
                message=f"A similar {request.guide_type.replace('_', ' ')} already exists: \"{existing.title}\" (v{existing.version})",
            )

    return DuplicateCheckResponse(exists=False)


# ============================================
# Generation Endpoints
# ============================================


@router.post("/generate", response_model=StudyGuideResponse)
async def generate_study_guide_endpoint(
    request: StudyGuideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a study guide from an assignment or custom content."""
    # Handle versioning
    version = 1
    parent_guide_id = None
    if request.regenerate_from_id:
        parent_guide_id, version = get_version_info(db, request.regenerate_from_id, current_user.id)

    # Get source content
    assignment = None
    course = None
    title = request.title or "Study Guide"
    description = request.content or ""

    if request.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == request.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        title = f"Study Guide: {assignment.title}"
        description = assignment.description or ""
        course = assignment.course

    if request.course_id and not course:
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

    course_name = course.name if course else "General"
    due_date = str(assignment.due_date) if assignment and assignment.due_date else None

    if not description:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate a study guide",
        )

    # Generate study guide using AI
    try:
        content = await generate_study_guide(
            assignment_title=title,
            assignment_description=description,
            course_name=course_name,
            due_date=due_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Deduplicate: return existing if same hash was created recently
    content_hash = compute_content_hash(title, "study_guide", request.assignment_id)
    existing = find_recent_duplicate(db, current_user.id, content_hash)
    if existing:
        return existing

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, title, description,
        course_id=request.course_id or (course.id if course else None),
        course_content_id=request.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=request.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=title,
        content=content,
        guide_type="study_guide",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
    )
    db.add(study_guide)
    db.commit()
    db.refresh(study_guide)

    return study_guide


@router.post("/quiz/generate", response_model=QuizResponse)
async def generate_quiz_endpoint(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a practice quiz from an assignment or custom content."""
    # Handle versioning
    version = 1
    parent_guide_id = None
    if request.regenerate_from_id:
        parent_guide_id, version = get_version_info(db, request.regenerate_from_id, current_user.id)

    topic = request.topic or "Quiz"
    content = request.content or ""

    if request.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == request.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        topic = assignment.title
        content = assignment.description or ""

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate a quiz",
        )

    # Generate quiz using AI
    try:
        quiz_json = await generate_quiz(
            topic=topic,
            content=content,
            num_questions=request.num_questions,
        )
        quiz_json = strip_json_fences(quiz_json)
        questions_data = json.loads(quiz_json)
        questions = [QuizQuestion(**q) for q in questions_data]
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse quiz response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Deduplicate: return existing if same hash was created recently
    content_hash = compute_content_hash(f"Quiz: {topic}", "quiz", request.assignment_id)
    existing = find_recent_duplicate(db, current_user.id, content_hash)
    if existing:
        existing_questions = [QuizQuestion(**q) for q in json.loads(existing.content)]
        return QuizResponse(
            id=existing.id, title=existing.title, questions=existing_questions,
            guide_type="quiz", version=existing.version,
            parent_guide_id=existing.parent_guide_id, created_at=existing.created_at,
        )

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, f"Quiz: {topic}", content,
        course_id=request.course_id,
        course_content_id=request.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=request.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=f"Quiz: {topic}",
        content=quiz_json,
        guide_type="quiz",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
    )
    db.add(study_guide)
    db.commit()
    db.refresh(study_guide)

    return QuizResponse(
        id=study_guide.id,
        title=study_guide.title,
        questions=questions,
        guide_type="quiz",
        version=study_guide.version,
        parent_guide_id=study_guide.parent_guide_id,
        created_at=study_guide.created_at,
    )


@router.post("/flashcards/generate", response_model=FlashcardSetResponse)
async def generate_flashcards_endpoint(
    request: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate flashcards from an assignment or custom content."""
    # Handle versioning
    version = 1
    parent_guide_id = None
    if request.regenerate_from_id:
        parent_guide_id, version = get_version_info(db, request.regenerate_from_id, current_user.id)

    topic = request.topic or "Flashcards"
    content = request.content or ""

    if request.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == request.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        topic = assignment.title
        content = assignment.description or ""

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Please provide assignment_id or content to generate flashcards",
        )

    # Generate flashcards using AI
    try:
        cards_json = await generate_flashcards(
            topic=topic,
            content=content,
            num_cards=request.num_cards,
        )
        cards_json = strip_json_fences(cards_json)
        cards_data = json.loads(cards_json)
        cards = [Flashcard(**c) for c in cards_data]
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse flashcards response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Deduplicate: return existing if same hash was created recently
    content_hash = compute_content_hash(f"Flashcards: {topic}", "flashcards", request.assignment_id)
    existing = find_recent_duplicate(db, current_user.id, content_hash)
    if existing:
        existing_cards = [Flashcard(**c) for c in json.loads(existing.content)]
        return FlashcardSetResponse(
            id=existing.id, title=existing.title, cards=existing_cards,
            guide_type="flashcards", version=existing.version,
            parent_guide_id=existing.parent_guide_id, created_at=existing.created_at,
        )

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, f"Flashcards: {topic}", content,
        course_id=request.course_id,
        course_content_id=request.course_content_id,
    )

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    study_guide = StudyGuide(
        user_id=current_user.id,
        assignment_id=request.assignment_id,
        course_id=resolved_course_id,
        course_content_id=resolved_cc_id,
        title=f"Flashcards: {topic}",
        content=cards_json,
        guide_type="flashcards",
        version=version,
        parent_guide_id=parent_guide_id,
        content_hash=content_hash,
    )
    db.add(study_guide)
    db.commit()
    db.refresh(study_guide)

    return FlashcardSetResponse(
        id=study_guide.id,
        title=study_guide.title,
        cards=cards,
        guide_type="flashcards",
        version=study_guide.version,
        parent_guide_id=study_guide.parent_guide_id,
        created_at=study_guide.created_at,
    )


# ============================================
# List / Get / Delete / Versions
# ============================================


@router.get("/guides", response_model=list[StudyGuideResponse])
def list_study_guides(
    guide_type: str | None = None,
    course_id: int | None = None,
    course_content_id: int | None = None,
    include_children: bool = False,
    student_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List study guides with role-based visibility.
    - Students: own guides + guides tagged to enrolled courses
    - Parents: own guides; with include_children=true also children's guides
    """
    if current_user.role == UserRole.STUDENT:
        enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
        query = db.query(StudyGuide).filter(
            or_(
                StudyGuide.user_id == current_user.id,
                and_(
                    StudyGuide.course_id.in_(enrolled_course_ids) if enrolled_course_ids else False,
                    StudyGuide.course_id.isnot(None),
                )
            )
        )
    elif current_user.role == UserRole.PARENT and include_children:
        user_ids = [current_user.id]
        if student_user_id:
            # Verify parent-child link
            children_ids = get_linked_children_user_ids(db, current_user.id)
            if student_user_id in children_ids:
                user_ids.append(student_user_id)
        else:
            user_ids.extend(get_linked_children_user_ids(db, current_user.id))
        query = db.query(StudyGuide).filter(StudyGuide.user_id.in_(user_ids))
    else:
        # Default: own guides only
        query = db.query(StudyGuide).filter(StudyGuide.user_id == current_user.id)

    if guide_type:
        query = query.filter(StudyGuide.guide_type == guide_type)
    if course_id:
        query = query.filter(StudyGuide.course_id == course_id)
    if course_content_id:
        query = query.filter(StudyGuide.course_content_id == course_content_id)

    return query.order_by(StudyGuide.created_at.desc()).all()


@router.get("/guides/{guide_id}", response_model=StudyGuideResponse)
def get_study_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific study guide with role-based access control."""
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Owner always has access
    if guide.user_id == current_user.id:
        return guide

    # Parent can view linked children's guides
    if current_user.role == UserRole.PARENT:
        children_user_ids = get_linked_children_user_ids(db, current_user.id)
        if guide.user_id in children_user_ids:
            return guide

    # Student can view course-tagged guides for enrolled courses
    if current_user.role == UserRole.STUDENT and guide.course_id:
        enrolled_course_ids = get_student_enrolled_course_ids(db, current_user.id)
        if guide.course_id in enrolled_course_ids:
            return guide

    raise HTTPException(status_code=404, detail="Study guide not found")


@router.get("/guides/{guide_id}/versions", response_model=list[StudyGuideResponse])
def list_guide_versions(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of a study guide."""
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    # Find the root guide
    root_id = guide.parent_guide_id if guide.parent_guide_id else guide.id

    # Get all versions (root + children)
    versions = (
        db.query(StudyGuide)
        .filter(
            or_(
                StudyGuide.id == root_id,
                StudyGuide.parent_guide_id == root_id,
            ),
            StudyGuide.user_id == current_user.id,
        )
        .order_by(StudyGuide.version.desc())
        .all()
    )

    if not versions:
        raise HTTPException(status_code=404, detail="Study guide not found")

    return versions


@router.delete("/guides/{guide_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a study guide (owner only)."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")
    db.delete(guide)
    db.commit()
    return None


@router.patch("/guides/{guide_id}", response_model=StudyGuideResponse)
def update_study_guide(
    guide_id: int,
    update: StudyGuideUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a study guide (owner only). Currently supports assigning to a course."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study guide not found")

    if update.course_id is not None:
        course = db.query(Course).filter(Course.id == update.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

    guide.course_id = update.course_id
    db.commit()
    db.refresh(guide)
    return guide


# ============================================
# File Upload Endpoints
# ============================================


@router.get("/upload/formats")
def get_upload_formats():
    """Get information about supported file upload formats."""
    return get_supported_formats()


@router.post("/upload/generate", response_model=StudyGuideResponse)
async def generate_from_file_upload(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    guide_type: str = Form("study_guide"),
    num_questions: int = Form(5),
    num_cards: int = Form(10),
    course_id: Optional[int] = Form(None),
    course_content_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate study material from an uploaded file.

    Supports: PDF, DOCX, PPTX, XLSX, TXT, images (OCR), and ZIP archives.
    Maximum file size: 100 MB.
    """
    if guide_type not in ("study_guide", "quiz", "flashcards"):
        raise HTTPException(
            status_code=400,
            detail="guide_type must be one of: study_guide, quiz, flashcards"
        )

    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    try:
        extracted_text = process_file(file_content, file.filename or "unknown")
    except FileProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from the uploaded file"
        )

    if not title:
        base_name = file.filename.rsplit('.', 1)[0] if file.filename else "Uploaded File"
        title = base_name

    # Generate the appropriate study material
    try:
        if guide_type == "quiz":
            quiz_json = await generate_quiz(
                topic=title,
                content=extracted_text,
                num_questions=num_questions,
            )
            quiz_json = strip_json_fences(quiz_json)
            questions_data = json.loads(quiz_json)
            questions = [QuizQuestion(**q) for q in questions_data]

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Quiz: {title}",
                content=quiz_json,
                guide_type="quiz",
                content_hash=compute_content_hash(f"Quiz: {title}", "quiz"),
            )

        elif guide_type == "flashcards":
            cards_json = await generate_flashcards(
                topic=title,
                content=extracted_text,
                num_cards=num_cards,
            )
            cards_json = strip_json_fences(cards_json)
            cards_data = json.loads(cards_json)
            cards = [Flashcard(**c) for c in cards_data]

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Flashcards: {title}",
                content=cards_json,
                guide_type="flashcards",
                content_hash=compute_content_hash(f"Flashcards: {title}", "flashcards"),
            )

        else:  # study_guide
            content = await generate_study_guide(
                assignment_title=title,
                assignment_description=extracted_text,
                course_name="Uploaded Content",
            )

            study_guide = StudyGuide(
                user_id=current_user.id,
                title=f"Study Guide: {title}",
                content=content,
                guide_type="study_guide",
                content_hash=compute_content_hash(f"Study Guide: {title}", "study_guide"),
            )

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Deduplicate: return existing if same hash was created recently
    if study_guide.content_hash:
        existing = find_recent_duplicate(db, current_user.id, study_guide.content_hash)
        if existing:
            return existing

    # Auto-create course + course_content if needed
    resolved_course_id, resolved_cc_id = ensure_course_and_content(
        db, current_user, title, extracted_text,
        course_id=course_id,
        course_content_id=course_content_id,
    )
    study_guide.course_id = resolved_course_id
    study_guide.course_content_id = resolved_cc_id

    # Enforce limit and save to database
    enforce_study_guide_limit(db, current_user)
    db.add(study_guide)
    db.commit()
    db.refresh(study_guide)

    return study_guide


@router.post("/upload/extract-text")
async def extract_text_from_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Extract text from an uploaded file without generating study material."""
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    try:
        extracted_text = process_file(file_content, file.filename or "unknown")
    except FileProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "filename": file.filename,
        "text": extracted_text,
        "character_count": len(extracted_text),
        "word_count": len(extracted_text.split()),
    }
