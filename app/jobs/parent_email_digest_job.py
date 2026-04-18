"""
Background job: process parent email digests for all active integrations.

Runs every 4 hours via APScheduler (#2651).
"""
import logging
import re
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session, joinedload

from app.db.database import SessionLocal
from app.models.parent_gmail_integration import (
    ParentGmailIntegration,
    ParentDigestSettings,
    DigestDeliveryLog,
)
from app.models.notification import NotificationType
from app.models.user import User

logger = logging.getLogger(__name__)


async def send_digest_for_integration(db: Session, integration: ParentGmailIntegration, *, skip_dedup: bool = False) -> dict:
    now = datetime.now(timezone.utc)

    if not skip_dedup:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        existing_log = (
            db.query(DigestDeliveryLog)
            .filter(
                DigestDeliveryLog.integration_id == integration.id,
                DigestDeliveryLog.delivered_at >= today_start,
                DigestDeliveryLog.status == "delivered",
            )
            .first()
        )
        if existing_log:
            return {"status": "skipped", "email_count": 0, "message": "Already delivered today"}

    settings = integration.digest_settings
    if not settings:
        return {"status": "skipped", "email_count": 0, "message": "No digest settings configured"}

    # Fetch child emails
    try:
        from app.services.parent_gmail_service import fetch_child_emails

        emails = await fetch_child_emails(db, integration)
    except Exception as e:
        error_msg = str(e).lower()
        if "token" in error_msg or "auth" in error_msg or "credentials" in error_msg:
            integration.is_active = False
            db.commit()
            logger.warning(
                "Deactivated integration %d (parent %d): token refresh failed | error=%s",
                integration.id,
                integration.parent_id,
                e,
            )
        else:
            logger.error(
                "Failed to fetch emails for integration %d | error=%s",
                integration.id,
                e,
            )
        log_entry = DigestDeliveryLog(
            parent_id=integration.parent_id,
            integration_id=integration.id,
            email_count=0,
            digest_content=None,
            status="failed",
            channels_used=settings.delivery_channels,
        )
        db.add(log_entry)
        db.commit()
        return {"status": "failed", "email_count": 0, "message": "Failed to fetch emails. Please try again or reconnect Gmail."}

    if not emails and not settings.notify_on_empty:
        return {"status": "skipped", "email_count": 0, "message": "No new emails"}

    child_name = integration.child_first_name or "your child"
    parent = integration.parent
    parent_name = parent.first_name if parent and parent.first_name else "Parent"

    try:
        from app.services.parent_digest_ai_service import (
            generate_parent_digest,
        )

        digest_content = await generate_parent_digest(
            emails,
            child_name,
            parent_name,
            settings.digest_format,
        )
    except Exception as e:
        logger.error(
            "AI digest generation failed for integration %d | error=%s",
            integration.id,
            e,
            exc_info=True,
        )
        log_entry = DigestDeliveryLog(
            parent_id=integration.parent_id,
            integration_id=integration.id,
            email_count=len(emails) if emails else 0,
            digest_content=None,
            status="failed",
            channels_used=settings.delivery_channels,
        )
        db.add(log_entry)
        db.commit()
        return {"status": "failed", "email_count": len(emails) if emails else 0, "message": "Failed to generate digest summary. Please try again."}

    channels = [c.strip() for c in settings.delivery_channels.split(",") if c.strip()]
    notification_channels = []
    if "in_app" in channels:
        notification_channels.append("app_notification")
    if "email" in channels:
        notification_channels.append("email")

    if parent:
        from app.services.notification_service import (
            send_multi_channel_notification,
        )

        send_multi_channel_notification(
            db=db,
            recipient=parent,
            sender=None,
            title=f"Email Digest for {child_name}",
            content=digest_content or "No new emails today.",
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link="/email-digest",
            channels=notification_channels,
        )

    # WhatsApp delivery (#2987, #3585, #3586, #3620)
    whatsapp_status: str | None = None
    if "whatsapp" in channels:
        if integration.whatsapp_verified and integration.whatsapp_phone:
            try:
                from app.services.whatsapp_service import send_whatsapp_message, send_whatsapp_template
                if settings.digest_format != "brief":
                    from app.services.parent_digest_ai_service import generate_parent_digest as gen_brief
                    whatsapp_content = await gen_brief(emails, child_name, parent_name, "brief")
                else:
                    whatsapp_content = digest_content
                plain_text = re.sub(r'<[^>]+>', '', whatsapp_content or "")

                # Truncate digest content BEFORE wrapping in template (#3586)
                # Reserve space for header + footer so they're never cut off
                header = f"Hi {parent_name}, here's your child's daily school email summary:\n\n"
                footer = "\n\nView full digest at https://www.classbridge.ca/email-digest"
                max_content_len = 1600 - len(header) - len(footer)
                if len(plain_text) > max_content_len:
                    plain_text = plain_text[:max_content_len - 3] + "..."

                # Use Content API template if content_sid configured (#3585)
                from app.core.config import settings as app_settings
                content_sid = app_settings.twilio_whatsapp_digest_content_sid
                if content_sid:
                    wa_success = send_whatsapp_template(
                        integration.whatsapp_phone,
                        content_sid,
                        {"1": parent_name, "2": plain_text},
                    )
                else:
                    # Fallback: body-text matching (works in sandbox / session window)
                    template_msg = f"{header}{plain_text}{footer}"
                    wa_success = send_whatsapp_message(integration.whatsapp_phone, template_msg)
                whatsapp_status = "sent" if wa_success else "failed"
            except Exception as e:
                whatsapp_status = "failed"
                logger.warning("WhatsApp delivery failed for integration %d: %s", integration.id, e)
        else:
            whatsapp_status = "skipped"

    email_count = len(emails) if emails else 0
    log_entry = DigestDeliveryLog(
        parent_id=integration.parent_id,
        integration_id=integration.id,
        email_count=email_count,
        digest_content=digest_content,
        digest_length_chars=len(digest_content) if digest_content else 0,
        channels_used=settings.delivery_channels,
        status="delivered",
        whatsapp_delivery_status=whatsapp_status,
    )
    db.add(log_entry)

    integration.last_synced_at = now
    db.commit()

    return {"status": "delivered", "email_count": email_count, "message": f"Digest delivered with {email_count} emails"}


