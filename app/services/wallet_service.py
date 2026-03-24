"""
Wallet service — business logic for the Digital Wallet system (§6.60).

Handles credit debit/credit operations, package enrollment,
and idempotency checks for payment processing.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_or_create_wallet(db: Session, user_id: int):
    """Return user's wallet, creating one if missing (defensive)."""
    from app.models.wallet import Wallet

    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        wallet = Wallet(user_id=user_id, package="free")
        db.add(wallet)
        db.flush()
        logger.info("Auto-created wallet for user_id=%s", user_id)
    return wallet


def record_transaction(
    db: Session,
    wallet_id: int,
    txn_type: str,
    amount: Decimal,
    reference_id: str | None = None,
    payment_method: str | None = None,
    note: str | None = None,
):
    """Create an immutable ledger entry. Computes balance_after from current wallet state."""
    from app.models.wallet import Wallet, WalletTransaction

    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    balance_after = Decimal(str(wallet.package_credits or 0)) + Decimal(str(wallet.purchased_credits or 0))

    txn = WalletTransaction(
        wallet_id=wallet_id,
        transaction_type=txn_type,
        amount=amount,
        balance_after=balance_after,
        reference_id=reference_id,
        payment_method=payment_method,
        note=note,
    )
    db.add(txn)
    db.flush()
    logger.info(
        "Wallet transaction | wallet_id=%s | type=%s | amount=%s | balance_after=%s | ref=%s",
        wallet_id, txn_type, amount, balance_after, reference_id,
    )
    return txn


def debit_wallet(db: Session, wallet, amount: Decimal, note: str | None = None):
    """Debit credits: purchased_credits first, then package_credits.

    Returns the WalletTransaction record.
    Raises 402 if insufficient balance.

    Uses a savepoint (nested transaction) so that both the balance update
    and the ledger entry are committed or rolled back atomically.
    """
    total = Decimal(str(wallet.purchased_credits or 0)) + Decimal(str(wallet.package_credits or 0))
    if total < amount:
        logger.warning(
            "Insufficient balance | wallet_id=%s | balance=%s | required=%s",
            wallet.id, total, amount,
        )
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Balance: {total}, required: {amount}",
        )

    # Wrap debit + transaction record in a savepoint for atomicity
    nested = db.begin_nested()
    try:
        remaining = amount
        purchased = Decimal(str(wallet.purchased_credits or 0))
        package = Decimal(str(wallet.package_credits or 0))

        # Debit from purchased_credits first
        if purchased >= remaining:
            wallet.purchased_credits = purchased - remaining
        else:
            remaining -= purchased
            wallet.purchased_credits = Decimal("0")
            wallet.package_credits = package - remaining

        db.flush()

        txn = record_transaction(
            db,
            wallet_id=wallet.id,
            txn_type="debit",
            amount=-amount,
            payment_method="system",
            note=note,
        )
        nested.commit()
        return txn
    except Exception:
        nested.rollback()
        logger.error(
            "Debit failed, rolled back | wallet_id=%s | amount=%s",
            wallet.id, amount, exc_info=True,
        )
        raise


def credit_wallet_purchase(
    db: Session,
    wallet,
    amount: Decimal,
    reference_id: str,
    payment_method: str = "stripe",
):
    """Add purchased credits with idempotency guard on reference_id.

    If a transaction with the same reference_id already exists, returns it
    without double-crediting.
    """
    from app.models.wallet import WalletTransaction

    # Idempotency guard
    existing = db.query(WalletTransaction).filter(
        WalletTransaction.reference_id == reference_id,
    ).first()
    if existing:
        logger.warning(
            "Duplicate credit attempt | reference_id=%s | skipping",
            reference_id,
        )
        return existing

    wallet.purchased_credits = Decimal(str(wallet.purchased_credits or 0)) + amount
    db.flush()

    return record_transaction(
        db,
        wallet_id=wallet.id,
        txn_type="purchase_credit",
        amount=amount,
        reference_id=reference_id,
        payment_method=payment_method,
        note=f"Credit purchase: {amount} credits via {payment_method}",
    )


def enroll_package(db: Session, wallet, package_name: str):
    """Change user's package tier. Updates package_credits to new tier's allocation.

    Upgrade: immediate credit grant.
    Downgrade: takes effect immediately (simplified for Phase 1).
    """
    from app.models.wallet import PackageTier

    tier = db.query(PackageTier).filter(
        PackageTier.name == package_name,
        PackageTier.is_active == True,
    ).first()
    if not tier:
        raise HTTPException(status_code=404, detail=f"Package tier '{package_name}' not found")

    old_package = wallet.package
    wallet.package = package_name
    wallet.package_credits = tier.monthly_credits
    db.flush()

    record_transaction(
        db,
        wallet_id=wallet.id,
        txn_type="package_credit",
        amount=Decimal(str(tier.monthly_credits)),
        payment_method="system",
        note=f"Package change: {old_package} -> {package_name}",
    )

    logger.info(
        "Package enrollment | wallet_id=%s | %s -> %s | credits=%s",
        wallet.id, old_package, package_name, tier.monthly_credits,
    )
    return wallet
