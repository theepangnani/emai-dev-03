"""
Background job: process parent email digests for all active integrations.

Runs every 4 hours via APScheduler (#2651).
"""
import logging
import re
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings as app_settings
from app.db.database import SessionLocal
from app.models.parent_gmail_integration import (
    ParentGmailIntegration,
    ParentDigestSettings,
    DigestDeliveryLog,
)
from app.models.notification import NotificationType
from app.models.task import Task
from app.models.user import User

logger = logging.getLogger(__name__)


def _notify_digest_task_created(
    db: Session,
    task: Task,
    integration: ParentGmailIntegration,
) -> None:
    """Send an in-app notification on email_digest auto-create (§6.13.1).

    Channels: in_app only (no email, no WhatsApp per MVP-1 decision). Truncates
    the title to 80 chars. Best-effort — failures are logged but never
    propagate (a notification failure must not roll back the Task upsert).
    """
    if task is None or task.assigned_to_user_id is None:
        return
    try:
        from app.services.notification_service import (
            send_multi_channel_notification,
        )

        recipient = db.query(User).filter(User.id == task.assigned_to_user_id).first()
        if recipient is None:
            return
        title_preview = (task.title or "")[:80]
        send_multi_channel_notification(
            db=db,
            recipient=recipient,
            sender=None,
            title="New task from teacher email",
            content=f"'{title_preview}' added to your tasks from teacher email",
            notification_type=NotificationType.TASK_CREATED,
            link="/tasks",
            channels=["app_notification"],
        )
    except Exception:
        logger.exception(
            "task_sync.digest.notify_created.error | task_id=%s integration_id=%s",
            getattr(task, "id", None),
            getattr(integration, "id", None),
        )


