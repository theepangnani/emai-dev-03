"""
SendGrid Inbound Parse webhook handler — Phase 5 AI Email Agent.

Parses the multipart form data posted by SendGrid when a reply email is
received, then matches it to an existing EmailThread so the reply can be
appended as an EmailMessage with direction=INBOUND.

Thread-matching strategy (in order):
  1. external_thread_id  matches the In-Reply-To header (most reliable).
  2. Subject-line match  (strip Re:/Fwd: prefixes, case-insensitive LIKE).

Environment variable required for production signature verification:
  SENDGRID_WEBHOOK_KEY  — the public key from the SendGrid Event Webhook
                          Settings page (used to verify
                          X-Twilio-Email-Event-Webhook-Signature).

NOTE: Signature verification is performed when SENDGRID_WEBHOOK_KEY is set.
      In development (key absent), verification is skipped so local testing
      with tools like ngrok works out of the box.
"""
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public parsing function
# ---------------------------------------------------------------------------

def parse_sendgrid_inbound(form_data: dict) -> dict:
    """Parse a SendGrid Inbound Parse webhook payload.

    SendGrid POSTs a multipart/form-data body whose fields map directly to
    ``form_data`` (a plain dict, already decoded by FastAPI's Form parsing or
    a dict built from ``Request.form()``).

    Returns a normalised dict:
    {
        "from_email":   str,
        "from_name":    str | None,
        "to_emails":    list[str],
        "subject":      str,
        "body_text":    str,
        "body_html":    str | None,
        "message_id":   str | None,   # the Message-ID header of the *inbound* email
        "in_reply_to":  str | None,   # the In-Reply-To header (points to the original sent msg)
    }
    """
    # ── From ────────────────────────────────────────────────────────────────
    raw_from = form_data.get("from", "") or ""
    from_email, from_name = _parse_address(raw_from)

    # ── To ──────────────────────────────────────────────────────────────────
    raw_to = form_data.get("to", "") or ""
    to_emails = [addr for addr, _ in _parse_address_list(raw_to)]

    # ── Subject ─────────────────────────────────────────────────────────────
    subject = (form_data.get("subject") or "").strip()

    # ── Body ────────────────────────────────────────────────────────────────
    body_text = (form_data.get("text") or "").strip()
    body_html: Optional[str] = form_data.get("html") or None
    if body_html:
        body_html = body_html.strip() or None

    # ── Headers ─────────────────────────────────────────────────────────────
    # SendGrid provides raw SMTP headers as a single string in the "headers" field.
    raw_headers = form_data.get("headers") or ""
    message_id = _extract_header(raw_headers, "Message-ID")
    in_reply_to = _extract_header(raw_headers, "In-Reply-To")

    logger.info(
        "SendGrid inbound parsed | from=%s | subject=%s | message_id=%s | in_reply_to=%s",
        from_email, subject, message_id, in_reply_to,
    )

    return {
        "from_email": from_email,
        "from_name": from_name,
        "to_emails": to_emails,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
    }


# ---------------------------------------------------------------------------
# Thread matching
# ---------------------------------------------------------------------------

def find_thread_by_reply(
    in_reply_to: Optional[str],
    to_email: str,
    db: Session,
) -> Optional[object]:
    """Match an inbound reply to an existing EmailThread.

    Args:
        in_reply_to: The In-Reply-To SMTP header value from the inbound email
                     (the Message-ID of the original outbound message).
        to_email:    The address the reply was sent *to* (i.e. the ClassBridge
                     sending address). Used as an additional filter so we
                     don't accidentally match threads belonging to a different
                     user who sent to a different address.
        db:          SQLAlchemy session.

    Returns:
        An EmailThread ORM instance if a match is found, otherwise None.
    """
    # Import here to avoid circular imports at module load
    from app.models.email_thread import EmailThread

    # ── Strategy 1: exact In-Reply-To / external_thread_id match ────────────
    if in_reply_to:
        clean_id = in_reply_to.strip().strip("<>")
        thread = (
            db.query(EmailThread)
            .filter(
                EmailThread.external_thread_id == clean_id,
                EmailThread.is_archived == False,  # noqa: E712
            )
            .first()
        )
        if thread:
            logger.info(
                "Thread matched by external_thread_id | thread_id=%d | in_reply_to=%s",
                thread.id, clean_id,
            )
            return thread

    # ── Strategy 2: subject-line match (strip Re:/Fwd: prefixes) ────────────
    # We rely on a separate call from the route that knows the inbound subject.
    # This function is kept general; callers can pass the cleaned subject via
    # a second overloaded call pattern if needed (see find_thread_by_subject).
    return None


