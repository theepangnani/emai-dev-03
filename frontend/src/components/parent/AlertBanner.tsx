import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './AlertBanner.css';

interface AlertBannerProps {
  overdueCount: number;
  pendingInvites: Array<{ id: number; email: string }>;
  onResendInvite: (inviteId: number) => void;
  resendingId: number | null;
}

export function AlertBanner({
  overdueCount,
  pendingInvites,
  onResendInvite,
  resendingId,
}: AlertBannerProps) {
  const navigate = useNavigate();
  const [redDismissed, setRedDismissed] = useState(false);
  const [amberDismissed, setAmberDismissed] = useState(false);

  const hasRed = overdueCount > 0 && !redDismissed;
  const hasAmber = pendingInvites.length > 0 && !amberDismissed;

  if (!hasRed && !hasAmber) {
    return null;
  }

  return (
    <div className="alert-banner">
      {hasRed && (
        <div className="alert-section red">
          <span className="alert-section-text">
            {'\u26A0'} {overdueCount} overdue item{overdueCount !== 1 ? 's' : ''}
          </span>
          <button
            className="alert-section-action"
            onClick={() => navigate('/tasks?due=overdue')}
          >
            View
          </button>
          <button
            className="alert-section-dismiss"
            onClick={() => setRedDismissed(true)}
            aria-label="Dismiss overdue alerts"
          >
            {'\u00D7'}
          </button>
        </div>
      )}

      {hasAmber && (
        <div className="alert-section amber">
          <div className="alert-section-text">
            {pendingInvites.length} pending invite{pendingInvites.length !== 1 ? 's' : ''}
            <div className="alert-invite-list">
              {pendingInvites.map((invite) => (
                <div key={invite.id} className="alert-invite-row">
                  <span className="alert-invite-email">{invite.email}</span>
                  <button
                    className="alert-resend-btn"
                    onClick={() => onResendInvite(invite.id)}
                    disabled={resendingId === invite.id}
                  >
                    {resendingId === invite.id ? 'Sending...' : 'Resend'}
                  </button>
                </div>
              ))}
            </div>
          </div>
          <button
            className="alert-section-dismiss"
            onClick={() => setAmberDismissed(true)}
            aria-label="Dismiss pending alerts"
          >
            {'\u00D7'}
          </button>
        </div>
      )}
    </div>
  );
}
