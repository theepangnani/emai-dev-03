"""
Subscription models for Stripe payment integration.

Defines SubscriptionPlan (catalogue of plans) and UserSubscription (per-user
subscription state, linked to Stripe customer/subscription IDs).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PlanInterval(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"


class SubscriptionPlan(Base):
    """Catalogue entry for a subscription plan (free, premium monthly, premium yearly)."""

    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    # e.g. "free", "premium_monthly", "premium_yearly"
    display_name = Column(String(100), nullable=False)
    # e.g. "Free", "Premium Monthly", "Premium Yearly"
    tier = Column(String(20), nullable=False)
    # "free" | "premium"
    price_cad = Column(Float, nullable=False, default=0.0)
    stripe_price_id = Column(String(100), nullable=True)
    # Stripe Price ID (price_xxx) — null for free plan
    interval = Column(Enum(PlanInterval), nullable=True)
    # null for free plan
    features = Column(Text, nullable=False, default="[]")
    # JSON list of feature strings for display
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    subscriptions: list["UserSubscription"] = relationship(
        "UserSubscription", back_populates="plan"
    )


class UserSubscription(Base):
    """Tracks a user's current subscription state, including Stripe identifiers."""

    __tablename__ = "user_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_subscriptions_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_id = Column(
        Integer,
        ForeignKey("subscription_plans.id"),
        nullable=False,
    )

    # Stripe identifiers
    stripe_customer_id = Column(String(100), nullable=True)
    # cus_xxx
    stripe_subscription_id = Column(String(100), nullable=True)
    # sub_xxx

    status = Column(
        Enum(SubscriptionStatus),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )

    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    trial_end = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscription")
    plan: "SubscriptionPlan" = relationship("SubscriptionPlan", back_populates="subscriptions")
