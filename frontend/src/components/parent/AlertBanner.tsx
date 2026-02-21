import { useState } from 'react';
import './AlertBanner.css';

interface AlertBannerProps {
  pendingInvites: Array<{ id: number; email: string }>;
  onResendInvite: (inviteId: number) => void;
  resendingId: number | null;
}

export function AlertBanner({
  pendingInvites,
  onResendInvite,
  resendingId,
}: AlertBannerProps) {
  const [amberDismissed, setAmberDismissed] = useState(false);

  const hasAmber = pendingInvites.length > 0 && !amberDismissed;

  if (!hasAmber) {
    return null;
  }

  return (
    <div className="alert-banner">
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
