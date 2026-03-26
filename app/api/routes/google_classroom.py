import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.db.database import get_db
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User, UserRole
from app.models.course import Course, student_courses
from app.models.assignment import Assignment
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.teacher_google_account import TeacherGoogleAccount
from app.models.course_content import CourseContent
from app.models.course_announcement import CourseAnnouncement
from app.models.invite import Invite, InviteType
from app.api.deps import get_current_user, require_role
from app.services.audit_service import log_action
from app.services.email_service import add_inspiration_to_email, send_email_sync, wrap_branded_email
from app.core.config import settings
from app.core.security import create_access_token


def _require_google_classroom():
    """Dependency that gates Google Classroom routes behind the toggle.

    Returns 404 when GOOGLE_CLASSROOM_ENABLED is false so disabled
    endpoints appear non-existent to clients.
    """
    if not settings.google_classroom_enabled:
        raise HTTPException(status_code=404, detail="Not Found")


from app.services.google_classroom import (
    get_authorization_url,
    exchange_code_for_tokens,
    get_user_info,
    list_courses,
    get_course_work,
    get_course_work_materials,
    list_course_teachers,
    list_course_announcements,
    GMAIL_READONLY_SCOPE,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google", tags=["Google Classroom"])

# In-memory OAuth state store (nonce → {purpose, user_id, created_at})
# Entries expire after 10 minutes.
_oauth_states: dict[str, dict] = {}
_STATE_TTL = 600  # seconds

# Temporary store for Google tokens during registration flow
# (google_id → {access_token, refresh_token, created_at})
# Tokens are consumed when the user completes registration.
_pending_google_tokens: dict[str, dict] = {}
_PENDING_TTL = 600  # seconds


def _create_oauth_state(purpose: str, user_id: int | None = None, code_verifier: str | None = None) -> str:
    """Generate a cryptographic state token and store its context."""
    # Clean expired entries
    now = time.time()
    expired = [k for k, v in _oauth_states.items() if now - v["created_at"] > _STATE_TTL]
    for k in expired:
        _oauth_states.pop(k, None)

    nonce = secrets.token_urlsafe(32)
    _oauth_states[nonce] = {"purpose": purpose, "user_id": user_id, "created_at": now, "code_verifier": code_verifier}
    return nonce


def _consume_oauth_state(nonce: str) -> dict | None:
    """Validate and consume a state token. Returns context or None."""
    entry = _oauth_states.pop(nonce, None)
    if not entry:
        return None
    if time.time() - entry["created_at"] > _STATE_TTL:
        return None
    return entry


def update_user_tokens(user: User, credentials, db: Session):
    """Update user's Google tokens if they were refreshed."""
    if credentials.token != user.google_access_token:
        user.google_access_token = credentials.token
        if credentials.refresh_token:
            user.google_refresh_token = credentials.refresh_token
        db.commit()


def _store_granted_scopes(user: User, granted_scopes_str: str) -> None:
    """Store the granted OAuth scopes on the user record.

    Google returns scopes as a space-separated string in the token response.
    We store them as comma-separated for consistency with other CSV columns.
    If user already has scopes, merge (union) old + new.
    """
    if not granted_scopes_str:
        return
    new_scopes = set(granted_scopes_str.split())
    if user.google_granted_scopes:
        existing = set(user.google_granted_scopes.split(","))
        new_scopes = existing | new_scopes
    user.google_granted_scopes = ",".join(sorted(new_scopes))


@router.get("/auth")
@limiter.limit("10/minute")
def google_auth(request: Request, user_id: int | None = None):
    """Get Google OAuth authorization URL.

    If user_id is provided, it will be included in the state to link
    the Google account to an existing user after callback.
    """
    state = _create_oauth_state(purpose="auth", user_id=user_id)
    authorization_url, _, code_verifier = get_authorization_url(state)
    # Store the PKCE code_verifier so the callback can use it
    _oauth_states[state]["code_verifier"] = code_verifier
    return {"authorization_url": authorization_url, "state": state}


@router.get("/connect")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def google_connect(
    request: Request,
    current_user: User = Depends(get_current_user),
    add_account: bool = Query(False, description="If true, adds as additional teacher Google account"),
    _gc=Depends(_require_google_classroom),
):
    """Get authorization URL for connecting Google to existing account."""
    purpose = "add_account" if add_account and current_user.has_role(UserRole.TEACHER) else "connect"
    state = _create_oauth_state(purpose=purpose, user_id=current_user.id)
    authorization_url, _, code_verifier = get_authorization_url(state)
    _oauth_states[state]["code_verifier"] = code_verifier
    return {"authorization_url": authorization_url}


@router.get("/callback")
@limiter.limit("10/minute")
def google_callback(
    request: Request,
    code: str,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback."""
    # Handle OAuth errors
    if error:
        params = urlencode({"error": error})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")

    # Validate state parameter (CSRF protection)
    if not state:
        params = urlencode({"error": "Missing OAuth state parameter"})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")

    state_data = _consume_oauth_state(state)
    if not state_data:
        params = urlencode({"error": "Invalid or expired OAuth state"})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")

    try:
        tokens = exchange_code_for_tokens(code, code_verifier=state_data.get("code_verifier"))
        user_info = get_user_info(tokens["access_token"])

        # Check if this is an add-account request for a teacher
        if state_data["purpose"] == "add_account" and state_data.get("user_id"):
            user = db.query(User).filter(User.id == state_data["user_id"]).first()
            if user and user.has_role(UserRole.TEACHER):
                teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
                if teacher:
                    google_email = user_info.get("email", "").lower()
                    # Check for duplicate
                    existing_acct = (
                        db.query(TeacherGoogleAccount)
                        .filter(TeacherGoogleAccount.teacher_id == teacher.id,
                                TeacherGoogleAccount.google_email == google_email)
                        .first()
                    )
                    if existing_acct:
                        existing_acct.access_token = tokens["access_token"]
                        if tokens.get("refresh_token"):
                            existing_acct.refresh_token = tokens["refresh_token"]
                    else:
                        is_first = db.query(TeacherGoogleAccount).filter(
                            TeacherGoogleAccount.teacher_id == teacher.id
                        ).count() == 0
                        new_acct = TeacherGoogleAccount(
                            teacher_id=teacher.id,
                            google_id=user_info["id"],
                            google_email=google_email,
                            display_name=user_info.get("name", ""),
                            access_token=tokens["access_token"],
                            refresh_token=tokens.get("refresh_token"),
                            is_primary=is_first,
                        )
                        db.add(new_acct)
                    # Also update User-level tokens for backward compat
                    # (only if no other user owns this google_id)
                    existing_owner = db.query(User).filter(
                        User.google_id == user_info["id"],
                        User.id != user.id,
                    ).first()
                    if not existing_owner:
                        user.google_id = user_info["id"]
                    user.google_access_token = tokens["access_token"]
                    if tokens.get("refresh_token"):
                        user.google_refresh_token = tokens["refresh_token"]
                    _store_granted_scopes(user, tokens.get("granted_scopes", ""))
                    db.commit()
                    params = urlencode({"google_connected": "true", "account_added": "true"})
                    return RedirectResponse(url=f"{settings.frontend_url}/dashboard?{params}")

        # Check if this is a connect request for existing user
        if state_data["purpose"] in ("connect", "add_account") and state_data.get("user_id"):
            user = db.query(User).filter(User.id == state_data["user_id"]).first()
            if user:
                # Check if another user already owns this google_id
                existing_owner = db.query(User).filter(
                    User.google_id == user_info["id"],
                    User.id != user.id,
                ).first()
                if existing_owner:
                    params = urlencode({"error": "This Google account is already linked to another user."})
                    return RedirectResponse(url=f"{settings.frontend_url}/dashboard?{params}")

                user.google_id = user_info["id"]
                user.google_access_token = tokens["access_token"]
                user.google_refresh_token = tokens.get("refresh_token")
                _store_granted_scopes(user, tokens.get("granted_scopes", ""))
                db.commit()

                # Redirect to dashboard with success (no tokens in URL)
                params = urlencode({"google_connected": "true"})
                return RedirectResponse(url=f"{settings.frontend_url}/dashboard?{params}")

        # Find existing user by Google ID first, then by email
        user = db.query(User).filter(User.google_id == user_info["id"]).first()
        found_by_google_id = user is not None
        if not user:
            user = db.query(User).filter(User.email == user_info["email"]).first()

        if user:
            if found_by_google_id:
                # google_id already matches — just refresh tokens
                user.google_access_token = tokens["access_token"]
                if tokens.get("refresh_token"):
                    user.google_refresh_token = tokens["refresh_token"]
            else:
                # Found by email — check for google_id conflict before linking
                existing_owner = db.query(User).filter(
                    User.google_id == user_info["id"],
                ).first()
                if existing_owner:
                    # google_id belongs to a different user — use that user instead
                    user = existing_owner
                    user.google_access_token = tokens["access_token"]
                    if tokens.get("refresh_token"):
                        user.google_refresh_token = tokens["refresh_token"]
                else:
                    user.google_id = user_info["id"]
                    user.google_access_token = tokens["access_token"]
                    user.google_refresh_token = tokens.get("refresh_token")
            _store_granted_scopes(user, tokens.get("granted_scopes", ""))
            db.commit()
            db.refresh(user)

            # Create access token for our app (passed via URL — acceptable for
            # server-to-browser redirect; token is short-lived)
            access_token = create_access_token(data={"sub": str(user.id)})
            params = urlencode({"token": access_token})
            return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")
        else:
            # No account yet — store Google tokens server-side and redirect
            # with only safe identifiers (no tokens in URL)
            google_id = user_info["id"]
            now = time.time()
            expired = [k for k, v in _pending_google_tokens.items() if now - v["created_at"] > _PENDING_TTL]
            for k in expired:
                _pending_google_tokens.pop(k, None)
            _pending_google_tokens[google_id] = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "created_at": now,
            }
            params = urlencode({
                "google_email": user_info["email"],
                "google_name": user_info.get("name", ""),
                "google_id": google_id,
            })
            return RedirectResponse(url=f"{settings.frontend_url}/register?{params}")

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        # Surface a more specific message for common failures
        err_str = str(e)
        if "400" in err_str and "token" in err_str.lower():
            msg = "Google authentication expired. Please try signing in again."
        else:
            msg = "Authentication failed. Please try again."
        params = urlencode({"error": msg})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")


@router.get("/status")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def google_status(request: Request, current_user: User = Depends(get_current_user), _gc=Depends(_require_google_classroom)):
    """Check if user has connected Google Classroom."""
    return {
        "connected": bool(current_user.google_access_token),
        "gmail_scope_granted": current_user.has_google_scope(GMAIL_READONLY_SCOPE),
        "google_email": None,  # Could fetch from Google if needed
    }


@router.delete("/disconnect")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def google_disconnect(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Disconnect Google Classroom from user account."""
    current_user.google_id = None
    current_user.google_access_token = None
    current_user.google_refresh_token = None
    current_user.google_granted_scopes = None
    db.commit()
    return {"message": "Google Classroom disconnected"}


@router.get("/courses")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_google_courses(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """List all Google Classroom courses for the authenticated user."""
    if not current_user.google_access_token:
        from app.core.faq_errors import raise_with_faq_hint, GOOGLE_NOT_CONNECTED
        raise_with_faq_hint(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
            faq_code=GOOGLE_NOT_CONNECTED,
        )

    courses, credentials = list_courses(
        current_user.google_access_token,
        current_user.google_refresh_token,
    )

    # Update tokens if refreshed
    update_user_tokens(current_user, credentials, db)

    return {"courses": courses}


_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


def _auto_invite_shadow_teacher(
    teacher: Teacher,
    teacher_email: str,
    teacher_name: str,
    inviting_user: User,
    db: Session,
) -> None:
    """Auto-create an invite and send email to a shadow teacher.

    Called when a parent/student syncs Google Classroom and a new shadow
    teacher record is created.

    Skips if:
    - AUTO_INVITE_SHADOW_TEACHERS config is disabled
    - Teacher was already invited in the last 30 days (debounce)
    - A pending (unexpired, unaccepted) invite already exists
    """
    # Guard: check config setting (#946)
    if not settings.auto_invite_shadow_teachers:
        logger.debug(f"Auto-invite disabled; skipping invite for {teacher_email}")
        return

    # Debounce: skip if teacher was already invited in last 30 days (#946)
    now = datetime.now(timezone.utc)
    if teacher.auto_invited_at:
        days_since = (now - teacher.auto_invited_at).days
        if days_since < 30:
            logger.debug(
                f"Shadow teacher {teacher_email} was auto-invited {days_since} days ago; skipping"
            )
            return

    # Check for existing pending invite
    existing_invite = (
        db.query(Invite)
        .filter(
            Invite.email == teacher_email,
            Invite.invite_type == InviteType.TEACHER,
            Invite.accepted_at.is_(None),
            Invite.expires_at > now,
        )
        .first()
    )
    if existing_invite:
        return

    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=teacher_email,
        invite_type=InviteType.TEACHER,
        token=token,
        expires_at=now + timedelta(days=30),
        invited_by_user_id=inviting_user.id,
        metadata_json={"source": "google_classroom_sync", "teacher_name": teacher_name},
    )
    db.add(invite)
    db.flush()

    # Track when invite was sent on the teacher record (#946)
    teacher.auto_invited_at = now

    # Send invite email
    invite_link = f"{settings.frontend_url}/accept-invite?token={token}"
    inviter_name = inviting_user.full_name or "A ClassBridge user"
    try:
        tpl_path = os.path.join(_TEMPLATE_DIR, "teacher_invite_shadow.html")
        if os.path.exists(tpl_path):
            with open(tpl_path, "r") as f:
                html = f.read()
            html = (
                html
                .replace("{{teacher_name}}", teacher_name or "Teacher")
                .replace("{{inviter_name}}", inviter_name)
                .replace("{{invite_link}}", invite_link)
            )
        else:
            body = (
                f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">You\'ve Been Invited to ClassBridge</h2>'
                f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">Hi {teacher_name or "there"},</p>'
                f'<p style="color:#333;line-height:1.6;margin:0 0 24px 0;"><strong>{inviter_name}</strong> synced their Google Classroom and your courses were discovered. '
                f'Join ClassBridge to connect with parents, share announcements, and track student progress.</p>'
                f'<a href="{invite_link}" style="display:inline-block;background:#4f46e5;color:white;text-decoration:none;padding:14px 28px;border-radius:8px;font-weight:600;font-size:16px;">Create Your Account</a>'
                f'<p style="color:#999;font-size:13px;margin:24px 0 0 0;">This invite expires in 30 days.</p>'
            )
            html = wrap_branded_email(body)
        html = add_inspiration_to_email(html, db, "teacher")
        send_email_sync(
            to_email=teacher_email,
            subject=f"{inviter_name} invited you to ClassBridge",
            html_content=html,
        )
        logger.info(f"Auto-invite email sent to shadow teacher {teacher_email}")
    except Exception as e:
        logger.warning(f"Failed to send auto-invite to shadow teacher {teacher_email}: {e}")


# Well-known personal email domains (not school/organization domains)
_PERSONAL_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk",
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "aol.com", "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me", "zoho.com", "yandex.com",
    "mail.com", "gmx.com", "gmx.net", "fastmail.com",
})


