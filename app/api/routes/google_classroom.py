from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.assignment import Assignment
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.services.google_classroom import (
    get_authorization_url,
    exchange_code_for_tokens,
    get_user_info,
    list_courses,
    get_course_work,
)

router = APIRouter(prefix="/google", tags=["Google Classroom"])


def update_user_tokens(user: User, credentials, db: Session):
    """Update user's Google tokens if they were refreshed."""
    if credentials.token != user.google_access_token:
        user.google_access_token = credentials.token
        if credentials.refresh_token:
            user.google_refresh_token = credentials.refresh_token
        db.commit()


@router.get("/auth")
def google_auth(user_id: int | None = None):
    """Get Google OAuth authorization URL.

    If user_id is provided, it will be included in the state to link
    the Google account to an existing user after callback.
    """
    state = str(user_id) if user_id else None
    authorization_url, returned_state = get_authorization_url(state)
    return {"authorization_url": authorization_url, "state": returned_state}


@router.get("/connect")
def google_connect(current_user: User = Depends(get_current_user)):
    """Get authorization URL for connecting Google to existing account."""
    state = f"connect:{current_user.id}"
    authorization_url, _ = get_authorization_url(state)
    return {"authorization_url": authorization_url}


@router.get("/callback")
def google_callback(
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

    try:
        tokens = exchange_code_for_tokens(code)
        user_info = get_user_info(tokens["access_token"])

        # Check if this is a connect request for existing user
        if state and state.startswith("connect:"):
            user_id = int(state.split(":")[1])
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.google_id = user_info["id"]
                user.google_access_token = tokens["access_token"]
                user.google_refresh_token = tokens.get("refresh_token")
                db.commit()

                # Redirect to dashboard with success
                params = urlencode({"google_connected": "true"})
                return RedirectResponse(url=f"{settings.frontend_url}/dashboard?{params}")

        # Find existing user by Google ID or email
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
        access_token = create_access_token(data={"sub": str(user.id)})

        # Redirect to frontend with token
        params = urlencode({"token": access_token})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")

    except Exception as e:
        params = urlencode({"error": str(e)})
        return RedirectResponse(url=f"{settings.frontend_url}/login?{params}")


@router.get("/status")
def google_status(current_user: User = Depends(get_current_user)):
    """Check if user has connected Google Classroom."""
    return {
        "connected": bool(current_user.google_access_token),
        "google_email": None,  # Could fetch from Google if needed
    }


@router.delete("/disconnect")
def google_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect Google Classroom from user account."""
    current_user.google_id = None
    current_user.google_access_token = None
    current_user.google_refresh_token = None
    db.commit()
    return {"message": "Google Classroom disconnected"}


@router.get("/courses")
def get_google_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all Google Classroom courses for the authenticated user."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    courses, credentials = list_courses(
        current_user.google_access_token,
        current_user.google_refresh_token,
    )

    # Update tokens if refreshed
    update_user_tokens(current_user, credentials, db)

    return {"courses": courses}


@router.post("/courses/sync")
def sync_google_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync Google Classroom courses to local database."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not connected to Google Classroom",
        )

    # Fetch courses from Google
    google_courses, credentials = list_courses(
        current_user.google_access_token,
        current_user.google_refresh_token,
    )

    # Update tokens if refreshed
    update_user_tokens(current_user, credentials, db)

    synced_courses = []
    for gc in google_courses:
        # Check if course already exists
        existing = db.query(Course).filter(
            Course.google_classroom_id == gc["id"]
        ).first()

        if existing:
            # Update existing course
            existing.name = gc.get("name", existing.name)
            existing.description = gc.get("description")
            synced_courses.append(existing)
        else:
            # Create new course
            course = Course(
                name=gc.get("name", "Untitled Course"),
                description=gc.get("description"),
                subject=gc.get("section"),
                google_classroom_id=gc["id"],
            )
            db.add(course)
            synced_courses.append(course)

    db.commit()

    return {
        "message": f"Synced {len(synced_courses)} courses",
        "courses": [{"id": c.id, "name": c.name, "google_id": c.google_classroom_id} for c in synced_courses],
    }


@router.get("/courses/{course_id}/assignments")
def get_google_assignments(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
def sync_google_assignments(
    google_course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
