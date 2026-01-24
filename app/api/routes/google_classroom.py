from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.services.google_classroom import (
    get_authorization_url,
    exchange_code_for_tokens,
    get_user_info,
    list_courses,
    get_course_work,
)

router = APIRouter(prefix="/google", tags=["Google Classroom"])


@router.get("/auth")
def google_auth():
    """Redirect to Google OAuth consent screen."""
    authorization_url, state = get_authorization_url()
    return {"authorization_url": authorization_url, "state": state}


@router.get("/callback")
def google_callback(
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback."""
    try:
        tokens = exchange_code_for_tokens(code)
        user_info = get_user_info(tokens["access_token"])

        # Find or create user
        user = db.query(User).filter(User.google_id == user_info["id"]).first()
        if not user:
            user = db.query(User).filter(User.email == user_info["email"]).first()

        if user:
            # Update existing user with Google tokens
            user.google_id = user_info["id"]
            user.google_access_token = tokens["access_token"]
            user.google_refresh_token = tokens.get("refresh_token")
        else:
            # Create new user
            from app.models.user import UserRole
            user = User(
                email=user_info["email"],
                full_name=user_info.get("name", user_info["email"]),
                role=UserRole.STUDENT,
                google_id=user_info["id"],
                google_access_token=tokens["access_token"],
                google_refresh_token=tokens.get("refresh_token"),
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        # Create access token for our app
        from app.core.security import create_access_token
        access_token = create_access_token(data={"sub": str(user.id)})

        return {
            "message": "Successfully authenticated with Google",
            "access_token": access_token,
            "token_type": "bearer",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {str(e)}",
        )


@router.get("/courses")
def get_google_courses(
    current_user: User = Depends(get_current_user),
):
    """List all Google Classroom courses for the authenticated user."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    courses = list_courses(
        current_user.google_access_token,
        current_user.google_refresh_token,
    )
    return {"courses": courses}


@router.get("/courses/{course_id}/assignments")
def get_google_assignments(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get all assignments for a Google Classroom course."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    coursework = get_course_work(
        current_user.google_access_token,
        course_id,
        current_user.google_refresh_token,
    )
    return {"assignments": coursework}
