"""
MCP Study Material Generation Tools for ClassBridge.

Exposes 7 FastAPI endpoints at /api/mcp/tools/study/... that allow LLM clients
to list, retrieve, search, generate, and convert study materials on behalf of
authenticated users.

Rate limiting: Simple in-memory per-user counter (10 AI generations per minute).
Dedup: content_hash (SHA-256) checked before any AI call to avoid redundant generation.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole
from app.services.ai_service import (
    generate_content,
    generate_flashcards as ai_generate_flashcards,
    generate_quiz as ai_generate_quiz,
    generate_study_guide as ai_generate_study_guide,
)

router = APIRouter(prefix="/api/mcp/tools/study", tags=["mcp-study"])

# ---------------------------------------------------------------------------
# In-memory rate limiter: { user_id: [(timestamp, count), ...] }
# We track one-minute windows per user.
# ---------------------------------------------------------------------------

_rate_limit_store: dict[int, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 10  # max AI generations per minute
_RATE_LIMIT_WINDOW = 60  # seconds


def _check_rate_limit(user_id: int) -> None:
    """Raise 429 if the user has exceeded 10 AI generations in the last 60 seconds."""
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    timestamps = _rate_limit_store[user_id]
    # Prune old entries
    timestamps[:] = [t for t in timestamps if t > window_start]
    if len(timestamps) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {_RATE_LIMIT_MAX} AI generations per minute.",
        )
    timestamps.append(now)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class StudyMaterialResponse(BaseModel):
    id: int
    title: str
    guide_type: str
    course_id: Optional[int] = None
    user_id: int
    content_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StudyMaterialDetailResponse(StudyMaterialResponse):
    content: str
    focus_prompt: Optional[str] = None
    version: int = 1


class GenerateGuideRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Source content to generate a study guide from")
    title: str = Field(..., min_length=1, max_length=255)
    course_id: Optional[int] = None
    focus_prompt: Optional[str] = Field(None, max_length=2000)


class GenerateQuizRequest(BaseModel):
    study_guide_id: Optional[int] = None
    content: Optional[str] = None
    num_questions: int = Field(5, ge=1, le=20)


class GenerateFlashcardsRequest(BaseModel):
    study_guide_id: Optional[int] = None
    content: Optional[str] = None


class ConvertRequest(BaseModel):
    study_guide_id: int
    target_type: str = Field(..., pattern="^(quiz|flashcards)$")


class GeneratedMaterialResponse(BaseModel):
    id: int
    title: str
    guide_type: str
    content: str
    course_id: Optional[int] = None
    content_hash: str
    created_at: Optional[datetime] = None
    deduplicated: bool = False  # True when an existing hash match was returned


# ---------------------------------------------------------------------------
# Helper: compute content hash
# ---------------------------------------------------------------------------


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_student_user_id(current_user: User, db: Session) -> int:
    """Return the user_id to use for study guide ownership."""
    return current_user.id


def _get_guide_or_404(guide_id: int, db: Session, current_user: User) -> StudyGuide:
    guide = db.query(StudyGuide).filter(StudyGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="Study material not found")
    # RBAC: owner, teacher, or admin can access
    if (
        guide.user_id != current_user.id
        and not current_user.has_role(UserRole.TEACHER)
        and not current_user.has_role(UserRole.ADMIN)
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    return guide


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/materials", response_model=list[StudyMaterialResponse], operation_id="mcp_list_study_materials")
def list_study_materials(
    guide_type: Optional[str] = Query(None, description="Filter by type: study_guide, quiz, flashcards"),
    course_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None, description="For teachers/parents — filter by student user_id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List study materials visible to the current user."""
    query = db.query(StudyGuide).filter(StudyGuide.archived_at.is_(None))

    # Determine owner filter
    if current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN):
        if student_id is not None:
            query = query.filter(StudyGuide.user_id == student_id)
        # Teachers/admins can see all (no extra restriction)
    else:
        # Students and parents see their own materials only
        query = query.filter(StudyGuide.user_id == current_user.id)

    if guide_type:
        query = query.filter(StudyGuide.guide_type == guide_type)
    if course_id is not None:
        query = query.filter(StudyGuide.course_id == course_id)

    return query.order_by(StudyGuide.created_at.desc()).limit(100).all()


@router.get("/materials/{material_id}", response_model=StudyMaterialDetailResponse, operation_id="mcp_get_study_material")
def get_study_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full content of a single study material."""
    return _get_guide_or_404(material_id, db, current_user)


@router.get("/search", response_model=list[StudyMaterialResponse], operation_id="mcp_search_study_materials")
def search_study_materials(
    q: str = Query(..., min_length=1, description="Keyword to search in title and content"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search study materials by keyword in title or content."""
    keyword = f"%{q}%"
    query = db.query(StudyGuide).filter(
        StudyGuide.archived_at.is_(None),
        or_(
            StudyGuide.title.ilike(keyword),
            StudyGuide.content.ilike(keyword),
        ),
    )

    if not (current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN)):
        query = query.filter(StudyGuide.user_id == current_user.id)

    return query.order_by(StudyGuide.created_at.desc()).limit(50).all()


