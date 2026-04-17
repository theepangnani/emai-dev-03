import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.token_blacklist import TokenBlacklist
from app.models.user import User, UserRole

# Simple TTL cache for token blacklist lookups
_blacklist_cache: dict[str, tuple[bool, float]] = {}
_BLACKLIST_CACHE_TTL = 60  # seconds


def _is_token_blacklisted(db: Session, jti: str) -> bool:
    """Check if a JTI is blacklisted, with in-memory caching."""
    now = time.time()
    cached = _blacklist_cache.get(jti)
    if cached and (now - cached[1]) < _BLACKLIST_CACHE_TTL:
        return cached[0]

    result = db.query(TokenBlacklist.id).filter(TokenBlacklist.jti == jti).first() is not None
    _blacklist_cache[jti] = (result, now)

    # Prune expired entries periodically (keep cache small)
    if len(_blacklist_cache) > 10000:
        expired = [k for k, (_, ts) in _blacklist_cache.items() if (now - ts) >= _BLACKLIST_CACHE_TTL]
        for k in expired:
            del _blacklist_cache[k]
        # Safety cap: if still too large after TTL eviction, evict oldest half
        if len(_blacklist_cache) > 50000:
            sorted_keys = sorted(_blacklist_cache, key=lambda k: _blacklist_cache[k][1])
            for k in sorted_keys[:len(sorted_keys) // 2]:
                del _blacklist_cache[k]

    return result

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Check token blacklist (revoked tokens)
    jti = payload.get("jti")
    if jti and _is_token_blacklisted(db, jti):
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    # Block deleted/anonymized accounts
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deleted",
        )

    # Make user ID available for rate limiter and request logging
    request.state.user_id = user.id

    return user


def get_current_user_optional(
    request: Request,
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the current user if a valid token is present, otherwise None."""
    if not token:
        return None
    try:
        return get_current_user(request=request, token=token, db=db)
    except HTTPException:
        return None


def get_current_user_sse(
    request: Request,
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current user for SSE endpoints.

    EventSource cannot send custom headers, so this dependency falls back
    to a ``token`` query parameter when no Authorization header is present.
    """
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(request=request, token=token, db=db)


def require_role(*roles: UserRole):
    """Dependency factory that checks the current user has one of the required roles."""
    def checker(current_user: User = Depends(get_current_user)):
        if not any(current_user.has_role(r) for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return checker


def can_access_material(db: Session, user: User, content) -> bool:
    """Check if a user is in the trust circle for a specific material.

    Trust circle grants access when any of the following is true:
      - User created the material
      - The course is public (not private)
      - User created the course
      - User is the assigned teacher
      - User (student) is enrolled in the course
      - User (parent) has a linked child enrolled in the course
    Pure admins naturally get no access (they match no rule above).
    Multi-role users (e.g. admin+parent) are evaluated through their other roles.
    """
    from app.models.course import Course, student_courses
    from app.models.student import Student, parent_students
    from app.models.teacher import Teacher

    # Creator of the material always has access
    if content.created_by_user_id == user.id:
        return True

    # Look up the course
    course = db.query(Course).filter(Course.id == content.course_id).first()
    if not course:
        return False

    # Public courses grant read access to all authenticated users
    if not course.is_private:
        return True

    # Course creator has access
    if course.created_by_user_id == user.id:
        return True

    # Assigned teacher has access
    if user.has_role(UserRole.TEACHER):
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher and course.teacher_id == teacher.id:
            return True

    # Enrolled student has access
    if user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            enrolled = (
                db.query(student_courses.c.course_id)
                .filter(
                    student_courses.c.student_id == student.id,
                    student_courses.c.course_id == content.course_id,
                )
                .first()
            )
            if enrolled:
                return True

    # Parent of enrolled student has access, or parent of child who created content/course
    if user.has_role(UserRole.PARENT):
        child_student_ids = [
            r[0] for r in db.query(parent_students.c.student_id).filter(
                parent_students.c.parent_id == user.id
            ).all()
        ]
        if child_student_ids:
            # Check if child is enrolled in the course
            enrolled = (
                db.query(student_courses.c.student_id)
                .filter(
                    student_courses.c.student_id.in_(child_student_ids),
                    student_courses.c.course_id == content.course_id,
                )
                .first()
            )
            if enrolled:
                return True

            # Check if child created the material or the course
            child_user_ids = [
                r[0] for r in db.query(Student.user_id).filter(
                    Student.id.in_(child_student_ids)
                ).all()
            ]
            if child_user_ids:
                if content.created_by_user_id in child_user_ids:
                    return True
                if course.created_by_user_id in child_user_ids:
                    return True

    return False


def can_access_course(db: Session, user: User, course_id: int) -> bool:
    """Check if a user has access to a specific course.

    Access is granted when any of the following is true:
      - User is ADMIN
      - User created the course
      - Course is public (not private)
      - User is the assigned teacher
      - User (student) is enrolled
      - User (parent) has a linked child enrolled
    """
    from app.domains.education.services import EducationService

    education_service = EducationService(db)
    return education_service.can_access_course(user, course_id)
