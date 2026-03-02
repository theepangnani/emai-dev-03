"""LMS Provider Registry — maps provider strings to adapter instances.

Each adapter implements the LMSProvider Protocol.  New providers are added by:
1. Creating a concrete adapter class
2. Calling register_provider(MyAdapter()) at module bottom

On import this module auto-registers:
  - GoogleClassroomAdapter (delegates to existing /api/google/* flow)
  - BrightspaceAdapter    (stub — OAuth not yet implemented)
  - CanvasAdapter          (stub — OAuth not yet implemented)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Protocol (interface)
# ---------------------------------------------------------------------------


@runtime_checkable
class LMSProvider(Protocol):
    """Interface all LMS adapters must implement."""

    provider_id: str       # "google_classroom" | "brightspace" | "canvas" | ...
    display_name: str      # Human-readable name shown in the UI
    supports_oauth: bool   # Whether OAuth is supported (False = manual token entry)
    requires_institution_url: bool  # True if the user must supply their school's base URL

    def get_auth_url(self, user_id: int, redirect_uri: str) -> str:
        """Return the OAuth authorization URL for this provider.

        Args:
            user_id:      ClassBridge user ID initiating the connection.
            redirect_uri: Where the provider should redirect after consent.

        Returns:
            Absolute URL the frontend should navigate the user to.
        """
        ...

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange an OAuth authorization code for access/refresh tokens.

        Args:
            code:         Authorization code received from the provider.
            redirect_uri: Must match the redirect_uri used in get_auth_url.

        Returns:
            Dict with keys: access_token, refresh_token, expires_at (ISO str).
        """
        ...


# ---------------------------------------------------------------------------
# Concrete adapters
# ---------------------------------------------------------------------------


class GoogleClassroomAdapter:
    """Adapter for the existing Google Classroom integration.

    OAuth is handled by the existing /api/google/* routes.
    This adapter exists purely for provider registry/discovery purposes.
    """

    provider_id = "google_classroom"
    display_name = "Google Classroom"
    supports_oauth = True
    requires_institution_url = False

    def get_auth_url(self, user_id: int, redirect_uri: str) -> str:
        """Delegate to the existing Google OAuth connect endpoint."""
        return f"/api/google/connect?redirect_uri={redirect_uri}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Not used — the existing /api/google/callback handles this."""
        raise NotImplementedError(
            "Google Classroom token exchange is handled by the existing "
            "/api/google/callback flow.  Do not call this method directly."
        )


class BrightspaceAdapter:
    """Stub adapter for D2L Brightspace.

    Full implementation deferred to #24 (Brightspace OAuth2 Service).
    Registered now so the provider appears in the UI and API discovery.
    """

    provider_id = "brightspace"
    display_name = "D2L Brightspace"
    supports_oauth = True
    requires_institution_url = True

    def get_auth_url(self, user_id: int, redirect_uri: str) -> str:
        raise NotImplementedError(
            "Brightspace OAuth is not yet configured.  "
            "Implement in #24 (Brightspace OAuth2 Service)."
        )

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError(
            "Brightspace OAuth is not yet configured.  "
            "Implement in #24 (Brightspace OAuth2 Service)."
        )


class CanvasAdapter:
    """Stub adapter for Instructure Canvas LMS.

    Registered now so the provider appears in the UI and API discovery.
    """

    provider_id = "canvas"
    display_name = "Canvas LMS"
    supports_oauth = True
    requires_institution_url = True

    def get_auth_url(self, user_id: int, redirect_uri: str) -> str:
        raise NotImplementedError("Canvas OAuth is not yet configured.")

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("Canvas OAuth is not yet configured.")


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, LMSProvider] = {}


def register_provider(adapter: LMSProvider) -> None:
    """Add (or replace) a provider in the global registry."""
    _REGISTRY[adapter.provider_id] = adapter


def get_provider(provider_id: str) -> LMSProvider | None:
    """Look up a provider by its string ID.  Returns None if not found."""
    return _REGISTRY.get(provider_id)


def list_providers() -> list[dict]:
    """Return a serializable list of all registered providers."""
    return [
        {
            "provider_id": p.provider_id,
            "display_name": p.display_name,
            "supports_oauth": p.supports_oauth,
            "requires_institution_url": p.requires_institution_url,
        }
        for p in _REGISTRY.values()
    ]


# ---------------------------------------------------------------------------
# Auto-register all built-in providers on import
# ---------------------------------------------------------------------------

register_provider(GoogleClassroomAdapter())
register_provider(BrightspaceAdapter())
register_provider(CanvasAdapter())
