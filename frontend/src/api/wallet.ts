/**
 * Wallet API client — Digital Wallet & Subscription System (§6.60).
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WalletData {
  id: number;
  package: string;
  package_credits: number;
  purchased_credits: number;
  total_credits: number;
  auto_refill_enabled: boolean;
  auto_refill_threshold_cents: number;
  auto_refill_amount_cents: number;
}

export interface PackageTier {
  id: number;
  name: string;
  monthly_credits: number;
  price_cents: number;
  is_active: boolean;
}

export interface CreditPackageItem {
  id: number;
  name: string;
  credits: number;
  price_cents: number;
}

export interface WalletTransactionItem {
  id: number;
  transaction_type: string;
  amount: number;
  balance_after: number;
  reference_id: string | null;
  payment_method: string | null;
  note: string | null;
  created_at: string;
}

export interface TransactionList {
  items: WalletTransactionItem[];
  total: number;
}

export interface CheckoutResponse {
  client_secret: string;
  publishable_key: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const walletApi = {
  /** Get current user's wallet balance and package info. */
  getWallet: () =>
    api.get<WalletData>('/api/wallet').then((r) => r.data),

  /** Get paginated transaction ledger. */
  getTransactions: (skip = 0, limit = 50) =>
    api
      .get<TransactionList>('/api/wallet/transactions', {
        params: { skip, limit },
      })
      .then((r) => r.data),

  /** List active package tiers. */
  getPackages: () =>
    api.get<PackageTier[]>('/api/wallet/packages').then((r) => r.data),

  /** Enroll in or change package tier. */
  enrollPackage: (packageName: string) =>
    api
      .post<WalletData>('/api/wallet/packages/enroll', {
        package_name: packageName,
      })
      .then((r) => r.data),

  /** List available credit packages for purchase. */
  getCreditPackages: () =>
    api
      .get<CreditPackageItem[]>('/api/wallet/credits')
      .then((r) => r.data),

  /** Create Stripe PaymentIntent for credit purchase. */
  createCheckout: (packageId: number) =>
    api
      .post<CheckoutResponse>('/api/wallet/credits/checkout', {
        package_id: packageId,
      })
      .then((r) => r.data),

  /** Update auto-refill settings. */
  updateAutoRefill: (enabled: boolean, thresholdCents: number, amountCents: number) =>
    api
      .patch<WalletData>('/api/wallet/auto-refill', {
        enabled,
        threshold_cents: thresholdCents,
        amount_cents: amountCents,
      })
      .then((r) => r.data),
};
