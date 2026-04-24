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
    # #4006 defensive pass: catch any HTML tag fragments that survived the
    # initial r'<[^>]+>' strip (malformed/unterminated tags in source AI output).
    # Also strip lone angle brackets that indicate tag residue.
    s = re.sub(r'<[^>]*>?', '', s)
    s = re.sub(r'</[^\s]*', '', s)  # unterminated closing tags
    s = s.replace('<', '').replace('>', '')
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

        fetch_result = await fetch_child_emails(db, integration, since=since)
        emails = fetch_result.get("emails", [])
        # #4058 — synced_at is applied to integration.last_synced_at only
        # at the final delivery-log commit below so a crash between fetch
        # and log does not silently swallow a parent-day of mail on retry.
        fetched_synced_at = fetch_result.get("synced_at")
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
                    # #4006 defensive pass: catch any HTML tag fragments that survived the
                    # initial r'<[^>]+>' strip (malformed/unterminated tags in source AI output).
                    # Also strip lone angle brackets that indicate tag residue.
                    sanitised_text = re.sub(r'<[^>]*>?', '', sanitised_text)
                    sanitised_text = re.sub(r'</[^\s]*', '', sanitised_text)  # unterminated closing tags
                    sanitised_text = sanitised_text.replace('<', '').replace('>', '')
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

    # #4058 — advance last_synced_at atomically with the DigestDeliveryLog
    # insert. Use the timestamp returned by fetch_child_emails (captured at
    # the moment the fetch succeeded) so the window advances to exactly
    # where we stopped reading. Fall back to ``now`` if the fetcher did
    # not supply one (e.g. no-op fetch on a no-query integration).
    integration.last_synced_at = fetched_synced_at or now
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
    """Run every 4 hours.

    Dispatch: when the ``parent.unified_digest_v2`` feature flag is ON,
    delegate to :func:`process_unified_parent_email_digests` which sends
    ONE digest per parent (grouped across all their integrations +
    attributed to kid profiles). When OFF, keep the legacy per-integration
    loop unchanged.
    """
    from app.services.feature_flag_service import is_feature_enabled

    logger.info("Running parent email digest job...")

    db = SessionLocal()
    try:
        if is_feature_enabled("parent.unified_digest_v2", db=db):
            logger.info(
                "Parent email digest: unified_digest_v2 flag ON — running unified path"
            )
            await process_unified_parent_email_digests(db)
        else:
            await _process_legacy_parent_email_digests(db)
    finally:
        db.close()


async def _process_legacy_parent_email_digests(db) -> None:
    """Legacy path: one digest per integration (pre-#4012 behavior).

    Extracted so :func:`process_parent_email_digests` can conditionally
    delegate to :func:`process_unified_parent_email_digests` when the
    ``parent.unified_digest_v2`` feature flag is ON without duplicating
    the fetch-loop scaffold.
    """
    sent = 0
    skipped = 0
    failed = 0
    try:
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


# ---------------------------------------------------------------------------
# Unified digest v2 (#4012, #4015) — single-digest-per-parent path
# ---------------------------------------------------------------------------

def _parent_first_name(parent: "User | None") -> str:
    """Derive a first-name greeting from ``User.full_name``.

    Mirrors the #3845 safe-split logic used by the legacy worker so the
    unified path greets parents identically.
    """
    if parent is None or not parent.full_name:
        return "Parent"
    parts = parent.full_name.split()
    return parts[0] if parts else "Parent"


