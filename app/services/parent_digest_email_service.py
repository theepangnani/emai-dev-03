"""
Service for rendering the branded parent email digest HTML template.
"""
import os

from app.core.config import settings as app_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _load_template(name: str) -> str:
    """Load an HTML template from the templates directory."""
    path = os.path.join(_TEMPLATE_DIR, name)
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("Email template not found: %s", path)
        return ""


def _render(template: str, **kwargs: str) -> str:
    """Replace {{key}} placeholders in a template string."""
    for k, v in kwargs.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def render_digest_email(
    parent_name: str,
    child_name: str,
    digest_html: str,
    digest_date: str,
    email_count: int,
    base_url: str = "",
) -> str:
    """Render the branded digest email HTML.

    Args:
        parent_name: Parent's first name for the greeting.
        child_name: Child's first name for context.
        digest_html: AI-generated digest content HTML.
        digest_date: Human-readable date string (e.g. "Monday, April 7").
        email_count: Number of emails summarized.

    Returns:
        Fully rendered HTML string ready for send_email_sync().
    """
    template = _load_template("parent_email_digest.html")
    if not template:
        # Fallback: wrap content in minimal branded layout
        from app.services.email_service import wrap_branded_email
        body = (
            f"<h2>Good morning, {parent_name}</h2>"
            f"<p>{digest_date} &middot; {email_count} school emails for {child_name}</p>"
            f"{digest_html}"
        )
        return wrap_branded_email(body)

    resolved_base_url = base_url or app_settings.frontend_url.rstrip("/")

    return _render(
        template,
        parent_name=parent_name,
        child_name=child_name,
        digest_content=digest_html,
        digest_date=digest_date,
        email_count=str(email_count),
        base_url=resolved_base_url,
    )
