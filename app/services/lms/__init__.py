"""LMS abstraction layer -- provider registry and public exports.

Usage::

    from app.services.lms import get_provider, LMSProvider

    provider = get_provider("google_classroom", access_token="...", refresh_token="...")
    courses = provider.get_courses()

Part of #775 / #776.
"""

from __future__ import annotations

from typing import Any

from app.services.lms.provider import (
    CanonicalAssignment,
    CanonicalCourse,
    CanonicalGrade,
    CanonicalMaterial,
    CanonicalStudent,
    CanonicalTeacher,
    LMSProvider,
)
from app.services.lms.google_classroom_adapter import GoogleClassroomAdapter

__all__ = [
    # Abstract interface
    "LMSProvider",
    # Canonical models
    "CanonicalCourse",
    "CanonicalAssignment",
    "CanonicalGrade",
    "CanonicalStudent",
    "CanonicalTeacher",
    "CanonicalMaterial",
    # Concrete adapters
    "GoogleClassroomAdapter",
    # Registry
    "get_provider",
    "list_providers",
]

# ── Provider registry ────────────────────────────────────────────────
# Maps provider name → adapter class. New LMS integrations only need to
# add an entry here.

_PROVIDERS: dict[str, type[LMSProvider]] = {
    "google_classroom": GoogleClassroomAdapter,
}


def get_provider(provider_name: str, **kwargs: Any) -> LMSProvider:
    """Instantiate an LMS provider by name.

    Parameters
    ----------
    provider_name : str
        Registry key, e.g. ``"google_classroom"``.
    **kwargs
        Passed directly to the provider constructor (e.g. ``access_token``,
        ``refresh_token``).

    Raises
    ------
    ValueError
        If ``provider_name`` is not registered.
    """
    cls = _PROVIDERS.get(provider_name)
    if not cls:
        available = ", ".join(sorted(_PROVIDERS.keys()))
        raise ValueError(
            f"Unknown LMS provider: {provider_name!r}. "
            f"Available providers: {available}"
        )
    return cls(**kwargs)


def list_providers() -> list[str]:
    """Return the names of all registered LMS providers."""
    return sorted(_PROVIDERS.keys())
