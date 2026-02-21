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
from app.schemas.user import UserCreate, UserResponse, Token, ForgotPasswordRequest, ResetPasswordRequest, OnboardingRequest, EmailVerifyRequest
from app.schemas.invite import AcceptInviteRequest
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_refresh_token, validate_password_strength, create_password_reset_token, decode_password_reset_token, create_email_verification_token, decode_email_verification_token, UNUSABLE_PASSWORD_HASH
from app.api.deps import get_current_user, oauth2_scheme
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, add_inspiration_to_email
from app.core.config import settings
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


_ALLOWED_REGISTRATION_ROLES = {UserRole.PARENT, UserRole.STUDENT, UserRole.TEACHER}

import logging as _logging
_logger = _logging.getLogger(__name__)


def _send_verification_email(user: User, db: Session) -> None:
    """Send a verification email (best-effort, never raises)."""
    try:
        token = create_email_verification_token(user.email)
        verify_url = f"{settings.frontend_url}/verify-email?token={token}"
        template = _load_template("email_verification.html")
        if template:
            html = _render(template, user_name=user.full_name or "there", verify_url=verify_url)
        else:
            html = f'<p>Click <a href="{verify_url}">here</a> to verify your email. This link expires in 24 hours.</p>'
        html = add_inspiration_to_email(html, db, user.role)
        send_email_sync(to_email=user.email, subject="ClassBridge — Verify Your Email", html_content=html)
    except Exception as e:
        _logger.warning("Failed to send verification email to %s: %s", user.email, e)


def _send_welcome_email(user: User, db: Session) -> None:
    """Send a welcome email after registration (best-effort, never raises)."""
    try:
        template = _load_template("welcome.html")
        if template:
            html = _render(template, user_name=user.full_name or "there",
                           app_url=settings.frontend_url)
        else:
            html = f'<p>Welcome to ClassBridge, {user.full_name or "there"}!</p>'
        html = add_inspiration_to_email(html, db, user.role or "parent")
        send_email_sync(to_email=user.email,
                        subject="Welcome to ClassBridge \u2014 Let's Get Started!",
                        html_content=html)
    except Exception as e:
        _logger.warning("Failed to send welcome email to %s: %s", user.email, e)