def _detect_classroom_type_from_domain(owner_email: str | None) -> str:
    """Detect classroom type based on email domain.

    School domains (e.g. @school.edu, @district.k12.ca.us) -> "school"
    Personal domains (gmail.com, yahoo.com, etc.) -> "private"
    """
    if not owner_email:
        return "private"
    domain = owner_email.rsplit("@", 1)[-1].lower() if "@" in owner_email else ""
    if not domain:
        return "private"
    if domain in _PERSONAL_EMAIL_DOMAINS:
        return "private"
    return "school"


def _set_classroom_type(course: Course, gc_data: dict | None, db: Session) -> None:
    """Set classroom_type based on Google Classroom data and teacher info.

    Detection priority:
    1. Teacher explicit teacher_type
    2. Teacher google_email domain
    3. Default to "private"

    Does not override if already set to school/private.
    """
    if course.classroom_type and course.classroom_type != "manual":
        return

    if course.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        if teacher and teacher.teacher_type:
            from app.models.teacher import TeacherType
            if teacher.teacher_type == TeacherType.SCHOOL_TEACHER:
                course.classroom_type = "school"
                return
            elif teacher.teacher_type == TeacherType.PRIVATE_TUTOR:
                course.classroom_type = "private"
                return

    if course.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        if teacher and teacher.google_email:
            course.classroom_type = _detect_classroom_type_from_domain(teacher.google_email)
            return

    course.classroom_type = "private"


