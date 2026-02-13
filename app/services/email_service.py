import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_via_sendgrid(to_email: str, subject: str, html_content: str) -> bool:
    """Send via SendGrid API."""
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
    logger.info(f"Email sent via SendGrid to {to_email} | status={response.status_code}")
    return True


def _send_via_smtp(to_email: str, subject: str, html_content: str) -> bool:
    """Send via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)

    logger.info(f"Email sent via SMTP to {to_email} | subject={subject}")
    return True


def send_email_sync(to_email: str, subject: str, html_content: str) -> bool:
    """Send an email. Uses SendGrid if configured, otherwise Gmail SMTP."""
    try:
        if settings.sendgrid_api_key:
            return _send_via_sendgrid(to_email, subject, html_content)
        elif settings.smtp_user and settings.smtp_password:
            return _send_via_smtp(to_email, subject, html_content)
        else:
            logger.warning("No email provider configured (set SENDGRID_API_KEY or SMTP_USER+SMTP_PASSWORD)")
            return False
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} | error={e}")
        return False


async def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Async wrapper for send_email_sync."""
    return send_email_sync(to_email, subject, html_content)
