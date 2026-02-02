import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send an email via SendGrid. Returns True on success, False on failure."""
    if not settings.sendgrid_api_key:
        logger.warning("SendGrid API key not configured, skipping email send")
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)

        logger.info(
            f"Email sent to {to_email} | subject={subject} | status={response.status_code}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email} | error={e}")
        return False