async def process_parent_email_digests():
    """Run every 4 hours. For each active integration, fetch emails, generate digest, deliver notification."""
    logger.info("Running parent email digest job...")

    db = SessionLocal()
    sent = 0
    skipped = 0
    failed = 0
    try:
        # Query active integrations with digest enabled and not paused
        now = datetime.now(timezone.utc)
        integrations = (
            db.query(ParentGmailIntegration)
            .join(ParentDigestSettings)
            .options(joinedload(ParentGmailIntegration.parent))
            .options(joinedload(ParentGmailIntegration.digest_settings))
            .filter(
                ParentGmailIntegration.is_active == True,  # noqa: E712
                ParentDigestSettings.digest_enabled == True,  # noqa: E712
            )
            .filter(
                (ParentGmailIntegration.paused_until == None)  # noqa: E711
                | (ParentGmailIntegration.paused_until < now)
            )
            .all()
        )

        logger.info(
            "Parent email digest: found %d active integrations", len(integrations)
        )

        for integration in integrations:
            try:
                result = await send_digest_for_integration(db, integration)
                if result["status"] == "delivered":
                    sent += 1
                elif result["status"] == "skipped":
                    skipped += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    "Parent email digest failed for integration %d | error=%s",
                    integration.id,
                    e,
                    exc_info=True,
                )
                db.rollback()
                failed += 1

        logger.info(
            "Parent email digest job complete | sent=%d | skipped=%d | failed=%d",
            sent,
            skipped,
            failed,
        )
    except Exception:
        db.rollback()
        logger.exception("Parent email digest job failed")
    finally:
        db.close()