def _send_verification_ack_email(user: User, db: Session) -> None:
    """Send an acknowledgement email after email verification (best-effort, never raises)."""
    try:
        template = _load_template("email_verified_welcome.html")
        if template:
            html = _render(template, user_name=user.full_name or "there",
                           app_url=settings.frontend_url)
        else:
            html = f'<p>Your email is verified, {user.full_name or "there"}! Explore ClassBridge.</p>'
        html = add_inspiration_to_email(html, db, user.role or "parent")
        send_email_sync(to_email=user.email,
                        subject="You're Verified \u2014 Explore Everything ClassBridge Has to Offer",
                        html_content=html)
    except Exception as e:
        _logger.warning("Failed to send verification ack email to %s: %s", user.email, e)


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Block admin self-registration (only when roles are provided)
    if user_data.role and user_data.role not in _ALLOWED_REGISTRATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role cannot be self-registered",
        )

    # Validate password strength
    pw_error = validate_password_strength(user_data.password)
    if pw_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_error)

    # Check if email already exists
    if user_data.email:
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check if username already exists
    if user_data.username:
        existing_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
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

    # Determine if this is a roleless registration (onboarding deferred)
    has_roles = bool(user_data.roles)

    # Google-authenticated users have verified email via Google
    is_google_signup = bool(user_data.google_id)

    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role if has_roles else None,
        roles=",".join(r.value for r in user_data.roles) if has_roles else "",
        needs_onboarding=not has_roles,
        email_verified=is_google_signup,
        email_verified_at=datetime.now(timezone.utc) if is_google_signup else None,
        google_id=user_data.google_id,
        google_access_token=google_access_token,
        google_refresh_token=google_refresh_token,
    )
    db.add(user)
    db.flush()

    # Create profile records only when roles are provided
    if has_roles:
        from app.services.user_service import ensure_profile_records
        ensure_profile_records(db, user)

        # Set teacher_type if teacher role and type provided
        if UserRole.TEACHER in user_data.roles and user_data.teacher_type:
            teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
            if teacher:
                teacher.teacher_type = TeacherType(user_data.teacher_type)

    # Student registration: store parent_email and trigger LinkRequest or Invite
    if has_roles and UserRole.STUDENT in user_data.roles and user_data.parent_email:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            student.parent_email = user_data.parent_email

            # Look up parent by email
            parent_user = db.query(User).filter(User.email == user_data.parent_email).first()
            if parent_user:
                # Parent exists — create LinkRequest for approval
                import secrets
                from datetime import timedelta
                from app.models.link_request import LinkRequest, LinkRequestType
                from app.services.notification_service import send_multi_channel_notification
                from app.models.notification import NotificationType

                link_req = LinkRequest(
                    request_type=LinkRequestType.STUDENT_TO_PARENT.value,
                    requester_user_id=user.id,
                    target_user_id=parent_user.id,
                    student_id=student.id,
                    relationship_type="guardian",
                    token=secrets.token_urlsafe(32),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
                db.add(link_req)
                db.flush()

                send_multi_channel_notification(
                    db=db,
                    recipient=parent_user,
                    sender=user,
                    title="Student Link Request",
                    content=f"{user.full_name} has registered as a student and is requesting to link to your account.",
                    notification_type=NotificationType.LINK_REQUEST,
                    link="/link-requests",
                )
            else:
                # Parent not in system — create Invite
                import secrets
                from datetime import timedelta
                token = secrets.token_urlsafe(32)
                invite = Invite(
                    email=user_data.parent_email,
                    invite_type=InviteType.PARENT,
                    token=token,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    invited_by_user_id=user.id,
                    metadata_json={
                        "student_user_id": user.id,
                        "student_id": student.id,
                        "relationship_type": "guardian",
                    },
                )
                db.add(invite)
                db.flush()

                # Send invite email (best-effort)
                try:
                    invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
                    invite_html = f"""
                        <h2>Your child has joined ClassBridge</h2>
                        <p><strong>{user.full_name}</strong> has registered on ClassBridge and listed you as their parent.</p>
                        <p>Create your parent account to stay connected with their education:</p>
                        <p><a href="{invite_link}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:6px;">Create My Account</a></p>
                        <p style="color:#666;font-size:14px;">This invite expires in 30 days.</p>
                    """
                    send_email_sync(
                        to_email=user_data.parent_email,
                        subject=f"{user.full_name} invited you to ClassBridge",
                        html_content=invite_html,
                    )
                except Exception as e:
                    _logger.warning("Failed to send parent invite email to %s: %s", user_data.parent_email, e)

    log_action(db, user_id=user.id, action="create", resource_type="user", resource_id=user.id,
               details={"role": user_data.role, "email": user_data.email, "username": user_data.username, "needs_onboarding": not has_roles},
               ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(user)

    # Send verification + welcome emails for non-Google signups (best-effort)
    if not is_google_signup:
        _send_verification_email(user, db)
        _send_welcome_email(user, db)

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


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    # Try email first, then username
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        log_action(db, user_id=None, action="login_failed", resource_type="user",
                   details={"identifier": form_data.username}, ip_address=ip)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
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
    # Validate token (FOR UPDATE prevents concurrent accept race condition)
    invite = db.query(Invite).filter(Invite.token == data.token).with_for_update().first()
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

    # Create user — email verified since they received the invite at this address
    user = User(
        email=invite.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=role,
        roles=role.value,
        email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
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
            shadow.is_platform_user = True
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

    if not user:
        _logger.warning("pwd_reset: no account found for requested email")
    elif not user.hashed_password or user.hashed_password == UNUSABLE_PASSWORD_HASH:
        _logger.warning(f"pwd_reset: user {user.id} has unusable password (invite/OAuth-only), skipping email")
    else:
        token = create_password_reset_token(user.email)
        reset_url = f"{settings.frontend_url}/reset-password?token={token}"
        template = _load_template("password_reset.html")
        if template:
            html = _render(template, user_name=user.full_name or "there", reset_url=reset_url)
        else:
            html = f'<p>Click <a href="{reset_url}">here</a> to reset your password. This link expires in 1 hour.</p>'
        html = add_inspiration_to_email(html, db, user.role)
        sent = send_email_sync(to_email=user.email, subject="ClassBridge — Reset Your Password", html_content=html)
        if sent:
            _logger.warning(f"pwd_reset: reset email sent to user {user.id}")
        else:
            _logger.warning(f"pwd_reset: failed to send reset email to user {user.id}")
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


@router.post("/onboarding", response_model=UserResponse)
def complete_onboarding(
    body: OnboardingRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete user onboarding by setting role(s) after registration."""
    # User must need onboarding
    if not current_user.needs_onboarding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onboarding already completed",
        )

    # Validate at least one role
    if not body.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one role is required",
        )

    # Parse and validate roles
    valid_role_values = {r.value for r in _ALLOWED_REGISTRATION_ROLES}
    for r in body.roles:
        if r not in valid_role_values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or disallowed role: {r}",
            )

    roles = [UserRole(r) for r in body.roles]

    # If teacher role, teacher_type is required
    if UserRole.TEACHER in roles:
        if not body.teacher_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Teacher type is required when selecting the teacher role",
            )
        if body.teacher_type not in ("school_teacher", "private_tutor"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid teacher type",
            )

    # Set roles on user
    current_user.role = roles[0]
    current_user.set_roles(roles)
    current_user.needs_onboarding = False
    db.flush()

    # Create profile records
    from app.services.user_service import ensure_profile_records
    ensure_profile_records(db, current_user)

    # Set teacher_type if applicable
    if UserRole.TEACHER in roles and body.teacher_type:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            teacher.teacher_type = TeacherType(body.teacher_type)

    log_action(db, user_id=current_user.id, action="onboarding_complete", resource_type="user",
               resource_id=current_user.id,
               details={"roles": body.roles, "teacher_type": body.teacher_type},
               ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(current_user)

    return UserResponse(
        id=current_user.id,
        email=current_user.email or "",
        full_name=current_user.full_name,
        role=current_user.role,
        roles=[r.value for r in current_user.get_roles_list()],
        is_active=current_user.is_active,
        google_connected=bool(current_user.google_access_token),
        needs_onboarding=False,
        email_verified=current_user.email_verified or False,
        created_at=current_user.created_at,
    )


@router.post("/verify-email")
def verify_email(body: EmailVerifyRequest, request: Request, db: Session = Depends(get_db)):
    """Verify a user's email address using a token from the verification email."""
    email = decode_email_verification_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    if user.email_verified:
        return {"message": "Email already verified"}

    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    log_action(db, user_id=user.id, action="email_verified", resource_type="user",
               resource_id=user.id, ip_address=request.client.host if request.client else None)
    db.commit()

    # Send verification acknowledgement email (best-effort)
    _send_verification_ack_email(user, db)

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
@limiter.limit("3/minute")
def resend_verification(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend the verification email for the current user."""
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    _send_verification_email(current_user, db)

    return {"message": "Verification email sent"}
