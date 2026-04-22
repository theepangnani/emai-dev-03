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
from app.models.user import User

logger = logging.getLogger(__name__)


class _SectionedWhatsAppDone(Exception):
    """Internal control-flow sentinel — sectioned WhatsApp path completed.

    #3956: the sectioned 3x3 digest uses V1/V2 WhatsApp templates that are
    exclusive to it and are fully handled before the legacy sanitisation
    block. Raising this sentinel inside the existing try/except jumps past
    the legacy path without re-implementing the outer error handling.
    """


def _sectioned_section_block(items: list[str], overflow: int) -> str:
    """Render a single sectioned block for the WhatsApp V2 4-variable template.

    Each block = up to 3 bullet lines + an optional "And N more" overflow line.
    Empty sections return "(none)" — Twilio V2 template rules forbid empty
    variables.
    """
    items = items[:3]
    if not items:
        return "(none)"
    lines = [f"- {it}" for it in items]
    if overflow and overflow > 0:
        lines.append(f"+ And {overflow} more")
    return "\n".join(lines)


def _flatten_sectioned_to_bullets(sectioned: dict) -> str:
    """Collapse sectioned 3x3 content into a single-line-with-bullets string.

    Used by the V1 WhatsApp template path when V2 env var is NOT set.
    Format:
        "Urgent • item1 • item2 • (And N more) • Announcements • ... • Action Items • ..."
    Empty sections are skipped entirely (no section heading).
    """
    overflow = sectioned.get("overflow") or {}
    pieces: list[str] = []
    labels = (
        ("urgent", "Urgent"),
        ("announcements", "Announcements"),
        ("action_items", "Action Items"),
    )
    for key, label in labels:
        items = (sectioned.get(key) or [])[:3]
        if not items:
            continue
        pieces.append(label)
        pieces.extend(items)
        try:
            more = int(overflow.get(key, 0) or 0)
        except (TypeError, ValueError):
            more = 0
        if more > 0:
            pieces.append(f"(And {more} more)")
    return " • ".join(pieces)