@router.post("/generate/guide", response_model=GeneratedMaterialResponse, operation_id="mcp_generate_study_guide")
async def generate_study_guide_tool(
    req: GenerateGuideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a study guide from provided content. Applies content-hash dedup and rate limiting."""
    _check_rate_limit(current_user.id)

    # Dedup check: hash is built from content + title + focus_prompt
    hash_input = f"{req.title}|{req.content}|{req.focus_prompt or ''}"
    chash = _content_hash(hash_input)

    existing = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == current_user.id,
            StudyGuide.content_hash == chash,
            StudyGuide.guide_type == "study_guide",
            StudyGuide.archived_at.is_(None),
        )
        .first()
    )
    if existing:
        return GeneratedMaterialResponse(
            id=existing.id,
            title=existing.title,
            guide_type=existing.guide_type,
            content=existing.content,
            course_id=existing.course_id,
            content_hash=chash,
            created_at=existing.created_at,
            deduplicated=True,
        )

    # Generate via AI
    generated_content = await ai_generate_study_guide(
        assignment_title=req.title,
        assignment_description=req.content,
        course_name=req.title,
        focus_prompt=req.focus_prompt,
    )

    guide = StudyGuide(
        user_id=current_user.id,
        title=req.title,
        content=generated_content,
        guide_type="study_guide",
        course_id=req.course_id,
        focus_prompt=req.focus_prompt,
        content_hash=chash,
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)

    return GeneratedMaterialResponse(
        id=guide.id,
        title=guide.title,
        guide_type=guide.guide_type,
        content=guide.content,
        course_id=guide.course_id,
        content_hash=chash,
        created_at=guide.created_at,
        deduplicated=False,
    )


@router.post("/generate/quiz", response_model=GeneratedMaterialResponse, operation_id="mcp_generate_quiz")
async def generate_quiz_tool(
    req: GenerateQuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a quiz from a study guide or raw content. Applies content-hash dedup and rate limiting."""
    _check_rate_limit(current_user.id)

    source_content: str
    source_title: str
    course_id: Optional[int] = None

    if req.study_guide_id is not None:
        guide = _get_guide_or_404(req.study_guide_id, db, current_user)
        source_content = guide.content
        source_title = guide.title
        course_id = guide.course_id
    elif req.content:
        source_content = req.content
        source_title = "MCP Quiz"
    else:
        raise HTTPException(status_code=400, detail="Provide either study_guide_id or content")

    hash_input = f"quiz|{source_title}|{source_content}|{req.num_questions}"
    chash = _content_hash(hash_input)

    existing = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == current_user.id,
            StudyGuide.content_hash == chash,
            StudyGuide.guide_type == "quiz",
            StudyGuide.archived_at.is_(None),
        )
        .first()
    )
    if existing:
        return GeneratedMaterialResponse(
            id=existing.id,
            title=existing.title,
            guide_type="quiz",
            content=existing.content,
            course_id=existing.course_id,
            content_hash=chash,
            created_at=existing.created_at,
            deduplicated=True,
        )

    generated_content = await ai_generate_quiz(
        topic=source_title,
        content=source_content,
        num_questions=req.num_questions,
    )

    quiz_title = f"{source_title} — Quiz"
    guide = StudyGuide(
        user_id=current_user.id,
        title=quiz_title,
        content=generated_content,
        guide_type="quiz",
        course_id=course_id,
        content_hash=chash,
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)

    return GeneratedMaterialResponse(
        id=guide.id,
        title=guide.title,
        guide_type="quiz",
        content=guide.content,
        course_id=guide.course_id,
        content_hash=chash,
        created_at=guide.created_at,
        deduplicated=False,
    )


@router.post("/generate/flashcards", response_model=GeneratedMaterialResponse, operation_id="mcp_generate_flashcards")
async def generate_flashcards_tool(
    req: GenerateFlashcardsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate flashcards from a study guide or raw content. Applies content-hash dedup and rate limiting."""
    _check_rate_limit(current_user.id)

    source_content: str
    source_title: str
    course_id: Optional[int] = None

    if req.study_guide_id is not None:
        guide = _get_guide_or_404(req.study_guide_id, db, current_user)
        source_content = guide.content
        source_title = guide.title
        course_id = guide.course_id
    elif req.content:
        source_content = req.content
        source_title = "MCP Flashcards"
    else:
        raise HTTPException(status_code=400, detail="Provide either study_guide_id or content")

    hash_input = f"flashcards|{source_title}|{source_content}"
    chash = _content_hash(hash_input)

    existing = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == current_user.id,
            StudyGuide.content_hash == chash,
            StudyGuide.guide_type == "flashcards",
            StudyGuide.archived_at.is_(None),
        )
        .first()
    )
    if existing:
        return GeneratedMaterialResponse(
            id=existing.id,
            title=existing.title,
            guide_type="flashcards",
            content=existing.content,
            course_id=existing.course_id,
            content_hash=chash,
            created_at=existing.created_at,
            deduplicated=True,
        )

    generated_content = await ai_generate_flashcards(
        topic=source_title,
        content=source_content,
    )

    fc_title = f"{source_title} — Flashcards"
    guide = StudyGuide(
        user_id=current_user.id,
        title=fc_title,
        content=generated_content,
        guide_type="flashcards",
        course_id=course_id,
        content_hash=chash,
    )
    db.add(guide)
    db.commit()
    db.refresh(guide)

    return GeneratedMaterialResponse(
        id=guide.id,
        title=guide.title,
        guide_type="flashcards",
        content=guide.content,
        course_id=guide.course_id,
        content_hash=chash,
        created_at=guide.created_at,
        deduplicated=False,
    )


@router.post("/convert", response_model=GeneratedMaterialResponse, operation_id="mcp_convert_study_material")
async def convert_study_material(
    req: ConvertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert an existing study guide into a quiz or flashcard set."""
    _check_rate_limit(current_user.id)

    source = _get_guide_or_404(req.study_guide_id, db, current_user)

    if req.target_type == "quiz":
        sub_req = GenerateQuizRequest(study_guide_id=source.id)
        return await generate_quiz_tool(sub_req, db=db, current_user=current_user)
    else:
        sub_req = GenerateFlashcardsRequest(study_guide_id=source.id)
        return await generate_flashcards_tool(sub_req, db=db, current_user=current_user)
