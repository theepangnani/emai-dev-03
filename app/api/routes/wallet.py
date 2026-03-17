"""
Wallet API routes — Digital Wallet & Subscription System (§6.60).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User
from app.models.wallet import CreditPackage, PackageTier, Wallet, WalletTransaction
from app.schemas.wallet import (
    AutoRefillRequest,
    CheckoutResponse,
    CreditPackageResponse,
    CreditPurchaseRequest,
    PackageEnrollRequest,
    PackageTierResponse,
    WalletResponse,
    WalletTransactionList,
    WalletTransactionResponse,
)
from app.services.wallet_service import get_or_create_wallet

logger = get_logger(__name__)

router = APIRouter(prefix="/wallet", tags=["Wallet"])
payments_router = APIRouter(prefix="/payments", tags=["Payments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wallet_response(wallet: Wallet) -> WalletResponse:
    """Build a WalletResponse from a Wallet model instance."""
    return WalletResponse(
        id=wallet.id,
        package=wallet.package,
        package_credits=float(wallet.package_credits or 0),
        purchased_credits=float(wallet.purchased_credits or 0),
        total_credits=float(
            (wallet.package_credits or 0) + (wallet.purchased_credits or 0)
        ),
        auto_refill_enabled=wallet.auto_refill_enabled or False,
        auto_refill_threshold_cents=wallet.auto_refill_threshold_cents or 0,
        auto_refill_amount_cents=wallet.auto_refill_amount_cents or 500,
    )


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_wallet(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's wallet balance and package info."""
    wallet = get_or_create_wallet(db, current_user.id)
    db.commit()
    return _wallet_response(wallet)


@router.get("/transactions")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_transactions(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paginated transaction ledger for current user."""
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        return WalletTransactionList(items=[], total=0)

    base_query = db.query(WalletTransaction).filter(
        WalletTransaction.wallet_id == wallet.id,
    )
    total = base_query.count()

    transactions = (
        base_query
        .order_by(WalletTransaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return WalletTransactionList(
        items=[
            WalletTransactionResponse(
                id=t.id,
                transaction_type=t.transaction_type,
                amount=float(t.amount),
                balance_after=float(t.balance_after),
                reference_id=t.reference_id,
                payment_method=t.payment_method,
                note=t.note,
                created_at=t.created_at,
            )
            for t in transactions
        ],
        total=total,
    )


@router.get("/packages")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_packages(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active package tiers."""
    tiers = db.query(PackageTier).filter(PackageTier.is_active == True).all()  # noqa: E712
    return [
        PackageTierResponse(
            id=t.id,
            name=t.name,
            monthly_credits=float(t.monthly_credits),
            price_cents=t.price_cents,
            is_active=t.is_active,
        )
        for t in tiers
    ]


@router.get("/credits")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_credit_packages(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List available credit packages for purchase."""
    packages = db.query(CreditPackage).filter(CreditPackage.is_active == True).all()  # noqa: E712
    return [
        CreditPackageResponse(
            id=p.id,
            name=p.name,
            credits=float(p.credits),
            price_cents=p.price_cents,
        )
        for p in packages
    ]


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

@router.post("/packages/enroll")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def enroll_in_package(
    request: Request,
    body: PackageEnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll in or change package tier."""
    from app.services.wallet_service import enroll_package

    wallet = get_or_create_wallet(db, current_user.id)
    wallet = enroll_package(db, wallet, body.package_name)
    db.commit()
    return _wallet_response(wallet)


@router.patch("/auto-refill")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def update_auto_refill(
    request: Request,
    body: AutoRefillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Configure wallet auto-refill settings."""
    wallet = get_or_create_wallet(db, current_user.id)

    if body.enabled is not None:
        wallet.auto_refill_enabled = body.enabled
    if body.threshold_cents is not None:
        wallet.auto_refill_threshold_cents = body.threshold_cents
    if body.amount_cents is not None:
        wallet.auto_refill_amount_cents = body.amount_cents

    db.commit()
    return _wallet_response(wallet)


# ---------------------------------------------------------------------------
# Stripe checkout
# ---------------------------------------------------------------------------

@router.post("/credits/checkout")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def create_checkout(
    request: Request,
    body: CreditPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe PaymentIntent for credit purchase. Returns client_secret."""
    package = db.query(CreditPackage).filter(
        CreditPackage.id == body.package_id,
        CreditPackage.is_active == True,  # noqa: E712
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Credit package not found")

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503, detail="Payment processing is not configured"
        )

    import stripe

    stripe.api_key = settings.stripe_secret_key

    intent = stripe.PaymentIntent.create(
        amount=package.price_cents,
        currency="cad",
        metadata={
            "user_id": str(current_user.id),
            "package_id": str(package.id),
            "credits": str(float(package.credits)),
        },
    )

    return CheckoutResponse(
        client_secret=intent.client_secret,
        publishable_key=settings.stripe_publishable_key,
    )


# ---------------------------------------------------------------------------
# Stripe webhook (no auth — signature verified via Stripe)
# ---------------------------------------------------------------------------

@payments_router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events. Idempotent via reference_id."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    import stripe

    stripe.api_key = settings.stripe_secret_key

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        metadata = intent.get("metadata", {})
        user_id = metadata.get("user_id")
        credits_str = metadata.get("credits")

        if not user_id or not credits_str:
            logger.warning("Webhook missing metadata | intent=%s", intent["id"])
            return {"status": "ok"}

        from app.services.wallet_service import credit_wallet_purchase

        wallet = get_or_create_wallet(db, int(user_id))
        credit_wallet_purchase(
            db,
            wallet,
            amount=Decimal(credits_str),
            reference_id=intent["id"],
            payment_method="stripe",
        )
        db.commit()
        logger.info(
            "Stripe payment processed | user_id=%s | credits=%s | intent=%s",
            user_id,
            credits_str,
            intent["id"],
        )

    return {"status": "ok"}
