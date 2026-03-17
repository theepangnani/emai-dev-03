"""
Background job: monthly credit refresh for wallet package tiers (§6.60).

Runs on the 1st of each month at 00:00 UTC via APScheduler.
Resets package_credits for all wallets to their tier's monthly allocation.
"""
import logging
from decimal import Decimal

from app.db.database import SessionLocal

logger = logging.getLogger(__name__)


async def refresh_monthly_credits():
    """Reset package_credits for all wallets to their tier's monthly_credits."""
    db = SessionLocal()
    count = 0
    try:
        from app.models.wallet import Wallet, PackageTier, WalletTransaction

        # Build tier lookup: {name: monthly_credits}
        tiers = {t.name: t.monthly_credits for t in db.query(PackageTier).filter(PackageTier.is_active == True).all()}

        if not tiers:
            logger.warning("No active package tiers found — skipping monthly refresh")
            return

        wallets = db.query(Wallet).all()
        for wallet in wallets:
            monthly = tiers.get(wallet.package)
            if monthly is None:
                continue

            wallet.package_credits = monthly
            db.add(WalletTransaction(
                wallet_id=wallet.id,
                transaction_type="package_credit",
                amount=Decimal(str(monthly)),
                balance_after=Decimal(str(monthly)) + Decimal(str(wallet.purchased_credits or 0)),
                payment_method="system",
                note=f"Monthly reset — {wallet.package} tier",
            ))
            count += 1

        db.commit()
        logger.info("Monthly credit refresh completed for %d wallets", count)
    except Exception:
        db.rollback()
        logger.exception("Monthly credit refresh failed")
    finally:
        db.close()
