from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import insert

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.teacher import Teacher, TeacherType
from app.models.student import Student, parent_students, RelationshipType
from app.models.invite import Invite, InviteType
from app.schemas.user import UserCreate, UserResponse, Token, ForgotPasswordRequest, ResetPasswordRequest
from app.schemas.invite import AcceptInviteRequest
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_refresh_token, validate_password_strength, create_password_reset_token, decode_password_reset_token, UNUSABLE_PASSWORD_HASH
from app.api.deps import get_current_user, oauth2_scheme
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, add_inspiration_to_email
from app.core.config import settings
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


_ALLOWED_REGISTRATION_ROLES = {UserRole.PARENT, UserRole.STUDENT, UserRole.TEACHER}


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Block admin self-registration
    if user_data.role not in _ALLOWED_REGISTRATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role cannot be self-registered",
        )

    # Validate password strength
    pw_error = validate_password_strength(user_data.password)
    if pw_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_error)

    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Resolve Google tokens from server-side store (not from client)
    google_access_token = None
    google_refresh_token = None
    if user_data.google_id:
        from app.api.routes.google_classroom import _pending_google_tokens, _PENDING_TTL
        import time as _time
        pending = _pending_google_tokens.pop(user_data.google_id, None)
        if pending and (_time.time() - pending["created_at"]) < _PENDING_TTL:
            google_access_token = pending["access_token"]
            google_refresh_token = pending.get("refresh_token")

    # Create new user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        roles=",".join(r.value for r in user_data.roles),
        google_id=user_data.google_id,
        google_access_token=google_access_token,
        google_refresh_token=google_refresh_token,
    )
    db.add(user)
    db.flush()

    # Create all profile records for selected roles
    from app.services.user_service import ensure_profile_records
    ensure_profile_records(db, user)

    # Set teacher_type if teacher role and type provided
    if UserRole.TEACHER in user_data.roles and user_data.teacher_type:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            teacher.teacher_type = TeacherType(user_data.teacher_type)

    log_action(db, user_id=user.id, action="create", resource_type="user", resource_id=user.id,
               details={"role": user_data.role, "email": user_data.email},
               ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email or "",
        full_name=user.full_name,
        role=user.role,
        roles=[r.value for r in user.get_roles_list()],
        is_active=user.is_active,
        google_connected=bool(user.google_access_token),
        created_at=user.created_at,
    )


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        log_action(db, user_id=None, action="login_failed", resource_type="user",
                   details={"email": form_data.username}, ip_address=ip)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    log_action(db, user_id=user.id, action="login", resource_type="user",
               resource_id=user.id, ip_address=ip)
    db.commit()
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current access token so it can no longer be used."""
    from jose import jwt as _jwt
    from app.models.token_blacklist import TokenBlacklist

    try:
        payload = _jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            blacklist_entry = TokenBlacklist(
                jti=jti,
                user_id=current_user.id,
                expires_at=expires_at,
                reason="logout",
            )
            db.add(blacklist_entry)
            log_action(db, user_id=current_user.id, action="logout", resource_type="user",
                       resource_id=current_user.id, ip_address=request.client.host if request.client else None)
            db.commit()
    except Exception:
        pass  # Best-effort; token is short-lived anyway

    return {"message": "Logged out successfully"}


@router.post("/accept-invite", response_model=Token)
def accept_invite(data: AcceptInviteRequest, request: Request, db: Session = Depends(get_db)):
    """Accept an invite and create a new user account."""
    # Validate token
    invite = db.query(Invite).filter(Invite.token == data.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")

    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="This invite has already been accepted")

    # Compare as naive UTC — SQLite returns naive, PostgreSQL returns aware
    if invite.expires_at.replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="This invite has expired")

    # Validate password strength
    pw_error = validate_password_strength(data.password)
    if pw_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_error)

    # Check if email already registered
    existing_user = db.query(User).filter(User.email == invite.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Determine role from invite type
    if invite.invite_type == InviteType.STUDENT:
        role = UserRole.STUDENT
    elif invite.invite_type == InviteType.PARENT:
        role = UserRole.PARENT
    else:
        role = UserRole.TEACHER

    # Create user
    user = User(
        email=invite.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=role,
        roles=role.value,
    )
    db.add(user)
    db.flush()

    # Create Teacher or Student record
    if role == UserRole.TEACHER:
        teacher_type_value = None
        metadata = invite.metadata_json or {}
        if metadata.get("teacher_type"):
            teacher_type_value = TeacherType(metadata["teacher_type"])

        # Check if a shadow teacher exists with this email — claim it
        shadow = db.query(Teacher).filter(
            Teacher.google_email == invite.email,
            Teacher.is_shadow == True,
        ).first()
        if shadow:
            shadow.user_id = user.id
            shadow.is_shadow = False
            if teacher_type_value:
                shadow.teacher_type = teacher_type_value
            teacher = shadow
        else:
            teacher = Teacher(user_id=user.id, teacher_type=teacher_type_value)
            db.add(teacher)
        db.flush()
    elif role == UserRole.STUDENT:
        student = Student(user_id=user.id)
        db.add(student)
        db.flush()

        # If invited by a parent, auto-link via parent_students
        inviter = db.query(User).filter(User.id == invite.invited_by_user_id).first()
        if inviter and inviter.role == UserRole.PARENT:
            metadata = invite.metadata_json or {}
            rel_type_str = metadata.get("relationship_type", "guardian")
            rel_type = RelationshipType(rel_type_str)
            db.execute(
                insert(parent_students).values(
                    parent_id=inviter.id,
                    student_id=student.id,
                    relationship_type=rel_type,
                )
            )

    elif role == UserRole.PARENT:
        # Auto-link parent to student if student_id is in metadata
        metadata = invite.metadata_json or {}
        student_id = metadata.get("student_id")
        if student_id:
            student = db.query(Student).filter(Student.id == student_id).first()
            if student:
                db.execute(
                    insert(parent_students).values(
                        parent_id=user.id,
                        student_id=student.id,
                        relationship_type=RelationshipType.GUARDIAN,
                    )
                )

    # Auto-enroll/assign based on course_id in invite metadata
    metadata = invite.metadata_json or {}
    course_id = metadata.get("course_id")
    if course_id:
        from app.models.course import Course, student_courses as _sc
        _course = db.query(Course).filter(Course.id == course_id).first()
        if _course:
            if role == UserRole.STUDENT:
                # Auto-enroll student in the course
                db.execute(insert(_sc).values(student_id=student.id, course_id=_course.id))
            elif role == UserRole.TEACHER:
                # Auto-assign teacher to course if still unassigned
                if _course.teacher_id is None:
                    _course.teacher_id = teacher.id

    # Mark invite as accepted
    invite.accepted_at = datetime.now(timezone.utc)

    # Backfill teacher_user_id on student_teachers rows for this teacher email
    if role == UserRole.TEACHER:
        from app.models.student import student_teachers
        from sqlalchemy import update
        db.execute(
            update(student_teachers)
            .where(
                student_teachers.c.teacher_email == invite.email,
                student_teachers.c.teacher_user_id.is_(None),
            )
            .values(teacher_user_id=user.id)
        )

    log_action(db, user_id=user.id, action="create", resource_type="user", resource_id=user.id,
               details={"via": "invite", "invite_type": invite.invite_type.value, "email": invite.email},
               ip_address=request.client.host if request.client else None)
    db.commit()

    # Return JWT so the user is logged in immediately
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    return Token(access_token=access_token, refresh_token=refresh_token)


from pydantic import BaseModel as _BaseModel


class _RefreshRequest(_BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
def refresh_access_token(request: Request, body: _RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    payload = decode_refresh_token(body.refresh_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    new_access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=new_access_token)


import os

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


def _load_template(name: str) -> str:
    path = os.path.join(_TEMPLATE_DIR, name)
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _render(template: str, **kwargs: str) -> str:
    for k, v in kwargs.items():
        template = template.replace("{{" + k + "}}", v)
    return template


@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Send a password reset email. Always returns 200 to avoid user enumeration."""
    user = db.query(User).filter(User.email == body.email).first()

    if user and user.hashed_password and user.hashed_password != UNUSABLE_PASSWORD_HASH:
        token = create_password_reset_token(user.email)
        reset_url = f"{settings.frontend_url}/reset-password?token={token}"
        template = _load_template("password_reset.html")
        if template:
            html = _render(template, user_name=user.full_name or "there", reset_url=reset_url)
        else:
            html = f'<p>Click <a href="{reset_url}">here</a> to reset your password. This link expires in 1 hour.</p>'
        html = add_inspiration_to_email(html, db, user.role)
        send_email_sync(to_email=user.email, subject="ClassBridge — Reset Your Password", html_content=html)
        try:
            log_action(db, user_id=user.id, action="pwd_reset_req", resource_type="user",
                       resource_id=user.id, ip_address=request.client.host if request.client else None)
            db.commit()
        except Exception:
            db.rollback()  # Ensure session is clean even if audit logging fails

    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Reset a user's password using a valid reset token."""
    email = decode_password_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    pw_error = validate_password_strength(body.new_password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    user.hashed_password = get_password_hash(body.new_password)
    log_action(db, user_id=user.id, action="password_reset", resource_type="user",
               resource_id=user.id, ip_address=request.client.host if request.client else None)
    db.commit()

    return {"message": "Password reset successfully. You can now sign in."}