def _render_unified_digest_sections(sections: dict) -> str:
    """Render the unified digest as a minimal HTML body.

    Kept deliberately simple — Stream 4 owns frontend polish; the worker
    just needs something deliverable through the existing
    ``send_multi_channel_notification`` path.

    ``sections`` shape:
        {
            "for_all_kids": [email, ...],
            "per_kid": { kid_id: [email, ...] },
            "per_kid_names": { kid_id: "FirstName" },
            "unattributed": [email, ...],
        }
    """
    parts: list[str] = []

    def _block(title: str, emails: list[dict]) -> str:
        if not emails:
            return ""
        items = "".join(
            "<li><strong>{subject}</strong> &mdash; {snippet}</li>".format(
                subject=(e.get("subject") or "(no subject)"),
                snippet=(e.get("snippet") or e.get("sender_email") or ""),
            )
            for e in emails
        )
        return f"<h3>{title}</h3><ul>{items}</ul>"

    parts.append(_block("For all your kids", sections.get("for_all_kids") or []))

    per_kid = sections.get("per_kid") or {}
    names = sections.get("per_kid_names") or {}
    for kid_id, emails in per_kid.items():
        label = names.get(kid_id) or f"Kid #{kid_id}"
        parts.append(_block(f"For {label}", emails))

    parts.append(_block("Unattributed", sections.get("unattributed") or []))

    body = "\n".join(p for p in parts if p)
    return body or "No new school emails today."


