"""Tutor Matching API routes (Phase 4).

Routes:
  GET  /api/tutor-matching/recommendations              — top matches for current student
  POST /api/tutor-matching/score/{tutor_id}             — score a specific tutor
  POST /api/tutor-matching/preferences                  — save matching preferences
  GET  /api/tutor-matching/compatibility/{tutor_id}     — detailed compatibility report
  GET  /api/tutor-matching/children/{student_id}/recommendations  — parent view of child
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.personalization import PersonalizationProfile
from app.models.student import Student, parent_students
from app.models.tutor_match_preference import TutorMatchPreference
from app.models.tutor_profile import TutorProfile
from app.models.user import User, UserRole
from app.services.tutor_matching import TutorMatchingEngine, TutorMatchScore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tutor-matching", tags=["Tutor Matching"])

_engine = TutorMatchingEngine()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TutorMatchPreferenceUpdate(BaseModel):
    max_hourly_rate_cad: Optional[float] = None
    preferred_subjects: Optional[list[str]] = None
    preferred_grade_levels: Optional[list[str]] = None
    preferred_availability: Optional[list[str]] = None
    min_rating: Optional[float] = None
    prefer_verified_only: Optional[bool] = None


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_match(match: TutorMatchScore, ai_explanation: str | None = None) -> dict:
    tutor = match.tutor
    return {
        "tutor_id": tutor.id,
        "tutor": {
            "id": tutor.id,
            "tutor_name": tutor.user.full_name if tutor.user else None,
            "headline": tutor.headline,
            "bio": tutor.bio,
            "subjects": json.loads(tutor.subjects) if tutor.subjects else [],
            "grade_levels": json.loads(tutor.grade_levels) if tutor.grade_levels else [],
            "hourly_rate_cad": tutor.hourly_rate_cad,
            "avg_rating": tutor.avg_rating,
            "review_count": tutor.review_count or 0,
            "is_verified": tutor.is_verified or False,
            "is_accepting_students": tutor.is_accepting_students,
            "available_days": json.loads(tutor.available_days) if tutor.available_days else [],
            "available_hours_start": tutor.available_hours_start,
            "available_hours_end": tutor.available_hours_end,
            "online_only": tutor.online_only,
            "location_city": tutor.location_city,
            "years_experience": tutor.years_experience,
        },
        "score": match.score,
        "breakdown": {
            "subject_match": match.subject_match,
            "subject_match_max": 35,
            "grade_match": match.grade_match,
            "grade_match_max": 20,
            "rating_score": match.rating_score,
            "rating_score_max": 20,
            "style_match": match.style_match,
            "style_match_max": 15,
            "price_score": match.price_score,
            "price_score_max": 10,
        },
        "covered_weak_subjects": match.covered_weak_subjects,
        "total_weak_subjects": match.total_weak_subjects,
        "explanation": ai_explanation or match.explanation,
        "has_ai_explanation": ai_explanation is not None,
    }


def _get_student_id_for_current_user(current_user: User, db: Session) -> int:
    """Resolve the student ID for a logged-in student user."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=400,
            detail="No student profile found for current user. "
                   "If you are a parent, use /children/{student_id}/recommendations.",
        )
    return student.id


def _load_preferences(user_id: int, db: Session) -> dict:
    """Load the user's saved match preferences as a plain dict."""
    pref = db.query(TutorMatchPreference).filter(
        TutorMatchPreference.user_id == user_id
    ).first()
    if not pref:
        return {}
    return {
        "max_hourly_rate_cad": pref.max_hourly_rate_cad,
        "min_rating": pref.min_rating,
        "prefer_verified_only": pref.prefer_verified_only,
        "preferred_subjects": json.loads(pref.preferred_subjects) if pref.preferred_subjects else [],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/recommendations")
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50),
    include_ai: bool = Query(False, description="Generate AI explanation for each match (slower)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN)),
):
    """Get top AI-matched tutors for the current student."""
    # Parents can call this only if they are also a student — otherwise use /children/{id}
    student_id = _get_student_id_for_current_user(current_user, db)
    prefs = _load_preferences(current_user.id, db)

    matches = _engine.get_top_matches(student_id, db, limit=limit, preferences=prefs)

    result = []
    for match in matches:
        ai_explanation = None
        if include_ai:
            try:
                student_profile = (
                    db.query(PersonalizationProfile)
                    .filter(PersonalizationProfile.student_id == student_id)
                    .first()
                )
                ai_explanation = await _engine.generate_ai_explanation(match, student_profile)
            except Exception as exc:
                logger.warning("AI explanation failed for tutor %d: %s", match.tutor_id, exc)
        result.append(_serialize_match(match, ai_explanation))

    return {
        "student_id": student_id,
        "total_matches": len(result),
        "matches": result,
    }


