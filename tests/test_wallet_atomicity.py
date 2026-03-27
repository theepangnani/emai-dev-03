"""
Tests for wallet debit atomicity (#2214).

Verifies that debit_wallet() uses a savepoint so that both the balance
update and the transaction record are committed or rolled back together.

Uses standalone fake models and an in-memory SQLite session to avoid
importing the full model graph (which requires optional dependencies).
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Integer, Numeric, String, Text, DateTime, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

# Separate declarative base for test-only models
_TestBase = declarative_base()


class _FakeWallet(_TestBase):
    """Minimal wallet table for testing (no FK to users)."""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    package = Column(String(20), default="free", nullable=False)
    package_credits = Column(Numeric(10, 2), default=0, nullable=False)
    purchased_credits = Column(Numeric(10, 2), default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class _FakeWalletTransaction(_TestBase):
    """Minimal transaction table for testing."""
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, nullable=False)
    transaction_type = Column(String(20), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=False)
    reference_id = Column(String(255), nullable=True)
    payment_method = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Fake module so `from app.models.wallet import Wallet` resolves to fakes ──
class _FakeWalletModule:
    Wallet = _FakeWallet
    WalletTransaction = _FakeWalletTransaction
    PackageTier = None
    CreditPackage = None


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_wallet_module():
    """Replace app.models.wallet with our fake module so the service layer
    uses _FakeWallet / _FakeWalletTransaction (avoiding User mapper issues)."""
    original = sys.modules.get("app.models.wallet")
    sys.modules["app.models.wallet"] = _FakeWalletModule()
    yield
    if original is not None:
        sys.modules["app.models.wallet"] = original
    else:
        sys.modules.pop("app.models.wallet", None)


@pytest.fixture()
def db():
    """In-memory SQLite session with test tables."""
    engine = create_engine("sqlite:///:memory:")
    _TestBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def wallet_with_credits(db):
    """Create a wallet with known balances."""
    wallet = _FakeWallet(
        user_id=1,
        package="free",
        package_credits=Decimal("5.00"),
        purchased_credits=Decimal("10.00"),
    )
    db.add(wallet)
    db.commit()
    return db.query(_FakeWallet).filter(_FakeWallet.user_id == 1).first()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Successful debit — happy path
# ─────────────────────────────────────────────────────────────────────────────

def test_debit_wallet_success(db, wallet_with_credits):
    """Successful debit updates balance and creates a transaction record."""
    from app.services.wallet_service import debit_wallet

    wallet = wallet_with_credits

    txn = debit_wallet(db, wallet, Decimal("3.00"), note="test debit")
    db.commit()

    assert txn is not None
    assert txn.transaction_type == "debit"
    assert txn.amount == Decimal("-3.00")
    # purchased_credits debited first: 10 - 3 = 7
    assert wallet.purchased_credits == Decimal("7.00")
    assert wallet.package_credits == Decimal("5.00")

    # Verify transaction record persisted
    saved_txn = db.query(_FakeWalletTransaction).filter(
        _FakeWalletTransaction.id == txn.id
    ).first()
    assert saved_txn is not None
    assert saved_txn.note == "test debit"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Debit spanning both credit pools
# ─────────────────────────────────────────────────────────────────────────────

def test_debit_wallet_spans_both_pools(db, wallet_with_credits):
    """Debit that exceeds purchased_credits spills into package_credits."""
    from app.services.wallet_service import debit_wallet

    wallet = wallet_with_credits

    txn = debit_wallet(db, wallet, Decimal("12.00"), note="spanning debit")
    db.commit()

    assert wallet.purchased_credits == Decimal("0.00")
    # 12 - 10 purchased = 2 from package; 5 - 2 = 3
    assert wallet.package_credits == Decimal("3.00")
    assert txn.amount == Decimal("-12.00")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Insufficient balance — 402
# ─────────────────────────────────────────────────────────────────────────────

def test_debit_wallet_insufficient_balance(db, wallet_with_credits):
    """Debit exceeding total balance raises 402 without any state change."""
    from app.services.wallet_service import debit_wallet

    wallet = wallet_with_credits
    original_purchased = Decimal(str(wallet.purchased_credits))
    original_package = Decimal(str(wallet.package_credits))

    with pytest.raises(HTTPException) as exc_info:
        debit_wallet(db, wallet, Decimal("999.00"))

    assert exc_info.value.status_code == 402
    assert Decimal(str(wallet.purchased_credits)) == original_purchased
    assert Decimal(str(wallet.package_credits)) == original_package


# ─────────────────────────────────────────────────────────────────────────────
# 4. Atomicity — record_transaction failure rolls back the balance debit
# ─────────────────────────────────────────────────────────────────────────────

def test_debit_wallet_rollback_on_transaction_record_failure(db, wallet_with_credits):
    """When record_transaction fails, the wallet balance is rolled back."""
    from app.services.wallet_service import debit_wallet

    wallet = wallet_with_credits
    original_purchased = Decimal(str(wallet.purchased_credits))
    original_package = Decimal(str(wallet.package_credits))

    with patch(
        "app.services.wallet_service.record_transaction",
        side_effect=RuntimeError("simulated flush failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated flush failure"):
            debit_wallet(db, wallet, Decimal("3.00"), note="should rollback")

    # After savepoint rollback, refresh wallet from DB
    db.refresh(wallet)

    # Balance must be restored to original values
    assert Decimal(str(wallet.purchased_credits)) == original_purchased
    assert Decimal(str(wallet.package_credits)) == original_package

    # No transaction record should exist for this attempt
    orphan_txns = db.query(_FakeWalletTransaction).filter(
        _FakeWalletTransaction.wallet_id == wallet.id,
        _FakeWalletTransaction.note == "should rollback",
    ).count()
    assert orphan_txns == 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Atomicity — DB error during debit flush rolls back cleanly
# ─────────────────────────────────────────────────────────────────────────────

def test_debit_wallet_rollback_on_debit_flush_failure(db, wallet_with_credits):
    """When the balance flush itself fails, everything is rolled back."""
    from app.services.wallet_service import debit_wallet

    wallet = wallet_with_credits
    original_purchased = Decimal(str(wallet.purchased_credits))
    original_package = Decimal(str(wallet.package_credits))

    original_flush = db.flush
    call_count = 0

    def failing_flush(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated balance flush failure")
        return original_flush(*args, **kwargs)

    with patch.object(db, "flush", side_effect=failing_flush):
        with pytest.raises(RuntimeError, match="simulated balance flush failure"):
            debit_wallet(db, wallet, Decimal("3.00"), note="flush fail")

    db.refresh(wallet)
    assert Decimal(str(wallet.purchased_credits)) == original_purchased
    assert Decimal(str(wallet.package_credits)) == original_package


# ─────────────────────────────────────────────────────────────────────────────
# 6. begin_nested() is called (structural test)
# ─────────────────────────────────────────────────────────────────────────────

def test_debit_wallet_uses_savepoint(db, wallet_with_credits):
    """Verify that debit_wallet() calls db.begin_nested() for atomicity."""
    from app.services.wallet_service import debit_wallet

    wallet = wallet_with_credits

    with patch.object(db, "begin_nested", wraps=db.begin_nested) as mock_nested:
        debit_wallet(db, wallet, Decimal("1.00"), note="savepoint check")
        db.commit()

    mock_nested.assert_called_once()