def _resolve_teacher_for_course(
    google_course_id: str,
    user: User,
    db: Session,
) -> Teacher | None:
    """Fetch teachers from Google Classroom and resolve/create a Teacher record."""
    try:
        google_teachers, credentials = list_course_teachers(
            user.google_access_token,
            google_course_id,
            user.google_refresh_token,
        )
        update_user_tokens(user, credentials, db)
    except Exception as e:
        logger.warning(f"Failed to list teachers for course {google_course_id}: {e}")
        return None

    if not google_teachers:
        return None

    # Use the first teacher (primary/owner)
    gt = google_teachers[0]
    profile = gt.get("profile", {})
    name_obj = profile.get("name", {})
    email = profile.get("emailAddress", "").lower()
    full_name = name_obj.get("fullName", "")

    if not email:
        return None

    # Try to match by google_email on Teacher
    teacher = db.query(Teacher).filter(Teacher.google_email == email).first()
    if teacher:
        return teacher

    # Try to match by email on User (registered teacher)
    teacher_user = (
        db.query(User)
        .filter(User.email == email, User.role == UserRole.TEACHER)
        .first()
    )
    if teacher_user:
        teacher = db.query(Teacher).filter(Teacher.user_id == teacher_user.id).first()
        if teacher:
            teacher.google_email = email
            return teacher

    # Create shadow teacher
    teacher = Teacher(
        is_shadow=True,
        is_platform_user=False,
        user_id=None,
        full_name=full_name,
        google_email=email,
    )
    db.add(teacher)
    db.flush()

    # Auto-send invite to shadow teacher (#57, #946)
    _auto_invite_shadow_teacher(teacher, email, full_name, user, db)

    return teacher


