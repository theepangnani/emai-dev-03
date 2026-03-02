"""Unified LMS sync orchestration across all providers (#27).

Runs every 15 minutes (or on-demand via API).

Stale detection: if last_sync_at > 7 days ago and status is "connected",
set status to "stale" and emit a warning log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.lms_connection import LMSConnection
from app.services.lms_registry import get_provider

logger = logging.getLogger(__name__)

# Threshold after which a "connected" connection is considered stale (7 days)
STALE_THRESHOLD_DAYS = 7


async def sync_all_connections(db: Session) -> dict[str, int]:
    """Sync all active LMS connections and detect stale ones.

    Returns a dict with keys "synced" and "errors".
    """
    connections = (
        db.query(LMSConnection)
        .filter(LMSConnection.status.in_(["connected", "stale"]))
        .all()
    )

    synced = 0
    errors = 0

    for conn in connections:
        # --- Stale detection ---
        if conn.last_sync_at is not None:
            last_sync = conn.last_sync_at
            # Normalise to UTC-aware datetime for comparison
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - last_sync
            if age > timedelta(days=STALE_THRESHOLD_DAYS) and conn.status == "connected":
                logger.warning(
                    "LMS connection %s (user=%s provider=%s) has not synced in %d days — marking stale",
                    conn.id,
                    conn.user_id,
                    conn.provider,
                    age.days,
                )
                conn.status = "stale"
                db.commit()
                continue  # Skip sync for now — just marked stale

        # --- Sync ---
        try:
            await sync_single_connection(conn, db)
            synced += 1
        except Exception as exc:
            logger.error("Sync error for connection %s (user=%s): %s", conn.id, conn.user_id, exc)
            conn.sync_error = str(exc)
            conn.status = "error"
            errors += 1

    db.commit()
    logger.info("LMS sync complete: %d synced, %d errors", synced, errors)
    return {"synced": synced, "errors": errors}


async def sync_single_connection(conn: LMSConnection, db: Session) -> None:
    """Sync a single LMS connection.  Provider-specific logic.

    For Google Classroom the heavy lifting is done by the existing
    google_classroom service; here we just update the metadata counters.

    For Brightspace/Canvas (not yet OAuth-implemented) we advance the
    last_sync_at timestamp so they are not incorrectly marked stale.
    """
    provider = get_provider(conn.provider)
    if not provider:
        raise ValueError(f"Unknown provider: {conn.provider}")

    now = datetime.now(timezone.utc)

    if conn.provider == "google_classroom":
        # Google Classroom sync is handled by the existing google_classroom service.
        # Here we just update the courses_synced counter from the Course table.
        from app.models.course import Course

        course_count = (
            db.query(Course)
            .filter(Course.created_by_user_id == conn.user_id)
            .count()
        )
        conn.courses_synced = course_count
        conn.last_sync_at = now
        conn.sync_error = None
        conn.status = "connected"
        logger.debug(
            "Google Classroom sync for connection %s: %d courses",
            conn.id,
            course_count,
        )
    else:
        # Brightspace, Canvas, Moodle — OAuth not yet implemented.
        # Update timestamp only to prevent stale detection from firing repeatedly.
        logger.info(
            "Provider %s sync not yet implemented for connection %s — updating timestamp only",
            conn.provider,
            conn.id,
        )
        conn.last_sync_at = now

    db.commit()


def schedule_lms_sync(scheduler, get_db_func) -> None:
    """Register the 15-minute LMS sync job with APScheduler."""
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler.add_job(
        func=_run_sync_job,
        args=[get_db_func],
        trigger=IntervalTrigger(minutes=15),
        id="lms_sync",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("LMS sync job scheduled (every 15 minutes)")


async def _run_sync_job(get_db_func) -> None:
    """Wrapper called by APScheduler — obtains a DB session then runs sync."""
    db: Session = next(get_db_func())
    try:
        result = await sync_all_connections(db)
        logger.info("Scheduled LMS sync finished: %s", result)
    except Exception as exc:
        logger.error("Scheduled LMS sync job crashed: %s", exc, exc_info=True)
    finally:
        db.close()
