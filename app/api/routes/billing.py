"""
Billing API routes for Stripe subscription management.

Public endpoints (no auth):
  POST /api/billing/webhook   — Stripe webhook receiver

Authenticated user endpoints:
  GET  /api/billing/plans         — List active subscription plans
  GET  /api/billing/subscription  — Current user's subscription
  POST /api/billing/checkout      — Create Stripe Checkout session
  POST /api/billing/portal        — Create Stripe Billing Portal session URL
  POST /api/billing/cancel        — Cancel subscription at period end

Admin endpoints:
  GET  /api/admin/billing/stats          — Revenue/user stats
  GET  /api/admin/billing/subscriptions  — All subscriptions (paginated)

NOTE: Do NOT add authentication to /webhook — it is called directly by Stripe.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature, require_role
from app.core.config import settings
from app.db.database import get_db
from app.models.subscription import SubscriptionPlan, SubscriptionStatus, UserSubscription
from app.models.user import User, UserRole
from app.services.stripe_service import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    id: int
    name: str
    display_name: str
    tier: str
    price_cad: float
    stripe_price_id: Optional[str]
    interval: Optional[str]
    features: list[str]
    is_active: bool

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    plan: PlanResponse
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    trial_end: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CheckoutRequest(BaseModel):
    plan_name: str  # "premium_monthly" | "premium_yearly"


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class BillingStatsResponse(BaseModel):
    total_premium: int
    monthly_revenue_cad: float
    new_this_month: int
    churn_count: int


class AdminSubscriptionItem(BaseModel):
    user_id: int
    user_email: Optional[str]
    user_name: Optional[str]
    plan_name: str
    plan_display_name: str
    status: str
    created_at: Optional[datetime]
    current_period_end: Optional[datetime]

    class Config:
        from_attributes = True


class AdminSubscriptionList(BaseModel):
    items: list[AdminSubscriptionItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_features(features_json: str) -> list[str]:
    """Parse JSON feature list from a SubscriptionPlan."""
    try:
        return json.loads(features_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _plan_to_response(plan: SubscriptionPlan) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        display_name=plan.display_name,
        tier=plan.tier,
        price_cad=plan.price_cad,
        stripe_price_id=plan.stripe_price_id,
        interval=plan.interval.value if plan.interval else None,
        features=_parse_features(plan.features),
        is_active=plan.is_active,
    )


def _get_or_create_stripe_customer(user: User, db: Session) -> str:
    """Return the Stripe customer ID for a user, creating one if needed."""
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    if sub and sub.stripe_customer_id:
        return sub.stripe_customer_id

    customer = stripe_service.create_customer(
        user_id=user.id,
        email=user.email or "",
        name=user.full_name or "",
    )
    return customer.id


def _get_free_plan(db: Session) -> SubscriptionPlan:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "free").first()
    if not plan:
        raise HTTPException(status_code=500, detail="Free plan not seeded in database.")
    return plan


# ---------------------------------------------------------------------------
# User-facing endpoints
# ---------------------------------------------------------------------------


@router.get("/api/billing/plans", response_model=list[PlanResponse])
def list_plans(_flag=Depends(require_feature("stripe_billing")), db: Session = Depends(get_db)):
    """Return all active subscription plans with feature lists."""
    plans = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active == True)  # noqa: E712
        .order_by(SubscriptionPlan.price_cad)
        .all()
    )
    return [_plan_to_response(p) for p in plans]


@router.get("/api/billing/subscription", response_model=Optional[SubscriptionResponse])
def get_subscription(
    _flag=Depends(require_feature("stripe_billing")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's subscription, or null if on the free plan with no record."""
    sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.user_id == current_user.id)
        .first()
    )
    if not sub:
        return None
    # Build response manually so the plan features are parsed
    plan = sub.plan
    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        plan=_plan_to_response(plan),
        stripe_customer_id=sub.stripe_customer_id,
        stripe_subscription_id=sub.stripe_subscription_id,
        status=sub.status.value,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
        trial_end=sub.trial_end,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


