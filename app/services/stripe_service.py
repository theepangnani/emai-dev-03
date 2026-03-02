"""
Stripe API wrapper for ClassBridge subscription billing.

Provides a thin service layer around the stripe SDK so that routes/jobs
interact with a well-typed interface instead of calling the SDK directly.

Settings required in .env:
  STRIPE_SECRET_KEY      — sk_live_xxx / sk_test_xxx
  STRIPE_WEBHOOK_SECRET  — whsec_xxx
  STRIPE_PUBLISHABLE_KEY — pk_live_xxx / pk_test_xxx (used by frontend)
"""
from __future__ import annotations

import stripe

from app.core.config import settings

stripe.api_key = settings.stripe_secret_key


class StripeService:
    """Thin wrapper around the Stripe SDK for ClassBridge billing operations."""

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------

    def create_customer(self, user_id: int, email: str, name: str) -> stripe.Customer:
        """Create a Stripe customer record with ClassBridge metadata."""
        return stripe.Customer.create(
            email=email,
            name=name,
            metadata={"user_id": str(user_id), "platform": "classbridge"},
        )

    def get_customer(self, customer_id: str) -> stripe.Customer:
        """Retrieve a Stripe customer by ID."""
        return stripe.Customer.retrieve(customer_id)

    # ------------------------------------------------------------------
    # Checkout & Portal
    # ------------------------------------------------------------------

    def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_days: int = 7,
    ) -> stripe.checkout.Session:
        """Create a Stripe Checkout session for a subscription purchase."""
        return stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data={"trial_period_days": trial_days},
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def create_billing_portal_session(self, customer_id: str, return_url: str) -> str:
        """Create a Stripe Billing Portal session and return its URL.

        The portal lets users update payment methods, view invoices, and
        manage or cancel their subscription without custom UI.
        """
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def cancel_subscription(
        self, subscription_id: str, at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a subscription at the end of the current period (default) or immediately."""
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=at_period_end,
        )

    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Retrieve a Stripe subscription by ID."""
        return stripe.Subscription.retrieve(subscription_id)

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        """Verify the Stripe webhook signature and parse the event payload."""
        return stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )


# Module-level singleton — import this in routes/jobs
stripe_service = StripeService()
