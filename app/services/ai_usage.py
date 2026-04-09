"""
AI usage limit enforcement helpers.

Provides check_ai_usage() and increment_ai_usage() to enforce per-user
AI credit limits across all generation paths.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.user import User

logger = get_logger(__name__)


def check_ai_usage(user: User, db: Session) -> None:
    """Check if user has remaining AI credits. Raises 429 if at limit.

    Checks wallet balance first (new system). Falls back to legacy
    ai_usage_limit check for users without wallets.
    """
    # --- Wallet-based credit check (§6.60) ---
    from app.models.wallet import Wallet

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if wallet:
        total = (wallet.package_credits or 0) + (wallet.purchased_credits or 0)
        if total > 0:
            return  # Wallet has credits — allow
        # Wallet exists but empty — check if legacy system allows it
        # (fall through to legacy check below)

    # --- Legacy ai_usage_limit check (unchanged) ---
    limit = getattr(user, "ai_usage_limit", None)
    count = getattr(user, "ai_usage_count", None)

    # Treat NULL / 0 limit as unlimited (admin users, pre-migration rows)
    if not limit:
        return

    if count is None:
        count = 0

    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"AI usage limit reached. You have used all {limit} of your "
                f"AI credits. Request more from the admin panel."
            ),
        )


def log_ai_usage(
    user: User,
    db: Session,
    generation_type: str,
    course_material_id: int | None = None,
    credits_used: int = 1,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    model_name: str | None = None,
    is_regeneration: bool = False,
    parent_generation_id: int | None = None,
) -> None:
    """Insert a row into ai_usage_history for audit trail."""
    from app.models.ai_usage_history import AIUsageHistory

    entry = AIUsageHistory(
        user_id=user.id,
        generation_type=generation_type,
        course_material_id=course_material_id,
        credits_used=credits_used,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model_name=model_name,
        is_regeneration=is_regeneration,
        parent_generation_id=parent_generation_id,
    )
    db.add(entry)
    logger.debug(
        "AI usage history logged | user_id=%s | type=%s | material=%s | regen=%s | tokens=%s | cost=$%.6f",
        user.id, generation_type, course_material_id, is_regeneration,
        total_tokens, estimated_cost_usd or 0,
    )


def increment_ai_usage(
    user: User,
    db: Session,
    generation_type: str = "unknown",
    course_material_id: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    model_name: str | None = None,
    is_regeneration: bool = False,
    parent_generation_id: int | None = None,
    wallet_debit_amount=None,
) -> None:
    """Increment user's AI usage count after successful generation.

    Also logs an entry to ai_usage_history for the audit trail.
    Debits wallet if user has one (§6.60).
    """
    log_ai_usage(
        user, db, generation_type, course_material_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model_name=model_name,
        is_regeneration=is_regeneration,
        parent_generation_id=parent_generation_id,
    )

    # --- Wallet debit (§6.60) ---
    from app.models.wallet import Wallet

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if wallet:
        from decimal import Decimal
        total = Decimal(str(wallet.purchased_credits or 0)) + Decimal(str(wallet.package_credits or 0))
        if total > 0:
            from app.services.wallet_service import debit_wallet
            try:
                amount = Decimal(str(wallet_debit_amount)) if wallet_debit_amount is not None else Decimal("1")
                debit_wallet(db, wallet, amount, note=f"AI generation: {generation_type}")
            except HTTPException:
                raise  # Let 402 (insufficient credits) propagate to client
            except Exception:
                logger.warning("Wallet debit failed for user_id=%s", user.id)
            # Don't also increment legacy counter if wallet was debited
            db.commit()
            return

    # --- Legacy counter increment (unchanged) ---
    limit = getattr(user, "ai_usage_limit", None)

    # Only track count if limits are active (non-zero, non-null)
    if not limit:
        db.commit()
        return

    current = getattr(user, "ai_usage_count", None) or 0
    user.ai_usage_count = current + 1
    db.commit()
    logger.info(
        "AI usage incremented | user_id=%s | count=%s/%s",
        user.id, user.ai_usage_count, user.ai_usage_limit,
    )