async def send_unified_digest_for_parent(
    db: "Session",
    parent_id: int,
    *,
    skip_dedup: bool = False,
    since: datetime | None = None,
) -> dict:
    """Fetch all integrations for one parent, attribute each email, deliver ONE digest.

    Returns a summary dict (same keys as
    :func:`send_digest_for_integration` plus ``attribution_counts`` for
    observability):

        {
            "status": "delivered" | "skipped" | "failed",
            "email_count": int,
            "attribution_counts": {
                "school_email": int,
                "sender_tag": int,
                "applies_to_all": int,
                "unattributed": int,
            },
            "message": str,
        }
    """
    # Lazy imports for the same test-reload reasons as other helpers.
    from app.models.user import User
    from app.services.parent_gmail_service import fetch_child_emails
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_APPLIES_TO_ALL,
        ATTR_SOURCE_SCHOOL_EMAIL,
        ATTR_SOURCE_SENDER_TAG,
        ATTR_SOURCE_UNATTRIBUTED,
        attribute_email,
        build_sectioned_digest,
    )

    now = datetime.now(timezone.utc)

    parent = db.query(User).filter(User.id == parent_id).first()
    if parent is None:
        return {
            "status": "skipped",
            "email_count": 0,
            "attribution_counts": {},
            "message": "Parent not found",
            "reason": "parent_missing",
        }

    integrations = (
        db.query(ParentGmailIntegration)
        .join(ParentDigestSettings)
        .options(joinedload(ParentGmailIntegration.digest_settings))
        .options(joinedload(ParentGmailIntegration.parent))
        .filter(ParentGmailIntegration.parent_id == parent_id)
        .filter(ParentGmailIntegration.is_active == True)  # noqa: E712
        .filter(ParentDigestSettings.digest_enabled == True)  # noqa: E712
        .filter(
            (ParentGmailIntegration.paused_until == None)  # noqa: E711
            | (ParentGmailIntegration.paused_until < now)
        )
        .all()
    )

    if not integrations:
        return {
            "status": "skipped",
            "email_count": 0,
            "attribution_counts": {},
            "message": "No active integrations for parent",
            "reason": "no_integrations",
        }

    # Dedup: one delivered digest per parent per day. The legacy path
    # dedups per integration; the unified path dedups per parent since
    # we send ONE envelope regardless of integration count.
    if not skip_dedup:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        integration_ids = [i.id for i in integrations]
        existing_log = (
            db.query(DigestDeliveryLog)
            .filter(
                DigestDeliveryLog.parent_id == parent_id,
                DigestDeliveryLog.integration_id.in_(integration_ids),
                DigestDeliveryLog.delivered_at >= today_start,
                DigestDeliveryLog.status == "delivered",
            )
            .first()
        )
        if existing_log:
            # #4052 — advance last_synced_at so the next run doesn't fetch
            # the same historical window indefinitely when dedup short-
            # circuits delivery.
            for integ in integrations:
                integ.last_synced_at = now
            db.commit()
            return {
                "status": "skipped",
                "email_count": 0,
                "attribution_counts": {},
                "message": "Already delivered today",
                "reason": "already_delivered",
            }

    # Fetch + attribute per integration, then merge. Emails that appear
    # from multiple integrations are deduplicated by ``source_id`` to
    # match the legacy behavior.
    attributed_pairs: list[tuple[dict, dict]] = []
    seen_ids: set[str] = set()
    # #4058 — record each integration's fetch-synced_at so we can stamp
    # last_synced_at atomically with the final delivery-log commit below
    # (see legacy send_digest_for_integration for the same pattern). This
    # prevents a crash between fetch and log from silently dropping a
    # parent-day of mail on retry.
    fetched_synced_at_by_id: dict[int, datetime] = {}
    for integration in integrations:
        try:
            fetch_result = await fetch_child_emails(db, integration, since=since)
        except Exception:
            logger.exception(
                "Unified digest: fetch failed | integration_id=%s parent_id=%s",
                integration.id,
                parent_id,
            )
            continue

        emails = fetch_result.get("emails", [])
        synced_at_value = fetch_result.get("synced_at")
        if synced_at_value is not None:
            fetched_synced_at_by_id[integration.id] = synced_at_value

        for email in emails or []:
            src = email.get("source_id")
            if src and src in seen_ids:
                continue
            if src:
                seen_ids.add(src)

            headers = {
                "to": email.get("to_addresses") or [],
                "delivered-to": email.get("delivered_to_addresses") or [],
                "from": email.get("sender_email") or "",
            }
            attribution = attribute_email(headers, parent_id, db)
            attributed_pairs.append((email, attribution))

    email_count = len(attributed_pairs)

    # Build section structure + attribution summary for observability.
    sections = build_sectioned_digest(attributed_pairs)
    attribution_counts = {
        ATTR_SOURCE_SCHOOL_EMAIL: 0,
        ATTR_SOURCE_SENDER_TAG: 0,
        ATTR_SOURCE_APPLIES_TO_ALL: 0,
        ATTR_SOURCE_UNATTRIBUTED: 0,
    }
    for _, attribution in attributed_pairs:
        key = attribution.get("source") or ATTR_SOURCE_UNATTRIBUTED
        attribution_counts[key] = attribution_counts.get(key, 0) + 1

    # Resolve kid-first-name labels for per-kid sections.
    from app.models.parent_gmail_integration import ParentChildProfile

    kid_id_set = set(sections.get("per_kid", {}).keys())
    per_kid_names: dict[int, str] = {}
    if kid_id_set:
        rows = (
            db.query(ParentChildProfile.id, ParentChildProfile.first_name)
            .filter(ParentChildProfile.id.in_(kid_id_set))
            .all()
        )
        per_kid_names = {pid: name for (pid, name) in rows}
    sections["per_kid_names"] = per_kid_names

    # No emails across all integrations → optionally skip (mirrors the
    # per-integration ``notify_on_empty`` semantics using the first
    # integration's settings as the parent-level default).
    primary_settings = integrations[0].digest_settings
    notify_on_empty = bool(primary_settings and primary_settings.notify_on_empty)
    if email_count == 0 and not notify_on_empty:
        # #4052 — advance last_synced_at so the next run's since-window
        # starts from now even when we skip delivery.
        for integ in integrations:
            integ.last_synced_at = now
        db.commit()
        return {
            "status": "skipped",
            "email_count": 0,
            "attribution_counts": attribution_counts,
            "message": "No new emails",
            "reason": "no_new_emails",
        }

    digest_html = _render_unified_digest_sections(sections)
    parent_name = _parent_first_name(parent)

    # Delivery: in_app + email only for the v2 MVP. WhatsApp is still
    # scoped to the legacy per-integration templates (Stream 5 handles
    # the v2 WhatsApp rollout). We reuse the primary integration's
    # ``delivery_channels`` setting to respect parent preferences.
    channels_setting = (
        primary_settings.delivery_channels
        if primary_settings and primary_settings.delivery_channels
        else "in_app,email"
    )
    channels = [c.strip() for c in channels_setting.split(",") if c.strip()]
    notification_channels: list[str] = []
    if "in_app" in channels:
        notification_channels.append("app_notification")
    if "email" in channels:
        notification_channels.append("email")

    in_app_ok: bool | None = None if "in_app" not in channels else False
    email_ok: bool | None = None if "email" not in channels else False

    delivery_result: dict | None = None
    if notification_channels:
        from app.services.notification_service import (
            send_multi_channel_notification,
        )

        delivery_result = send_multi_channel_notification(
            db=db,
            recipient=parent,
            sender=None,
            title="Email Digest for your kids",
            content=digest_html,
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link="/email-digest",
            channels=notification_channels,
        )

    if delivery_result:
        if "in_app" in channels:
            in_app_ok = delivery_result.get("in_app")
        if "email" in channels:
            email_ok = delivery_result.get("email")

    outcomes = [
        x
        for x in (
            in_app_ok if "in_app" in channels else None,
            email_ok if "email" in channels else None,
        )
        if x is not None
    ]
    if not outcomes:
        overall_status = "skipped"
    elif all(outcomes):
        overall_status = "delivered"
    elif not any(outcomes):
        overall_status = "failed"
    else:
        overall_status = "partial"

    # #4052 — Persist a single synthetic DigestDeliveryLog per unified run
    # (keyed to integrations[0]) so the existing per-integration /logs
    # endpoint still surfaces it without duplicating history rows. The
    # ``scope`` column is intentionally not introduced this round —
    # keeping this change minimal per the fix scope.
    email_delivery_status = (
        None
        if "email" not in channels or email_ok is None
        else ("sent" if email_ok else "failed")
    )
    primary_integration = integrations[0]
    log_entry = DigestDeliveryLog(
        parent_id=parent_id,
        integration_id=primary_integration.id,
        email_count=email_count,
        digest_content=digest_html,
        digest_length_chars=len(digest_html),
        channels_used=channels_setting,
        status=overall_status,
        email_delivery_status=email_delivery_status,
    )
    db.add(log_entry)
    # #4058 — advance last_synced_at atomically with the delivery-log
    # insert. Only stamp integrations whose fetch actually succeeded
    # (present in the map). If the fetch errored for an integration, we
    # intentionally leave its stamp pinned so the retry picks up the real
    # unread window — advancing to ``now`` here would silently drop that
    # integration's unread mail on the next run (mini-#4058 regression).
    for integration in integrations:
        if integration.id in fetched_synced_at_by_id:
            integration.last_synced_at = fetched_synced_at_by_id[integration.id]
    db.commit()

    message = (
        f"Unified digest delivered with {email_count} emails"
        if overall_status == "delivered"
        else f"Unified digest {overall_status} ({email_count} emails)"
    )
    return {
        "status": overall_status,
        "email_count": email_count,
        "attribution_counts": attribution_counts,
        "message": message,
    }


