import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Insert an audit log entry.

    Uses a SAVEPOINT so that failures in audit logging never corrupt
    the caller's transaction.  If the insert fails the savepoint is
    rolled back and the outer transaction remains healthy.
    """
    if not settings.audit_log_enabled:
        return
    try:
        with db.begin_nested():
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(entry)
            db.flush()
    except Exception:
        logger.warning("Failed to write audit log", exc_info=True)
