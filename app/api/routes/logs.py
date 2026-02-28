"""
API routes for logging.
Receives logs from the frontend and writes them to the server log files.
Requires authentication to prevent log flooding/injection.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List

from app.core.logging_config import get_logger, FrontendLogHandler
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/logs", tags=["Logging"])

logger = get_logger("emai.frontend")
frontend_handler = FrontendLogHandler(logger)

_MAX_MESSAGE_LENGTH = 2000
_MAX_BATCH_SIZE = 50
_VALID_LEVELS = {"debug", "info", "warn", "error"}


class LogEntry(BaseModel):
    """Single log entry from frontend."""
    level: str  # debug, info, warn, error
    message: str = Field(max_length=_MAX_MESSAGE_LENGTH)
    timestamp: Optional[str] = None
    context: Optional[dict] = None


class LogBatch(BaseModel):
    """Batch of log entries from frontend."""
    entries: List[LogEntry] = Field(max_length=_MAX_BATCH_SIZE)


@router.post("/")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def receive_log(
    entry: LogEntry,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Receive a single log entry from the frontend (authenticated)."""
    level = entry.level.lower()
    if level not in _VALID_LEVELS:
        level = "info"

    context = entry.context or {}
    context["user_id"] = current_user.id

    if request.client:
        context["client_ip"] = request.client.host

    user_agent = request.headers.get("user-agent")
    if user_agent:
        context["user_agent"] = user_agent[:100]

    frontend_handler.log(
        level=level,
        message=entry.message[:_MAX_MESSAGE_LENGTH],
        context=context,
    )

    return {"status": "logged"}


@router.post("/batch")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def receive_log_batch(
    batch: LogBatch,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Receive a batch of log entries from the frontend (authenticated)."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    for entry in batch.entries[:_MAX_BATCH_SIZE]:
        level = entry.level.lower()
        if level not in _VALID_LEVELS:
            level = "info"

        context = entry.context or {}
        context["user_id"] = current_user.id

        if client_ip:
            context["client_ip"] = client_ip
        if user_agent:
            context["user_agent"] = user_agent[:100]

        frontend_handler.log(
            level=level,
            message=entry.message[:_MAX_MESSAGE_LENGTH],
            context=context,
        )

    return {"status": "logged", "count": len(batch.entries)}
