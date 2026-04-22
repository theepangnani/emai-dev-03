"""Background job: upsert Tasks from Assignment rows on a rolling window.

CB-TASKSYNC-001 I4 (issue #3916). Runs at 06:45 UTC — 15 minutes before the
daily digest (07:00 UTC) — so the digest email reflects the freshly-synced
tasks.

The job delegates all business logic to
:func:`app.services.task_sync_service.sync_all_upcoming_assignments` and is a
no-op when the ``task_sync_enabled`` feature flag is off. Exceptions raised by
the service are logged and swallowed so a bad batch never crashes the
scheduler.
"""
from app.core.logging_config import get_logger
from app.db.database import SessionLocal
from app.services.feature_flag_service import is_feature_enabled
from app.services.task_sync_service import sync_all_upcoming_assignments

logger = get_logger(__name__)


async def sync_assignments_to_tasks():
    """Scheduled 06:45 UTC — upsert Tasks from all Assignments in rolling window.

    Runs 15 min before the daily digest (07:00 UTC) so the digest email
    reflects the freshly-synced tasks.
    """
    if not is_feature_enabled("task_sync_enabled"):
        logger.info("task_sync.skipped | flag=off")
        return
    db = SessionLocal()
    try:
        stats = sync_all_upcoming_assignments(db)
        logger.info("task_sync_summary | source=assignment %s", stats)
    except Exception:
        logger.exception("task_sync.failed | source=assignment")
    finally:
        db.close()
