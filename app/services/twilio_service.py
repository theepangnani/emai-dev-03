import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    """Mask phone for logging: +1416555**** """
    if not phone or len(phone) < 8:
        return "***"
    return phone[:7] + "*" * (len(phone) - 7)


def is_twilio_configured(channel: str = "whatsapp") -> bool:
    """Check if Twilio credentials are configured for the given channel."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return False
    if channel == "whatsapp" and not settings.twilio_whatsapp_from:
        return False
    if channel == "sms" and not settings.twilio_sms_from:
        return False
    return True


def send_whatsapp(to_phone: str, body: str) -> dict:
    """Send WhatsApp message via Twilio. Returns {sid, status}."""
    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        body=body,
        from_=f"whatsapp:{settings.twilio_whatsapp_from}",
        to=f"whatsapp:{to_phone}",
    )
    logger.info(
        "WhatsApp sent to %s: sid=%s status=%s",
        _mask_phone(to_phone),
        message.sid,
        message.status,
    )
    return {"sid": message.sid, "status": message.status}


def send_sms(to_phone: str, body: str) -> dict:
    """Send SMS via Twilio. Returns {sid, status}."""
    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        body=body,
        from_=settings.twilio_sms_from,
        to=to_phone,
    )
    logger.info(
        "SMS sent to %s: sid=%s status=%s",
        _mask_phone(to_phone),
        message.sid,
        message.status,
    )
    return {"sid": message.sid, "status": message.status}
