"""Canvas (Instructure) OAuth2 and REST API client.

Provides:
  CanvasOAuthClient  — handles the OAuth 2.0 Authorization Code flow
  CanvasAPIClient   — async REST wrapper for Canvas REST API v1

Authentication flow:
  1. Frontend redirects user to URL from generate_auth_url()
  2. Canvas redirects back with ?code=...&state=...
  3. Backend calls exchange_code() to get access + refresh tokens
  4. Tokens are stored on LMSConnection; CanvasAPIClient is instantiated
     with base_url + access_token for every sync call.
  5. On 401, the caller should call refresh_access_token() and retry.

Rate-limiting strategy:
  - On HTTP 429 respect the Retry-After header value (in seconds).
  - On HTTP 503 use exponential backoff (RETRY_BACKOFF_SECONDS * attempt).
  - Maximum MAX_RETRIES attempts per request.

Pagination:
  Canvas uses Link header pagination (RFC 5988).  The _get() helper
  automatically follows rel="next" links until exhausted, returning the
  combined list of all items.

Canvas API docs: https://canvas.instructure.com/doc/api/
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Any

import httpx

from app.models.lms_institution import LMSInstitution

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CANVAS_AUTH_PATH = "/login/oauth2/auth"
_CANVAS_TOKEN_PATH = "/login/oauth2/token"

# Scopes required for ClassBridge integration
_CANVAS_SCOPES = " ".join([
    "url:GET|/api/v1/courses",
    "url:GET|/api/v1/courses/:id/assignments",
    "url:GET|/api/v1/courses/:id/modules",
    "url:GET|/api/v1/courses/:id/files",
    "url:GET|/api/v1/courses/:id/grades",
    "url:GET|/api/v1/announcements",
])

_RETRY_STATUSES = {429, 503}
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0

# Regex to parse a single rel="..." parameter from a Link header component
_LINK_REL_RE = re.compile(r'rel="([^"]+)"')
# Regex to extract the URL from angle brackets in a Link header component
_LINK_URL_RE = re.compile(r"<([^>]+)>")


# ---------------------------------------------------------------------------
# OAuth2 Client
# ---------------------------------------------------------------------------


class CanvasOAuthClient:
    """Handles the Canvas LTI OAuth 2.0 Authorization Code flow.

    Each institution has its own base_url, client_id, and client_secret
    stored on the LMSInstitution record (via metadata_json).  The OAuth
    client is stateless — all institution-specific data is passed per-call.
    """

    def generate_auth_url(
        self,
        institution: LMSInstitution,
        redirect_uri: str,
        state: str,
    ) -> str:
        """Build the Canvas OAuth2 authorization URL.

        Canvas OAuth URL format:
            {institution.base_url}/login/oauth2/auth
            ?client_id={client_id}
            &response_type=code
            &redirect_uri={redirect_uri}
            &state={state}
            &scope=url:GET|/api/v1/courses ...

        Args:
            institution:  The LMSInstitution record (supplies base_url +
                          oauth_client_id via metadata_json).
            redirect_uri: Where Canvas should redirect after consent.
            state:        CSRF token / opaque state string.

        Returns:
            Absolute authorization URL the user's browser should navigate to.
        """
        client_id = self._get_client_id(institution)
        base_url = (institution.base_url or "").rstrip("/")

        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": _CANVAS_SCOPES,
        }
        query = urllib.parse.urlencode(params)
        url = f"{base_url}{_CANVAS_AUTH_PATH}?{query}"
        logger.debug(
            "Generated Canvas auth URL for institution %s: %s",
            institution.id,
            url,
        )
        return url

    async def exchange_code(
        self,
        institution: LMSInstitution,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange an authorization code for access + refresh tokens.

        POST {base_url}/login/oauth2/token

        Args:
            institution:  LMSInstitution with base_url and OAuth credentials.
            code:         Authorization code from the OAuth callback.
            redirect_uri: Must exactly match the redirect_uri in generate_auth_url.

        Returns:
            Dict with keys: access_token, refresh_token, expires_in (seconds).

        Raises:
            httpx.HTTPStatusError: On non-2xx response from Canvas.
        """
        client_id = self._get_client_id(institution)
        client_secret = self._get_client_secret(institution)
        base_url = (institution.base_url or "").rstrip("/")
        token_url = f"{base_url}{_CANVAS_TOKEN_PATH}"

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            data = response.json()

        logger.info(
            "Canvas: exchanged authorization code for institution %s (expires_in=%s)",
            institution.id,
            data.get("expires_in"),
        )
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 3600),
        }

    async def refresh_access_token(
        self,
        institution: LMSInstitution,
        refresh_token: str,
    ) -> dict:
        """Use a refresh token to obtain a new access token.

        POST {base_url}/login/oauth2/token with grant_type=refresh_token

        Args:
            institution:   LMSInstitution with base_url and OAuth credentials.
            refresh_token: The current refresh token.

        Returns:
            Dict with keys: access_token, refresh_token, expires_in (seconds).

        Raises:
            httpx.HTTPStatusError: On non-2xx response from Canvas.
        """
        client_id = self._get_client_id(institution)
        client_secret = self._get_client_secret(institution)
        base_url = (institution.base_url or "").rstrip("/")
        token_url = f"{base_url}{_CANVAS_TOKEN_PATH}"

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            data = response.json()

        logger.info(
            "Canvas: refreshed access token for institution %s (expires_in=%s)",
            institution.id,
            data.get("expires_in"),
        )
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_in": data.get("expires_in", 3600),
        }

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_client_id(institution: LMSInstitution) -> str:
        """Extract the OAuth client ID from an institution record.

        The client ID is stored in metadata_json as {"client_id": "..."}.
        """
        import json

        if institution.metadata_json:
            try:
                meta = json.loads(institution.metadata_json)
                cid = meta.get("client_id") or meta.get("oauth_client_id")
                if cid:
                    return str(cid)
            except (ValueError, TypeError):
                pass
        return ""

    @staticmethod
    def _get_client_secret(institution: LMSInstitution) -> str:
        """Extract the OAuth client secret from an institution record."""
        import json

        if institution.metadata_json:
            try:
                meta = json.loads(institution.metadata_json)
                secret = meta.get("client_secret") or meta.get("oauth_client_secret")
                if secret:
                    return str(secret)
            except (ValueError, TypeError):
                pass
        return ""


