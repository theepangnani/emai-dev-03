/**
 * Billing API client for Stripe subscription management.
 *
 * Endpoints:
 *   GET  /api/billing/plans                   — list active plans
 *   GET  /api/billing/subscription            — current user's subscription
 *   POST /api/billing/checkout                — create Stripe Checkout session
 *   POST /api/billing/portal                  — create Stripe Billing Portal session
 *   POST /api/billing/cancel                  — cancel subscription at period end
 *   GET  /api/admin/billing/stats             — admin revenue stats
 *   GET  /api/admin/billing/subscriptions     — admin subscription list (paginated)
 */
import { api } from './client';

// ─── Response types ───────────────────────────────────────────────────────────

export interface SubscriptionPlan {
  id: number;
  name: string;
  display_name: string;
  tier: 'free' | 'premium';
  price_cad: number;
  stripe_price_id: string | null;
  interval: 'monthly' | 'yearly' | null;
  features: string[];
  is_active: boolean;
}

export interface UserSubscription {
  id: number;
  user_id: number;
  plan: SubscriptionPlan;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  status: 'active' | 'past_due' | 'canceled' | 'trialing' | 'incomplete';
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  trial_end: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface PortalResponse {
  portal_url: string;
}

export interface BillingStats {
  total_premium: number;
  monthly_revenue_cad: number;
  new_this_month: number;
  churn_count: number;
}

export interface AdminSubscriptionItem {
  user_id: number;
  user_email: string | null;
  user_name: string | null;
  plan_name: string;
  plan_display_name: string;
  status: string;
  created_at: string | null;
  current_period_end: string | null;
}

export interface AdminSubscriptionList {
  items: AdminSubscriptionItem[];
  total: number;
  page: number;
  page_size: number;
}

// ─── API functions ────────────────────────────────────────────────────────────

export const billingApi = {
  /** List all active subscription plans with features. */
  getPlans: () => api.get<SubscriptionPlan[]>('/api/billing/plans'),

  /** Get the current user's subscription record (null if on free with no record). */
  getSubscription: () => api.get<UserSubscription | null>('/api/billing/subscription'),

  /**
   * Create a Stripe Checkout session for the given plan.
   * @param plan_name  "premium_monthly" | "premium_yearly"
   * Returns a checkout_url to redirect the user to Stripe.
   */
  createCheckout: (plan_name: string) =>
    api.post<CheckoutResponse>('/api/billing/checkout', { plan_name }),

  /**
   * Create a Stripe Billing Portal session for the current user.
   * Returns a portal_url to redirect the user to the self-service portal.
   */
  createPortal: () => api.post<PortalResponse>('/api/billing/portal'),

  /** Cancel the current subscription at the end of the billing period. */
  cancelSubscription: () => api.post<{ status: string }>('/api/billing/cancel'),

  // ── Admin ──────────────────────────────────────────────────────────────────

  /** Admin: get aggregate billing stats (MRR, premium count, etc.). */
  getStats: () => api.get<BillingStats>('/api/admin/billing/stats'),

  /**
   * Admin: paginated list of all subscriptions.
   * @param page  1-based page number (default 1)
   */
  getSubscriptions: (page = 1) =>
    api.get<AdminSubscriptionList>('/api/admin/billing/subscriptions', {
      params: { page },
    }),
};