@router.post("/api/billing/checkout", response_model=CheckoutResponse)
def create_checkout_session(
    body: CheckoutRequest,
    _flag=Depends(require_feature("stripe_billing")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session for the requested plan.

    Returns a checkout_url to redirect the user to Stripe Checkout.
    After payment Stripe redirects to /settings/billing?success=true.
    """
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.name == body.plan_name, SubscriptionPlan.is_active == True)  # noqa: E712
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{body.plan_name}' not found.",
        )
    if plan.tier == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot checkout for the free plan.",
        )
    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This plan does not have a Stripe Price ID configured yet.",
        )

    customer_id = _get_or_create_stripe_customer(current_user, db)

    # Persist the customer_id so we can look the user up from webhook events
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == current_user.id).first()
    if sub:
        sub.stripe_customer_id = customer_id
        db.commit()
    else:
        free_plan = _get_free_plan(db)
        sub = UserSubscription(
            user_id=current_user.id,
            plan_id=free_plan.id,
            stripe_customer_id=customer_id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(sub)
        db.commit()

    success_url = f"{settings.frontend_url}/settings/billing?success=true"
    cancel_url = f"{settings.frontend_url}/settings/billing?canceled=true"

    try:
        session = stripe_service.create_checkout_session(
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe checkout session error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to create Stripe checkout session.")

    return CheckoutResponse(checkout_url=session.url)


@router.post("/api/billing/portal", response_model=PortalResponse)
def create_billing_portal(
    _flag=Depends(require_feature("stripe_billing")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Billing Portal session for the current user.

    Returns a portal_url to redirect the user to the self-service portal
    where they can update payment info, view invoices, or cancel.
    """
    sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.user_id == current_user.id)
        .first()
    )
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Please subscribe first.",
        )

    return_url = f"{settings.frontend_url}/settings/billing"
    try:
        portal_url = stripe_service.create_billing_portal_session(
            customer_id=sub.stripe_customer_id,
            return_url=return_url,
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe billing portal error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to create billing portal session.")

    return PortalResponse(portal_url=portal_url)


@router.post("/api/billing/cancel")
def cancel_subscription(
    _flag=Depends(require_feature("stripe_billing")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel the current user's subscription at the end of the current period."""
    sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.user_id == current_user.id)
        .first()
    )
    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found.",
        )

    try:
        stripe_service.cancel_subscription(sub.stripe_subscription_id, at_period_end=True)
    except stripe.error.StripeError as exc:
        logger.error("Stripe cancel error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to cancel subscription.")

    sub.cancel_at_period_end = True
    db.commit()
    return {"status": "scheduled_for_cancellation"}


# ---------------------------------------------------------------------------
# Stripe Webhook — NO AUTH (called directly by Stripe)
# ---------------------------------------------------------------------------


@router.post("/api/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events for subscription lifecycle management.

    Events handled:
      - checkout.session.completed      → create/update UserSubscription, set tier=premium
      - customer.subscription.updated   → sync status and period dates
      - customer.subscription.deleted   → set tier=free, status=canceled
      - invoice.payment_failed          → set status=past_due
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except ValueError:
        logger.warning("Stripe webhook: invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook: invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"], db)

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(event["data"]["object"], db)

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event["data"]["object"], db)

    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event["data"]["object"], db)

    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Webhook event handlers
# ---------------------------------------------------------------------------


def _find_subscription_by_customer(customer_id: str, db: Session) -> Optional[UserSubscription]:
    return (
        db.query(UserSubscription)
        .filter(UserSubscription.stripe_customer_id == customer_id)
        .first()
    )


def _set_user_tier(user_id: int, tier: str, db: Session) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.subscription_tier = tier


def _handle_checkout_completed(session: dict, db: Session) -> None:
    """checkout.session.completed: link Stripe subscription to user, upgrade tier."""
    customer_id: str = session.get("customer", "")
    stripe_sub_id: str = session.get("subscription", "")
    if not customer_id or not stripe_sub_id:
        logger.error("checkout.session.completed missing customer/subscription IDs")
        return

    # Determine the plan from the Stripe subscription
    try:
        stripe_sub = stripe_service.get_subscription(stripe_sub_id)
        price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    except Exception as exc:
        logger.error("Failed to retrieve Stripe subscription %s: %s", stripe_sub_id, exc)
        return

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.stripe_price_id == price_id).first()
    if not plan:
        logger.error("No SubscriptionPlan found for Stripe price_id=%s", price_id)
        return

    period_start = _ts_to_dt(stripe_sub.get("current_period_start"))
    period_end = _ts_to_dt(stripe_sub.get("current_period_end"))
    trial_end = _ts_to_dt(stripe_sub.get("trial_end"))
    stripe_status = stripe_sub.get("status", "active")

    user_sub = _find_subscription_by_customer(customer_id, db)
    if user_sub:
        user_sub.plan_id = plan.id
        user_sub.stripe_subscription_id = stripe_sub_id
        user_sub.status = _map_status(stripe_status)
        user_sub.current_period_start = period_start
        user_sub.current_period_end = period_end
        user_sub.trial_end = trial_end
        user_sub.cancel_at_period_end = False
        _set_user_tier(user_sub.user_id, plan.tier, db)
    else:
        logger.warning(
            "checkout.session.completed: no UserSubscription found for customer %s", customer_id
        )
        # Try to find by metadata (fallback)
        metadata = session.get("metadata") or {}
        user_id_str = metadata.get("user_id")
        if user_id_str:
            user_sub = UserSubscription(
                user_id=int(user_id_str),
                plan_id=plan.id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=stripe_sub_id,
                status=_map_status(stripe_status),
                current_period_start=period_start,
                current_period_end=period_end,
                trial_end=trial_end,
            )
            db.add(user_sub)
            _set_user_tier(int(user_id_str), plan.tier, db)

    db.commit()
    logger.info("Upgraded user subscription to plan '%s'", plan.name)


