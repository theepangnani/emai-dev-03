"""
Tests for the Digital Wallet system (§6.60).
"""
import pytest
from decimal import Decimal

from conftest import PASSWORD, _auth

from app.models.user import User, UserRole
from app.models.wallet import Wallet, PackageTier, WalletTransaction, CreditPackage
from app.core.security import get_password_hash


@pytest.fixture()
def wallet_users(db_session):
    """Create test users with wallets."""
    hashed = get_password_hash(PASSWORD)

    student = User(
        email="wallet_student@test.com",
        username="wallet_student",
        hashed_password=hashed,
        full_name="Wallet Student",
        role=UserRole.STUDENT,
        roles="student",
        onboarding_completed=True,
        email_verified=True,
    )
    db_session.add(student)
    db_session.flush()

    admin = User(
        email="wallet_admin@test.com",
        username="wallet_admin",
        hashed_password=hashed,
        full_name="Wallet Admin",
        role=UserRole.ADMIN,
        roles="admin",
        onboarding_completed=True,
        email_verified=True,
    )
    db_session.add(admin)
    db_session.flush()

    # Create wallets
    student_wallet = Wallet(user_id=student.id, package="free", package_credits=10, purchased_credits=5)
    admin_wallet = Wallet(user_id=admin.id, package="free")
    db_session.add_all([student_wallet, admin_wallet])

    # Seed tiers
    if db_session.query(PackageTier).count() == 0:
        db_session.add_all([
            PackageTier(name="free", monthly_credits=0, price_cents=0),
            PackageTier(name="standard", monthly_credits=100, price_cents=500),
            PackageTier(name="premium", monthly_credits=500, price_cents=1000),
        ])

    # Seed credit packages
    if db_session.query(CreditPackage).count() == 0:
        db_session.add_all([
            CreditPackage(name="Starter", credits=50, price_cents=200),
            CreditPackage(name="Standard", credits=200, price_cents=500),
        ])

    db_session.commit()
    return {"student": student, "admin": admin, "student_wallet": student_wallet}


class TestGetWallet:
    def test_get_wallet_returns_balance(self, client, wallet_users):
        headers = _auth(client, wallet_users["student"].email)
        resp = client.get("/api/wallet", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["package"] == "free"
        assert data["package_credits"] == 10.0
        assert data["purchased_credits"] == 5.0
        assert data["total_credits"] == 15.0

    def test_get_wallet_auto_creates_if_missing(self, client, db_session, wallet_users):
        """Wallet is auto-created for users who don't have one."""
        # Create a user without a wallet
        user = User(
            email="no_wallet@test.com",
            username="no_wallet",
            hashed_password=get_password_hash(PASSWORD),
            full_name="No Wallet",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(user)
        db_session.commit()

        headers = _auth(client, "no_wallet@test.com")
        resp = client.get("/api/wallet", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["package"] == "free"

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/wallet")
        assert resp.status_code in (401, 403)


class TestTransactions:
    def test_get_transactions_empty(self, client, wallet_users):
        headers = _auth(client, wallet_users["student"].email)
        resp = client.get("/api/wallet/transactions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_transactions_with_data(self, client, db_session, wallet_users):
        wallet = wallet_users["student_wallet"]
        txn = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type="debit",
            amount=-1,
            balance_after=14,
            payment_method="system",
            note="Test debit",
        )
        db_session.add(txn)
        db_session.commit()

        headers = _auth(client, wallet_users["student"].email)
        resp = client.get("/api/wallet/transactions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["transaction_type"] == "debit"


class TestPackages:
    def test_list_packages(self, client, wallet_users):
        headers = _auth(client, wallet_users["student"].email)
        resp = client.get("/api/wallet/packages", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        names = {t["name"] for t in data}
        assert names == {"free", "standard", "premium"}

    def test_enroll_in_package(self, client, wallet_users):
        headers = _auth(client, wallet_users["student"].email)
        resp = client.post(
            "/api/wallet/packages/enroll",
            json={"package_name": "standard"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["package"] == "standard"
        assert data["package_credits"] == 100.0

    def test_enroll_invalid_package_returns_404(self, client, wallet_users):
        headers = _auth(client, wallet_users["student"].email)
        resp = client.post(
            "/api/wallet/packages/enroll",
            json={"package_name": "nonexistent"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestCreditPackages:
    def test_list_credit_packages(self, client, wallet_users):
        headers = _auth(client, wallet_users["student"].email)
        resp = client.get("/api/wallet/credits", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Starter"


class TestWalletService:
    """Unit tests for wallet_service functions."""

    def test_debit_order_purchased_first(self, db_session, wallet_users):
        from app.services.wallet_service import debit_wallet

        wallet = wallet_users["student_wallet"]
        # Student has 10 package + 5 purchased = 15 total
        debit_wallet(db_session, wallet, Decimal("3"), note="test debit")
        db_session.commit()

        # purchased_credits should be debited first: 5 - 3 = 2
        assert float(wallet.purchased_credits) == 2.0
        assert float(wallet.package_credits) == 10.0

    def test_debit_crosses_pools(self, db_session, wallet_users):
        from app.services.wallet_service import debit_wallet

        wallet = wallet_users["student_wallet"]
        # Reset to known state
        wallet.purchased_credits = Decimal("2")
        wallet.package_credits = Decimal("10")
        db_session.flush()

        # Debit 5: takes 2 from purchased, 3 from package
        debit_wallet(db_session, wallet, Decimal("5"), note="cross-pool debit")
        db_session.commit()

        assert float(wallet.purchased_credits) == 0.0
        assert float(wallet.package_credits) == 7.0

    def test_debit_insufficient_raises_402(self, db_session, wallet_users):
        from app.services.wallet_service import debit_wallet
        from fastapi import HTTPException

        wallet = wallet_users["student_wallet"]
        wallet.purchased_credits = Decimal("0")
        wallet.package_credits = Decimal("1")
        db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            debit_wallet(db_session, wallet, Decimal("5"))
        assert exc_info.value.status_code == 402

    def test_idempotency_guard(self, db_session, wallet_users):
        from app.services.wallet_service import credit_wallet_purchase

        wallet = wallet_users["student_wallet"]
        ref_id = "pi_test_123"

        # First credit
        txn1 = credit_wallet_purchase(db_session, wallet, Decimal("50"), reference_id=ref_id)
        db_session.commit()
        balance_after_first = float(wallet.purchased_credits)

        # Second credit with same reference_id — should be skipped
        txn2 = credit_wallet_purchase(db_session, wallet, Decimal("50"), reference_id=ref_id)
        db_session.commit()
        balance_after_second = float(wallet.purchased_credits)

        assert txn1.id == txn2.id  # Same transaction returned
        assert balance_after_first == balance_after_second  # No double credit
