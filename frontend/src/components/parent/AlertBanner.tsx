import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './AlertBanner.css';

interface AlertBannerProps {
  overdueCount: number;
  dueTodayCount: number;
  dueNext3DaysCount: number;
  unreadMessages: number;
  pendingInvites: Array<{ id: number; email: string }>;
  onResendInvite: (inviteId: number) => void;
  resendingId: number | null;
}

export function AlertBanner({
  overdueCount,
  dueTodayCount,
  dueNext3DaysCount,
  unreadMessages,
  pendingInvites,
  onResendInvite,
  resendingId,
}: AlertBannerProps) {
  const navigate = useNavigate();
  const [redDismissed, setRedDismissed] = useState(false);
  const [amberDismissed, setAmberDismissed] = useState(false);
  const [blueDismissed, setBlueDismissed] = useState(false);

  const hasRed = overdueCount > 0 && !redDismissed;
  const hasAmber = (pendingInvites.length > 0 || unreadMessages > 0) && !amberDismissed;
  const hasBlue = (dueTodayCount > 0 || dueNext3DaysCount > 0) && !blueDismissed;

  if (!hasRed && !hasAmber && !hasBlue) {
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
            {pendingInvites.length > 0 && (
              <div>
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
            )}
            {unreadMessages > 0 && (
              <div>
                {unreadMessages} unread message{unreadMessages !== 1 ? 's' : ''}{' '}
                <button
                  className="alert-section-action"
                  onClick={() => navigate('/messages')}
                >
                  View
                </button>
              </div>
            )}
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

      {hasBlue && (
        <div className="alert-section blue">
          <span className="alert-section-text">
            {dueTodayCount} due today, {dueNext3DaysCount} due in next 3 days
          </span>
          <button
            className="alert-section-action"
            onClick={() => navigate('/tasks?due=today')}
          >
            View
          </button>
          <button
            className="alert-section-dismiss"
            onClick={() => setBlueDismissed(true)}
            aria-label="Dismiss upcoming deadline alerts"
          >
            {'\u00D7'}
          </button>
        </div>
      )}
    </div>
  );
}
