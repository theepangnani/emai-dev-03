"""Gmail polling service for parent email digest."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_token
from app.models.parent_gmail_integration import ParentGmailIntegration
from app.services.gmail_monitor import _parse_gmail_message
from app.services.google_classroom import get_gmail_service

logger = logging.getLogger(__name__)

# Parent Gmail OAuth consents to these 3 scopes only — must match gmail_oauth_service.GMAIL_OAUTH_SCOPES
PARENT_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


async def fetch_child_emails(
    db: Session,
    integration: ParentGmailIntegration,
    since: datetime | None = None,
    max_results: int = 50,
) -> list[dict]:
    """
    Poll parent's Gmail for emails from child's school email.

    - Builds Gmail API client using stored tokens (decrypt if needed)
    - Queries: from:{child_school_email} in:inbox after:{since_epoch}
    - Parses each message via _parse_gmail_message()
    - Returns list of email dicts: {source_id, sender_name, sender_email,
      subject, body, snippet, received_at}
    - Updates integration.last_synced_at on success
    - On token refresh failure: sets is_active=False
    - Deduplicates by gmail_message_id (source_id)
    """
    # Build Gmail query parts from both email_address and sender_name.
    # Prefer new monitored_emails table; fall back to legacy child_school_email.
    monitored_entries = integration.monitored_emails or []
    query_parts: list[str] = []
    for m in monitored_entries:
        if getattr(m, "email_address", None):
            query_parts.append(f'from:"{m.email_address}"')
        if getattr(m, "sender_name", None):
            query_parts.append(f'from:"{m.sender_name}"')

    # Backward compat: fall back to legacy child_school_email if nothing else configured
    if not query_parts and integration.child_school_email:
        query_parts.append(f'from:"{integration.child_school_email}"')

    if not query_parts:
        logger.warning(
            "Integration %d has no monitored entries configured",
            integration.id,
        )
        return []

    # Determine 'since' timestamp
    if since is None:
        since = integration.last_synced_at or (
            datetime.now(timezone.utc) - timedelta(hours=24)
        )

    # Decrypt tokens
    access_token = (
        decrypt_token(integration.access_token)
        if integration.access_token
        else None
    )
    refresh_token = (
        decrypt_token(integration.refresh_token)
        if integration.refresh_token
        else None
    )

    if not access_token:
        logger.error("Integration %d has no access token", integration.id)
        return []

    def _sync_fetch(at, rt, q_parts, since_dt, max_res):
        """Synchronous Gmail fetch — runs in thread pool."""
        svc, creds = get_gmail_service(at, rt, scopes=PARENT_GMAIL_SCOPES)
        epoch_seconds = int(since_dt.timestamp())
        if len(q_parts) == 1:
            query = f'{q_parts[0]} in:inbox after:{epoch_seconds}'
        else:
            query = f'({" OR ".join(q_parts)}) in:inbox after:{epoch_seconds}'

        results = (
            svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_res)
            .execute()
        )

        messages = results.get("messages", [])
        parsed = []
        seen_ids: set[str] = set()

        for msg_stub in messages:
            msg_id = msg_stub["id"]
            if msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)

            try:
                msg = (
                    svc.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                parsed.append(_parse_gmail_message(msg))
            except HttpError as e:
                logger.warning("Failed to fetch message %s: %s", msg_id, e)

        return parsed, creds

    try:
        parsed, credentials = await asyncio.to_thread(
            _sync_fetch,
            access_token,
            refresh_token,
            query_parts,
            since,
            max_results,
        )
    except HttpError as e:
        if e.resp.status in (401, 403):
            logger.error(
                "Gmail auth failed for integration %d: %s",
                integration.id,
                e,
            )
            integration.is_active = False
            db.commit()
        else:
            logger.error(
                "Gmail API error for integration %d: %s",
                integration.id,
                e,
            )
        return []
    except Exception as e:
        logger.error(
            "Failed to build Gmail service for integration %d: %s",
            integration.id,
            e,
        )
        integration.is_active = False
        db.commit()
        return []

    # Update last_synced_at (DB ops stay on main thread)
    integration.last_synced_at = datetime.now(timezone.utc)

    # If credentials were refreshed, update stored tokens
    if credentials.token != access_token:
        from app.core.encryption import encrypt_token

        integration.access_token = encrypt_token(credentials.token)
        if (
            credentials.refresh_token
            and credentials.refresh_token != refresh_token
        ):
            integration.refresh_token = encrypt_token(
                credentials.refresh_token
            )

    db.commit()

    logger.info(
        "Fetched %d emails for integration %d (parent %d, query_parts: %s)",
        len(parsed),
        integration.id,
        integration.parent_id,
        query_parts,
    )
    return parsed


async def verify_forwarding(
    db: Session,
    integration: ParentGmailIntegration,
) -> dict:
    """
    Verify that the child's school email is forwarding to parent's Gmail.

    Checks for at least 1 email from child_school_email in the last 30 days.
    Returns: {verified: bool, email_count: int, latest_email_date: str|None}
    """
    # Build Gmail query parts from both email_address and sender_name.
    monitored_entries = integration.monitored_emails or []
    query_parts: list[str] = []
    for m in monitored_entries:
        if getattr(m, "email_address", None):
            query_parts.append(f'from:"{m.email_address}"')
        if getattr(m, "sender_name", None):
            query_parts.append(f'from:"{m.sender_name}"')

    if not query_parts and integration.child_school_email:
        query_parts.append(f'from:"{integration.child_school_email}"')

    if not query_parts:
        return {
            "verified": False,
            "email_count": 0,
            "latest_email_date": None,
            "message": "No monitored senders configured",
        }

    access_token = (
        decrypt_token(integration.access_token)
        if integration.access_token
        else None
    )
    refresh_token = (
        decrypt_token(integration.refresh_token)
        if integration.refresh_token
        else None
    )

    if not access_token:
        return {
            "verified": False,
            "email_count": 0,
            "latest_email_date": None,
            "message": "No access token",
        }

    def _sync_verify(at, rt, q_parts):
        """Synchronous Gmail verify — runs in thread pool."""
        svc, creds = get_gmail_service(at, rt, scopes=PARENT_GMAIL_SCOPES)

        # Check last 30 days
        since_dt = datetime.now(timezone.utc) - timedelta(days=30)
        epoch_seconds = int(since_dt.timestamp())
        if len(q_parts) == 1:
            query = f'{q_parts[0]} in:inbox after:{epoch_seconds}'
        else:
            query = f'({" OR ".join(q_parts)}) in:inbox after:{epoch_seconds}'

        results = (
            svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=5)
            .execute()
        )

        messages = results.get("messages", [])
        count = len(messages)
        latest = None

        if messages:
            msg = (
                svc.users()
                .messages()
                .get(
                    userId="me",
                    id=messages[0]["id"],
                    format="metadata",
                    metadataHeaders=["Date"],
                )
                .execute()
            )
            headers = {
                h["name"].lower(): h["value"]
                for h in msg["payload"]["headers"]
            }
            latest = headers.get("date")

        return count, latest, creds

    try:
        email_count, latest_date, credentials = await asyncio.to_thread(
            _sync_verify,
            access_token,
            refresh_token,
            query_parts,
        )
    except HttpError as e:
        return {
            "verified": False,
            "email_count": 0,
            "latest_email_date": None,
            "message": f"Gmail API error: {e!s}",
        }
    except Exception as e:
        return {
            "verified": False,
            "email_count": 0,
            "latest_email_date": None,
            "message": f"Gmail connection failed: {e!s}",
        }

    # Update credentials if refreshed (DB ops stay on main thread)
    if credentials.token != access_token:
        from app.core.encryption import encrypt_token

        integration.access_token = encrypt_token(credentials.token)
        if (
            credentials.refresh_token
            and credentials.refresh_token != refresh_token
        ):
            integration.refresh_token = encrypt_token(
                credentials.refresh_token
            )
        db.commit()

    return {
        "verified": email_count > 0,
        "email_count": email_count,
        "latest_email_date": latest_date,
        "message": (
            "Forwarding verified — emails found from school address"
            if email_count > 0
            else "No emails found from school address in the last 30 days"
        ),
    }
