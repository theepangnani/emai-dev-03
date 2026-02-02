import logging
from datetime import datetime

from googleapiclient.errors import HttpError
from app.services.google_classroom import get_classroom_service

logger = logging.getLogger(__name__)


def fetch_classroom_announcements(
    access_token: str,
    refresh_token: str | None,
    course_ids: list[str] | None = None,
) -> tuple[list[dict], object]:
    """
    Fetch announcements from Google Classroom courses.

    Returns list of parsed announcement dicts and credentials.
    """
    service, credentials = get_classroom_service(access_token, refresh_token)

    if not course_ids:
        try:
            courses_result = service.courses().list(
                pageSize=100, courseStates=["ACTIVE"]
            ).execute()
            courses = courses_result.get("courses", [])
            course_ids = [c["id"] for c in courses]
        except HttpError as e:
            logger.error(f"Failed to list courses: {e}")
            return [], credentials

    announcements = []
    course_name_map = {}

    for cid in course_ids:
        try:
            course = service.courses().get(id=cid).execute()
            course_name_map[cid] = course.get("name", "Unknown Course")
        except HttpError:
            course_name_map[cid] = "Unknown Course"

    for cid in course_ids:
        try:
            result = service.courses().announcements().list(
                courseId=cid, pageSize=50
            ).execute()

            for ann in result.get("announcements", []):
                announcements.append({
                    "source_id": f"ann_{ann['id']}",
                    "sender_name": ann.get("creatorUserId", "Teacher"),
                    "sender_email": None,
                    "subject": f"Announcement: {course_name_map.get(cid, 'Course')}",
                    "body": ann.get("text", ""),
                    "snippet": (ann.get("text", ""))[:200],
                    "course_name": course_name_map.get(cid),
                    "course_id": cid,
                    "received_at": _parse_classroom_time(
                        ann.get("updateTime") or ann.get("creationTime")
                    ),
                })
        except HttpError as e:
            logger.warning(f"Failed to fetch announcements for course {cid}: {e}")

    return announcements, credentials


def _parse_classroom_time(time_str: str | None) -> datetime | None:
    """Parse Google Classroom timestamp."""
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
