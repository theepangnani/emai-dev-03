"""
API routes for logging.
Receives logs from the frontend and writes them to the server log files.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional, List

from app.core.logging_config import get_logger, FrontendLogHandler

router = APIRouter(prefix="/logs", tags=["Logging"])

logger = get_logger("emai.frontend")
frontend_handler = FrontendLogHandler(logger)


class LogEntry(BaseModel):
    """Single log entry from frontend."""
    level: str  # debug, info, warn, error
    message: str
    timestamp: Optional[str] = None
    context: Optional[dict] = None


class LogBatch(BaseModel):
    """Batch of log entries from frontend."""
    entries: List[LogEntry]


@router.post("/")
async def receive_log(entry: LogEntry, request: Request):
    """
    Receive a single log entry from the frontend.

    This endpoint allows the frontend to send logs to the server
    for centralized logging and debugging.
    """
    context = entry.context or {}

    # Add request info to context
    if request.client:
        context["client_ip"] = request.client.host

    # Add user agent if available
    user_agent = request.headers.get("user-agent")
    if user_agent:
        # Truncate long user agents
        context["user_agent"] = user_agent[:100] if len(user_agent) > 100 else user_agent

    frontend_handler.log(
        level=entry.level,
        message=entry.message,
        context=context,
    )

    return {"status": "logged"}


@router.post("/batch")
async def receive_log_batch(batch: LogBatch, request: Request):
    """
    Receive a batch of log entries from the frontend.

    More efficient for sending multiple logs at once.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    for entry in batch.entries:
        context = entry.context or {}

        if client_ip:
            context["client_ip"] = client_ip
        if user_agent:
            context["user_agent"] = user_agent[:100] if len(user_agent) > 100 else user_agent

        frontend_handler.log(
            level=entry.level,
            message=entry.message,
            context=context,
        )

    return {"status": "logged", "count": len(batch.entries)}
