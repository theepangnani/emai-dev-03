"""Request correlation ID support via contextvars.

Generates a UUID for each incoming HTTP request and stores it in a
contextvar so that every log record emitted during that request can
include the same correlation ID.  Accepts an incoming ``X-Request-ID``
header for distributed tracing; otherwise generates a new UUID4.
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Context variable – accessible from any async or sync code in the request
# ---------------------------------------------------------------------------
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Return the current request's correlation ID (empty string outside a request)."""
    return correlation_id_ctx.get()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Set a correlation ID for every request and echo it back in the response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Prefer caller-supplied ID (distributed tracing); fall back to new UUID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        token = correlation_id_ctx.set(request_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            correlation_id_ctx.reset(token)
