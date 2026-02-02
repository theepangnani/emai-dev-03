import logging
import base64
from datetime import datetime

from googleapiclient.errors import HttpError
from app.services.google_classroom import get_gmail_service

logger = logging.getLogger(__name__)


def fetch_teacher_emails(
    access_token: str,
    refresh_token: str | None,
    after_timestamp: datetime | None = None,
    max_results: int = 50,
) -> tuple[list[dict], object]:
    """
    Fetch emails from Gmail inbox (primary category).

    Returns list of parsed email dicts and credentials (for token refresh tracking).
    """
    service, credentials = get_gmail_service(access_token, refresh_token)

    query_parts = ["in:inbox", "category:primary"]
    if after_timestamp:
        epoch_seconds = int(after_timestamp.timestamp())
        query_parts.append(f"after:{epoch_seconds}")

    query = " ".join(query_parts)

    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
        ).execute()

        messages = results.get("messages", [])
        parsed = []

        for msg_stub in messages:
            try:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_stub["id"],
                    format="full",
                ).execute()
                parsed.append(_parse_gmail_message(msg))
            except HttpError as e:
                logger.warning(f"Failed to fetch message {msg_stub['id']}: {e}")

        return parsed, credentials

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return [], credentials


def _parse_gmail_message(msg: dict) -> dict:
    """Parse a Gmail API message into a clean dict."""
    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

    body_text = _extract_body_text(msg["payload"])

    return {
        "source_id": msg["id"],
        "sender_name": _extract_sender_name(headers.get("from", "")),
        "sender_email": _extract_sender_email(headers.get("from", "")),
        "subject": headers.get("subject", "(No Subject)"),
        "body": body_text,
        "snippet": msg.get("snippet", ""),
        "received_at": datetime.fromtimestamp(int(msg["internalDate"]) / 1000),
    }


def _extract_body_text(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _extract_body_text(part)
        if text:
            return text
    return ""


def _extract_sender_name(from_header: str) -> str:
    """Extract display name from 'Name <email>' format."""
    if "<" in from_header:
        return from_header.split("<")[0].strip().strip('"')
    return from_header


def _extract_sender_email(from_header: str) -> str:
    """Extract email from 'Name <email>' format."""
    if "<" in from_header and ">" in from_header:
        return from_header.split("<")[1].split(">")[0]
    return from_header
