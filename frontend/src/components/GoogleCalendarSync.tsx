/**
 * GoogleCalendarSync — self-contained card that shows Google Calendar sync
 * status and lets the user connect, sync now, or disconnect.
 *
 * Props:
 *   googleConnected — true when the user already has Google OAuth tokens (i.e.
 *                     Google Classroom is connected). We only show this card when
 *                     the base Google connection exists.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { googleCalendarApi } from '../api/googleCalendar';
import './GoogleCalendarSync.css';

interface Props {
  /** Whether the user has connected Google at all (base OAuth tokens exist). */
  googleConnected: boolean;
}

export function GoogleCalendarSync({ googleConnected }: Props) {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Fetch calendar connection status
  const { data: status, isLoading } = useQuery({
    queryKey: ['google-calendar-status'],
    queryFn: googleCalendarApi.getStatus,
    enabled: googleConnected,
    staleTime: 30_000,
  });

  const showToast = (type: 'success' | 'error', text: string) => {
    setToast({ type, text });
    setTimeout(() => setToast(null), 4000);
  };

  // Connect mutation — opens OAuth flow
  const connectMutation = useMutation({
    mutationFn: googleCalendarApi.connect,
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: () => {
      showToast('error', 'Failed to start Google Calendar connection. Please try again.');
    },
  });

  // Sync mutation — bulk syncs tasks
  const syncMutation = useMutation({
    mutationFn: googleCalendarApi.sync,
    onSuccess: (data) => {
      showToast('success', data.message || `Synced ${data.synced} tasks to Google Calendar`);
      queryClient.invalidateQueries({ queryKey: ['google-calendar-status'] });
    },
    onError: () => {
      showToast('error', 'Failed to sync tasks to Google Calendar.');
    },
  });

  // Disconnect mutation
  const disconnectMutation = useMutation({
    mutationFn: googleCalendarApi.disconnect,
    onSuccess: () => {
      showToast('success', 'Google Calendar sync disconnected.');
      queryClient.invalidateQueries({ queryKey: ['google-calendar-status'] });
    },
    onError: () => {
      showToast('error', 'Failed to disconnect Google Calendar.');
    },
  });

  if (!googleConnected) return null;
  if (isLoading) return null;

  const scopeGranted = status?.scope_granted ?? false;

  return (
    <div className="gcal-sync-card">
      {toast && (
        <div className={`gcal-toast gcal-toast--${toast.type}`} role="alert">
          {toast.text}
        </div>
      )}

      <div className="gcal-sync-header">
        <div className="gcal-sync-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </div>
        <div className="gcal-sync-title-area">
          <h4 className="gcal-sync-title">Google Calendar Sync</h4>
          <p className="gcal-sync-desc">Sync your tasks to Google Calendar</p>
        </div>
        {scopeGranted && (
          <span className="gcal-connected-badge" aria-label="Connected">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Connected
          </span>
        )}
      </div>

      <div className="gcal-sync-actions">
        {!scopeGranted ? (
          <button
            className="gcal-btn gcal-btn--primary"
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
          >
            {connectMutation.isPending ? 'Connecting...' : 'Connect Google Calendar'}
          </button>
        ) : (
          <>
            <button
              className="gcal-btn gcal-btn--secondary"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending || disconnectMutation.isPending}
            >
              {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
            </button>
            <button
              className="gcal-btn gcal-btn--danger"
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending || syncMutation.isPending}
            >
              {disconnectMutation.isPending ? 'Disconnecting...' : 'Disconnect'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
