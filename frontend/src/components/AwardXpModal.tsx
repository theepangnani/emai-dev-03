import { useState, useEffect } from 'react';
import { xpApi } from '../api/xp';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { ReportBugLink } from './ReportBugLink';

interface AwardXpModalProps {
  open: boolean;
  onClose: () => void;
  studentName: string;
  studentUserId: number;
  onSuccess?: () => void;
}

export function AwardXpModal({
  open,
  onClose,
  studentName,
  studentUserId,
  onSuccess,
}: AwardXpModalProps) {
  const [points, setPoints] = useState(5);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [weeklyCap, setWeeklyCap] = useState<number>(50);

  const modalRef = useFocusTrap<HTMLDivElement>(open, onClose);

  useEffect(() => {
    if (!open || !studentUserId) return;
    setPoints(5);
    setReason('');
    setError(null);
    setSuccess(false);
    xpApi.getBrownieRemaining(studentUserId).then((data) => {
      setRemaining(data.remaining);
      setWeeklyCap(data.weekly_cap);
    }).catch(() => {
      setRemaining(null);
    });
  }, [open, studentUserId]);

  if (!open) return null;

  const handleSubmit = async () => {
    if (points < 1 || points > 50) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await xpApi.awardBrowniePoints(studentUserId, points, reason);
      setSuccess(true);
      setRemaining(result.remaining_weekly_cap);
      onSuccess?.();
      setTimeout(() => {
        setSuccess(false);
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to award XP');
    } finally {
      setSubmitting(false);
    }
  };

  const maxAward = remaining !== null ? Math.min(50, remaining) : 50;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Award XP"
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Award XP to {studentName}</h2>
        <p className="modal-desc">
          Recognize great effort by awarding brownie points (XP).
        </p>

        {success ? (
          <div className="link-success" style={{ padding: '20px 0', textAlign: 'center' }}>
            Awarded {points} XP to {studentName}!
          </div>
        ) : (
          <div className="modal-form">
            <label>
              XP Amount (1-{maxAward})
              <input
                type="range"
                min={1}
                max={maxAward || 1}
                value={Math.min(points, maxAward || 1)}
                onChange={(e) => setPoints(Number(e.target.value))}
                disabled={submitting || maxAward === 0}
                style={{ width: '100%' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', color: 'var(--color-ink-muted)' }}>
                <span>1</span>
                <strong style={{ fontSize: '18px', color: 'var(--color-ink)' }}>{Math.min(points, maxAward || 1)}</strong>
                <span>{maxAward}</span>
              </div>
            </label>

            {remaining !== null && (
              <p style={{ fontSize: '13px', color: 'var(--color-ink-muted)', margin: '4px 0 8px' }}>
                Remaining this week: {remaining} / {weeklyCap} XP
              </p>
            )}

            {remaining === 0 && (
              <p className="link-error">
                You have reached the weekly cap of {weeklyCap} XP for this student.
              </p>
            )}

            <label>
              Reason (optional)
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Great job on homework!"
                disabled={submitting}
                maxLength={200}
                rows={3}
              />
            </label>

            {error && <><p className="link-error">{error}</p><ReportBugLink errorMessage={error} /></>}
          </div>
        )}

        {!success && (
          <div className="modal-actions">
            <button className="cancel-btn" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button
              className="generate-btn"
              onClick={handleSubmit}
              disabled={submitting || maxAward === 0 || points < 1}
            >
              {submitting ? 'Awarding...' : `Award ${Math.min(points, maxAward || 1)} XP`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