def _sync_courses_for_user(user: User, db: Session, classroom_type: str | None = None) -> list[dict]:
    """Shared course sync logic. Returns list of synced course dicts.

    Args:
        classroom_type: If provided ("school" or "private"), overrides auto-detection
                        from teacher type and applies to all synced courses.
    """
    try:
        google_courses, credentials = list_courses(
            user.google_access_token,
            user.google_refresh_token,
        )
    except Exception as e:
        logger.warning(f"Failed to list Google courses for user {user.id}: {e}")
        from app.core.faq_errors import raise_with_faq_hint, GOOGLE_SYNC_FAILED
        raise_with_faq_hint(
            status_code=502,
            detail="Failed to fetch courses from Google Classroom. The Google connection may have expired — please reconnect Google.",
            faq_code=GOOGLE_SYNC_FAILED,
        )
    update_user_tokens(user, credentials, db)

    # Determine if this user is a teacher
    teacher = None
    if user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()

    # Determine if this user is a student
    student = None
    if user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == user.id).first()

    synced_courses = []
    for gc in google_courses:
        existing = db.query(Course).filter(
            Course.google_classroom_id == gc["id"]
        ).first()

        if existing:
            existing.name = gc.get("name", existing.name)
            existing.description = gc.get("description")
            if teacher and not existing.teacher_id:
                existing.teacher_id = teacher.id
            course = existing
        else:
            course = Course(
                name=gc.get("name", "Untitled Course"),
                description=gc.get("description"),
                subject=gc.get("section"),
                google_classroom_id=gc["id"],
                teacher_id=teacher.id if teacher else None,
            )
            db.add(course)
            db.flush()

        # Resolve teacher from Google if course has no teacher
        if not course.teacher_id:
            resolved_teacher = _resolve_teacher_for_course(gc["id"], user, db)
            if resolved_teacher:
                course.teacher_id = resolved_teacher.id

        # Set classroom_type: explicit parameter overrides auto-detection
        if classroom_type in ("school", "private"):
            course.classroom_type = classroom_type
        else:
            _set_classroom_type(course, gc, db)

        # Link student to course
        if student:
            existing_link = (
                db.query(student_courses)
                .filter(
                    student_courses.c.student_id == student.id,
                    student_courses.c.course_id == course.id,
                )
                .first()
            )
            if not existing_link:
                db.execute(
                    student_courses.insert().values(
                        student_id=student.id,
                        course_id=course.id,
                    )
                )

        synced_courses.append(course)

    db.commit()

    # Sync courseWorkMaterials, assignments, and announcements for each synced course
    total_materials = 0
    total_assignments = 0
    total_announcements = 0
    for course in synced_courses:
        if not course.google_classroom_id:
            continue
        total_materials += _sync_materials_for_course(course, user, db)
        total_assignments += _sync_assignments_for_course(course, user, db)
        total_announcements += _sync_announcements_for_course(course, user, db)

    return {
        "courses": [{"id": c.id, "name": c.name, "google_id": c.google_classroom_id} for c in synced_courses],
        "materials_synced": total_materials,
        "assignments_synced": total_assignments,
        "announcements_synced": total_announcements,
    }


