/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — Reject reason modal.
 *
 * The backend `POST /api/cmcp/review/{id}/reject` requires a non-empty
 * `reason` (1-2000 chars, Pydantic-enforced 422). This modal collects
 * the reason and surfaces validation in-modal before the API call.
 */
import { useEffect, useState } from 'react';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface RejectReasonModalProps {
  open: boolean;
  artifactTitle: string;
  isSubmitting: boolean;
  errorMessage?: string | null;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}

const MIN_REASON_LEN = 1;
const MAX_REASON_LEN = 2000;

export function RejectReasonModal({
  open,
  artifactTitle,
  isSubmitting,
  errorMessage,
  onCancel,
  onConfirm,
}: RejectReasonModalProps) {
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const trapRef = useFocusTrap<HTMLDivElement>(open, onCancel);

  // Clear the form whenever the modal is opened so re-opening after a
  // submit-fail or cancel doesn't carry stale text into the next attempt.
  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: reset draft + validation state when external `open` prop transitions to true (modal just appeared)
      setReason('');
      setTouched(false);
    }
  }, [open]);

  if (!open) return null;

  const trimmed = reason.trim();
  const tooShort = trimmed.length < MIN_REASON_LEN;
  const tooLong = trimmed.length > MAX_REASON_LEN;
  const showShortError = touched && tooShort;
  const isInvalid = tooShort || tooLong;

  const handleConfirm = () => {
    setTouched(true);
    if (isInvalid || isSubmitting) return;
    onConfirm(trimmed);
  };

  return (
    <div
      className="cmcp-review-modal-overlay"
      role="presentation"
      onClick={onCancel}
    >
      <div
        ref={trapRef}
        className="cmcp-review-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cmcp-reject-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="cmcp-reject-title" className="cmcp-review-modal-title">
          Reject artifact
        </h2>
        <p className="cmcp-review-modal-subtitle">{artifactTitle}</p>

        <div className="cmcp-review-modal-field">
          <label
            htmlFor="cmcp-reject-reason"
            className="cmcp-review-modal-field-label"
          >
            Reason for rejection
            <span className="cmcp-review-modal-required" aria-hidden="true">
              {' '}
              *
            </span>
          </label>
          <textarea
            id="cmcp-reject-reason"
            className="cmcp-review-modal-textarea"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={MAX_REASON_LEN}
            rows={5}
            aria-required="true"
            aria-invalid={showShortError || tooLong ? 'true' : 'false'}
            aria-describedby={
              showShortError
                ? 'cmcp-reject-reason-err'
                : tooLong
                  ? 'cmcp-reject-reason-toolong'
                  : undefined
            }
            disabled={isSubmitting}
          />
          {showShortError && (
            <span
              id="cmcp-reject-reason-err"
              className="cmcp-review-modal-error"
            >
              A reason is required to reject an artifact.
            </span>
          )}
          {tooLong && (
            <span
              id="cmcp-reject-reason-toolong"
              className="cmcp-review-modal-error"
            >
              Reason must be {MAX_REASON_LEN} characters or fewer.
            </span>
          )}
          {errorMessage && !showShortError && !tooLong && (
            <span className="cmcp-review-modal-error" role="alert">
              {errorMessage}
            </span>
          )}
        </div>

        <div className="cmcp-review-modal-actions">
          <button
            type="button"
            className="cmcp-review-modal-btn cmcp-review-modal-btn--cancel"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="cmcp-review-modal-btn cmcp-review-modal-btn--danger"
            onClick={handleConfirm}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Rejecting…' : 'Reject artifact'}
          </button>
        </div>
      </div>
    </div>
  );
}
