from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.user import User, UserRole

# auto_error=False so missing Authorization header does NOT 401 immediately —
# we fall back to httpOnly cookie before raising.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Repository dependency factories
#
# Usage in route handlers:
#   from app.api.deps import get_task_repo
#
#   @router.get("/")
#   def list_tasks(repo: TaskRepository = Depends(get_task_repo)):
#       return repo.list_for_user(...)
#
# The factory pattern keeps repository construction out of route bodies and
# makes it trivial to swap implementations or inject mocks in tests.
# ---------------------------------------------------------------------------


def get_task_repo(db: Session = Depends(get_db)):
    """FastAPI dependency that returns a TaskRepository bound to the current DB session."""
    from app.repositories.task_repository import TaskRepository
    return TaskRepository(db)


def get_course_content_repo(db: Session = Depends(get_db)):
    """FastAPI dependency that returns a CourseContentRepository bound to the current DB session."""
    from app.repositories.course_content_repository import CourseContentRepository
    return CourseContentRepository(db)


def get_study_guide_repo(db: Session = Depends(get_db)):
    """FastAPI dependency that returns a StudyGuideRepository bound to the current DB session."""
    from app.repositories.study_guide_repository import StudyGuideRepository
    return StudyGuideRepository(db)


def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Prefer explicit Authorization: Bearer header (mobile / API / test clients)
    token = bearer_token

    # 2. Fall back to httpOnly cookie (web clients — cookie sent automatically)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Check token blacklist (revoked tokens)
    jti = payload.get("jti")
    if jti:
        from app.models.token_blacklist import TokenBlacklist
        revoked = db.query(TokenBlacklist.id).filter(TokenBlacklist.jti == jti).first()
        if revoked:
            raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    # Make user ID available for rate limiter and request logging
    request.state.user_id = user.id

    return user


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
