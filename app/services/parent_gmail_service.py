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
    # Build list of monitored emails — prefer new table, fall back to legacy field
    monitored = integration.monitored_emails if hasattr(integration, 'monitored_emails') else []
    monitored_addresses = [m.email_address for m in monitored] if monitored else []
    if not monitored_addresses and integration.child_school_email:
        monitored_addresses = [integration.child_school_email]
    if not monitored_addresses:
        logger.warning(
            "Integration %d has no monitored email addresses configured",
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

    def _sync_fetch(at, rt, email_addresses, since_dt, max_res):
        """Synchronous Gmail fetch — runs in thread pool."""
        svc, creds = get_gmail_service(at, rt)
        epoch_seconds = int(since_dt.timestamp())
        if len(email_addresses) == 1:
            query = f'from:"{email_addresses[0]}" in:inbox after:{epoch_seconds}'
        else:
            from_parts = " OR ".join(f'from:"{addr}"' for addr in email_addresses)
            query = f'({from_parts}) in:inbox after:{epoch_seconds}'

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
            monitored_addresses,
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
        "Fetched %d emails for integration %d (parent %d, monitored: %s)",
        len(parsed),
        integration.id,
        integration.parent_id,
        monitored_addresses,
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
    monitored = integration.monitored_emails if hasattr(integration, 'monitored_emails') else []
    monitored_addresses = [m.email_address for m in monitored] if monitored else []
    if not monitored_addresses and integration.child_school_email:
        monitored_addresses = [integration.child_school_email]
    if not monitored_addresses:
        return {
            "verified": False,
            "email_count": 0,
            "latest_email_date": None,
            "message": "No monitored email addresses configured",
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

    def _sync_verify(at, rt, email_addresses):
        """Synchronous Gmail verify — runs in thread pool."""
        svc, creds = get_gmail_service(at, rt)

        # Check last 30 days
        since_dt = datetime.now(timezone.utc) - timedelta(days=30)
        epoch_seconds = int(since_dt.timestamp())
        if len(email_addresses) == 1:
            query = f'from:"{email_addresses[0]}" in:inbox after:{epoch_seconds}'
        else:
            from_parts = " OR ".join(f'from:"{addr}"' for addr in email_addresses)
            query = f'({from_parts}) in:inbox after:{epoch_seconds}'

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
            monitored_addresses,
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
