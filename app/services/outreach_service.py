import html
import logging

from sqlalchemy.orm import Session

from app.models.parent_contact import ParentContact, OutreachTemplate, OutreachLog
from app.services.email_service import send_email_sync, wrap_branded_email
from app.services.twilio_service import is_twilio_configured, send_whatsapp, send_sms

logger = logging.getLogger(__name__)


def render_template_text(text: str, variables: dict[str, str]) -> str:
    """Replace {{var_name}} placeholders with values (no escaping)."""
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def render_template_html(text: str, variables: dict[str, str]) -> str:
    """Replace {{var_name}} placeholders with HTML-escaped values."""
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", html.escape(value))
    return result


def _build_contact_variables(contact: ParentContact) -> dict[str, str]:
    """Build variable dict from a contact record."""
    return {
        "full_name": contact.full_name or "",
        "child_name": contact.child_name or "",
        "school_name": contact.school_name or "",
        "classbridge_url": "https://www.classbridge.ca",
    }


def send_outreach(
    db: Session,
    contact_ids: list[int],
    channel: str,
    sent_by_user_id: int,
    template_id: int | None = None,
    custom_subject: str | None = None,
    custom_body: str | None = None,
) -> dict:
    """
    Send outreach to contacts. Returns {sent_count, failed_count, errors}.
    """
    # Check channel availability
    if channel in ("whatsapp", "sms") and not is_twilio_configured(channel):
        from app.core.config import settings

        missing = []
        if not settings.twilio_account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not settings.twilio_auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if channel == "whatsapp" and not settings.twilio_whatsapp_from:
            missing.append("TWILIO_WHATSAPP_FROM")
        if channel == "sms" and not settings.twilio_sms_from:
            missing.append("TWILIO_SMS_FROM")
        raise ValueError(
            f"{channel.upper()} not configured. Set {', '.join(missing)} env vars."
        )

    # Load contacts
    contacts = (
        db.query(ParentContact).filter(ParentContact.id.in_(contact_ids)).all()
    )
    if not contacts:
        raise ValueError("No contacts found for the given IDs")

    # Load template if provided
    template = None
    if template_id:
        template = (
            db.query(OutreachTemplate)
            .filter(OutreachTemplate.id == template_id)
            .first()
        )
        if not template:
            raise ValueError(f"Template {template_id} not found")

    sent_count = 0
    failed_count = 0
    errors = []

    for contact in contacts:
        # Determine recipient detail
        if channel == "email":
            recipient = contact.email
            if not recipient:
                errors.append(
                    {
                        "contact_id": contact.id,
                        "contact_name": contact.full_name,
                        "error": "No email address",
                    }
                )
                failed_count += 1
                continue
        else:  # whatsapp or sms
            recipient = contact.phone
            if not recipient:
                errors.append(
                    {
                        "contact_id": contact.id,
                        "contact_name": contact.full_name,
                        "error": "No phone number",
                    }
                )
                failed_count += 1
                continue

        # Build variables and render
        variables = _build_contact_variables(contact)

        if template:
            subject = (
                render_template_text(template.subject or "", variables)
                if template.subject
                else custom_subject
            )
            body_text = render_template_text(template.body_text, variables)
            body_html = (
                render_template_html(template.body_html, variables)
                if template.body_html
                else None
            )
        else:
            subject = custom_subject
            body_text = render_template_text(custom_body or "", variables)
            body_html = None

        # Capture body snapshot for audit
        body_snapshot = body_text

        # Send
        error_message = None
        send_status = "sent"
        try:
            if channel == "email":
                html_content = wrap_branded_email(
                    body_html or f"<p>{html.escape(body_text)}</p>"
                )
                success = send_email_sync(
                    recipient, subject or "Message from ClassBridge", html_content
                )
                if not success:
                    send_status = "failed"
                    error_message = "Email service returned failure"
            elif channel == "whatsapp":
                send_whatsapp(recipient, body_text)
            elif channel == "sms":
                send_sms(recipient, body_text)
        except Exception as e:
            send_status = "failed"
            error_message = str(e)[:500]
            logger.warning(
                "Outreach send failed for contact %d via %s: %s",
                contact.id,
                channel,
                e,
            )

        # Create outreach log entry
        log_entry = OutreachLog(
            parent_contact_id=contact.id,
            template_id=template_id,
            channel=channel,
            status=send_status,
            recipient_detail=recipient,
            body_snapshot=body_snapshot,
            sent_by_user_id=sent_by_user_id,
            error_message=error_message,
        )
        db.add(log_entry)

        if send_status == "sent":
            sent_count += 1
        else:
            failed_count += 1
            errors.append(
                {
                    "contact_id": contact.id,
                    "contact_name": contact.full_name,
                    "error": error_message or "Send failed",
                }
            )

    db.commit()
    return {"sent_count": sent_count, "failed_count": failed_count, "errors": errors}
