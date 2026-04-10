"""WhatsApp notification delivery via Twilio."""
import logging
import secrets

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    """Mask phone number for logging: +1416****34"""
    if len(phone) > 6:
        return phone[:4] + "****" + phone[-2:]
    return "****"


# Twilio is optional — gracefully handle missing package
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.info("Twilio not installed — WhatsApp integration disabled")


def is_whatsapp_enabled() -> bool:
    """Check if WhatsApp is configured."""
    return (
        TWILIO_AVAILABLE
        and bool(getattr(settings, "twilio_account_sid", None))
        and bool(getattr(settings, "twilio_auth_token", None))
        and bool(getattr(settings, "twilio_whatsapp_from", None))
    )


def send_whatsapp_message(to_phone: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    if not is_whatsapp_enabled():
        logger.warning("WhatsApp not configured — skipping delivery to %s", _mask_phone(to_phone))
        return False

    try:
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        # Truncate to WhatsApp's 1600 char limit
        if len(message) > 1600:
            message = message[:1597] + "..."

        msg = client.messages.create(
            from_=f"whatsapp:{settings.twilio_whatsapp_from}",
            to=f"whatsapp:{to_phone}",
            body=message,
        )
        logger.info("WhatsApp message sent to %s: SID %s", _mask_phone(to_phone), msg.sid)
        return True
    except Exception as e:
        logger.error("WhatsApp send failed to %s: %s", _mask_phone(to_phone), e)
        return False


def generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return f"{secrets.randbelow(1000000):06d}"


def send_otp(phone: str, otp_code: str) -> bool:
    """Send OTP verification code via WhatsApp."""
    message = f"Your ClassBridge verification code is: {otp_code}\n\nThis code expires in 10 minutes."
    return send_whatsapp_message(phone, message)
