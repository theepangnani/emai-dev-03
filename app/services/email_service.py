import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_via_sendgrid(to_email: str, subject: str, html_content: str) -> bool:
    """Send via SendGrid API."""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=(settings.from_email, "ClassBridge"),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    sg = SendGridAPIClient(settings.sendgrid_api_key)
    response = sg.send(message)
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(f"SendGrid returned status {response.status_code}: {response.body}")
    logger.info(f"Email sent via SendGrid to {to_email} | status={response.status_code}")
    return True


def _send_via_smtp(to_email: str, subject: str, html_content: str) -> bool:
    """Send via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr(("ClassBridge", settings.smtp_user.strip()))
    msg["To"] = to_email.strip()
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)

    logger.info(f"Email sent via SMTP to {to_email} | subject={subject}")
    return True


def send_emails_batch(emails: list[tuple[str, str, str]]) -> int:
    """Send multiple emails reusing a single SMTP connection.

    Args:
        emails: list of (to_email, subject, html_content) tuples.

    Returns:
        Number of successfully sent emails.
    """
    if not emails:
        return 0

    # Try SendGrid first (each call is an HTTP request, no connection reuse needed)
    if _has_valid_sendgrid_key():
        count = 0
        for to_email, subject, html_content in emails:
            try:
                _send_via_sendgrid(to_email, subject, html_content)
                count += 1
            except Exception as e:
                logger.warning(f"SendGrid failed for {to_email} | error={e}")
        if count > 0:
            return count
        logger.warning("SendGrid failed for all emails, falling back to SMTP")

    # SMTP batch: single connection for all emails
    if not (settings.smtp_user and settings.smtp_password):
        logger.warning("No email provider configured for batch send")
        return 0

    count = 0
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)

            for to_email, subject, html_content in emails:
                try:
                    msg = MIMEMultipart("alternative")
                    msg["From"] = formataddr(("ClassBridge", settings.smtp_user.strip()))
                    msg["To"] = to_email.strip()
                    msg["Subject"] = subject
                    msg.attach(MIMEText(html_content, "html"))
                    server.send_message(msg)
                    count += 1
                    logger.info(f"Batch email sent to {to_email}")
                except Exception as e:
                    logger.warning(f"Failed to send batch email to {to_email} | error={e}")
    except Exception as e:
        logger.error(f"SMTP connection failed for batch send | error={e}")

    return count


def _has_valid_sendgrid_key() -> bool:
    """Check if SendGrid API key looks valid (starts with SG.)."""
    key = settings.sendgrid_api_key
    return bool(key and key.startswith("SG."))


def send_email_sync(to_email: str, subject: str, html_content: str) -> bool:
    """Send an email. Tries SendGrid first, falls back to SMTP on failure."""
    # Try SendGrid first if configured
    if _has_valid_sendgrid_key():
        try:
            return _send_via_sendgrid(to_email, subject, html_content)
        except Exception as e:
            logger.warning(f"SendGrid failed for {to_email}, falling back to SMTP | error={e}")

    # Fall back to SMTP
    if settings.smtp_user and settings.smtp_password:
        try:
            return _send_via_smtp(to_email, subject, html_content)
        except Exception as e:
            logger.error(f"SMTP failed for {to_email} | error={e}")
            return False

    logger.warning("No email provider configured (set SENDGRID_API_KEY or SMTP_USER+SMTP_PASSWORD)")
    return False


async def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Async wrapper for send_email_sync."""
    return send_email_sync(to_email, subject, html_content)


def wrap_branded_email(body_html: str) -> str:
    """Wrap body HTML in the ClassBridge branded email template.

    Matches the same layout used by the Jinja HTML templates in app/templates/:
    logo, indigo accent bar, white content area, footer.
    """
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background-color:#f5f7fa;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;padding:32px 16px;">
    <tr>
      <td style="background:#ffffff;padding:24px 32px 16px 32px;border-radius:16px 16px 0 0;text-align:center;">
        <img src="https://www.classbridge.ca/classbridge-logo.png" alt="ClassBridge" width="180" style="display:block;margin:0 auto;width:180px;max-width:100%;height:auto;" />
      </td>
    </tr>
    <tr>
      <td style="height:4px;background:#4f46e5;font-size:0;line-height:0;">&nbsp;</td>
    </tr>
    <tr>
      <td style="background:white;padding:32px;border-radius:0 0 16px 16px;box-shadow:0 4px 12px rgba(0,0,0,0.05);">
        {body_html}
      </td>
    </tr>
    <tr>
      <td style="padding:16px;text-align:center;color:#9CA3AF;font-size:12px;">
        ClassBridge &mdash; Stay connected with your child's education
      </td>
    </tr>
  </table>
</body>
</html>"""


def add_inspiration_to_email(html_content: str, db, role: str) -> str:
    """Append a random inspirational message footer to email HTML.

    If no message is found or an error occurs, returns the original HTML unchanged.
    """
    try:
        from app.services.inspiration_service import get_random_message

        msg = get_random_message(db, role)
        if not msg:
            return html_content

        author_line = f' — {msg["author"]}' if msg.get("author") else ""
        footer = (
            '<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;'
            'text-align:center;color:#6b7280;font-size:13px;">'
            f'<em>"{msg["text"]}"</em>{author_line}'
            '</div>'
        )
        return html_content + footer
    except Exception:
        return html_content
