from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


def get_google_auth_flow() -> Flow:
    """Create OAuth flow for Google Classroom."""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def get_authorization_url(state: str | None = None) -> tuple[str, str]:
    """Get the Google OAuth authorization URL."""
    flow = get_google_auth_flow()
    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return authorization_url, returned_state


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    flow = get_google_auth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }


def get_credentials(access_token: str, refresh_token: str | None = None) -> Credentials:
    """Get Google credentials with automatic refresh capability."""
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    return credentials


def refresh_credentials(credentials: Credentials) -> dict | None:
    """Refresh expired credentials and return new tokens."""
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
    return None


def get_classroom_service(access_token: str, refresh_token: str | None = None):
    """Build Google Classroom API service with auto-refresh."""
    credentials = get_credentials(access_token, refresh_token)

    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    return build("classroom", "v1", credentials=credentials), credentials


def get_user_info(access_token: str) -> dict:
    """Get user info from Google."""
    credentials = Credentials(token=access_token)
    service = build("oauth2", "v2", credentials=credentials)
    return service.userinfo().get().execute()


def list_courses(access_token: str, refresh_token: str | None = None) -> tuple[list[dict], Credentials]:
    """List all courses for the authenticated user."""
    service, credentials = get_classroom_service(access_token, refresh_token)
    results = service.courses().list(pageSize=100).execute()
    return results.get("courses", []), credentials


def get_course_work(
    access_token: str,
    course_id: str,
    refresh_token: str | None = None,
) -> tuple[list[dict], Credentials]:
    """Get all coursework (assignments) for a course."""
    service, credentials = get_classroom_service(access_token, refresh_token)
    try:
        results = service.courses().courseWork().list(courseId=course_id, pageSize=100).execute()
        return results.get("courseWork", []), credentials
    except Exception:
        return [], credentials


def get_student_submissions(
    access_token: str,
    course_id: str,
    coursework_id: str,
    refresh_token: str | None = None,
) -> tuple[list[dict], Credentials]:
    """Get student submissions for a coursework item."""
    service, credentials = get_classroom_service(access_token, refresh_token)
    try:
        results = (
            service.courses()
            .courseWork()
            .studentSubmissions()
            .list(courseId=course_id, courseWorkId=coursework_id)
            .execute()
        )
        return results.get("studentSubmissions", []), credentials
    except Exception:
        return [], credentials