def _sync_materials_for_course(course: Course, user: User, db: Session) -> int:
    """Sync courseWorkMaterials from Google Classroom into CourseContent. Returns count synced."""
    try:
        materials, credentials = get_course_work_materials(
            user.google_access_token,
            course.google_classroom_id,
            user.google_refresh_token,
        )
        update_user_tokens(user, credentials, db)
    except Exception as e:
        logger.warning(f"Failed to fetch courseWorkMaterials for course {course.google_classroom_id}: {e}")
        return 0

    count = 0
    for mat in materials:
        # Skip drafts/deleted
        if mat.get("state") in ("DRAFT", "DELETED"):
            continue

        material_id = mat.get("id")
        if not material_id:
            continue

        # Check if already synced
        existing = db.query(CourseContent).filter(
            CourseContent.google_classroom_material_id == material_id,
        ).first()

        title = mat.get("title", "Untitled Material")
        description = mat.get("description", "")
        alternate_link = mat.get("alternateLink", "")

        # Extract first link URL from materials array if available
        reference_url = None
        mat_items = mat.get("materials", [])
        for item in mat_items:
            if "link" in item:
                reference_url = item["link"].get("url")
                break
            if "driveFile" in item:
                reference_url = item["driveFile"].get("driveFile", {}).get("alternateLink")
                break
            if "youtubeVideo" in item:
                reference_url = item["youtubeVideo"].get("alternateLink")
                break

        if existing:
            existing.title = title
            existing.description = description
            existing.google_classroom_url = alternate_link
            existing.reference_url = reference_url or existing.reference_url
        else:
            content = CourseContent(
                course_id=course.id,
                title=title,
                description=description,
                content_type="resources",
                google_classroom_url=alternate_link,
                google_classroom_material_id=material_id,
                reference_url=reference_url,
                source_type="google_classroom",
            )
            db.add(content)
            count += 1

    db.commit()
    return count


