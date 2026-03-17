"""
Digital Wallet models — Wallet, PackageTier, WalletTransaction, CreditPackage.

Part of the Digital Wallet & Subscription System (§6.60, #1384).
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Wallet(Base):
    """Per-user digital wallet with dual credit pools."""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    package = Column(String(20), default="free", nullable=False)
    package_credits = Column(Numeric(10, 2), default=0, nullable=False)
    purchased_credits = Column(Numeric(10, 2), default=0, nullable=False)
    auto_refill_enabled = Column(Boolean, default=False, server_default="FALSE")
    auto_refill_threshold_cents = Column(Integer, default=0)
    auto_refill_amount_cents = Column(Integer, default=500)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id], lazy="joined")

    @property
    def total_balance(self):
        return (self.package_credits or 0) + (self.purchased_credits or 0)

    __table_args__ = (
        Index("ix_wallets_user_id", "user_id"),
    )


class PackageTier(Base):
    """Admin-managed subscription tier configuration."""
    __tablename__ = "package_tiers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20), unique=True, nullable=False)
    monthly_credits = Column(Numeric(10, 2), nullable=False)
    price_cents = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, server_default="TRUE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WalletTransaction(Base):
    """Immutable transaction ledger — records are never deleted."""
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(
        Integer,
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_type = Column(String(20), nullable=False)  # package_credit, purchase_credit, debit, refund
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=False)
    reference_id = Column(String(255), nullable=True, index=True)  # idempotency key (Stripe PaymentIntent ID)
    payment_method = Column(String(20), nullable=True)  # stripe, interac, system
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("Wallet", foreign_keys=[wallet_id])

    __table_args__ = (
        Index("ix_wallet_transactions_reference_id", "reference_id"),
        Index("ix_wallet_transactions_wallet_id", "wallet_id"),
    )


class CreditPackage(Base):
    """Purchasable credit bundles (à la carte)."""
    __tablename__ = "credit_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    credits = Column(Numeric(10, 2), nullable=False)
    price_cents = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, server_default="TRUE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
