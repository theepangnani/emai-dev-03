import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.models.course import Course, student_courses
from app.schemas.user import UserResponse, SwitchRoleRequest
from app.schemas.consent import ConsentPreferences, ConsentPreferencesResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


def _user_response(user: User) -> UserResponse:
    """Build a UserResponse with the roles list populated."""
    return UserResponse(
        id=user.id,
        email=user.email or "",
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        roles=[r.value for r in user.get_roles_list()],
        is_active=user.is_active,
        google_connected=bool(user.google_access_token),
        needs_onboarding=user.needs_onboarding or False,
        email_verified=user.email_verified or False,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_current_user_info(request: Request, current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@router.post("/me/switch-role", response_model=UserResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def switch_role(
    request: Request,
    data: SwitchRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Switch the user's active dashboard role. The requested role must be in their roles list."""
    try:
        target_role = UserRole(data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {data.role}",
        )

    if not current_user.has_role(target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have the '{data.role}' role",
        )

    # Defensive: ensure profile exists before switching
    from app.services.user_service import ensure_profile_records
    ensure_profile_records(db, current_user)

    current_user.role = target_role
    db.commit()
    db.refresh(current_user)
    return _user_response(current_user)


@router.put("/me/consent-preferences", response_model=ConsentPreferencesResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_consent_preferences(
    request: Request,
    preferences: ConsentPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store the user's cookie / data-processing consent preferences (#797)."""
    prefs_dict = {
        "essential": True,  # Always on
        "analytics": preferences.analytics,
        "ai_processing": preferences.ai_processing,
    }
    current_user.consent_preferences = json.dumps(prefs_dict)
    current_user.consent_given_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return ConsentPreferencesResponse(
        essential=True,
        analytics=preferences.analytics,
        ai_processing=preferences.ai_processing,
        consent_given_at=current_user.consent_given_at,
    )


@router.get("/me/consent-preferences", response_model=ConsentPreferencesResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_consent_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Retrieve the user's current consent preferences (#797)."""
    if current_user.consent_preferences:
        try:
            prefs = json.loads(current_user.consent_preferences)
        except (json.JSONDecodeError, TypeError):
            prefs = {"essential": True, "analytics": False, "ai_processing": False}
    else:
        prefs = {"essential": True, "analytics": False, "ai_processing": False}
    return ConsentPreferencesResponse(
        essential=prefs.get("essential", True),
        analytics=prefs.get("analytics", False),
        ai_processing=prefs.get("ai_processing", False),
        consent_given_at=current_user.consent_given_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a user profile. Access: own profile, admin (all), parent (linked children),
    teacher (students in their courses)."""
    # Own profile — always allowed
    if user_id == current_user.id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return _user_response(user)

    # Admin sees all
    if current_user.has_role(UserRole.ADMIN):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return _user_response(user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Parent can see linked children's profiles
    if current_user.has_role(UserRole.PARENT):
        student = db.query(Student).filter(Student.user_id == user_id).first()
        if student:
            link = db.query(parent_students).filter(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student.id,
            ).first()
            if link:
                return _user_response(user)

    # Teacher can see students enrolled in their courses
    if current_user.has_role(UserRole.TEACHER):
        student = db.query(Student).filter(Student.user_id == user_id).first()
        if student:
            teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
            if teacher:
                course_ids = [
                    r[0] for r in db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
                ]
                if course_ids:
                    enrolled = db.query(student_courses).filter(
                        student_courses.c.student_id == student.id,
                        student_courses.c.course_id.in_(course_ids),
                    ).first()
                    if enrolled:
                        return _user_response(user)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