def _handle_subscription_updated(stripe_sub: dict, db: Session) -> None:
    """customer.subscription.updated: sync status and billing period."""
    stripe_sub_id: str = stripe_sub.get("id", "")
    customer_id: str = stripe_sub.get("customer", "")

    user_sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )
    if not user_sub:
        user_sub = _find_subscription_by_customer(customer_id, db)

    if not user_sub:
        logger.warning(
            "subscription.updated: no UserSubscription found for sub %s / cus %s",
            stripe_sub_id,
            customer_id,
        )
        return

    user_sub.status = _map_status(stripe_sub.get("status", "active"))
    user_sub.current_period_start = _ts_to_dt(stripe_sub.get("current_period_start"))
    user_sub.current_period_end = _ts_to_dt(stripe_sub.get("current_period_end"))
    user_sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
    user_sub.trial_end = _ts_to_dt(stripe_sub.get("trial_end"))

    db.commit()
    logger.info("Updated subscription %s → status=%s", stripe_sub_id, user_sub.status)


def _handle_subscription_deleted(stripe_sub: dict, db: Session) -> None:
    """customer.subscription.deleted: downgrade user to free tier."""
    stripe_sub_id: str = stripe_sub.get("id", "")
    customer_id: str = stripe_sub.get("customer", "")

    user_sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )
    if not user_sub:
        user_sub = _find_subscription_by_customer(customer_id, db)

    if not user_sub:
        logger.warning(
            "subscription.deleted: no UserSubscription found for sub %s / cus %s",
            stripe_sub_id,
            customer_id,
        )
        return

    free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "free").first()
    if free_plan:
        user_sub.plan_id = free_plan.id

    user_sub.status = SubscriptionStatus.CANCELED
    user_sub.stripe_subscription_id = None
    _set_user_tier(user_sub.user_id, "free", db)

    db.commit()
    logger.info("Subscription %s deleted; user downgraded to free", stripe_sub_id)


def _handle_payment_failed(invoice: dict, db: Session) -> None:
    """invoice.payment_failed: mark subscription as past_due."""
    customer_id: str = invoice.get("customer", "")
    stripe_sub_id: str = invoice.get("subscription", "")

    user_sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )
    if not user_sub:
        user_sub = _find_subscription_by_customer(customer_id, db)

    if not user_sub:
        logger.warning(
            "invoice.payment_failed: no subscription found for cus %s", customer_id
        )
        return

    user_sub.status = SubscriptionStatus.PAST_DUE
    db.commit()
    logger.info("Marked subscription as past_due for customer %s", customer_id)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

admin_router = APIRouter(tags=["admin-billing"])


