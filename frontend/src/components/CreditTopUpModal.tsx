import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { loadStripe } from '@stripe/stripe-js';
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js';
import { walletApi } from '../api/wallet';
import type { CreditPackageItem } from '../api/wallet';
import { ReportBugLink } from './ReportBugLink';
import './CreditTopUpModal.css';

// Initialize Stripe once at module scope
const stripePublishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY;
const stripePromise = stripePublishableKey
  ? loadStripe(stripePublishableKey)
  : null;

interface CreditTopUpModalProps {
  open: boolean;
  onClose: () => void;
}

/** Inner payment form — rendered inside <Elements> provider. */
function PaymentForm({ onSuccess }: { onSuccess: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setProcessing(true);
    setError(null);

    const result = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });

    if (result.error) {
      setError(result.error.message || 'Payment failed');
      setProcessing(false);
    } else {
      onSuccess();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="payment-form">
      <PaymentElement />
      {error && <><p className="payment-error">{error}</p><ReportBugLink errorMessage={error} /></>}
      <button
        type="submit"
        className="btn-pay"
        disabled={!stripe || processing}
      >
        {processing ? 'Processing...' : 'Pay Now'}
      </button>
    </form>
  );
}

export default function CreditTopUpModal({
  open,
  onClose,
}: CreditTopUpModalProps) {
  const queryClient = useQueryClient();
  const [selectedPkg, setSelectedPkg] = useState<CreditPackageItem | null>(
    null
  );
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const { data: packages } = useQuery({
    queryKey: ['credit-packages'],
    queryFn: walletApi.getCreditPackages,
    enabled: open,
  });

  const handleSelectPackage = async (pkg: CreditPackageItem) => {
    setSelectedPkg(pkg);
    setCheckoutLoading(true);
    try {
      const res = await walletApi.createCheckout(pkg.id);
      setClientSecret(res.client_secret);
    } catch {
      setSelectedPkg(null);
    } finally {
      setCheckoutLoading(false);
    }
  };

  const handlePaymentSuccess = () => {
    setSuccess(true);
    queryClient.invalidateQueries({ queryKey: ['wallet'] });
    queryClient.invalidateQueries({ queryKey: ['wallet-transactions'] });
    setTimeout(() => {
      handleClose();
    }, 2000);
  };

  const handleClose = () => {
    setSelectedPkg(null);
    setClientSecret(null);
    setSuccess(false);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="topup-modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={handleClose}>
          &times;
        </button>
        <h3>Buy Credits</h3>

        {success ? (
          <div className="payment-success">
            <span className="success-icon">&#10003;</span>
            <p>Payment successful! Credits added to your wallet.</p>
          </div>
        ) : !selectedPkg ? (
          <div className="package-list">
            <p className="package-list-desc">
              Select a credit pack to purchase:
            </p>
            {packages?.map((pkg) => (
              <div
                key={pkg.id}
                className="credit-pack-card"
                onClick={() => handleSelectPackage(pkg)}
              >
                <div className="pack-info">
                  <span className="pack-name">{pkg.name}</span>
                  <span className="pack-credits">{pkg.credits} credits</span>
                </div>
                <span className="pack-price">
                  ${(pkg.price_cents / 100).toFixed(2)} CAD
                </span>
              </div>
            ))}
          </div>
        ) : checkoutLoading ? (
          <div className="checkout-loading">
            <p>Setting up payment...</p>
          </div>
        ) : clientSecret && stripePromise ? (
          <div className="stripe-payment">
            <div className="selected-pack">
              <span>{selectedPkg.name}</span>
              <span>
                {selectedPkg.credits} credits &mdash; $
                {(selectedPkg.price_cents / 100).toFixed(2)} CAD
              </span>
            </div>
            <Elements
              stripe={stripePromise}
              options={{ clientSecret }}
            >
              <PaymentForm onSuccess={handlePaymentSuccess} />
            </Elements>
            <button
              className="btn-back"
              onClick={() => {
                setSelectedPkg(null);
                setClientSecret(null);
              }}
            >
              &larr; Back to packages
            </button>
          </div>
        ) : (
          <div className="payment-error">
            <p>Payment processing is not configured.</p>
          </div>
        )}
      </div>
    </div>
  );
}