async def process_unified_parent_email_digests(db) -> None:
    """Unified path: one digest per parent (flag ON).

    Queries the distinct set of parents with at least one active
    integration and digests enabled, then delegates to
    :func:`send_unified_digest_for_parent` for each.
    """
    sent = 0
    skipped = 0
    failed = 0
    try:
        now = datetime.now(timezone.utc)
        parent_id_rows = (
            db.query(ParentGmailIntegration.parent_id)
            .join(ParentDigestSettings)
            .filter(
                ParentGmailIntegration.is_active == True,  # noqa: E712
                ParentDigestSettings.digest_enabled == True,  # noqa: E712
            )
            .filter(
                (ParentGmailIntegration.paused_until == None)  # noqa: E711
                | (ParentGmailIntegration.paused_until < now)
            )
            .distinct()
            .all()
        )
        parent_ids = [row[0] for row in parent_id_rows]

        logger.info(
            "Unified parent email digest: found %d parents", len(parent_ids)
        )

        for parent_id in parent_ids:
            try:
                result = await send_unified_digest_for_parent(db, parent_id)
                status = result.get("status")
                if status == "delivered":
                    sent += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    failed += 1
            except Exception:
                logger.exception(
                    "Unified parent email digest failed | parent_id=%s",
                    parent_id,
                )
                db.rollback()
                failed += 1

        logger.info(
            "Unified parent email digest job complete | sent=%d | skipped=%d | failed=%d",
            sent,
            skipped,
            failed,
        )
    except Exception:
        db.rollback()
        logger.exception("Unified parent email digest job failed")