@router.post("/score/{tutor_id}")
async def score_tutor(
    tutor_id: int,
    include_ai: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN)),
):
    """Score a specific tutor against the current student."""
    tutor = db.query(TutorProfile).filter(TutorProfile.id == tutor_id).first()
    if not tutor:
        raise HTTPException(status_code=404, detail="Tutor not found")

    student_id = _get_student_id_for_current_user(current_user, db)
    prefs = _load_preferences(current_user.id, db)

    match = _engine.compute_match_score(tutor, student_id, db, prefs)

    ai_explanation = None
    if include_ai:
        try:
            student_profile = (
                db.query(PersonalizationProfile)
                .filter(PersonalizationProfile.student_id == student_id)
                .first()
            )
            ai_explanation = await _engine.generate_ai_explanation(match, student_profile)
        except Exception as exc:
            logger.warning("AI explanation failed: %s", exc)

    return _serialize_match(match, ai_explanation)


@router.post("/preferences")
def update_preferences(
    payload: TutorMatchPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save the current user's tutor matching preferences."""
    pref = db.query(TutorMatchPreference).filter(
        TutorMatchPreference.user_id == current_user.id
    ).first()

    if not pref:
        pref = TutorMatchPreference(user_id=current_user.id)
        db.add(pref)

    update_data = payload.model_dump(exclude_unset=True)

    # JSON-encode list fields
    for list_field in ("preferred_subjects", "preferred_grade_levels", "preferred_availability"):
        if list_field in update_data:
            update_data[list_field] = json.dumps(update_data[list_field])

    for field_name, value in update_data.items():
        setattr(pref, field_name, value)

    db.commit()
    db.refresh(pref)

    return {
        "message": "Preferences saved",
        "preferences": {
            "max_hourly_rate_cad": pref.max_hourly_rate_cad,
            "preferred_subjects": json.loads(pref.preferred_subjects) if pref.preferred_subjects else [],
            "preferred_grade_levels": json.loads(pref.preferred_grade_levels) if pref.preferred_grade_levels else [],
            "preferred_availability": json.loads(pref.preferred_availability) if pref.preferred_availability else [],
            "min_rating": pref.min_rating,
            "prefer_verified_only": pref.prefer_verified_only,
        },
    }


@router.get("/preferences")
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's tutor matching preferences."""
    pref = db.query(TutorMatchPreference).filter(
        TutorMatchPreference.user_id == current_user.id
    ).first()

    if not pref:
        return {
            "max_hourly_rate_cad": None,
            "preferred_subjects": [],
            "preferred_grade_levels": [],
            "preferred_availability": [],
            "min_rating": 3.0,
            "prefer_verified_only": False,
        }

    return {
        "max_hourly_rate_cad": pref.max_hourly_rate_cad,
        "preferred_subjects": json.loads(pref.preferred_subjects) if pref.preferred_subjects else [],
        "preferred_grade_levels": json.loads(pref.preferred_grade_levels) if pref.preferred_grade_levels else [],
        "preferred_availability": json.loads(pref.preferred_availability) if pref.preferred_availability else [],
        "min_rating": pref.min_rating,
        "prefer_verified_only": pref.prefer_verified_only,
    }


@router.get("/compatibility/{tutor_id}")
async def get_compatibility(
    tutor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN)),
):
    """Detailed compatibility analysis between the current student and a specific tutor."""
    tutor = db.query(TutorProfile).filter(TutorProfile.id == tutor_id).first()
    if not tutor:
        raise HTTPException(status_code=404, detail="Tutor not found")

    student_id = _get_student_id_for_current_user(current_user, db)
    prefs = _load_preferences(current_user.id, db)

    match = _engine.compute_match_score(tutor, student_id, db, prefs)

    student_profile = (
        db.query(PersonalizationProfile)
        .filter(PersonalizationProfile.student_id == student_id)
        .first()
    )

    ai_explanation = None
    try:
        ai_explanation = await _engine.generate_ai_explanation(match, student_profile)
    except Exception as exc:
        logger.warning("AI explanation for compatibility failed: %s", exc)

    result = _serialize_match(match, ai_explanation)
    result["student_learning_style"] = student_profile.learning_style if student_profile else None
    result["student_grade"] = None

    student = db.query(Student).filter(Student.id == student_id).first()
    if student:
        result["student_grade"] = student.grade_level

    return result


@router.get("/children/{student_id}/recommendations")
async def get_child_recommendations(
    student_id: int,
    limit: int = Query(10, ge=1, le=50),
    include_ai: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """Get AI-matched tutor recommendations for a parent's child."""
    # Verify the student exists
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Verify the parent owns this child (skip check for admin)
    if not current_user.has_role(UserRole.ADMIN):
        link = db.execute(
            parent_students.select().where(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student_id,
            )
        ).first()
        if not link:
            raise HTTPException(
                status_code=403,
                detail="You are not linked to this student",
            )

    prefs = _load_preferences(current_user.id, db)
    matches = _engine.get_top_matches(student_id, db, limit=limit, preferences=prefs)

    result = []
    for match in matches:
        ai_explanation = None
        if include_ai:
            try:
                student_profile = (
                    db.query(PersonalizationProfile)
                    .filter(PersonalizationProfile.student_id == student_id)
                    .first()
                )
                ai_explanation = await _engine.generate_ai_explanation(match, student_profile)
            except Exception as exc:
                logger.warning("AI explanation failed for child tutor match: %s", exc)
        result.append(_serialize_match(match, ai_explanation))

    return {
        "student_id": student_id,
        "student_name": student.user.full_name if student.user else None,
        "total_matches": len(result),
        "matches": result,
    }
