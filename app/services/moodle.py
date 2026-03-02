"""Moodle REST API client.

Provides:
  MoodleOAuthClient  — handles Moodle token-based authentication
  MoodleAPIClient   — async REST wrapper for Moodle Web Services API

Authentication flow:
  Moodle does not use OAuth2 Authorization Code flow.  Instead it uses a
  token-based approach:

  Option A — Username/password exchange (server-side):
    1. POST /login/token.php with username, password, service
    2. Moodle returns {token, privatetoken}
    3. Use token for all subsequent API calls

  Option B — Manual token entry (recommended for ClassBridge):
    1. Admin generates a Web Service token in Moodle admin panel
    2. User pastes the token into ClassBridge
    3. Backend validates via core_webservice_get_site_info
    4. Token is stored on LMSConnection.access_token_enc

  All API calls are POST to:
    {base_url}/webservice/rest/server.php
  with form-encoded body:
    wstoken={token}
    moodlewsrestformat=json
    wsfunction={function_name}
    ...additional params...

  Error responses from Moodle return HTTP 200 with JSON body:
    {"exception": "...", "errorcode": "...", "message": "..."}

Rate-limiting strategy:
  - On HTTP 429 or 503 wait RETRY_BACKOFF_SECONDS between retries.
  - Maximum MAX_RETRIES attempts per request.

Moodle Web Services docs: https://docs.moodle.org/dev/Web_service_API_functions
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOKEN_PATH = "/login/token.php"
_WS_PATH = "/webservice/rest/server.php"
_MOODLE_SERVICE = "moodle_mobile_app"

_RETRY_STATUSES = {429, 503}
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


# ---------------------------------------------------------------------------
# OAuth / Token Client
# ---------------------------------------------------------------------------


class MoodleOAuthClient:
    """Handles Moodle token-based authentication.

    Moodle uses a REST token (not OAuth2 Authorization Code).  This client
    supports two flows:
      1. Username/password exchange — POST /login/token.php
      2. Manual token entry — user pastes a pre-generated Web Service token

    For ClassBridge integration we use the manual token entry flow because:
      - OAuth2 is not natively supported by most Moodle installations
      - Web Service tokens are easy to generate and revoke in Moodle admin
      - No client_id / client_secret configuration is required per institution
    """

    def get_auth_url(self, institution) -> str:
        """Return a Moodle token entry page URL.

        Since Moodle does not support OAuth2 redirect flows, this returns a
        JSON-describing URL that the frontend uses to show a manual token
        entry form rather than a browser redirect.

        Args:
            institution: LMSInstitution with base_url.

        Returns:
            A JSON-info string formatted as a URL.  The frontend should
            detect this provider type (supports_oauth=False) and display the
            manual token entry form instead of redirecting.
        """
        base_url = (institution.base_url or "").rstrip("/")
        # Point the user to the Moodle admin token management page
        token_page = f"{base_url}/admin/settings.php?section=webservicetokens"
        return token_page

    async def authenticate(
        self,
        username: str,
        password: str,
        base_url: str,
        service: str = _MOODLE_SERVICE,
    ) -> dict:
        """Authenticate with Moodle via username + password.

        POST {base_url}/login/token.php
          ?username={username}
          &password={password}
          &service={service}

        Args:
            username: Moodle username.
            password: Moodle password.
            base_url: Institution's Moodle base URL (e.g. "https://moodle.school.edu").
            service:  Moodle Web Service name (default: "moodle_mobile_app").

        Returns:
            Dict with keys: token, privatetoken (privatetoken may be empty).

        Raises:
            ValueError: If Moodle returns an error in the response body.
            httpx.HTTPStatusError: On non-2xx HTTP response.
        """
        url = f"{base_url.rstrip('/')}{_TOKEN_PATH}"
        params = {
            "username": username,
            "password": password,
            "service": service,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params=params)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise ValueError(f"Moodle authentication failed: {data.get('error')} — {data.get('debuginfo', '')}")

        token = data.get("token", "")
        if not token:
            raise ValueError("Moodle returned an empty token.")

        logger.info("Moodle: authenticated user '%s' at %s", username, base_url)
        return {
            "token": token,
            "privatetoken": data.get("privatetoken", ""),
        }

    async def validate_token(self, token: str, base_url: str) -> dict:
        """Validate a Moodle Web Service token by calling core_webservice_get_site_info.

        GET {base_url}/webservice/rest/server.php
          ?wsfunction=core_webservice_get_site_info
          &wstoken={token}
          &moodlewsrestformat=json

        Args:
            token:    The Moodle Web Service token to validate.
            base_url: Institution's Moodle base URL.

        Returns:
            Dict with site info including: sitename, username, userid, siteurl,
            release, functions (list of available WS functions).

        Raises:
            ValueError: If the token is invalid or Moodle returns an exception.
            httpx.HTTPStatusError: On non-2xx HTTP response.
        """
        url = f"{base_url.rstrip('/')}{_WS_PATH}"
        params = {
            "wsfunction": "core_webservice_get_site_info",
            "wstoken": token,
            "moodlewsrestformat": "json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, dict) and "exception" in data:
            raise ValueError(
                f"Moodle token validation failed: {data.get('exception')} "
                f"({data.get('errorcode')}) — {data.get('message', '')}"
            )

        logger.info(
            "Moodle: validated token for site '%s' (userid=%s)",
            data.get("sitename"),
            data.get("userid"),
        )
        return data


# ---------------------------------------------------------------------------
# REST API Client
# ---------------------------------------------------------------------------


class MoodleAPIClient:
    """Async REST wrapper for the Moodle Web Services API.

    All Moodle Web Service calls are POST to:
        {base_url}/webservice/rest/server.php

    with form-encoded body:
        wstoken={token}
        moodlewsrestformat=json
        wsfunction={function_name}
        ...additional params...

    Moodle returns HTTP 200 for both success and error responses.
    Error responses have {"exception": ..., "errorcode": ..., "message": ...}.

    Retry logic:
        HTTP 429 and 503 are retried up to MAX_RETRIES times with an
        exponential backoff (RETRY_BACKOFF_SECONDS * attempt).
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._ws_url = f"{self._base_url}{_WS_PATH}"

    # ── Public API ───────────────────────────────────────────────────────

    async def get_site_info(self) -> dict:
        """Fetch Moodle site info (also used for token validation).

        wsfunction: core_webservice_get_site_info

        Returns:
            Dict with: sitename, username, userid, siteurl, release,
            functions (list of enabled WS functions).
        """
        data = await self._post({"wsfunction": "core_webservice_get_site_info"})
        if not isinstance(data, dict):
            return {}
        logger.debug(
            "get_site_info: sitename=%s userid=%s",
            data.get("sitename"),
            data.get("userid"),
        )
        return data

    async def get_courses(self, user_id: int | str) -> list[dict]:
        """Fetch all courses the user is enrolled in.

        wsfunction: core_enrol_get_users_courses

        Args:
            user_id: Moodle user ID (from get_site_info()["userid"]).

        Returns:
            List of course dicts.  Each dict has at minimum:
              - id         (int)   — Moodle course ID
              - fullname   (str)   — full course name
              - shortname  (str)   — short course code
              - summary    (str)   — course description
              - format     (str)   — course format ("weeks", "topics", etc.)
        """
        data = await self._post({
            "wsfunction": "core_enrol_get_users_courses",
            "userid": str(user_id),
        })
        if isinstance(data, dict) and "exception" in data:
            logger.warning("get_courses: Moodle error — %s", data.get("message"))
            return []
        result = data if isinstance(data, list) else []
        logger.debug("get_courses: user_id=%s, fetched %d courses", user_id, len(result))
        return result

    async def get_assignments(self, course_id: int | str) -> list[dict]:
        """Fetch assignments for a Moodle course.

        wsfunction: mod_assign_get_assignments

        Args:
            course_id: Moodle course ID.

        Returns:
            List of assignment dicts.  Each dict has at minimum:
              - id          (int)
              - name        (str)
              - duedate     (int)  — Unix timestamp (0 = no due date)
              - grade       (str)  — max grade/points
              - intro       (str)  — assignment description
        """
        data = await self._post({
            "wsfunction": "mod_assign_get_assignments",
            "courseids[0]": str(course_id),
        })
        if isinstance(data, dict):
            if "exception" in data:
                logger.warning("get_assignments: Moodle error — %s", data.get("message"))
                return []
            # Response shape: {"courses": [{"id": ..., "assignments": [...]}]}
            courses = data.get("courses", [])
            assignments: list[dict] = []
            for course_data in courses:
                assignments.extend(course_data.get("assignments", []))
            logger.debug(
                "get_assignments: course_id=%s, %d assignments",
                course_id,
                len(assignments),
            )
            return assignments
        return []

    async def get_grades(self, course_id: int | str) -> dict:
        """Fetch grade overview for a Moodle course.

        wsfunction: gradereport_overview_get_course_grade

        Args:
            course_id: Moodle course ID.

        Returns:
            Dict with grade info.  May include:
              - grade    (str)  — current grade
              - rawgrade (str)  — raw grade value
        """
        data = await self._post({
            "wsfunction": "gradereport_overview_get_course_grade",
            "courseid": str(course_id),
        })
        if isinstance(data, dict) and "exception" in data:
            logger.warning("get_grades: Moodle error — %s", data.get("message"))
            return {}
        return data if isinstance(data, dict) else {}

    async def get_course_contents(self, course_id: int | str) -> list[dict]:
        """Fetch course sections + module contents.

        wsfunction: core_course_get_contents

        Args:
            course_id: Moodle course ID.

        Returns:
            List of section dicts.  Each section has a "modules" list.
            Each module has:
              - id          (int)
              - name        (str)
              - modname     (str)   — "resource", "assign", "forum", etc.
              - contents    (list)  — list of file/URL content items
        """
        data = await self._post({
            "wsfunction": "core_course_get_contents",
            "courseid": str(course_id),
        })
        if isinstance(data, dict) and "exception" in data:
            logger.warning("get_course_contents: Moodle error — %s", data.get("message"))
            return []
        result = data if isinstance(data, list) else []
        logger.debug(
            "get_course_contents: course_id=%s, %d sections",
            course_id,
            len(result),
        )
        return result

    async def get_announcements(self, course_id: int | str) -> list[dict]:
        """Fetch announcements for a Moodle course.

        Strategy:
          1. Get course contents to find the news forum (modname="forum")
          2. Call mod_forum_get_forum_discussions with the forum instance ID

        Args:
            course_id: Moodle course ID.

        Returns:
            List of discussion dicts.  Each dict has at minimum:
              - id        (int)
              - name      (str)   — discussion subject
              - message   (str)   — post body
              - created   (int)   — Unix timestamp
        """
        # Step 1: Find the news forum via course contents
        sections = await self.get_course_contents(course_id)
        forum_id: int | None = None
        for section in sections:
            for module in section.get("modules", []):
                if module.get("modname") == "forum":
                    forum_id = module.get("instance")
                    break
            if forum_id:
                break

        if not forum_id:
            logger.debug(
                "get_announcements: no forum found for course_id=%s", course_id
            )
            return []

        # Step 2: Get discussions for the forum
        data = await self._post({
            "wsfunction": "mod_forum_get_forum_discussions",
            "forumid": str(forum_id),
        })
        if isinstance(data, dict):
            if "exception" in data:
                logger.warning("get_announcements: Moodle error — %s", data.get("message"))
                return []
            discussions = data.get("discussions", [])
        elif isinstance(data, list):
            discussions = data
        else:
            discussions = []

        logger.debug(
            "get_announcements: course_id=%s forumid=%s, %d discussions",
            course_id,
            forum_id,
            len(discussions),
        )
        return discussions

    async def get_files(self, course_id: int | str) -> list[dict]:
        """Fetch file resources for a Moodle course.

        Uses core_course_get_contents and extracts modules with modname="resource"
        along with their file content items.

        Args:
            course_id: Moodle course ID.

        Returns:
            List of file content dicts.  Each dict has at minimum:
              - filename    (str)   — file name
              - fileurl     (str)   — download URL (requires ?token=... appended)
              - filesize    (int)   — size in bytes
              - mimetype    (str)   — MIME type
              - module_name (str)   — parent module name (added by us)
        """
        sections = await self.get_course_contents(course_id)
        files: list[dict] = []
        for section in sections:
            for module in section.get("modules", []):
                if module.get("modname") == "resource":
                    for content_item in module.get("contents", []):
                        if content_item.get("type") == "file":
                            enriched = dict(content_item)
                            enriched["module_name"] = module.get("name", "")
                            enriched["module_id"] = module.get("id")
                            files.append(enriched)
        logger.debug(
            "get_files: course_id=%s, %d files", course_id, len(files)
        )
        return files

    # ── Internal HTTP helpers ────────────────────────────────────────────

    async def _post(
        self,
        params: dict[str, Any],
    ) -> Any:
        """POST to Moodle Web Services endpoint with retry on 429/503.

        All Moodle WS calls use POST with form-encoded body.  The wstoken
        and moodlewsrestformat=json parameters are always added automatically.

        Args:
            params: Additional form parameters (must include "wsfunction").

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            httpx.HTTPStatusError: After MAX_RETRIES on persistent HTTP errors.
            ValueError: If Moodle returns an exception in the response body.
        """
        body: dict[str, str] = {
            "wstoken": self._token,
            "moodlewsrestformat": "json",
        }
        body.update({k: str(v) for k, v in params.items()})

        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response = await client.post(self._ws_url, data=body)

                    if response.status_code in _RETRY_STATUSES:
                        wait = RETRY_BACKOFF_SECONDS * attempt
                        logger.warning(
                            "Moodle API returned %s for %s; retrying in %.1fs "
                            "(attempt %d/%d)",
                            response.status_code,
                            params.get("wsfunction"),
                            wait,
                            attempt,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Moodle returns HTTP 200 even for errors — check JSON body
                    if isinstance(data, dict) and "exception" in data:
                        error_code = data.get("errorcode", "")
                        message = data.get("message", "")
                        logger.warning(
                            "Moodle WS exception for %s: %s (%s)",
                            params.get("wsfunction"),
                            error_code,
                            message,
                        )
                        # Return the error dict so callers can handle it
                        return data

                    return data

                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in _RETRY_STATUSES:
                        last_exc = exc
                        wait = RETRY_BACKOFF_SECONDS * attempt
                        await asyncio.sleep(wait)
                        continue
                    raise
                except httpx.RequestError as exc:
                    last_exc = exc
                    wait = RETRY_BACKOFF_SECONDS * attempt
                    logger.warning(
                        "Moodle network error for %s (attempt %d/%d): %s",
                        params.get("wsfunction"),
                        attempt,
                        MAX_RETRIES,
                        exc,
                    )
                    await asyncio.sleep(wait)

        if last_exc:
            raise last_exc
        return {}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def parse_unix_timestamp(ts: int | float | None) -> datetime | None:
    """Convert a Moodle Unix timestamp to a timezone-aware UTC datetime.

    Args:
        ts: Unix timestamp (seconds since epoch).  0 means "no date".

    Returns:
        UTC datetime, or None if ts is 0 / None / invalid.
    """
    if not ts:
        return None
    try:
        ts_int = int(ts)
        if ts_int <= 0:
            return None
        return datetime.fromtimestamp(ts_int, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def map_module_content_type(modname: str) -> str:
    """Map a Moodle module name to a CourseContent content_type string.

    Moodle modname values:
      "resource"  → "document"   (file resources)
      "url"       → "resources"  (external URL links)
      "page"      → "notes"      (Moodle pages / text content)
      "folder"    → "document"   (folder of files)
      Other       → "other"

    Args:
        modname: Moodle module name (e.g. "resource", "url", "page").

    Returns:
        CourseContent.content_type string.
    """
    mapping = {
        "resource": "document",
        "url": "resources",
        "page": "notes",
        "folder": "document",
        "book": "notes",
        "wiki": "notes",
    }
    return mapping.get(modname, "other")
