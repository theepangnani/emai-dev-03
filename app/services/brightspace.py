"""Brightspace (D2L) OAuth2 and REST API client.

Provides:
  BrightspaceOAuthClient — handles the OAuth 2.0 Authorization Code flow
  BrightspaceAPIClient  — async REST wrapper for Brightspace LP/LE APIs

Authentication flow:
  1. Frontend redirects user to URL from generate_auth_url()
  2. Brightspace redirects back with ?code=...&state=...
  3. Backend calls exchange_code() to get access + refresh tokens
  4. Tokens are stored on LMSConnection; BrightspaceAPIClient is instantiated
     with base_url + access_token for every sync call.
  5. On 401, the caller should call refresh_access_token() and retry.

Rate-limiting strategy:
  - On HTTP 429 or 503 wait RETRY_BACKOFF_SECONDS between retries.
  - Maximum MAX_RETRIES attempts per request.

Brightspace API versions used:
  - LP (Learning Platform) 1.28 — enrollments
  - LE (Learning Environment) 1.52 — content, assignments, grades, announcements
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import Any

import httpx

from app.models.lms_institution import LMSInstitution

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LP_VERSION = "1.28"
_LE_VERSION = "1.52"
_OAUTH_PATH = "/d2l/auth/api/token"
_AUTH_PATH = "/d2l/auth/api/oauth2/auth"
_RETRY_STATUSES = {429, 503}
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


# ---------------------------------------------------------------------------
# OAuth2 Client
# ---------------------------------------------------------------------------


class BrightspaceOAuthClient:
    """Handles the Brightspace OAuth 2.0 Authorization Code flow.

    Each institution has its own base_url, client_id, and client_secret
    stored on the LMSInstitution record.  The OAuth client is stateless —
    all institution-specific data is passed per-call.
    """

    def generate_auth_url(
        self,
        institution: LMSInstitution,
        redirect_uri: str,
        state: str,
    ) -> str:
        """Build the Brightspace OAuth2 authorization URL.

        Args:
            institution:  The LMSInstitution record (supplies base_url +
                          oauth_client_id via metadata_json or direct fields).
            redirect_uri: Where Brightspace should redirect after consent.
            state:        CSRF token / opaque state string.

        Returns:
            Absolute authorization URL the user's browser should navigate to.
        """
        client_id = self._get_client_id(institution)
        base_url = institution.base_url or ""

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "core:*:*",
        }
        query = urllib.parse.urlencode(params)
        url = f"{base_url.rstrip('/')}{_AUTH_PATH}?{query}"
        logger.debug(
            "Generated Brightspace auth URL for institution %s: %s",
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

        Args:
            institution:  LMSInstitution with base_url and OAuth credentials.
            code:         Authorization code from the OAuth callback.
            redirect_uri: Must exactly match the redirect_uri in generate_auth_url.

        Returns:
            Dict with keys: access_token, refresh_token, expires_in (seconds).

        Raises:
            httpx.HTTPStatusError: On non-2xx response from Brightspace.
        """
        client_id = self._get_client_id(institution)
        client_secret = self._get_client_secret(institution)
        base_url = institution.base_url or ""
        token_url = f"{base_url.rstrip('/')}{_OAUTH_PATH}"

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
            "Exchanged authorization code for institution %s (expires_in=%s)",
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

        Args:
            institution:   LMSInstitution with base_url and OAuth credentials.
            refresh_token: The current refresh token.

        Returns:
            Dict with keys: access_token, refresh_token, expires_in (seconds).

        Raises:
            httpx.HTTPStatusError: On non-2xx response from Brightspace.
        """
        client_id = self._get_client_id(institution)
        client_secret = self._get_client_secret(institution)
        base_url = institution.base_url or ""
        token_url = f"{base_url.rstrip('/')}{_OAUTH_PATH}"

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
            "Refreshed access token for institution %s (expires_in=%s)",
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
        Falls back to a direct attribute if the column is ever added.
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
        # Graceful fallback — callers should always configure institutions correctly
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


class BrightspaceAPIClient:
    """Async REST wrapper for the Brightspace Learning Platform / Learning
    Environment APIs.

    All methods return raw dicts from the Brightspace JSON response; mapping
    to canonical models is the responsibility of BrightspaceAdapter.

    Retry logic:
        HTTP 429 and 503 are retried up to MAX_RETRIES times with an
        exponential backoff (RETRY_BACKOFF_SECONDS * attempt).
    """

    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token

    # ── Public API ───────────────────────────────────────────────────────

    async def get_courses(self) -> list[dict]:
        """Fetch all course enrollments for the authenticated user.

        Endpoint: GET /d2l/api/lp/{version}/enrollments/myenrollments/

        Returns:
            List of enrollment dicts.  Each dict has at minimum:
              - OrgUnit.Id       (int)   — the course/org unit ID
              - OrgUnit.Name     (str)
              - OrgUnit.Type.Id  (int)   — 3 = Course Offering
        """
        url = f"{self._base_url}/d2l/api/lp/{_LP_VERSION}/enrollments/myenrollments/"
        params = {"orgUnitTypeId": 3}  # 3 = Course Offering
        items: list[dict] = []
        bookmark: str | None = None

        while True:
            if bookmark:
                params["bookmark"] = bookmark
            data = await self._get(url, params=dict(params))
            items.extend(data.get("Items", []))
            paging = data.get("PagingInfo", {})
            if paging.get("HasMoreItems"):
                bookmark = paging.get("Bookmark")
            else:
                break

        logger.debug("get_courses: fetched %d enrollments", len(items))
        return items

    async def get_course_content(self, course_id: int | str) -> list[dict]:
        """Fetch the content table-of-contents for a course.

        Endpoint: GET /d2l/api/le/{version}/{orgUnitId}/content/toc/

        Returns:
            List of module dicts.  Each module may contain nested Topics.
        """
        url = f"{self._base_url}/d2l/api/le/{_LE_VERSION}/{course_id}/content/toc/"
        data = await self._get(url)
        modules: list[dict] = data.get("Modules", [])
        logger.debug(
            "get_course_content: course_id=%s, %d modules", course_id, len(modules)
        )
        return modules

    async def get_assignments(self, course_id: int | str) -> list[dict]:
        """Fetch dropbox (assignment) folders for a course.

        Endpoint: GET /d2l/api/le/{version}/{orgUnitId}/dropbox/folders/

        Returns:
            List of dropbox folder dicts.  Each dict contains at minimum:
              - Id           (int)
              - Name         (str)
              - CompletionDate (str | None) — ISO 8601 due date
        """
        url = f"{self._base_url}/d2l/api/le/{_LE_VERSION}/{course_id}/dropbox/folders/"
        data = await self._get(url)
        # Response is a paged object with "Objects" key
        if isinstance(data, dict):
            items = data.get("Objects", data.get("Items", []))
        else:
            items = data if isinstance(data, list) else []
        logger.debug(
            "get_assignments: course_id=%s, %d dropbox folders", course_id, len(items)
        )
        return items

    async def get_grades(self, course_id: int | str) -> list[dict]:
        """Fetch final grade values for the current user in a course.

        Endpoint: GET /d2l/api/le/{version}/{orgUnitId}/grades/final/values/myGradeValues/

        Returns:
            List of grade value dicts.
        """
        url = (
            f"{self._base_url}/d2l/api/le/{_LE_VERSION}/{course_id}"
            "/grades/final/values/myGradeValues/"
        )
        data = await self._get(url)
        items = data if isinstance(data, list) else data.get("Items", [])
        logger.debug(
            "get_grades: course_id=%s, %d grade entries", course_id, len(items)
        )
        return items

    async def get_announcements(self, course_id: int | str) -> list[dict]:
        """Fetch news (announcement) items for a course.

        Endpoint: GET /d2l/api/le/{version}/{orgUnitId}/news/

        Returns:
            List of news item dicts.
        """
        url = f"{self._base_url}/d2l/api/le/{_LE_VERSION}/{course_id}/news/"
        data = await self._get(url)
        items = data if isinstance(data, list) else data.get("Items", [])
        logger.debug(
            "get_announcements: course_id=%s, %d items", course_id, len(items)
        )
        return items

    # ── Internal HTTP helpers ────────────────────────────────────────────

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an authenticated GET with retry on 429/503.

        Args:
            url:    Absolute URL to request.
            params: Optional query parameters.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            httpx.HTTPStatusError: After MAX_RETRIES on persistent errors.
        """
        headers = {"Authorization": f"Bearer {self._access_token}"}
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response = await client.get(url, headers=headers, params=params)
                    if response.status_code in _RETRY_STATUSES:
                        wait = RETRY_BACKOFF_SECONDS * attempt
                        logger.warning(
                            "Brightspace API returned %s for %s; retrying in %.1fs "
                            "(attempt %d/%d)",
                            response.status_code,
                            url,
                            wait,
                            attempt,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    return response.json()
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
                        "Network error for %s (attempt %d/%d): %s",
                        url,
                        attempt,
                        MAX_RETRIES,
                        exc,
                    )
                    await asyncio.sleep(wait)

        if last_exc:
            raise last_exc
        return {}
