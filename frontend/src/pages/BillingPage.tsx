/**
 * BillingPage — Subscription & Billing page at /settings/billing
 *
 * Shows the user's current plan, plan comparison cards, and actions to
 * upgrade (via Stripe Checkout), manage billing (Stripe Portal), or cancel.
 *
 * Shows a success banner if the URL contains ?success=true (returned from
 * Stripe Checkout after a successful payment).
 */
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { billingApi, type SubscriptionPlan, type UserSubscription } from '../api/billing';
import { useAuth } from '../context/AuthContext';
import './BillingPage.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(amount);
}

// ─── Plan Card ────────────────────────────────────────────────────────────────

interface PlanCardProps {
  plan: SubscriptionPlan;
  isCurrentPlan: boolean;
  onUpgradeMonthly?: () => void;
  onUpgradeYearly?: () => void;
  upgrading: boolean;
}

function PlanCard({
  plan,
  isCurrentPlan,
  onUpgradeMonthly,
  onUpgradeYearly,
  upgrading,
}: PlanCardProps) {
  const isPremium = plan.tier === 'premium';

  return (
    <div className={`billing-plan-card ${isPremium ? 'billing-plan-card--premium' : ''} ${isCurrentPlan ? 'billing-plan-card--current' : ''}`}>
      <div className="billing-plan-header">
        <h3 className="billing-plan-name">
          {isPremium && <span className="billing-plan-star">&#9733;</span>}{' '}
          {isPremium ? 'Premium' : 'Free'}
        </h3>
        {isCurrentPlan && <span className="billing-current-badge">Current Plan</span>}
      </div>

      {isPremium ? (
        <div className="billing-plan-pricing">
          <div className="billing-plan-price">
            <span className="billing-price-amount">$9.99</span>
            <span className="billing-price-period">/month</span>
          </div>
          <div className="billing-plan-price billing-plan-price--yearly">
            <span className="billing-price-amount billing-price-amount--small">or $99.99</span>
            <span className="billing-price-period">/year</span>
          </div>
        </div>
      ) : (
        <div className="billing-plan-pricing">
          <div className="billing-plan-price">
            <span className="billing-price-amount">$0</span>
            <span className="billing-price-period">/month</span>
          </div>
        </div>
      )}

      <ul className="billing-plan-features">
        {plan.features.map((f, i) => (
          <li key={i} className="billing-plan-feature">
            <span className="billing-feature-check">&#10003;</span> {f}
          </li>
        ))}
      </ul>

      <div className="billing-plan-actions">
        {isCurrentPlan && plan.tier === 'free' && (
          <button className="billing-btn billing-btn--disabled" disabled>
            Current Plan
          </button>
        )}
        {!isCurrentPlan && isPremium && onUpgradeMonthly && (
          <button
            className="billing-btn billing-btn--primary"
            onClick={onUpgradeMonthly}
            disabled={upgrading}
          >
            {upgrading ? 'Redirecting...' : 'Upgrade Monthly'}
          </button>
        )}
        {!isCurrentPlan && isPremium && onUpgradeYearly && (
          <button
            className="billing-btn billing-btn--secondary"
            onClick={onUpgradeYearly}
            disabled={upgrading}
          >
            {upgrading ? 'Redirecting...' : (
              <>
                Upgrade Yearly{' '}
                <span className="billing-save-badge">Save 17%</span>
              </>
            )}
          </button>
        )}
        {isCurrentPlan && isPremium && (
          <button className="billing-btn billing-btn--disabled" disabled>
            Current Plan
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function BillingPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const isSuccess = searchParams.get('success') === 'true';

  const plansQuery = useQuery({
    queryKey: ['billingPlans'],
    queryFn: () => billingApi.getPlans().then((r) => r.data),
  });

  const subscriptionQuery = useQuery({
    queryKey: ['userSubscription'],
    queryFn: () => billingApi.getSubscription().then((r) => r.data),
  });

  const cancelMutation = useMutation({
    mutationFn: () => billingApi.cancelSubscription(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userSubscription'] });
      setShowCancelDialog(false);
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.detail || 'Failed to cancel subscription.');
      setShowCancelDialog(false);
    },
  });

  const handleUpgrade = async (planName: string) => {
    setUpgrading(true);
    setErrorMessage('');
    try {
      const res = await billingApi.createCheckout(planName);
      window.location.href = res.data.checkout_url;
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || 'Failed to start checkout. Please try again.');
      setUpgrading(false);
    }
  };

  const handleManageBilling = async () => {
    setErrorMessage('');
    try {
      const res = await billingApi.createPortal();
      window.location.href = res.data.portal_url;
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || 'Failed to open billing portal.');
    }
  };

  const currentTier = user?.subscription_tier ?? 'free';
  const subscription: UserSubscription | null = subscriptionQuery.data ?? null;
  const plans: SubscriptionPlan[] = plansQuery.data ?? [];

  const freePlan = plans.find((p) => p.name === 'free');
  const premiumPlan = plans.find((p) => p.tier === 'premium') ?? plans.find((p) => p.name === 'premium_monthly');
  const isOnPremium = currentTier === 'premium';

  return (
    <DashboardLayout>
      <div className="billing-page">
        <h1 className="billing-title">Subscription &amp; Billing</h1>

        {isSuccess && (
          <div className="billing-success-banner" role="alert">
            Payment successful! Your account has been upgraded to Premium.
          </div>
        )}

        {errorMessage && (
          <div className="billing-error-banner" role="alert">
            {errorMessage}
          </div>
        )}

        <div className="billing-current-plan">
          <span className="billing-current-plan-label">Current Plan:</span>
          <span className={`billing-tier-badge billing-tier-badge--${currentTier}`}>
            {currentTier === 'premium' ? 'Premium' : 'Free'}
          </span>
        </div>

        <hr className="billing-divider" />

        {/* Plan comparison cards */}
        {plansQuery.isLoading ? (
          <div className="billing-loading">Loading plans...</div>
        ) : (
          <div className="billing-plans-grid">
            {freePlan && (
              <PlanCard
                plan={freePlan}
                isCurrentPlan={!isOnPremium}
                upgrading={upgrading}
              />
            )}
            {premiumPlan && (
              <PlanCard
                plan={premiumPlan}
                isCurrentPlan={isOnPremium}
                onUpgradeMonthly={!isOnPremium ? () => handleUpgrade('premium_monthly') : undefined}
                onUpgradeYearly={!isOnPremium ? () => handleUpgrade('premium_yearly') : undefined}
                upgrading={upgrading}
              />
            )}
          </div>
        )}

        {/* Current subscription details (premium users) */}
        {isOnPremium && subscription && (
          <>
            <hr className="billing-divider" />
            <div className="billing-subscription-details">
              <h2 className="billing-subscription-title">Subscription Details</h2>
              <div className="billing-subscription-info">
                <div className="billing-info-row">
                  <span className="billing-info-label">Current period:</span>
                  <span className="billing-info-value">
                    {formatDate(subscription.current_period_start)} &ndash;{' '}
                    {formatDate(subscription.current_period_end)}
                  </span>
                </div>
                <div className="billing-info-row">
                  <span className="billing-info-label">Status:</span>
                  <span className={`billing-status-badge billing-status-badge--${subscription.status}`}>
                    {subscription.status.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                </div>
                {subscription.cancel_at_period_end && (
                  <div className="billing-cancel-notice">
                    Your subscription will be canceled on{' '}
                    <strong>{formatDate(subscription.current_period_end)}</strong>.
                  </div>
                )}
                {subscription.trial_end && new Date(subscription.trial_end) > new Date() && (
                  <div className="billing-trial-notice">
                    Free trial ends on{' '}
                    <strong>{formatDate(subscription.trial_end)}</strong>.
                  </div>
                )}
              </div>

              <div className="billing-management-actions">
                <button
                  className="billing-btn billing-btn--primary"
                  onClick={handleManageBilling}
                >
                  Manage Billing
                </button>
                {!subscription.cancel_at_period_end && (
                  <button
                    className="billing-btn billing-btn--danger"
                    onClick={() => setShowCancelDialog(true)}
                  >
                    Cancel Subscription
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Cancel confirmation dialog */}
      {showCancelDialog && (
        <div
          className="billing-modal-overlay"
          onClick={() => setShowCancelDialog(false)}
        >
          <div
            className="billing-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Cancel Subscription"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="billing-modal-title">Cancel Subscription?</h2>
            <p className="billing-modal-body">
              Your premium access will continue until the end of the current billing period.
              After that, your account will revert to the Free plan.
            </p>
            <div className="billing-modal-actions">
              <button
                className="billing-btn billing-btn--secondary"
                onClick={() => setShowCancelDialog(false)}
              >
                Keep Subscription
              </button>
              <button
                className="billing-btn billing-btn--danger"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending ? 'Canceling...' : 'Yes, Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