async def send_digest_for_integration(
    db: Session,
    integration: ParentGmailIntegration,
    *,
    skip_dedup: bool = False,
    since: datetime | None = None,
    create_tasks: bool = True,
) -> dict:
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
            return {
                "status": "skipped",
                "email_count": 0,
                "message": "Already delivered today",
                "reason": "already_delivered",
            }

    settings = integration.digest_settings
    if not settings:
        return {
            "status": "skipped",
            "email_count": 0,
            "message": "No digest settings configured",
            "reason": "no_settings",
        }

    # Fetch child emails
    try:
        from app.services.parent_gmail_service import fetch_child_emails

        emails = await fetch_child_emails(db, integration, since=since)
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
        return {
            "status": "skipped",
            "email_count": 0,
            "message": "No new emails",
            "reason": "no_new_emails",
        }

    child_name = integration.child_first_name or "your child"
    parent = integration.parent
    parent_name = "Parent"
    if parent and parent.full_name:
        parts = parent.full_name.split()
        if parts:
            parent_name = parts[0]

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

    # ── CB-TASKSYNC-001 I6 (#3918): wire email-digest → task sync ──
    # Extract structured urgent items and upsert Tasks. Gated by the
    # `task_sync_enabled` feature flag AND the caller-supplied `create_tasks`
    # flag (scheduled 4h job passes True; HTTP "Send digest now" passes False
    # unless the MVP-1 pilot query-param override is used — see #3929).
    if create_tasks and emails:
        try:
            from app.services.feature_flag_service import is_feature_enabled

            if is_feature_enabled("task_sync_enabled", db=db):
                from app.services.parent_digest_ai_service import (
                    extract_digest_items,
                )
                from app.services.task_sync_service import (
                    resolve_integration_child_user_id,
                    upsert_task_from_digest_item,
                )

                tz_name = (
                    getattr(settings, "timezone", None) or "America/Toronto"
                )
                items = await extract_digest_items(emails, tz_name=tz_name)
                child_uid = resolve_integration_child_user_id(db, integration)
                parent_user = integration.parent
                # Snapshot pre-existing Task ids ONCE per digest run (review
                # I3). Maintained in-loop by adding each newly-created Task id
                # — keeps the created-vs-updated classification O(1) per item
                # instead of re-querying on every loop iteration.
                assignee_probe_id = child_uid or (
                    parent_user.id if parent_user else None
                )
                pre_ids: set[int] = set()
                if assignee_probe_id is not None:
                    pre_ids = {
                        row[0]
                        for row in (
                            db.query(Task.id)
                            .filter(Task.source == "email_digest")
                            .filter(Task.assigned_to_user_id == assignee_probe_id)
                            .all()
                        )
                    }
                for item in items:
                    try:
                        task = upsert_task_from_digest_item(
                            db,
                            parent_user,
                            child_uid,
                            item,
                            tz_name=tz_name,
                        )
                        # upsert_task_from_digest_item commits internally; the
                        # trailing db.commit() below flushes only the
                        # Notification row added by the helper. Helper
                        # swallows its own exceptions, so a notification
                        # failure cannot roll back a successful upsert.
                        if task is not None and task.id not in pre_ids:
                            _notify_digest_task_created(db, task, integration)
                            db.commit()
                            pre_ids.add(task.id)
                    except Exception:
                        db.rollback()
                        logger.exception(
                            "task_sync.digest | failed | title=%s",
                            getattr(item, "title", "<unknown>"),
                        )
        except Exception:
            logger.exception(
                "task_sync.digest | extract_items failed | integration_id=%s",
                integration.id,
            )

    channels = [c.strip() for c in settings.delivery_channels.split(",") if c.strip()]
    notification_channels = []
    if "in_app" in channels:
        notification_channels.append("app_notification")
    if "email" in channels:
        notification_channels.append("email")

    # Per-channel outcomes (#3880, refined #3887): True=sent, False=actual
    # delivery failure, None=not applicable (channel not requested OR
    # preference-suppressed / no email on file). None is explicitly NOT a
    # failure and is excluded from the overall-status computation.
    #
    # Channel-aware default: if a channel IS selected but the send code path
    # is skipped (pathological: parent is None), register the channel as
    # "tried but failed" (False) rather than "not applicable" (None). If the
    # notification service actually runs, these are overwritten below with
    # whatever the service returned — including None for preference-suppressed.
    in_app_ok: bool | None = None if "in_app" not in channels else False
    email_ok: bool | None = None if "email" not in channels else False
    delivery_result: dict | None = None

    if parent:
        from app.services.notification_service import (
            send_multi_channel_notification,
        )

        delivery_result = send_multi_channel_notification(
            db=db,
            recipient=parent,
            sender=None,
            title=f"Email Digest for {child_name}",
            content=digest_content or "No new emails today.",
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link="/email-digest",
            channels=notification_channels,
        )

    if delivery_result:
        # send_multi_channel_notification returns per-channel outcomes keyed by
        # channel id ("in_app" corresponds to the "app_notification" channel
        # passed above). Each value is True / False / None — preserve the None
        # (preference-suppressed) so it is excluded from overall-status
        # computation below (#3887).
        if "in_app" in channels:
            in_app_ok = delivery_result.get("in_app")
        if "email" in channels:
            email_ok = delivery_result.get("email")

    # WhatsApp delivery (#2987, #3585, #3586, #3620)
    whatsapp_status: str | None = None
    whatsapp_ok: bool | None = None
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

                # Header / footer used by the freeform fallback path
                header = f"Hi {parent_name}, here's your child's daily school email summary:\n\n"
                footer = "\n\nView full digest at https://www.classbridge.ca/email-digest"

                # Use Content API template if content_sid configured (#3585)
                content_sid = app_settings.twilio_whatsapp_digest_content_sid
                if content_sid:
                    # #3904 — preserve \n and \t inside the template variable so paragraph
                    # breaks survive (most WhatsApp Content templates accept newlines). Strip
                    # only non-printable control chars (ASCII 0-8, 11-12, 14-31). The whitespace-
                    # collapse step from the over-aggressive #3879 fix is dropped — it was the
                    # cause of the wall-of-text formatting bug. Per-variable 1024 cap stays.
                    sanitised_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', plain_text).strip()
                    max_var_len = 1024
                    if len(sanitised_text) > max_var_len:
                        sanitised_text = sanitised_text[:max_var_len - 3] + "..."
                    # parent_name: still strip newlines/control chars (it's a single-line variable;
                    # split()[0] of full_name shouldn't have any anyway, defence in depth).
                    sanitised_parent_name = re.sub(r'[\x00-\x1f]', ' ', parent_name).strip()
                    wa_success = send_whatsapp_template(
                        integration.whatsapp_phone,
                        content_sid,
                        {"1": sanitised_parent_name, "2": sanitised_text},
                    )
                else:
                    # Fallback: body-text matching (works in sandbox / session window).
                    # Truncate digest content BEFORE wrapping in template (#3586).
                    # Reserve space for header + footer so they're never cut off.
                    max_content_len = 1600 - len(header) - len(footer)
                    if len(plain_text) > max_content_len:
                        plain_text = plain_text[:max_content_len - 3] + "..."
                    template_msg = f"{header}{plain_text}{footer}"
                    wa_success = send_whatsapp_message(integration.whatsapp_phone, template_msg)
                whatsapp_status = "sent" if wa_success else "failed"
                whatsapp_ok = bool(wa_success)
            except Exception as e:
                whatsapp_status = "failed"
                whatsapp_ok = False
                logger.warning("WhatsApp delivery failed for integration %d: %s", integration.id, e)
        else:
            whatsapp_status = "skipped"
            # WhatsApp selected but not verified / phone missing → not
            # applicable (None), NOT a failure (#3887). The parent hasn't
            # finished WhatsApp setup, so we cannot score this channel.
            whatsapp_ok = None

    # Compute overall status from selected channels (#3880, refined #3887).
    # Filter out None (not applicable / skipped) — only count actual outcomes.
    outcomes = [x for x in (
        in_app_ok if "in_app" in channels else None,
        email_ok if "email" in channels else None,
        whatsapp_ok if "whatsapp" in channels else None,
    ) if x is not None]

    if not outcomes:
        # Every selected channel was intentionally skipped (preference off,
        # WhatsApp not verified, etc.) OR no channels selected at all.
        overall_status = "skipped"
    elif all(outcomes):
        overall_status = "delivered"
    elif not any(outcomes):
        overall_status = "failed"
    else:
        overall_status = "partial"

    # Persisted per-channel email status (#3880) — mirrors whatsapp_delivery_status.
    # True=sent, False=failed, None=skipped (not requested or preference off).
    if "email" not in channels or email_ok is None:
        email_delivery_status = None if "email" not in channels else "skipped"
    else:
        email_delivery_status = "sent" if email_ok else "failed"

    email_count = len(emails) if emails else 0
    log_entry = DigestDeliveryLog(
        parent_id=integration.parent_id,
        integration_id=integration.id,
        email_count=email_count,
        digest_content=digest_content,
        digest_length_chars=len(digest_content) if digest_content else 0,
        channels_used=settings.delivery_channels,
        status=overall_status,
        whatsapp_delivery_status=whatsapp_status,
        email_delivery_status=email_delivery_status,
    )
    db.add(log_entry)

    integration.last_synced_at = now
    db.commit()

    # failed_labels must only list channels with an actual failure (False),
    # NOT channels that were skipped / not applicable (None) — #3887.
    failed_labels: list[str] = []
    if "in_app" in channels and in_app_ok is False:
        failed_labels.append("in-app")
    if "email" in channels and email_ok is False:
        failed_labels.append("email")
    if "whatsapp" in channels and whatsapp_ok is False:
        failed_labels.append("WhatsApp")

    if overall_status == "delivered":
        message = f"Digest delivered with {email_count} emails"
    elif overall_status == "partial":
        message = (
            f"Digest partially delivered ({email_count} emails). "
            f"Failed channels: {', '.join(failed_labels)}. Check your setup."
        )
    elif overall_status == "failed":
        message = (
            f"Digest delivery failed on all channels ({email_count} emails). "
            f"Please try again or check your setup."
        )
    elif overall_status == "skipped" and any(c in channels for c in ("in_app", "email", "whatsapp")):
        # Every selected channel was intentionally skipped — no failure, but
        # nothing was delivered either (#3887). Guide the parent to fix
        # preferences rather than "check your setup" (implies failure).
        message = (
            f"No eligible channels ({email_count} emails). "
            f"Please verify WhatsApp or enable notifications in your preferences."
        )
    else:
        message = f"Digest skipped ({email_count} emails)."

    channel_status = {
        "in_app": in_app_ok,
        "email": email_ok,
        "whatsapp": whatsapp_ok,
    }

    # #3894: when overall_status == "skipped" AND at least one channel was
    # actually selected (i.e., this is the "every selected channel intentionally
    # skipped" branch, not a no-channels-selected edge case), surface the
    # machine-readable reason "no_eligible_channels" so frontends can gate the
    # "Open preferences" link on the situations where it's actionable.
    reason: str | None = None
    if overall_status == "skipped" and any(
        c in channels for c in ("in_app", "email", "whatsapp")
    ):
        reason = "no_eligible_channels"

    return {
        "status": overall_status,
        "email_count": email_count,
        "message": message,
        "channel_status": channel_status,
        "reason": reason,
    }


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