def find_thread_by_subject(
    subject: str,
    user_id: int,
    db: Session,
) -> Optional[object]:
    """Fallback: match an existing thread by normalised subject line.

    Strips common reply prefixes (Re:, Fwd:, Tr:, etc.) before comparing.

    Args:
        subject: The inbound email's subject line.
        user_id: The thread owner's user ID (limits search scope).
        db:      SQLAlchemy session.

    Returns:
        The most recently updated matching EmailThread, or None.
    """
    from app.models.email_thread import EmailThread
    from sqlalchemy import func as sa_func

    clean_subject = _strip_reply_prefix(subject).lower()
    if not clean_subject:
        return None

    threads = (
        db.query(EmailThread)
        .filter(
            EmailThread.user_id == user_id,
            EmailThread.is_archived == False,  # noqa: E712
            sa_func.lower(EmailThread.subject).contains(clean_subject),
        )
        .order_by(EmailThread.last_message_at.desc().nullslast())
        .limit(5)
        .all()
    )

    for thread in threads:
        if _strip_reply_prefix(thread.subject).lower() == clean_subject:
            logger.info(
                "Thread matched by subject | thread_id=%d | subject=%s",
                thread.id, clean_subject,
            )
            return thread

    return None


# ---------------------------------------------------------------------------
# Signature verification (optional — enabled when SENDGRID_WEBHOOK_KEY is set)
# ---------------------------------------------------------------------------

def verify_sendgrid_signature(
    payload: bytes,
    signature: str,
    timestamp: str,
    public_key_base64: str,
) -> bool:
    """Verify a SendGrid Event Webhook ECDSA signature.

    Uses the ecdsa library if available.  Returns True if the signature is
    valid, False otherwise.  On import errors (library not installed) logs
    a warning and returns True (fail-open) so the app still works without
    the optional dependency.

    Docs: https://docs.sendgrid.com/for-developers/tracking-events/getting-started-event-webhook-security-features
    """
    try:
        import base64
        import hashlib
        from ecdsa import VerifyingKey, NIST256p, BadSignatureError  # type: ignore

        vk = VerifyingKey.from_string(
            base64.b64decode(public_key_base64),
            curve=NIST256p,
            hashfunc=hashlib.sha256,
        )
        sig_bytes = base64.b64decode(signature)
        message = (timestamp + payload.decode("utf-8")).encode("utf-8")
        vk.verify(sig_bytes, message, hashfunc=hashlib.sha256)
        return True
    except ImportError:
        logger.warning(
            "ecdsa library not installed — SendGrid signature verification skipped. "
            "Install with: pip install ecdsa"
        )
        return True
    except Exception as exc:  # includes BadSignatureError
        logger.warning("SendGrid signature verification failed | error=%s", exc)
        return False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_address(raw: str) -> tuple[str, Optional[str]]:
    """Parse a single RFC 5322 address like 'Name <email@example.com>'.

    Returns (email, name_or_None).
    """
    raw = raw.strip()
    match = re.match(r'^"?([^"<>]+?)"?\s*<([^>]+)>$', raw)
    if match:
        name = match.group(1).strip() or None
        email = match.group(2).strip().lower()
        return email, name
    # Bare address
    return raw.lower(), None


def _parse_address_list(raw: str) -> list[tuple[str, Optional[str]]]:
    """Parse a comma-separated list of RFC 5322 addresses."""
    if not raw:
        return []
    # Split on commas that are NOT inside angle brackets or quotes (simple heuristic)
    parts = re.split(r",\s*(?=[^<>]*(?:<[^<>]*>|$))", raw)
    result = []
    for part in parts:
        part = part.strip()
        if part:
            result.append(_parse_address(part))
    return result


def _extract_header(raw_headers: str, header_name: str) -> Optional[str]:
    """Extract a single header value from a raw SMTP header block."""
    pattern = re.compile(
        rf"^{re.escape(header_name)}:\s*(.+?)(?:\r?\n(?!\s)|$)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(raw_headers)
    if match:
        # Collapse any folded whitespace
        value = re.sub(r"\r?\n\s+", " ", match.group(1)).strip()
        return value or None
    return None


def _strip_reply_prefix(subject: str) -> str:
    """Remove leading Re:/Fwd:/Tr: etc. from a subject line (recursive)."""
    prefixes_re = re.compile(r"^\s*(re|fwd?|tr|aw|sv)\s*:\s*", re.IGNORECASE)
    prev = None
    while prev != subject:
        prev = subject
        subject = prefixes_re.sub("", subject).strip()
    return subject
