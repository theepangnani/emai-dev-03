"""Advanced AI Personalization API routes (Phase 3).

Routes:
  GET    /api/personalization/profile                           — Student's personalization profile
  PUT    /api/personalization/profile                           — Update preferences
  GET    /api/personalization/mastery                           — All subject mastery (recomputes if >24 h stale)
  POST   /api/personalization/mastery/refresh                   — Force recompute mastery
  GET    /api/personalization/mastery/{subject_code}            — Single subject mastery
  GET    /api/personalization/difficulty/{subject}/{type}       — Recommended difficulty
  POST   /api/personalization/difficulty/{subject}/{type}/feedback — Report attempt result
  POST   /api/personalization/analyze                           — AI learning-style detection + recommendations
  GET    /api/personalization/recommendations                   — Latest cached AI recommendations

  GET    /api/personalization/children/{student_id}/mastery     — Parent: child mastery
  GET    /api/personalization/children/{student_id}/profile     — Parent: child profile
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_feature, require_role
from app.db.database import get_db
from app.models.personalization import (
    AdaptiveDifficulty,
    LearningStyle,
    PersonalizationProfile,
    SubjectMastery,
)
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.services.personalization import PersonalizationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/personalization", tags=["Personalization"])

engine = PersonalizationEngine()

# ────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ────────────────────────────────────────────────────────────────────────────


class PersonalizationProfileResponse(BaseModel):
    id: int
    student_id: int
    learning_style: Optional[str] = None
    learning_style_confidence: float
    preferred_difficulty: str
    study_session_length: int
    preferred_study_time: str
    strong_subjects: list[str]
    weak_subjects: list[str]
    last_analyzed_at: Optional[str] = None
    ai_analysis_count: int
    recommendations_generated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class PersonalizationProfileUpdate(BaseModel):
    learning_style: Optional[str] = None
    preferred_difficulty: Optional[str] = None
    study_session_length: Optional[int] = None
    preferred_study_time: Optional[str] = None


class SubjectMasteryResponse(BaseModel):
    id: int
    student_id: int
    subject_code: str
    subject_name: str
    mastery_score: float
    mastery_level: str
    quiz_score_avg: float
    quiz_attempts: int
    grade_avg: float
    last_quiz_date: Optional[str] = None
    trend: str
    recommended_next_topics: list[str]

    model_config = {"from_attributes": True}


class AdaptiveDifficultyResponse(BaseModel):
    student_id: int
    subject_code: str
    content_type: str
    current_difficulty: str
    recommended_difficulty: str
    consecutive_correct: int
    consecutive_incorrect: int
    total_attempts: int

    model_config = {"from_attributes": True}


class AttemptFeedbackRequest(BaseModel):
    passed: bool


class RecommendationsResponse(BaseModel):
    weak_areas: list[str]
    recommended_topics: list[str]
    study_schedule: dict[str, str]
    preferred_format: str
    difficulty_adjustment: str
    summary: Optional[str] = None
    generated_at: Optional[str] = None


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _get_student_for_user(db: Session, user: User) -> Student:
    """Return Student record for a STUDENT-role user, or 403."""
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


def _verify_parent_child_access(db: Session, user: User, student_id: int) -> Student:
    """Verify PARENT or ADMIN can view this student's data. Returns the Student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if user.has_role(UserRole.ADMIN):
        return student

    if user.has_role(UserRole.PARENT):
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == user.id,
                parent_students.c.student_id == student_id,
            )
        ).first()
        if link:
            return student
        raise HTTPException(status_code=403, detail="Not authorized to view this student")

    raise HTTPException(status_code=403, detail="Insufficient permissions")


def _profile_to_response(profile: PersonalizationProfile) -> PersonalizationProfileResponse:
    return PersonalizationProfileResponse(
        id=profile.id,
        student_id=profile.student_id,
        learning_style=profile.learning_style,
        learning_style_confidence=profile.learning_style_confidence or 0.0,
        preferred_difficulty=profile.preferred_difficulty or "medium",
        study_session_length=profile.study_session_length or 25,
        preferred_study_time=profile.preferred_study_time or "evening",
        strong_subjects=_json_list(profile.strong_subjects),
        weak_subjects=_json_list(profile.weak_subjects),
        last_analyzed_at=profile.last_analyzed_at.isoformat() if profile.last_analyzed_at else None,
        ai_analysis_count=profile.ai_analysis_count or 0,
        recommendations_generated_at=(
            profile.recommendations_generated_at.isoformat()
            if profile.recommendations_generated_at
            else None
        ),
    )


