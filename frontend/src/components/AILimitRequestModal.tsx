import { useState } from 'react';
import { aiUsageApi } from '../api/aiUsage';
import { useFocusTrap } from '../utils/useFocusTrap';
import { ReportBugLink } from './ReportBugLink';
import './AILimitRequestModal.css';

interface AILimitRequestModalProps {
  open: boolean;
  onClose: () => void;
}

export function AILimitRequestModal({ open, onClose }: AILimitRequestModalProps) {
  const [amount, setAmount] = useState(10);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const trapRef = useFocusTrap(open, onClose);

  const handleSubmit = async () => {
    if (amount < 1) {
      setError('Please request at least 1 credit.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await aiUsageApi.requestMore({
        requested_amount: amount,
        reason: reason.trim() || undefined,
      });
      setSubmitted(true);
    } catch {
      setError('Failed to submit request. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    // Reset state on close
    setAmount(10);
    setReason('');
    setSubmitting(false);
    setSubmitted(false);
    setError('');
    onClose();
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        ref={trapRef}
        className="modal ai-limit-request-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-limit-request-title"
        onClick={(e) => e.stopPropagation()}
      >
        {submitted ? (
          <>
            <div className="ai-limit-request-success-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M9 12l2 2 4-4" />
              </svg>
            </div>
            <h2 id="ai-limit-request-title">Request Submitted!</h2>
            <p className="ai-limit-request-desc">
              Your request for additional AI credits has been sent. An admin will review it shortly.
            </p>
            <div className="modal-actions">
              <button className="generate-btn" onClick={handleClose}>
                Done
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 id="ai-limit-request-title">Request More AI Credits</h2>
            <p className="ai-limit-request-desc">
              You've reached your AI credit limit. Submit a request for additional credits and an admin will review it.
            </p>

            <div className="modal-form">
              <label>
                Desired additional credits
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={amount}
                  onChange={(e) => setAmount(Math.max(1, parseInt(e.target.value) || 1))}
                  disabled={submitting}
                />
              </label>

              <label>
                Reason (optional)
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g., Preparing for midterm exams, need to generate more study materials..."
                  rows={3}
                  disabled={submitting}
                />
              </label>

              {error && (
                <div className="modal-error">
                  <span className="error-icon">!</span>
                  <span className="error-message">{error}</span>
                  <ReportBugLink errorMessage={error} />
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button className="cancel-btn" onClick={handleClose} disabled={submitting}>
                Cancel
              </button>
              <button className="generate-btn" onClick={handleSubmit} disabled={submitting || amount < 1}>
                {submitting ? 'Submitting...' : 'Submit Request'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
