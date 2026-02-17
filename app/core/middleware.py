"""Custom middleware for security headers and domain redirect."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # HSTS only in production (served over HTTPS via Cloud Run)
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # CSP: strict in prod, permissive in dev (Vite HMR needs unsafe-eval)
        if settings.environment == "production":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' http://localhost:*; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:*; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https: http://localhost:*; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self' http://localhost:* ws://localhost:*; "
                "frame-ancestors 'none'"
            )

        return response


class DomainRedirectMiddleware(BaseHTTPMiddleware):
    """301 redirect non-canonical domains to the canonical domain.

    Redirects clazzbridge.com, www.clazzbridge.com, and bare classbridge.ca
    to www.classbridge.ca (or whatever CANONICAL_DOMAIN is set to).
    Skips /health so Cloud Run liveness probes are not affected.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        canonical = settings.canonical_domain
        if not canonical:
            return await call_next(request)

        # Use X-Forwarded-Host (set by Cloud Run) or fall back to Host header
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host", "")
        )
        # Strip port if present
        host = host.split(":")[0].lower()

        # Skip health check (Cloud Run probes) and already-canonical requests
        if request.url.path == "/health" or host == canonical:
            return await call_next(request)

        # Build redirect URL preserving path and query string
        scheme = request.headers.get("x-forwarded-proto", "https")
        redirect_url = f"{scheme}://{canonical}{request.url.path}"
        if request.url.query:
            redirect_url += f"?{request.url.query}"

        return RedirectResponse(url=redirect_url, status_code=301)
