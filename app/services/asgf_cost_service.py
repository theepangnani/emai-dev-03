"""ASGF cost logging and session cap enforcement (#3405)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.ai_usage_history import AIUsageHistory
from app.models.learning_history import LearningHistory

logger = get_logger(__name__)

# Free-tier cap: 10 ASGF sessions per student per month.
ASGF_FREE_TIER_LIMIT = 10


async def log_asgf_cost(
    session_id: str,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user_id: int,
    db: Session,
) -> None:
    """Log an AI cost entry for an ASGF operation to ``ai_usage_history``.

    Parameters
    ----------
    session_id:
        The ASGF session UUID (hex).
    operation:
        A short label such as ``"asgf_plan"``, ``"asgf_slide"``, ``"asgf_quiz"``.
    model:
        The LLM model name, e.g. ``"gpt-4o-mini"``.
    input_tokens / output_tokens:
        Token counts returned by the LLM.
    user_id:
        The user who triggered the operation.
    db:
        Active SQLAlchemy session.
    """
    total_tokens = input_tokens + output_tokens

    # Rough cost estimate (gpt-4o-mini pricing as of 2025-Q1).
    cost_per_input = 0.15 / 1_000_000   # $0.15 per 1M input tokens
    cost_per_output = 0.60 / 1_000_000  # $0.60 per 1M output tokens
    estimated_cost = input_tokens * cost_per_input + output_tokens * cost_per_output

    row = AIUsageHistory(
        user_id=user_id,
        generation_type=operation,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=round(estimated_cost, 6),
        model_name=model,
    )
    try:
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning(
            "Failed to log ASGF cost for session %s operation %s",
            session_id,
            operation,
        )


async def check_session_cap(student_id: int, db: Session) -> dict:
    """Count ASGF sessions this calendar month for a student.

    Returns
    -------
    dict with keys ``used``, ``limit``, ``remaining``, ``can_start``.
    """
    now = datetime.now(timezone.utc)
    used = (
        db.query(func.count(LearningHistory.id))
        .filter(
            LearningHistory.student_id == student_id,
            LearningHistory.session_type == "asgf",
            extract("year", LearningHistory.created_at) == now.year,
            extract("month", LearningHistory.created_at) == now.month,
        )
        .scalar()
    ) or 0

    limit = ASGF_FREE_TIER_LIMIT
    remaining = max(0, limit - used)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "can_start": remaining > 0,
    }


async def get_monthly_cost_summary(student_id: int, db: Session) -> dict:
    """Total AI cost for ASGF operations this month for a given student.

    Joins ``ai_usage_history`` rows whose ``generation_type`` starts with
    ``"asgf_"`` to learning_history via user ownership.

    Returns
    -------
    dict with ``total_cost_usd``, ``total_tokens``, ``session_count``.
    """
    now = datetime.now(timezone.utc)

    session_count = (
        db.query(func.count(LearningHistory.id))
        .filter(
            LearningHistory.student_id == student_id,
            LearningHistory.session_type == "asgf",
            extract("year", LearningHistory.created_at) == now.year,
            extract("month", LearningHistory.created_at) == now.month,
        )
        .scalar()
    ) or 0

    # Sum cost from ai_usage_history for asgf_* generation types this month.
    cost_row = (
        db.query(
            func.coalesce(func.sum(AIUsageHistory.estimated_cost_usd), 0.0),
            func.coalesce(func.sum(AIUsageHistory.total_tokens), 0),
        )
        .filter(
            AIUsageHistory.generation_type.like("asgf_%"),
            extract("year", AIUsageHistory.created_at) == now.year,
            extract("month", AIUsageHistory.created_at) == now.month,
        )
        .first()
    )

    total_cost = float(cost_row[0]) if cost_row else 0.0
    total_tokens = int(cost_row[1]) if cost_row else 0

    return {
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "session_count": session_count,
    }