def _sanitise_whatsapp_var(text: str) -> str:
    """Apply the #3941 Twilio V1 daily_digest variable sanitisation rules."""
    s = text.replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'\n{2,}', ' • ', s)
    s = re.sub(r'[\n\r\t]', ' ', s)
    s = re.sub(r'[\x00-\x1f]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) > 1024:
        s = s[:1021] + "..."
    return s


def _send_sectioned_whatsapp_v2(
    to_phone: str,
    content_sid: str,
    parent_name: str,
    sectioned: dict,
) -> bool:
    """Send the 4-variable Twilio V2 sectioned daily-digest template.

    Variables:
      1 -> parent_name
      2 -> urgent_block (3 items + overflow, newline-separated, or "(none)")
      3 -> announcements_block (same)
      4 -> action_items_block (same)
    """
    from app.services.whatsapp_service import send_whatsapp_template

    overflow = sectioned.get("overflow") or {}

    def _of(key: str) -> int:
        try:
            return max(0, int(overflow.get(key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    urgent_block = _sectioned_section_block(sectioned.get("urgent") or [], _of("urgent"))
    announcements_block = _sectioned_section_block(
        sectioned.get("announcements") or [], _of("announcements")
    )
    action_items_block = _sectioned_section_block(
        sectioned.get("action_items") or [], _of("action_items")
    )

    sanitised_parent_name = re.sub(r'[\x00-\x1f]', ' ', parent_name).strip()
    return send_whatsapp_template(
        to_phone,
        content_sid,
        {
            "1": sanitised_parent_name,
            "2": urgent_block,
            "3": announcements_block,
            "4": action_items_block,
        },
    )


def _sectioned_to_plain_text(sectioned: dict) -> str:
    """Render sectioned content as plain text for the delivery-log digest_content column."""
    overflow = sectioned.get("overflow") or {}
    parts: list[str] = []
    labels = (
        ("urgent", "Urgent"),
        ("announcements", "Announcements"),
        ("action_items", "Action Items"),
    )
    for key, label in labels:
        items = (sectioned.get(key) or [])[:3]
        if not items:
            continue
        parts.append(f"{label}:")
        parts.extend(f"- {it}" for it in items)
        try:
            more = int(overflow.get(key, 0) or 0)
        except (TypeError, ValueError):
            more = 0
        if more > 0:
            parts.append(f"And {more} more")
        parts.append("")
    return "\n".join(parts).strip()


async def send_digest_for_integration(db: Session, integration: ParentGmailIntegration, *, skip_dedup: bool = False, since: datetime | None = None) -> dict:
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

    # #3956: "sectioned" format uses the 3x3 JSON contract and a different
    # render path (3 section headings + overflow "More ->" CTA). Legacy brief/
    # full/actions_only formats keep the single-HTML-blob path unchanged.
    is_sectioned = settings.digest_format == "sectioned"
    sectioned_content: dict | None = None

    try:
        from app.services.parent_digest_ai_service import (
            generate_parent_digest,
            generate_sectioned_digest,
        )

        if is_sectioned:
            sectioned_content = await generate_sectioned_digest(
                emails, child_name, parent_name
            )
            # When JSON parse / AI errors force legacy fallback, the sectioned
            # dict carries a ``legacy_blob`` HTML string. Use that as the
            # primary digest_content so the email-render path and delivery-log
            # persistence still work.
            if sectioned_content.get("legacy_blob"):
                digest_content = sectioned_content["legacy_blob"]
            else:
                # Build a plain-text fallback representation for the
                # DigestDeliveryLog.digest_content column so historical logs
                # still contain something readable.
                digest_content = _sectioned_to_plain_text(sectioned_content)
        else:
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

        # #3956: render sectioned 3x3 HTML when available; legacy_blob already
        # propagated into digest_content above so the legacy render path runs
        # unchanged.
        if (
            is_sectioned
            and sectioned_content
            and not sectioned_content.get("legacy_blob")
        ):
            from app.services.notification_service import (
                build_sectioned_digest_email_body,
            )

            email_html_content = build_sectioned_digest_email_body(sectioned_content)
        else:
            email_html_content = digest_content or "No new emails today."

        delivery_result = send_multi_channel_notification(
            db=db,
            recipient=parent,
            sender=None,
            title=f"Email Digest for {child_name}",
            content=email_html_content,
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

                # #3956: sectioned 3x3 has its own WhatsApp paths.
                # - V2 env var set  -> 4-variable Twilio template call
                # - V2 env var empty -> fall back to V1 single-variable template
                #   (flatten sectioned into single-line-with-bullets).
                use_sectioned_wa = (
                    is_sectioned
                    and sectioned_content
                    and not sectioned_content.get("legacy_blob")
                )
                if use_sectioned_wa:
                    v2_sid = app_settings.twilio_whatsapp_digest_content_sid_v2
                    v1_sid = app_settings.twilio_whatsapp_digest_content_sid

                    if v2_sid:
                        wa_success = _send_sectioned_whatsapp_v2(
                            integration.whatsapp_phone,
                            v2_sid,
                            parent_name,
                            sectioned_content,
                        )
                    else:
                        # V1 path: flatten 3x3 into single-line-with-bullets.
                        flattened = _flatten_sectioned_to_bullets(sectioned_content)
                        if v1_sid:
                            sanitised_text = _sanitise_whatsapp_var(flattened)
                            sanitised_parent_name = re.sub(
                                r'[\x00-\x1f]', ' ', parent_name
                            ).strip()
                            wa_success = send_whatsapp_template(
                                integration.whatsapp_phone,
                                v1_sid,
                                {"1": sanitised_parent_name, "2": sanitised_text},
                            )
                        else:
                            # No SID at all -> freeform fallback with flattened text.
                            header = (
                                f"Hi {parent_name}, here's your child's daily "
                                f"school email summary:\n\n"
                            )
                            footer = (
                                "\n\nView full digest at "
                                "https://www.classbridge.ca/email-digest"
                            )
                            max_content_len = 1600 - len(header) - len(footer)
                            body = (
                                flattened[:max_content_len - 3] + "..."
                                if len(flattened) > max_content_len
                                else flattened
                            )
                            wa_success = send_whatsapp_message(
                                integration.whatsapp_phone,
                                f"{header}{body}{footer}",
                            )
                    whatsapp_status = "sent" if wa_success else "failed"
                    whatsapp_ok = bool(wa_success)
                    # Sectioned path handled — skip the legacy sanitisation block.
                    raise _SectionedWhatsAppDone()

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
                    # #3941 — Twilio's daily_digest Content Template rejects \n in variables
                    # (empirically verified: #3906's newline-preservation caused HTTP 400 on
                    # every send). Substitute structural newlines with visible section
                    # markers so parents still get a scannable digest without hitting Twilio's
                    # variable-content policy. See #3905 for the proper multi-variable
                    # redesign that supersedes this workaround.
                    sanitised_text = plain_text
                    # Normalise CRLF / CR line endings to LF first so the
                    # paragraph-break pattern below catches Windows and old-
                    # Mac line endings too (PR-review suggestion on #3941).
                    sanitised_text = sanitised_text.replace('\r\n', '\n').replace('\r', '\n')
                    # Paragraph break → bullet marker (visible section boundary)
                    sanitised_text = re.sub(r'\n{2,}', ' • ', sanitised_text)
                    # Single \n / \r / \t → space
                    sanitised_text = re.sub(r'[\n\r\t]', ' ', sanitised_text)
                    # Strip all remaining control chars (ASCII 0-31)
                    sanitised_text = re.sub(r'[\x00-\x1f]', ' ', sanitised_text)
                    # Collapse whitespace runs
                    sanitised_text = re.sub(r'\s+', ' ', sanitised_text).strip()
                    # Per-variable 1024 cap
                    max_var_len = 1024
                    if len(sanitised_text) > max_var_len:
                        sanitised_text = sanitised_text[:max_var_len - 3] + "..."
                    # parent_name: single-line variable — strip all control chars
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
            except _SectionedWhatsAppDone:
                # #3956 — sectioned WhatsApp path already set status/ok above.
                pass
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