def _sync_assignments_for_course(course: Course, user: User, db: Session) -> int:
    """Auto-sync assignments from Google Classroom during course sync. Returns count of new assignments."""
    try:
        google_assignments, credentials = get_course_work(
            user.google_access_token,
            course.google_classroom_id,
            user.google_refresh_token,
        )
        update_user_tokens(user, credentials, db)
    except Exception as e:
        logger.warning(f"Failed to fetch assignments for course {course.google_classroom_id}: {e}")
        return 0

    count = 0
    for ga in google_assignments:
        existing = db.query(Assignment).filter(
            Assignment.google_classroom_id == ga["id"]
        ).first()

        if existing:
            existing.title = ga.get("title", existing.title)
            existing.description = ga.get("description")
        else:
            due_date = None
            if "dueDate" in ga:
                from datetime import datetime
                d = ga["dueDate"]
                due_date = datetime(d.get("year", 2024), d.get("month", 1), d.get("day", 1))

            assignment = Assignment(
                title=ga.get("title", "Untitled Assignment"),
                description=ga.get("description"),
                course_id=course.id,
                google_classroom_id=ga["id"],
                due_date=due_date,
                max_points=ga.get("maxPoints"),
            )
            db.add(assignment)
            count += 1

    db.commit()
    return count


def _sync_announcements_for_course(course: Course, user: User, db: Session) -> int:
    """Sync announcements from Google Classroom into CourseAnnouncement. Returns count of new announcements."""
    import json

    try:
        google_announcements, credentials = list_course_announcements(
            user.google_access_token,
            course.google_classroom_id,
            user.google_refresh_token,
        )
        update_user_tokens(user, credentials, db)
    except Exception as e:
        logger.warning(f"Failed to fetch announcements for course {course.google_classroom_id}: {e}")
        return 0

    count = 0
    for ga in google_announcements:
        # Skip non-published announcements
        if ga.get("state") in ("DRAFT", "DELETED"):
            continue

        announcement_id = ga.get("id")
        if not announcement_id:
            continue

        existing = db.query(CourseAnnouncement).filter(
            CourseAnnouncement.google_announcement_id == announcement_id,
        ).first()

        text = ga.get("text", "")
        creator_name = None
        creator_email = None
        creator_profile = ga.get("creatorUserId")
        # The API returns creatorUserId but not name directly; we store what we can
        alternate_link = ga.get("alternateLink", "")

        # Parse creation/update times
        creation_time = None
        update_time = None
        if ga.get("creationTime"):
            try:
                creation_time = datetime.fromisoformat(ga["creationTime"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        if ga.get("updateTime"):
            try:
                update_time = datetime.fromisoformat(ga["updateTime"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Serialize materials array to JSON
        materials_json = None
        if ga.get("materials"):
            try:
                materials_json = json.dumps(ga["materials"])
            except (TypeError, ValueError):
                pass

        if existing:
            existing.text = text
            existing.creation_time = creation_time or existing.creation_time
            existing.update_time = update_time
            existing.materials_json = materials_json
            existing.alternate_link = alternate_link
        else:
            announcement = CourseAnnouncement(
                course_id=course.id,
                google_announcement_id=announcement_id,
                text=text,
                creator_name=creator_name,
                creator_email=creator_email,
                creation_time=creation_time,
                update_time=update_time,
                materials_json=materials_json,
                alternate_link=alternate_link,
            )
            db.add(announcement)
            count += 1

    db.commit()
    return count


@router.post("/courses/sync")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def sync_google_courses(
    request: Request,
    classroom_type: str | None = Query(
        None,
        description='Override classroom type for synced courses: "school" or "private"',
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Sync Google Classroom courses to local database.

    Optional query parameter `classroom_type` overrides auto-detection:
    - "school" — school classroom (students cannot download documents)
    - "private" — private/tutor classroom (full access)
    """
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    result = _sync_courses_for_user(current_user, db, classroom_type=classroom_type)

    log_action(db, user_id=current_user.id, action="sync", resource_type="google_classroom")
    db.commit()

    courses = result["courses"]
    materials = result["materials_synced"]
    assignments = result["assignments_synced"]
    announcements = result["announcements_synced"]

    parts = [f"Synced {len(courses)} course{'s' if len(courses) != 1 else ''}"]
    if materials:
        parts.append(f"{materials} new material{'s' if materials != 1 else ''}")
    if assignments:
        parts.append(f"{assignments} new assignment{'s' if assignments != 1 else ''}")
    if announcements:
        parts.append(f"{announcements} new announcement{'s' if announcements != 1 else ''}")

    return {
        "message": ", ".join(parts),
        "courses": courses,
        "materials_synced": materials,
        "assignments_synced": assignments,
        "announcements_synced": announcements,
    }


@router.get("/courses/{course_id}/assignments")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_google_assignments(
    request: Request,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Get all assignments for a Google Classroom course."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    coursework, credentials = get_course_work(
        current_user.google_access_token,
        course_id,
        current_user.google_refresh_token,
    )

    # Update tokens if refreshed
    update_user_tokens(current_user, credentials, db)

    return {"assignments": coursework}


@router.post("/courses/{google_course_id}/assignments/sync")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def sync_google_assignments(
    request: Request,
    google_course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Sync assignments from a Google Classroom course to local database."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    # Find local course
    course = db.query(Course).filter(
        Course.google_classroom_id == google_course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found. Please sync courses first.",
        )

    # Fetch assignments from Google
    google_assignments, credentials = get_course_work(
        current_user.google_access_token,
        google_course_id,
        current_user.google_refresh_token,
    )

    # Update tokens if refreshed
    update_user_tokens(current_user, credentials, db)

    synced_assignments = []
    for ga in google_assignments:
        # Check if assignment already exists
        existing = db.query(Assignment).filter(
            Assignment.google_classroom_id == ga["id"]
        ).first()

        if existing:
            # Update existing assignment
            existing.title = ga.get("title", existing.title)
            existing.description = ga.get("description")
            synced_assignments.append(existing)
        else:
            # Parse due date if available
            due_date = None
            if "dueDate" in ga:
                from datetime import datetime
                d = ga["dueDate"]
                due_date = datetime(d.get("year", 2024), d.get("month", 1), d.get("day", 1))

            # Create new assignment
            assignment = Assignment(
                title=ga.get("title", "Untitled Assignment"),
                description=ga.get("description"),
                course_id=course.id,
                google_classroom_id=ga["id"],
                due_date=due_date,
                max_points=ga.get("maxPoints"),
            )
            db.add(assignment)
            synced_assignments.append(assignment)

    db.commit()

    return {
        "message": f"Synced {len(synced_assignments)} assignments",
        "assignments": [{"id": a.id, "title": a.title} for a in synced_assignments],
    }


@router.post("/courses/{google_course_id}/materials/sync")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def sync_google_materials(
    request: Request,
    google_course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Sync courseWorkMaterials from a Google Classroom course to CourseContent."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    course = db.query(Course).filter(
        Course.google_classroom_id == google_course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found. Please sync courses first.",
        )

    _sync_materials_for_course(course, current_user, db)

    materials_count = db.query(CourseContent).filter(
        CourseContent.course_id == course.id,
        CourseContent.google_classroom_material_id.isnot(None),
    ).count()

    return {
        "message": f"Synced materials for {course.name}",
        "materials_count": materials_count,
    }


# ── Course Announcements (#2279) ─────────────────────────────────────

@router.get("/courses/{course_id}/announcements")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_course_announcements(
    request: Request,
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    after: str | None = Query(None, description="Filter announcements after this ISO date"),
    before: str | None = Query(None, description="Filter announcements before this ISO date"),
    _gc=Depends(_require_google_classroom),
):
    """Get synced announcements for a course.

    Returns locally-stored announcements that were synced from Google Classroom.
    Supports optional date-range filtering via `after` and `before` query params.
    """
    from app.api.deps import can_access_course

    # Verify user can access this course
    if not can_access_course(db, current_user, course_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this course",
        )

    query = db.query(CourseAnnouncement).filter(
        CourseAnnouncement.course_id == course_id,
    )

    if after:
        try:
            after_dt = datetime.fromisoformat(after)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid 'after' date format: {after}")
        query = query.filter(CourseAnnouncement.creation_time >= after_dt)

    if before:
        try:
            before_dt = datetime.fromisoformat(before)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid 'before' date format: {before}")
        query = query.filter(CourseAnnouncement.creation_time <= before_dt)

    announcements = query.order_by(CourseAnnouncement.creation_time.desc()).all()

    return [
        {
            "id": a.id,
            "course_id": a.course_id,
            "google_announcement_id": a.google_announcement_id,
            "text": a.text,
            "creator_name": a.creator_name,
            "creator_email": a.creator_email,
            "creation_time": a.creation_time.isoformat() if a.creation_time else None,
            "update_time": a.update_time.isoformat() if a.update_time else None,
            "materials_json": a.materials_json,
            "alternate_link": a.alternate_link,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in announcements
    ]


# ── Teacher Google Accounts ──────────────────────────────────────────

@router.get("/teacher/accounts")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_teacher_google_accounts(
    request: Request,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """List all Google accounts linked to the current teacher."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        return []
    accounts = (
        db.query(TeacherGoogleAccount)
        .filter(TeacherGoogleAccount.teacher_id == teacher.id)
        .order_by(TeacherGoogleAccount.is_primary.desc(), TeacherGoogleAccount.connected_at)
        .all()
    )
    return [
        {
            "id": a.id,
            "google_email": a.google_email,
            "display_name": a.display_name,
            "account_label": a.account_label,
            "is_primary": a.is_primary,
            "connected_at": a.connected_at.isoformat() if a.connected_at else None,
            "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
        }
        for a in accounts
    ]


@router.patch("/teacher/accounts/{account_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_teacher_google_account(
    request: Request,
    account_id: int,
    label: str | None = Query(None),
    set_primary: bool = Query(False),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Update label or primary status for a teacher Google account."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    account = (
        db.query(TeacherGoogleAccount)
        .filter(TeacherGoogleAccount.id == account_id, TeacherGoogleAccount.teacher_id == teacher.id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")
    if label is not None:
        account.account_label = label
    if set_primary:
        # Unset all others
        db.query(TeacherGoogleAccount).filter(
            TeacherGoogleAccount.teacher_id == teacher.id
        ).update({"is_primary": False})
        account.is_primary = True
    db.commit()
    return {"status": "ok"}


@router.post("/sync-grades/{course_id}")
def sync_grades_for_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Sync grades from Google Classroom for a specific course.

    Fetches student submissions and updates StudentAssignment grades
    and GradeRecord analytics rows.
    """
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Classroom not connected. Please connect your Google account first.",
        )

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    if not course.google_classroom_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This course is not linked to Google Classroom",
        )

    # Verify user has access to this course
    from app.api.deps import can_access_course
    if not can_access_course(db, current_user, course_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this course",
        )

    from app.services.grade_sync_service import sync_grades_for_course as _sync_grades
    result = _sync_grades(current_user, course, db)

    synced = result["synced"]
    errors = result["errors"]
    if errors:
        message = f"Synced {synced} grade(s) with {errors} error(s)"
    else:
        message = f"Synced {synced} grade(s) from Google Classroom"

    log_action(db, user_id=current_user.id, action="sync", resource_type="grades", resource_id=course_id)
    db.commit()

    return {"synced": synced, "errors": errors, "message": message}


@router.delete("/teacher/accounts/{account_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def remove_teacher_google_account(
    request: Request,
    account_id: int,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    _gc=Depends(_require_google_classroom),
):
    """Remove a linked Google account from teacher."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    account = (
        db.query(TeacherGoogleAccount)
        .filter(TeacherGoogleAccount.id == account_id, TeacherGoogleAccount.teacher_id == teacher.id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")
    db.delete(account)
    db.commit()
    return {"status": "ok"}