def _mastery_to_response(m: SubjectMastery) -> SubjectMasteryResponse:
    return SubjectMasteryResponse(
        id=m.id,
        student_id=m.student_id,
        subject_code=m.subject_code,
        subject_name=m.subject_name,
        mastery_score=m.mastery_score or 0.0,
        mastery_level=m.mastery_level or "beginner",
        quiz_score_avg=m.quiz_score_avg or 0.0,
        quiz_attempts=m.quiz_attempts or 0,
        grade_avg=m.grade_avg or 0.0,
        last_quiz_date=m.last_quiz_date.isoformat() if m.last_quiz_date else None,
        trend=m.trend or "stable",
        recommended_next_topics=_json_list(m.recommended_next_topics),
    )


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _is_mastery_stale(masteries: list[SubjectMastery]) -> bool:
    """True if no mastery records exist or oldest updated_at is > 24 hours ago."""
    if not masteries:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    # updated_at may be naive (SQLite); compare naively when needed
    for m in masteries:
        if m.updated_at is None:
            return True
        updated = m.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated < cutoff:
            return True
    return False


# ────────────────────────────────────────────────────────────────────────────
# Student endpoints
# ────────────────────────────────────────────────────────────────────────────


@router.get("/profile", response_model=PersonalizationProfileResponse)
def get_profile(
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return the student's personalization profile (creates blank if absent)."""
    student = _get_student_for_user(db, current_user)
    profile = engine.get_or_create_profile(student.id, db)
    db.commit()
    return _profile_to_response(profile)


@router.put("/profile", response_model=PersonalizationProfileResponse)
def update_profile(
    data: PersonalizationProfileUpdate,
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Update student preferences (learning style, session length, difficulty, time)."""
    student = _get_student_for_user(db, current_user)
    profile = engine.get_or_create_profile(student.id, db)

    if data.learning_style is not None:
        # Validate
        try:
            LearningStyle(data.learning_style)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid learning_style value")
        profile.learning_style = data.learning_style

    if data.preferred_difficulty is not None:
        if data.preferred_difficulty not in ("easy", "medium", "hard", "adaptive"):
            raise HTTPException(status_code=400, detail="Invalid preferred_difficulty")
        profile.preferred_difficulty = data.preferred_difficulty

    if data.study_session_length is not None:
        if not (5 <= data.study_session_length <= 120):
            raise HTTPException(status_code=400, detail="study_session_length must be 5-120 minutes")
        profile.study_session_length = data.study_session_length

    if data.preferred_study_time is not None:
        if data.preferred_study_time not in ("morning", "afternoon", "evening"):
            raise HTTPException(status_code=400, detail="Invalid preferred_study_time")
        profile.preferred_study_time = data.preferred_study_time

    db.commit()
    db.refresh(profile)
    return _profile_to_response(profile)


@router.get("/mastery", response_model=list[SubjectMasteryResponse])
def get_mastery(
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return all subject mastery scores, recomputing if data is > 24 h stale."""
    student = _get_student_for_user(db, current_user)

    existing = (
        db.query(SubjectMastery)
        .filter(SubjectMastery.student_id == student.id)
        .all()
    )

    if _is_mastery_stale(existing):
        existing = engine.compute_mastery(student.id, db)
        db.commit()

    return [_mastery_to_response(m) for m in existing]


@router.post("/mastery/refresh", response_model=list[SubjectMasteryResponse])
def refresh_mastery(
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Force-recompute mastery scores."""
    student = _get_student_for_user(db, current_user)
    masteries = engine.compute_mastery(student.id, db)
    db.commit()
    return [_mastery_to_response(m) for m in masteries]


@router.get("/mastery/{subject_code}", response_model=SubjectMasteryResponse)
def get_subject_mastery(
    subject_code: str,
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return mastery for a single subject code."""
    student = _get_student_for_user(db, current_user)
    mastery = (
        db.query(SubjectMastery)
        .filter(
            SubjectMastery.student_id == student.id,
            SubjectMastery.subject_code == subject_code,
        )
        .first()
    )
    if not mastery:
        raise HTTPException(status_code=404, detail="No mastery data for this subject")
    return _mastery_to_response(mastery)


@router.get(
    "/difficulty/{subject_code}/{content_type}",
    response_model=AdaptiveDifficultyResponse,
)
def get_difficulty(
    subject_code: str,
    content_type: str,
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return the recommended difficulty for a student/subject/content_type."""
    if content_type not in ("study_guide", "quiz", "flashcard"):
        raise HTTPException(status_code=400, detail="Invalid content_type")

    student = _get_student_for_user(db, current_user)
    recommended = engine.recommend_difficulty(student.id, subject_code, content_type, db)

    record = (
        db.query(AdaptiveDifficulty)
        .filter(
            AdaptiveDifficulty.student_id == student.id,
            AdaptiveDifficulty.subject_code == subject_code,
            AdaptiveDifficulty.content_type == content_type,
        )
        .first()
    )

    current = record.current_difficulty if record else "medium"
    consecutive_correct = record.consecutive_correct if record else 0
    consecutive_incorrect = record.consecutive_incorrect if record else 0
    total_attempts = record.total_attempts if record else 0

    return AdaptiveDifficultyResponse(
        student_id=student.id,
        subject_code=subject_code,
        content_type=content_type,
        current_difficulty=current,
        recommended_difficulty=recommended,
        consecutive_correct=consecutive_correct,
        consecutive_incorrect=consecutive_incorrect,
        total_attempts=total_attempts,
    )


@router.post(
    "/difficulty/{subject_code}/{content_type}/feedback",
    response_model=AdaptiveDifficultyResponse,
)
def report_attempt(
    subject_code: str,
    content_type: str,
    body: AttemptFeedbackRequest,
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Report a quiz/flashcard attempt result to update adaptive difficulty."""
    if content_type not in ("study_guide", "quiz", "flashcard"):
        raise HTTPException(status_code=400, detail="Invalid content_type")

    student = _get_student_for_user(db, current_user)
    record = engine.update_difficulty_after_attempt(
        student.id, subject_code, content_type, body.passed, db
    )
    db.commit()
    db.refresh(record)

    recommended = engine.recommend_difficulty(student.id, subject_code, content_type, db)

    return AdaptiveDifficultyResponse(
        student_id=student.id,
        subject_code=subject_code,
        content_type=content_type,
        current_difficulty=record.current_difficulty,
        recommended_difficulty=recommended,
        consecutive_correct=record.consecutive_correct,
        consecutive_incorrect=record.consecutive_incorrect,
        total_attempts=record.total_attempts,
    )


@router.post("/analyze")
async def analyze_student(
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Run AI learning-style detection and generate study recommendations.

    Stores results on the PersonalizationProfile and returns combined payload.
    """
    student = _get_student_for_user(db, current_user)
    profile = engine.get_or_create_profile(student.id, db)

    # Detect learning style
    style, confidence = await engine.detect_learning_style(student.id, db)

    # Generate recommendations
    recommendations = await engine.generate_study_recommendations(student.id, db)

    # Persist
    profile.learning_style = style.value
    profile.learning_style_confidence = confidence
    profile.last_analyzed_at = datetime.now(timezone.utc)
    profile.ai_analysis_count = (profile.ai_analysis_count or 0) + 1
    profile.recommendations_json = json.dumps(recommendations)
    profile.recommendations_generated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)

    return {
        "profile": _profile_to_response(profile),
        "recommendations": recommendations,
    }


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    _flag=Depends(require_feature("ai_personalization")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return latest cached AI recommendations."""
    student = _get_student_for_user(db, current_user)
    profile = engine.get_or_create_profile(student.id, db)
    db.commit()

    if not profile.recommendations_json:
        raise HTTPException(
            status_code=404,
            detail="No recommendations yet. Run POST /personalization/analyze first.",
        )

    try:
        data = json.loads(profile.recommendations_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupted recommendations data")

    data["generated_at"] = (
        profile.recommendations_generated_at.isoformat()
        if profile.recommendations_generated_at
        else None
    )
    return data


# ────────────────────────────────────────────────────────────────────────────
# Parent / Admin endpoints
# ────────────────────────────────────────────────────────────────────────────


@router.get(
    "/children/{student_id}/mastery",
    response_model=list[SubjectMasteryResponse],
)
def get_child_mastery(
    student_id: int,
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Parent/Admin: view a child's subject mastery scores."""
    student = _verify_parent_child_access(db, current_user, student_id)

    existing = (
        db.query(SubjectMastery)
        .filter(SubjectMastery.student_id == student.id)
        .all()
    )

    if _is_mastery_stale(existing):
        existing = engine.compute_mastery(student.id, db)
        db.commit()

    return [_mastery_to_response(m) for m in existing]


@router.get(
    "/children/{student_id}/profile",
    response_model=PersonalizationProfileResponse,
)
def get_child_profile(
    student_id: int,
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Parent/Admin: view a child's personalization profile."""
    student = _verify_parent_child_access(db, current_user, student_id)
    profile = engine.get_or_create_profile(student.id, db)
    db.commit()
    return _profile_to_response(profile)