@admin_router.get("/api/admin/billing/stats", response_model=BillingStatsResponse)
def admin_billing_stats(
    _flag=Depends(require_feature("stripe_billing")),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Return aggregate billing metrics for the admin dashboard."""
    from sqlalchemy import func as sql_func

    active_subs = (
        db.query(UserSubscription)
        .join(SubscriptionPlan)
        .filter(
            SubscriptionPlan.tier == "premium",
            UserSubscription.status.in_(
                [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
            ),
        )
        .all()
    )

    total_premium = len(active_subs)

    # Monthly Revenue estimate (convert yearly to monthly equivalent)
    monthly_revenue = 0.0
    for sub in active_subs:
        plan = sub.plan
        if plan.interval and plan.interval.value == "yearly":
            monthly_revenue += plan.price_cad / 12
        else:
            monthly_revenue += plan.price_cad

    # New subscriptions this calendar month
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = (
        db.query(UserSubscription)
        .join(SubscriptionPlan)
        .filter(
            SubscriptionPlan.tier == "premium",
            UserSubscription.created_at >= month_start,
        )
        .count()
    )

    # Churn: subscriptions canceled this month
    churn_count = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.status == SubscriptionStatus.CANCELED,
            UserSubscription.updated_at >= month_start,
        )
        .count()
    )

    return BillingStatsResponse(
        total_premium=total_premium,
        monthly_revenue_cad=round(monthly_revenue, 2),
        new_this_month=new_this_month,
        churn_count=churn_count,
    )


@admin_router.get("/api/admin/billing/subscriptions", response_model=AdminSubscriptionList)
def admin_list_subscriptions(
    _flag=Depends(require_feature("stripe_billing")),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Return a paginated list of all user subscriptions for admin review."""
    query = (
        db.query(UserSubscription)
        .join(SubscriptionPlan)
        .join(User, User.id == UserSubscription.user_id)
        .order_by(UserSubscription.created_at.desc())
    )
    total = query.count()
    subs = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for sub in subs:
        items.append(
            AdminSubscriptionItem(
                user_id=sub.user_id,
                user_email=sub.user.email if sub.user else None,
                user_name=sub.user.full_name if sub.user else None,
                plan_name=sub.plan.name,
                plan_display_name=sub.plan.display_name,
                status=sub.status.value,
                created_at=sub.created_at,
                current_period_end=sub.current_period_end,
            )
        )

    return AdminSubscriptionList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _ts_to_dt(ts: Optional[int]) -> Optional[datetime]:
    """Convert a Unix timestamp (int) to a timezone-aware datetime, or None."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _map_status(stripe_status: str) -> SubscriptionStatus:
    """Map a Stripe subscription status string to our SubscriptionStatus enum."""
    mapping = {
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "trialing": SubscriptionStatus.TRIALING,
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "incomplete_expired": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.PAST_DUE,
    }
    return mapping.get(stripe_status, SubscriptionStatus.INCOMPLETE)


# ---------------------------------------------------------------------------
# Seed helper — called from main.py startup
# ---------------------------------------------------------------------------

FREE_PLAN_FEATURES = [
    "Up to 3 children",
    "Basic AI study tools",
    "500 MB storage",
    "100 study guides",
    "Google Classroom sync",
]

PREMIUM_MONTHLY_FEATURES = [
    "Unlimited children",
    "AI Insights & analytics",
    "5 GB storage",
    "500 study guides",
    "Priority support",
    "50 MB file uploads",
    "25 files per session",
]

PREMIUM_YEARLY_FEATURES = PREMIUM_MONTHLY_FEATURES + ["Save 17% vs monthly"]


def seed_subscription_plans(db: Session) -> None:
    """Idempotently seed the three base subscription plans.

    Called during application startup (main.py lifespan).
    Plans are only inserted if they don't already exist (by name).
    """
    plans_data = [
        {
            "name": "free",
            "display_name": "Free",
            "tier": "free",
            "price_cad": 0.0,
            "stripe_price_id": None,
            "interval": None,
            "features": json.dumps(FREE_PLAN_FEATURES),
            "is_active": True,
        },
        {
            "name": "premium_monthly",
            "display_name": "Premium Monthly",
            "tier": "premium",
            "price_cad": 9.99,
            "stripe_price_id": "price_PLACEHOLDER_MONTHLY",
            "interval": "monthly",
            "features": json.dumps(PREMIUM_MONTHLY_FEATURES),
            "is_active": True,
        },
        {
            "name": "premium_yearly",
            "display_name": "Premium Yearly",
            "tier": "premium",
            "price_cad": 99.99,
            "stripe_price_id": "price_PLACEHOLDER_YEARLY",
            "interval": "yearly",
            "features": json.dumps(PREMIUM_YEARLY_FEATURES),
            "is_active": True,
        },
    ]

    for plan_data in plans_data:
        existing = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.name == plan_data["name"])
            .first()
        )
        if not existing:
            from app.models.subscription import PlanInterval

            interval_val = plan_data.pop("interval", None)
            plan = SubscriptionPlan(**plan_data)
            if interval_val:
                plan.interval = PlanInterval(interval_val)
            db.add(plan)
            logger.info("Seeded subscription plan: %s", plan_data.get("name", ""))

    db.commit()
