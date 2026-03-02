"""Tutor Marketplace API routes (Phase 4).

Routes:
  GET    /api/tutors/                          — search/list tutors (auth required)
  GET    /api/tutors/profile/me                — get my tutor profile (teacher)
  GET    /api/tutors/bookings/mine             — list my booking requests (parent/student)
  POST   /api/tutors/profile                   — create my tutor profile (teacher)
  PATCH  /api/tutors/profile                   — update my tutor profile (teacher)
  GET    /api/tutors/{id}                      — get tutor profile by id
  GET    /api/tutors/{id}/bookings             — get bookings for tutor (teacher sees own)
  POST   /api/tutors/{id}/book                 — request a booking (parent/student)
  PATCH  /api/tutors/{id}/verify               — verify tutor (admin only)
  PATCH  /api/tutors/bookings/{id}/respond     — accept/decline booking (teacher)
  PATCH  /api/tutors/bookings/{id}/review      — leave rating/review after session
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.tutor_profile import TutorProfile
from app.models.tutor_booking import TutorBooking
from app.models.student import Student
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tutors", tags=["Tutors"])

VALID_BOOKING_STATUSES = {"pending", "accepted", "declined", "completed", "cancelled"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TutorProfileCreate(BaseModel):
    bio: str
    headline: str
    subjects: list[str]
    grade_levels: list[str]
    languages: list[str] = ["English"]
    hourly_rate_cad: float
    session_duration_minutes: int = 60
    available_days: list[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    available_hours_start: str = "16:00"
    available_hours_end: str = "20:00"
    timezone: str = "America/Toronto"
    online_only: bool = False
    location_city: Optional[str] = None
    years_experience: Optional[int] = None
    certifications: Optional[list[str]] = None
    school_affiliation: Optional[str] = None
    is_accepting_students: bool = True

    @validator("subjects")
    def subjects_not_empty(cls, v):
        if not v:
            raise ValueError("subjects must not be empty")
        return v

    @validator("hourly_rate_cad")
    def rate_positive(cls, v):
        if v <= 0:
            raise ValueError("hourly_rate_cad must be positive")
        return v


class TutorProfileUpdate(BaseModel):
    bio: Optional[str] = None
    headline: Optional[str] = None
    subjects: Optional[list[str]] = None
    grade_levels: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    hourly_rate_cad: Optional[float] = None
    session_duration_minutes: Optional[int] = None
    available_days: Optional[list[str]] = None
    available_hours_start: Optional[str] = None
    available_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    online_only: Optional[bool] = None
    location_city: Optional[str] = None
    years_experience: Optional[int] = None
    certifications: Optional[list[str]] = None
    school_affiliation: Optional[str] = None
    is_active: Optional[bool] = None
    is_accepting_students: Optional[bool] = None


class BookingCreate(BaseModel):
    subject: str
    message: Optional[str] = None
    proposed_date: Optional[str] = None   # ISO datetime string
    duration_minutes: int = 60
    student_id: Optional[int] = None      # required if requester is a parent


class BookingRespond(BaseModel):
    status: str   # "accepted" | "declined"
    tutor_response: Optional[str] = None

    @validator("status")
    def valid_status(cls, v):
        if v not in {"accepted", "declined"}:
            raise ValueError("status must be 'accepted' or 'declined'")
        return v


class BookingReview(BaseModel):
    rating: int
    review_text: Optional[str] = None

    @validator("rating")
    def rating_range(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("rating must be between 1 and 5")
        return v


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_profile(profile: TutorProfile) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "tutor_name": profile.user.full_name if profile.user else None,
        "bio": profile.bio,
        "headline": profile.headline,
        "subjects": json.loads(profile.subjects) if profile.subjects else [],
        "grade_levels": json.loads(profile.grade_levels) if profile.grade_levels else [],
        "languages": json.loads(profile.languages) if profile.languages else ["English"],
        "hourly_rate_cad": profile.hourly_rate_cad,
        "session_duration_minutes": profile.session_duration_minutes or 60,
        "available_days": json.loads(profile.available_days) if profile.available_days else [],
        "available_hours_start": profile.available_hours_start or "16:00",
        "available_hours_end": profile.available_hours_end or "20:00",
        "timezone": profile.timezone or "America/Toronto",
        "online_only": profile.online_only or False,
        "location_city": profile.location_city,
        "is_verified": profile.is_verified or False,
        "years_experience": profile.years_experience,
        "certifications": json.loads(profile.certifications) if profile.certifications else [],
        "school_affiliation": profile.school_affiliation,
        "total_sessions": profile.total_sessions or 0,
        "avg_rating": profile.avg_rating,
        "review_count": profile.review_count or 0,
        "is_active": profile.is_active,
        "is_accepting_students": profile.is_accepting_students,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def _serialize_booking(booking: TutorBooking) -> dict:
    return {
        "id": booking.id,
        "tutor_id": booking.tutor_id,
        "student_id": booking.student_id,
        "requested_by_user_id": booking.requested_by_user_id,
        "subject": booking.subject,
        "message": booking.message,
        "proposed_date": booking.proposed_date.isoformat() if booking.proposed_date else None,
        "duration_minutes": booking.duration_minutes or 60,
        "status": booking.status or "pending",
        "tutor_response": booking.tutor_response,
        "responded_at": booking.responded_at.isoformat() if booking.responded_at else None,
        "rating": booking.rating,
        "review_text": booking.review_text,
        "reviewed_at": booking.reviewed_at.isoformat() if booking.reviewed_at else None,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
        # Denormalized for display
        "tutor_name": booking.tutor.user.full_name if booking.tutor and booking.tutor.user else None,
        "student_name": booking.student.user.full_name if booking.student and booking.student.user else None,
        "requester_name": booking.requested_by.full_name if booking.requested_by else None,
    }


def _create_notification(db: Session, user_id: int, title: str, content: str, link: str | None = None):
    """Create an in-app notification for a user."""
    try:
        notification = Notification(
            user_id=user_id,
            type=NotificationType.SYSTEM,
            title=title,
            content=content,
            link=link,
            read=False,
        )
        db.add(notification)
        # Caller is responsible for commit
    except Exception as exc:
        logger.warning(f"Failed to create notification for user {user_id}: {exc}")


# ---------------------------------------------------------------------------
# Routes — fixed paths first to avoid conflicts with {id} routes
# ---------------------------------------------------------------------------

@router.get("/profile/me")
def get_my_tutor_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Get the current teacher's own tutor profile."""
    profile = db.query(TutorProfile).filter(TutorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Tutor profile not found. Create one first.")
    return _serialize_profile(profile)


@router.get("/bookings/mine")
def get_my_bookings(
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List booking requests made by the current user (parent/student)."""
    q = (
        db.query(TutorBooking)
        .filter(TutorBooking.requested_by_user_id == current_user.id)
    )
    if status:
        q = q.filter(TutorBooking.status == status)
    bookings = q.order_by(TutorBooking.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize_booking(b) for b in bookings]


@router.post("/profile", status_code=201)
def create_tutor_profile(
    payload: TutorProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Create a tutor marketplace profile (teachers only). is_verified defaults to False."""
    existing = db.query(TutorProfile).filter(TutorProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Tutor profile already exists. Use PATCH /api/tutors/profile to update.",
        )

    profile = TutorProfile(
        user_id=current_user.id,
        bio=payload.bio,
        headline=payload.headline,
        subjects=json.dumps(payload.subjects),
        grade_levels=json.dumps(payload.grade_levels),
        languages=json.dumps(payload.languages),
        hourly_rate_cad=payload.hourly_rate_cad,
        session_duration_minutes=payload.session_duration_minutes,
        available_days=json.dumps(payload.available_days),
        available_hours_start=payload.available_hours_start,
        available_hours_end=payload.available_hours_end,
        timezone=payload.timezone,
        online_only=payload.online_only,
        location_city=payload.location_city,
        is_verified=False,   # admin sets this
        years_experience=payload.years_experience,
        certifications=json.dumps(payload.certifications) if payload.certifications else None,
        school_affiliation=payload.school_affiliation,
        is_accepting_students=payload.is_accepting_students,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    logger.info(f"TutorProfile created: id={profile.id} user_id={current_user.id}")
    return _serialize_profile(profile)


@router.patch("/profile")
def update_tutor_profile(
    payload: TutorProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Update the current teacher's tutor profile."""
    profile = db.query(TutorProfile).filter(TutorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Tutor profile not found. Create one first.")

    update_data = payload.model_dump(exclude_unset=True)

    # JSON-serialize list fields
    for list_field in ("subjects", "grade_levels", "languages", "available_days", "certifications"):
        if list_field in update_data:
            val = update_data.pop(list_field)
            update_data[list_field] = json.dumps(val) if val is not None else None

    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)


@router.patch("/bookings/{booking_id}/respond")
def respond_to_booking(
    booking_id: int,
    payload: BookingRespond,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Accept or decline a booking request (tutor only)."""
    booking = db.query(TutorBooking).filter(TutorBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Verify that this tutor owns the booking
    profile = db.query(TutorProfile).filter(
        TutorProfile.id == booking.tutor_id,
        TutorProfile.user_id == current_user.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=403, detail="Not authorized to respond to this booking")

    if booking.status not in ("pending",):
        raise HTTPException(status_code=400, detail=f"Cannot respond to booking in status '{booking.status}'")

    booking.status = payload.status
    booking.tutor_response = payload.tutor_response
    booking.responded_at = datetime.now(timezone.utc)

    # Notify requester
    status_label = "accepted" if payload.status == "accepted" else "declined"
    _create_notification(
        db,
        user_id=booking.requested_by_user_id,
        title=f"Tutor booking {status_label}",
        content=f"Your tutoring request for {booking.subject} has been {status_label}.",
        link=f"/tutors",
    )

    db.commit()
    db.refresh(booking)
    return _serialize_booking(booking)


@router.patch("/bookings/{booking_id}/review")
def review_booking(
    booking_id: int,
    payload: BookingReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leave a rating/review after a completed session."""
    booking = db.query(TutorBooking).filter(TutorBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only the requester can leave a review
    if booking.requested_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to review this booking")

    if booking.status != "completed":
        raise HTTPException(status_code=400, detail="Can only review completed bookings")

    if booking.rating is not None:
        raise HTTPException(status_code=400, detail="This booking has already been reviewed")

    booking.rating = payload.rating
    booking.review_text = payload.review_text
    booking.reviewed_at = datetime.now(timezone.utc)

    # Update tutor avg_rating and review_count (denormalized stats)
    tutor = db.query(TutorProfile).filter(TutorProfile.id == booking.tutor_id).first()
    if tutor:
        current_count = tutor.review_count or 0
        current_avg = tutor.avg_rating or 0.0
        new_count = current_count + 1
        new_avg = ((current_avg * current_count) + payload.rating) / new_count
        tutor.review_count = new_count
        tutor.avg_rating = round(new_avg, 2)

    db.commit()
    db.refresh(booking)
    return _serialize_booking(booking)


# ---------------------------------------------------------------------------
# Routes — parameterized paths
# ---------------------------------------------------------------------------

@router.get("/")
def search_tutors(
    subject: Optional[str] = Query(None, description="Filter by subject (case-insensitive LIKE)"),
    grade_level: Optional[str] = Query(None, description="Filter by grade level"),
    max_rate: Optional[float] = Query(None, description="Max hourly rate in CAD"),
    online_only: Optional[bool] = Query(None),
    min_rating: Optional[float] = Query(None, description="Minimum avg_rating"),
    language: Optional[str] = Query(None, description="Filter by language"),
    verified: Optional[bool] = Query(None, description="Filter by is_verified"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search and list active tutor profiles with optional filters."""
    q = db.query(TutorProfile).filter(
        TutorProfile.is_active == True  # noqa: E712
    )

    if subject:
        q = q.filter(TutorProfile.subjects.ilike(f"%{subject}%"))
    if grade_level:
        q = q.filter(TutorProfile.grade_levels.ilike(f"%{grade_level}%"))
    if max_rate is not None:
        q = q.filter(TutorProfile.hourly_rate_cad <= max_rate)
    if online_only is not None:
        q = q.filter(TutorProfile.online_only == online_only)
    if min_rating is not None:
        q = q.filter(TutorProfile.avg_rating >= min_rating)
    if language:
        q = q.filter(TutorProfile.languages.ilike(f"%{language}%"))
    if verified is not None:
        q = q.filter(TutorProfile.is_verified == verified)

    profiles = q.order_by(
        TutorProfile.is_verified.desc(),
        TutorProfile.avg_rating.desc(),
        TutorProfile.created_at.desc(),
    ).offset(skip).limit(limit).all()

    return [_serialize_profile(p) for p in profiles]


@router.get("/{tutor_id}")
def get_tutor(
    tutor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific tutor profile by ID."""
    profile = db.query(TutorProfile).filter(TutorProfile.id == tutor_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Tutor not found")
    return _serialize_profile(profile)


@router.get("/{tutor_id}/bookings")
def get_tutor_bookings(
    tutor_id: int,
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Get bookings for a specific tutor (teacher sees only their own)."""
    profile = db.query(TutorProfile).filter(TutorProfile.id == tutor_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Tutor not found")

    # Non-admin teachers can only see their own bookings
    if not current_user.has_role(UserRole.ADMIN) and profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view these bookings")

    q = db.query(TutorBooking).filter(TutorBooking.tutor_id == tutor_id)
    if status:
        q = q.filter(TutorBooking.status == status)

    bookings = q.order_by(TutorBooking.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize_booking(b) for b in bookings]


@router.post("/{tutor_id}/book", status_code=201)
def book_tutor(
    tutor_id: int,
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request a tutoring session with a tutor (parent or student)."""
    # Only parents and students can book
    if not (current_user.has_role(UserRole.PARENT) or current_user.has_role(UserRole.STUDENT)):
        raise HTTPException(status_code=403, detail="Only parents and students can book tutors")

    tutor = db.query(TutorProfile).filter(TutorProfile.id == tutor_id).first()
    if not tutor:
        raise HTTPException(status_code=404, detail="Tutor not found")
    if not tutor.is_active:
        raise HTTPException(status_code=400, detail="Tutor is not currently active")
    if not tutor.is_accepting_students:
        raise HTTPException(status_code=400, detail="Tutor is not currently accepting new students")

    # Resolve student_id
    student_id = payload.student_id
    if student_id is None:
        # For student users: find their own student record
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(
                status_code=400,
                detail="Could not determine student. Provide student_id.",
            )
        student_id = student.id
    else:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

    proposed_date = None
    if payload.proposed_date:
        try:
            proposed_date = datetime.fromisoformat(payload.proposed_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid proposed_date format. Use ISO datetime.")

    booking = TutorBooking(
        tutor_id=tutor_id,
        student_id=student_id,
        requested_by_user_id=current_user.id,
        subject=payload.subject,
        message=payload.message,
        proposed_date=proposed_date,
        duration_minutes=payload.duration_minutes,
        status="pending",
    )
    db.add(booking)

    # Notify tutor
    _create_notification(
        db,
        user_id=tutor.user_id,
        title="New tutoring request",
        content=f"You have a new tutoring request for {payload.subject} from {current_user.full_name}.",
        link=f"/tutors/dashboard",
    )

    db.commit()
    db.refresh(booking)
    logger.info(f"TutorBooking created: id={booking.id} tutor_id={tutor_id} student_id={student_id}")
    return _serialize_booking(booking)


@router.patch("/{tutor_id}/verify")
def verify_tutor(
    tutor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Set is_verified=True for a tutor profile (admin only)."""
    profile = db.query(TutorProfile).filter(TutorProfile.id == tutor_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Tutor not found")

    profile.is_verified = True
    db.commit()
    db.refresh(profile)

    # Notify tutor
    _create_notification(
        db,
        user_id=profile.user_id,
        title="Your tutor profile is now verified",
        content="Congratulations! Your tutor profile has been verified by an admin.",
        link="/tutors/dashboard",
    )
    db.commit()

    logger.info(f"TutorProfile {tutor_id} verified by admin user {current_user.id}")
    return _serialize_profile(profile)
