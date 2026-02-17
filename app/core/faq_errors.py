"""Helpers for raising HTTP exceptions with FAQ error code references.

Usage:
    from app.core.faq_errors import raise_with_faq_hint

    raise_with_faq_hint(
        status_code=400,
        detail="Google Classroom sync failed. Your connection may have expired.",
        faq_code="GOOGLE_SYNC_FAILED",
    )

The response body will be:
    {"detail": "...", "faq_code": "GOOGLE_SYNC_FAILED"}

The frontend FAQErrorHint component can use faq_code to fetch the matching FAQ
entry via GET /api/faq/by-error-code/{code}.
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse


# Predefined error codes — keep in sync with seed FAQ entries
GOOGLE_SYNC_FAILED = "GOOGLE_SYNC_FAILED"
GOOGLE_NOT_CONNECTED = "GOOGLE_NOT_CONNECTED"
STUDY_GUIDE_LIMIT = "STUDY_GUIDE_LIMIT"
AI_GENERATION_FAILED = "AI_GENERATION_FAILED"
INVITE_EXPIRED = "INVITE_EXPIRED"


def raise_with_faq_hint(
    status_code: int,
    detail: str,
    faq_code: str,
) -> None:
    """Raise an HTTPException whose body includes a faq_code field.

    FastAPI's default exception handler only serializes `detail`, so we use
    a custom HTTPException subclass that overrides the response body.
    """
    raise FAQHintException(
        status_code=status_code,
        detail=detail,
        faq_code=faq_code,
    )


class FAQHintException(HTTPException):
    """HTTPException that includes a faq_code in the JSON response."""

    def __init__(self, status_code: int, detail: str, faq_code: str):
        super().__init__(status_code=status_code, detail=detail)
        self.faq_code = faq_code


def faq_hint_exception_handler(_request, exc: FAQHintException):
    """Custom handler registered on the FastAPI app."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "faq_code": exc.faq_code},
    )
