"""
Pydantic schemas for the Digital Wallet & Subscription System (§6.60).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WalletResponse(BaseModel):
    """Wallet balance and package info."""
    id: int
    package: str
    package_credits: float
    purchased_credits: float
    total_credits: float
    auto_refill_enabled: bool
    auto_refill_threshold_cents: int
    auto_refill_amount_cents: int

    model_config = ConfigDict(from_attributes=True)


class PackageTierResponse(BaseModel):
    """Available subscription tier."""
    id: int
    name: str
    monthly_credits: float
    price_cents: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class WalletTransactionResponse(BaseModel):
    """Single transaction in the immutable ledger."""
    id: int
    transaction_type: str
    amount: float
    balance_after: float
    reference_id: str | None = None
    payment_method: str | None = None
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WalletTransactionList(BaseModel):
    """Paginated transaction list."""
    items: list[WalletTransactionResponse]
    total: int


class CreditPackageResponse(BaseModel):
    """Purchasable credit bundle."""
    id: int
    name: str
    credits: float
    price_cents: int

    model_config = ConfigDict(from_attributes=True)


class PackageEnrollRequest(BaseModel):
    """Request to change subscription tier."""
    package_name: str = Field(..., description="Tier name: free, standard, or premium")


class CreditPurchaseRequest(BaseModel):
    """Request to buy a credit pack via Stripe."""
    package_id: int = Field(..., gt=0)


class CheckoutResponse(BaseModel):
    """Stripe PaymentIntent client secret for frontend."""
    client_secret: str
    publishable_key: str


class AutoRefillRequest(BaseModel):
    """Configure wallet auto-refill settings."""
    enabled: bool
    threshold_cents: int = Field(0, ge=0)
    amount_cents: int = Field(500, ge=100)
