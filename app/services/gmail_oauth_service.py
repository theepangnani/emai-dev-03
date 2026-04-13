"""Gmail OAuth2 service for parent personal email integration.

Handles the OAuth2 flow so parents can connect their personal Gmail
to ClassBridge for email digest polling (gmail.readonly scope).
"""

import logging
from urllib.parse import urlencode

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# gmail.readonly for email digest polling, userinfo.email + profile to
# identify the connected Gmail address in the OAuth callback.
GMAIL_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_gmail_auth_url(redirect_uri: str, state: str | None = None) -> str:
    """Generate a Google OAuth2 authorization URL for gmail.readonly scope.

    Args:
        redirect_uri: The URI Google should redirect to after consent.
        state: Optional opaque state string for CSRF protection.

    Returns:
        The full authorization URL the frontend should redirect to.
    """
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state

    return f"{GOOGLE_AUTH_URI}?{urlencode(params)}"


def exchange_gmail_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for access + refresh tokens.

    Args:
        code: The authorization code from Google's redirect.
        redirect_uri: Must match the redirect_uri used in the auth URL.

    Returns:
        Dict with keys: access_token, refresh_token, expires_in, granted_scopes.

    Raises:
        requests.HTTPError: If the token exchange fails.
    """
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    response = requests.post(GOOGLE_TOKEN_URI, data=data)
    if not response.ok:
        try:
            error_detail = response.json()
        except Exception:
            error_detail = response.text[:500]
        logger.error(
            "Gmail token exchange failed: %s - %s (redirect_uri=%s)",
            response.status_code,
            error_detail,
            redirect_uri,
        )
        response.raise_for_status()

    tokens = response.json()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
        "granted_scopes": tokens.get("scope", ""),
    }


def refresh_gmail_token(refresh_token: str) -> dict:
    """Refresh an expired Gmail access token.

    Args:
        refresh_token: The refresh token stored from the initial exchange.

    Returns:
        Dict with keys: access_token, expires_in.

    Raises:
        requests.HTTPError: If the refresh fails.
    """
    data = {
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
    }

    response = requests.post(GOOGLE_TOKEN_URI, data=data)
    if not response.ok:
        try:
            error_detail = response.json()
        except Exception:
            error_detail = response.text[:500]
        logger.error(
            "Gmail token refresh failed: %s - %s",
            response.status_code,
            error_detail,
        )
        response.raise_for_status()

    tokens = response.json()
    return {
        "access_token": tokens["access_token"],
        "expires_in": tokens.get("expires_in"),
    }