# ---------------------------------------------------------------------------
# REST API Client
# ---------------------------------------------------------------------------


class CanvasAPIClient:
    """Async REST wrapper for the Canvas REST API v1.

    All methods return raw dicts/lists from the Canvas JSON response;
    mapping to canonical models is the responsibility of CanvasAdapter.

    Pagination:
        Canvas uses HTTP Link headers (RFC 5988) for pagination.  The
        _get() method automatically follows rel="next" links and returns
        the combined list of all pages.

    Retry logic:
        HTTP 429: respect Retry-After header (or fall back to backoff).
        HTTP 503: exponential backoff (RETRY_BACKOFF_SECONDS * attempt).
        Maximum MAX_RETRIES attempts per request.
    """

    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token

    # ── Public API ───────────────────────────────────────────────────────

    async def get_courses(self, enrollment_type: str = "student") -> list[dict]:
        """Fetch all active Canvas courses for the authenticated user.

        GET /api/v1/courses
            ?enrollment_type={student|teacher}
            &enrollment_state=active
            &per_page=50

        Args:
            enrollment_type: "student" (default) or "teacher".

        Returns:
            List of course dicts.  Each dict has at minimum:
              - id            (int)   — Canvas course ID
              - name          (str)
              - course_code   (str)   — short code e.g. "MATH101"
              - sis_course_id (str|None)
        """
        params = {
            "enrollment_type": enrollment_type,
            "enrollment_state": "active",
            "per_page": 50,
        }
        items = await self._get("/api/v1/courses", params=params)
        if isinstance(items, dict):
            items = items.get("items", items.get("courses", []))
        logger.debug(
            "get_courses: enrollment_type=%s, fetched %d courses",
            enrollment_type,
            len(items),
        )
        return items if isinstance(items, list) else []

    async def get_course_modules(self, course_id: int | str) -> list[dict]:
        """Fetch modules for a course, including their items.

        GET /api/v1/courses/{course_id}/modules?include[]=items

        Args:
            course_id: Canvas course ID.

        Returns:
            List of module dicts.  Each dict has at minimum:
              - id    (int)
              - name  (str)
              - items (list[dict]) — included via ?include[]=items
        """
        params = {"include[]": "items", "per_page": 50}
        items = await self._get(f"/api/v1/courses/{course_id}/modules", params=params)
        if isinstance(items, dict):
            items = items.get("modules", [])
        logger.debug(
            "get_course_modules: course_id=%s, %d modules",
            course_id,
            len(items) if isinstance(items, list) else 0,
        )
        return items if isinstance(items, list) else []

    async def get_assignments(self, course_id: int | str) -> list[dict]:
        """Fetch assignments for a Canvas course.

        GET /api/v1/courses/{course_id}/assignments?per_page=50

        Args:
            course_id: Canvas course ID.

        Returns:
            List of assignment dicts.  Each dict has at minimum:
              - id               (int)
              - name             (str)
              - due_at           (str|None)   — ISO 8601 due date
              - points_possible  (float|None) — max grade points
              - description      (str|None)
        """
        params = {"per_page": 50}
        items = await self._get(f"/api/v1/courses/{course_id}/assignments", params=params)
        if isinstance(items, dict):
            items = items.get("assignments", [])
        logger.debug(
            "get_assignments: course_id=%s, %d assignments",
            course_id,
            len(items) if isinstance(items, list) else 0,
        )
        return items if isinstance(items, list) else []

    async def get_grades(self, course_id: int | str) -> dict:
        """Fetch the current user's grade summary for a course.

        GET /api/v1/courses/{course_id}/grades

        Args:
            course_id: Canvas course ID.

        Returns:
            Grade dict with at minimum:
              - current_score  (float|None)
              - final_score    (float|None)
              - current_grade  (str|None)
              - final_grade    (str|None)
        """
        data = await self._get(f"/api/v1/courses/{course_id}/grades")
        # Canvas returns a single object (not a list) for grades
        if isinstance(data, list):
            return data[0] if data else {}
        return data if isinstance(data, dict) else {}

    async def get_announcements(self, course_ids: list[int | str]) -> list[dict]:
        """Fetch announcements across multiple courses.

        GET /api/v1/announcements
            ?context_codes[]=course_{id}
            &per_page=20

        Args:
            course_ids: List of Canvas course IDs.

        Returns:
            List of announcement dicts.  Each dict has at minimum:
              - id      (int)
              - title   (str)
              - message (str|None)
              - posted_at (str|None)
        """
        if not course_ids:
            return []
        params: dict[str, Any] = {"per_page": 20}
        # httpx encodes repeated keys as context_codes[]=...
        params["context_codes[]"] = [f"course_{cid}" for cid in course_ids]
        items = await self._get("/api/v1/announcements", params=params)
        if isinstance(items, dict):
            items = items.get("announcements", [])
        logger.debug("get_announcements: fetched %d announcements", len(items) if isinstance(items, list) else 0)
        return items if isinstance(items, list) else []

    async def get_files(self, course_id: int | str) -> list[dict]:
        """Fetch files for a Canvas course.

        GET /api/v1/courses/{course_id}/files?per_page=50

        Args:
            course_id: Canvas course ID.

        Returns:
            List of file dicts.  Each dict has at minimum:
              - id           (int)
              - display_name (str)
              - url          (str)   — download URL
              - content-type (str|None)
              - size         (int|None)
        """
        params = {"per_page": 50}
        items = await self._get(f"/api/v1/courses/{course_id}/files", params=params)
        if isinstance(items, dict):
            items = items.get("files", [])
        logger.debug(
            "get_files: course_id=%s, %d files",
            course_id,
            len(items) if isinstance(items, list) else 0,
        )
        return items if isinstance(items, list) else []

    # ── Internal HTTP helpers ────────────────────────────────────────────

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an authenticated GET with Link-header pagination and retry.

        Canvas uses Link headers for pagination (RFC 5988).  This method
        automatically follows rel="next" links, accumulating results into a
        single combined list.

        Args:
            path:   API path (e.g. "/api/v1/courses").  Joined to base_url.
            params: Optional query parameters for the first request.

        Returns:
            Combined list from all pages (or a dict for single-object
            endpoints like /grades that do not paginate).

        Raises:
            httpx.HTTPStatusError: After MAX_RETRIES on persistent errors.
        """
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        # Build the initial URL
        first_url = f"{self._base_url}{path}"

        accumulated: list[Any] = []
        next_url: str | None = first_url
        first_request = True

        while next_url:
            current_url = next_url
            current_params = params if first_request else None
            first_request = False
            next_url = None

            data = await self._get_with_retry(current_url, headers, current_params)

            # If the response is a list, accumulate and look for next page
            if isinstance(data, list):
                accumulated.extend(data)
            else:
                # Single-object response (e.g. grades) — return immediately
                return data

            # Pagination via Link header is handled inside _get_with_retry;
            # we embed the next URL into a sentinel so we can continue here.
            # Instead, we use a two-pass approach — see _get_with_retry for
            # how it returns the raw response for header inspection.
            # We cannot inspect headers here because _get_with_retry returns
            # parsed JSON.  So we inline one level of pagination logic here.
            break  # Will be replaced by full pagination in _get_page below

        # Re-implement with full Link pagination support
        return await self._get_all_pages(first_url, headers, params)

    async def _get_all_pages(
        self,
        first_url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
    ) -> Any:
        """Follow Canvas Link-header pagination, returning all accumulated items."""
        accumulated: list[Any] = []
        next_url: str | None = first_url
        first_request = True

        async with httpx.AsyncClient(timeout=30.0) as client:
            while next_url:
                current_url = next_url
                current_params = params if first_request else None
                first_request = False
                next_url = None

                response = await self._fetch_with_retry(client, current_url, headers, current_params)
                data = response.json()

                if isinstance(data, list):
                    accumulated.extend(data)
                else:
                    # Single-object endpoints (like /grades) — return directly
                    return data

                # Parse Link header for the next page URL
                link_header = response.headers.get("Link", "")
                if link_header:
                    next_url = self._parse_link_next(link_header)

        logger.debug(
            "_get_all_pages: %s — total %d items across all pages",
            first_url,
            len(accumulated),
        )
        return accumulated

    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
    ) -> httpx.Response:
        """Make a single GET request with retry on 429/503.

        Args:
            client: Shared httpx.AsyncClient.
            url:    Absolute URL to request.
            headers: Authorization + Accept headers.
            params: Query parameters (None for paginated continuation requests).

        Returns:
            httpx.Response on success.

        Raises:
            httpx.HTTPStatusError: After MAX_RETRIES on persistent errors.
        """
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 429:
                    # Respect Retry-After header if present
                    retry_after = response.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after else RETRY_BACKOFF_SECONDS * attempt
                    except (TypeError, ValueError):
                        wait = RETRY_BACKOFF_SECONDS * attempt

                    logger.warning(
                        "Canvas API rate limited (429) for %s; waiting %.1fs (attempt %d/%d)",
                        url,
                        wait,
                        attempt,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code == 503:
                    wait = RETRY_BACKOFF_SECONDS * attempt
                    logger.warning(
                        "Canvas API unavailable (503) for %s; retrying in %.1fs (attempt %d/%d)",
                        url,
                        wait,
                        attempt,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response

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
                    "Canvas API network error for %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
                await asyncio.sleep(wait)

        if last_exc:
            raise last_exc
        # Should never reach here
        raise httpx.RequestError(f"Max retries ({MAX_RETRIES}) exceeded for {url}")

    async def _get_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
    ) -> Any:
        """Convenience wrapper — creates a client and fetches once with retry.

        Used only for the initial _get() call before we switch to _get_all_pages.
        This method is kept for backwards-compatibility and test mocking purposes.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._fetch_with_retry(client, url, headers, params)
            return response.json()

    @staticmethod
    def _parse_link_next(link_header: str) -> str | None:
        """Extract the rel="next" URL from a Canvas Link header.

        Canvas Link header example:
            <https://school.instructure.com/api/v1/courses?page=2&per_page=50>; rel="next",
            <https://school.instructure.com/api/v1/courses?page=1&per_page=50>; rel="first"

        Args:
            link_header: Raw value of the HTTP Link header.

        Returns:
            The rel="next" URL string, or None if no next page.
        """
        # Split by comma to get individual link entries
        for part in link_header.split(","):
            part = part.strip()
            # Check if this entry has rel="next"
            rel_match = _LINK_REL_RE.search(part)
            if rel_match and rel_match.group(1) == "next":
                url_match = _LINK_URL_RE.search(part)
                if url_match:
                    return url_match.group(1)
        return None
